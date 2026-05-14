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

    # PIL IMAGE -> NUMPY

    img = np.array(image)

    # RGB -> GRAY

    gray = cv2.cvtColor(

        img,

        cv2.COLOR_RGB2GRAY
    )

    # =====================================
    # SHARPEN IMAGE
    # =====================================

    sharpen_kernel = np.array([

        [-1,-1,-1],

        [-1, 9,-1],

        [-1,-1,-1]

    ])

    sharpen = cv2.filter2D(

        gray,

        -1,

        sharpen_kernel
    )

    # =====================================
    # THRESHOLD
    # =====================================

    thresh = cv2.threshold(

        sharpen,

        150,

        255,

        cv2.THRESH_BINARY
    )[1]

    return thresh

# =========================================
# OCR TEXT EXTRACTION
# =========================================

def extract_text(image):

    processed = preprocess_image(
        image
    )

    results = reader.readtext(

        processed,

        detail=0,

        paragraph=True
    )

    text = "\n".join(results)

    # DEBUG PRINT

    print("\n===== OCR TEXT =====\n")

    print(text)

    print("\n====================\n")

    return text