"""Fine-tune LayoutLMv3 for GST invoice field extraction (token classification).

    python scripts/train_layoutlmv3.py --data data/synthetic_ocr --output models/layoutlmv3-gst

Use a GPU (a free Colab T4 is enough); on CPU expect hours. --data may also be
data/synthetic to train on the generator's exact word boxes. Reports
entity-level precision / recall / F1 on the test split, separately for layouts
seen in training and for the held-out layout.

Note: microsoft/layoutlmv3-base is licensed CC BY-NC-SA 4.0 (non-commercial).
Pass --model SCUT-DLVCLab/lilt-roberta-en-base for an MIT-licensed alternative.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import (AutoModelForTokenClassification, AutoProcessor, AutoTokenizer,
                          Trainer, TrainingArguments)


def load_split(data_dir: Path, name: str, limit: int = 0) -> list:
    with open(data_dir / f"{name}.jsonl", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]
    return records[:limit] if limit else records


def spans(labels: list) -> set:
    """{(type, start, end)} for each IOB2 entity."""
    found, start = set(), None
    for i, label in enumerate(list(labels) + ["O"]):
        inside = label.startswith("I-") and start is not None and labels[start][2:] == label[2:]
        if start is not None and not inside:
            found.add((labels[start][2:], start, i))
            start = None
        if label.startswith("B-") or (label.startswith("I-") and start is None):
            start = i
    return found


def entity_scores(truth: list, predicted: list) -> dict:
    """Exact-span entity precision/recall/F1, overall and per type."""
    counts = Counter()
    for gold, guess in zip(truth, predicted):
        gold_spans, guess_spans = spans(gold), spans(guess)
        for kind, *_ in gold_spans & guess_spans:
            counts[kind, "tp"] += 1
        for kind, *_ in guess_spans - gold_spans:
            counts[kind, "fp"] += 1
        for kind, *_ in gold_spans - guess_spans:
            counts[kind, "fn"] += 1

    def prf(tp, fp, fn):
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
                "support": tp + fn}

    kinds = sorted({kind for kind, _ in counts})
    report = {kind: prf(counts[kind, "tp"], counts[kind, "fp"], counts[kind, "fn"]) for kind in kinds}
    report["overall"] = prf(*(sum(counts[kind, key] for kind in kinds) for key in ("tp", "fp", "fn")))
    return report


class InvoiceDataset(torch.utils.data.Dataset):
    """Encodes lazily. Invoices longer than max_length tokens are cut into overlapping windows."""

    def __init__(self, records, data_dir, encode, label_ids, max_length=512, stride=128):
        self.items = []
        for record in records:
            encoding = encode(record, data_dir, max_length, stride)
            for window in range(len(encoding["input_ids"])):
                word_ids = encoding.word_ids(window)
                labels, previous = [], None
                for word_id in word_ids:
                    # Only the first sub-token of each word is scored.
                    if word_id is None or word_id == previous:
                        labels.append(-100)
                    else:
                        labels.append(label_ids[record["labels"][word_id]])
                    previous = word_id
                item = {key: torch.as_tensor(np.asarray(value[window]))
                        for key, value in encoding.items() if key != "overflow_to_sample_mapping"}
                item["labels"] = torch.tensor(labels)
                self.items.append(item)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


def make_encoder(model_name: str):
    """LayoutLMv3 takes the page image as well; text+layout models (LiLT) take words and boxes only."""
    if "layoutlmv3" in model_name.lower():
        processor = AutoProcessor.from_pretrained(model_name, apply_ocr=False)

        def encode(record, data_dir, max_length, stride):
            image = Image.open(data_dir / record["image"]).convert("RGB")
            return processor(image, record["words"], boxes=record["bboxes"], truncation=True,
                             max_length=max_length, stride=stride, padding="max_length",
                             return_overflowing_tokens=True)
        return encode, processor

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def encode(record, data_dir, max_length, stride):
        return tokenizer(record["words"], boxes=record["bboxes"], truncation=True,
                         max_length=max_length, stride=stride, padding="max_length",
                         return_overflowing_tokens=True)
    return encode, tokenizer


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=Path("data/synthetic_ocr"))
    parser.add_argument("--output", type=Path, default=Path("models/layoutlmv3-gst"))
    parser.add_argument("--model", default="microsoft/layoutlmv3-base")
    parser.add_argument("--epochs", type=float, default=20)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=-1, help="stop early (for smoke tests)")
    parser.add_argument("--limit", type=int, default=0, help="use only the first N records per split")
    args = parser.parse_args()

    label_list = json.loads((args.data / "labels.json").read_text(encoding="utf-8"))
    label_ids = {label: i for i, label in enumerate(label_list)}
    encode, processor = make_encoder(args.model)
    splits = {name: load_split(args.data, name, args.limit) for name in ("train", "val", "test")}
    datasets = {name: InvoiceDataset(records, args.data, encode, label_ids) for name, records in splits.items()}
    print({name: f"{len(splits[name])} invoices, {len(datasets[name])} windows" for name in splits})

    model = AutoModelForTokenClassification.from_pretrained(
        args.model, num_labels=len(label_list),
        id2label=dict(enumerate(label_list)), label2id=label_ids)

    def decode(logits, label_rows):
        predictions = np.argmax(logits, axis=-1)
        truth, guessed = [], []
        for prediction, labels in zip(predictions, label_rows):
            keep = labels != -100
            truth.append([label_list[i] for i in labels[keep]])
            guessed.append([label_list[i] for i in prediction[keep]])
        return truth, guessed

    def compute_metrics(eval_prediction):
        overall = entity_scores(*decode(eval_prediction.predictions, eval_prediction.label_ids))["overall"]
        return {key: overall[key] for key in ("precision", "recall", "f1")}

    use_gpu = torch.cuda.is_available()
    quick = args.max_steps > 0
    total_steps = args.max_steps if quick else int(len(datasets["train"]) / args.batch_size * args.epochs)
    warmup = max(1, total_steps // 10)
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.output),
            num_train_epochs=args.epochs,
            max_steps=args.max_steps,
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=args.batch_size * 2,
            learning_rate=args.lr,
            warmup_steps=warmup,
            weight_decay=0.01,
            eval_strategy="no" if quick else "epoch",
            save_strategy="no" if quick else "epoch",
            save_total_limit=1,
            load_best_model_at_end=not quick,
            metric_for_best_model="f1",
            logging_steps=5 if quick else 25,
            fp16=use_gpu,
            seed=args.seed,
            report_to="none",
        ),
        train_dataset=datasets["train"],
        eval_dataset=datasets["val"],
        compute_metrics=compute_metrics,
    )
    trainer.train()

    # Test report, split by whether the layout was seen in training.
    output = trainer.predict(datasets["test"])
    truth, guessed = decode(output.predictions, output.label_ids)
    seen_layouts = {record["meta"]["template"] for record in splits["train"]}
    window_layout = []
    for record in splits["test"]:
        windows = len(encode(record, args.data, 512, 128)["input_ids"])
        window_layout += [record["meta"]["template"] in seen_layouts] * windows
    report = {"all": entity_scores(truth, guessed)}
    for name, wanted in (("seen_layouts", True), ("unseen_layouts", False)):
        rows = [i for i, seen in enumerate(window_layout) if seen == wanted]
        if rows:
            report[name] = entity_scores([truth[i] for i in rows], [guessed[i] for i in rows])

    args.output.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(args.output))
    processor.save_pretrained(str(args.output))
    (args.output / "test_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for name, scores in report.items():
        print(f"{name}: {scores['overall']}")
    print(f"Per-entity scores are in {args.output / 'test_report.json'}")


if __name__ == "__main__":
    main()
