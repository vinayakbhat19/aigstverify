# =========================================
# FILE: utils/ocr.py
# =========================================

import easyocr
import numpy as np
import cv2

# =========================================
# LOAD OCR MODEL
# =========================================

reader = easyocr.Reader(
    ['en'],
    gpu=False
)

# =========================================
# IMAGE PREPROCESSING
# =========================================

def preprocess_image(image):

    # PIL → NUMPY

    img = np.array(image)

    # RGB → GRAY

    gray = cv2.cvtColor(

        img,

        cv2.COLOR_RGB2GRAY
    )

    # =====================================
    # ENLARGE IMAGE
    # =====================================

    height, width = gray.shape

    if width > 1200:

        scale = 1200 / width

        gray = cv2.resize(

            gray,

            None,

            fx=scale,

            fy=scale,

            interpolation=cv2.INTER_AREA
        )

    # =====================================
    # REMOVE NOISE
    # =====================================

    gray = cv2.GaussianBlur(

        gray,

        (3, 3),

        0
    )

    # =====================================
    # SHARPEN
    # =====================================

    sharpen_kernel = np.array([

        [-1, -1, -1],

        [-1,  9, -1],

        [-1, -1, -1]

    ])

    sharpen = cv2.filter2D(

        gray,

        -1,

        sharpen_kernel
    )

    # =====================================
    # THRESHOLD
    # =====================================

    processed = cv2.adaptiveThreshold(

        sharpen,

        255,

        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,

        cv2.THRESH_BINARY,

        11,

        2
    )

    return processed

# =========================================
# OCR EXTRACTION
# =========================================

def extract_text(image):

    processed = preprocess_image(
        image
    )

    results = reader.readtext(

        processed,

        detail=0,
        paragraph=False,
        batch_size=1
    )

    text = "\n".join(results)

    # DEBUG

    print("\n===== OCR TEXT =====\n")

    print(text)

    print("\n====================\n")

    return text