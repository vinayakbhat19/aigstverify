"""Renders invoices to images with headless Chromium and reads word boxes from the DOM."""

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).parent / "templates"

# Collects every visible word with its box and the data-f label of its enclosing element.
EXTRACT_JS = r"""
() => {
  const entityIds = new Map();
  const out = [];
  const walker = document.createTreeWalker(document.querySelector('.page'), NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const holder = node.parentElement.closest('[data-f]');
    if (holder && !entityIds.has(holder)) entityIds.set(holder, entityIds.size);
    const re = /\S+/g;
    for (let hit = re.exec(node.data); hit; hit = re.exec(node.data)) {
      range.setStart(node, hit.index);
      range.setEnd(node, hit.index + hit[0].length);
      const rects = Array.from(range.getClientRects()).filter(q => q.width > 0.5 && q.height > 0.5);
      if (!rects.length) continue;
      out.push({
        text: hit[0],
        x0: Math.min(...rects.map(q => q.left)) + window.scrollX,
        y0: Math.min(...rects.map(q => q.top)) + window.scrollY,
        x1: Math.max(...rects.map(q => q.right)) + window.scrollX,
        y1: Math.max(...rects.map(q => q.bottom)) + window.scrollY,
        field: holder ? holder.dataset.f : null,
        entity: holder ? entityIds.get(holder) : -1,
      });
    }
  }
  return out;
}
"""


def reading_order(words: list) -> list:
    """Top-to-bottom, left-to-right: the order an OCR engine would emit."""
    lines = []
    for w in sorted(words, key=lambda w: ((w["y0"] + w["y1"]) / 2, w["x0"])):
        yc, h = (w["y0"] + w["y1"]) / 2, w["y1"] - w["y0"]
        line = lines[-1] if lines else None
        if line and abs(yc - line["yc"]) < 0.5 * min(h, line["h"]):
            line["words"].append(w)
        else:
            lines.append({"yc": yc, "h": h, "words": [w]})
    return [w for line in lines for w in sorted(line["words"], key=lambda w: w["x0"])]


def bio_labels(words: list) -> list:
    """B- on the first word of each run of the same entity, I- on the rest."""
    labels, previous = [], None
    for w in words:
        if w["field"] is None:
            labels.append("O")
            previous = None
        else:
            labels.append(("I-" if w["entity"] == previous else "B-") + w["field"])
            previous = w["entity"]
    return labels


class Renderer:
    def __init__(self):
        from playwright.sync_api import sync_playwright

        self.env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), undefined=StrictUndefined,
                               trim_blocks=True, lstrip_blocks=True)
        self._pw = sync_playwright().start()
        # GSTVISION_CHROMIUM lets you point at a system Chrome/Chromium binary.
        self._browser = self._pw.chromium.launch(executable_path=os.environ.get("GSTVISION_CHROMIUM") or None)
        self._contexts = {}

    def _page(self, width: int, scale: float):
        key = (width, scale)
        if key not in self._contexts:
            context = self._browser.new_context(viewport={"width": width, "height": 600},
                                                device_scale_factor=scale)
            self._contexts[key] = context.new_page()
        return self._contexts[key]

    def render(self, template: str, inv: dict, S: dict, L: dict, m, r):
        """Returns (PNG bytes, words in reading order with pixel boxes and BIO labels)."""
        html = self.env.get_template(f"{template}.j2").render(inv=inv, S=S, L=L, m=m, r=r)
        page = self._page(S["width"], S["scale"])
        page.set_content(html)
        page.evaluate("document.fonts.ready")
        words = reading_order(page.evaluate(EXTRACT_JS))
        png = page.screenshot(full_page=True, type="png")
        labels = bio_labels(words)
        scale = S["scale"]
        return png, [
            {"text": w["text"], "label": label,
             "box": [w["x0"] * scale, w["y0"] * scale, w["x1"] * scale, w["y1"] * scale]}
            for w, label in zip(words, labels)
        ]

    def close(self):
        self._browser.close()
        self._pw.stop()
