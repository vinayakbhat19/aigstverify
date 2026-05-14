import pandas as pd

from xgboost import XGBClassifier

import joblib

# =====================================
# TRAINING DATA
# =====================================

data = pd.DataFrame({

    "amount": [

        1000,
        5000,
        12000,
        25000,
        70000,
        150000,
        250000
    ],

    "gst": [

        50,
        250,
        600,
        4500,
        100,
        35000,
        70000
    ],

    "gst_valid": [

        1,
        1,
        1,
        1,
        0,
        1,
        0
    ],

    "gst_match": [

        1,
        1,
        1,
        0,
        0,
        0,
        0
    ],

    "duplicate": [

        0,
        0,
        0,
        0,
        1,
        1,
        1
    ],

    "fraud": [

        0,
        0,
        0,
        1,
        1,
        1,
        1
    ]
})

# =====================================
# FEATURES
# =====================================

X = data[[

    "amount",

    "gst",

    "gst_valid",

    "gst_match",

    "duplicate"
]]

# =====================================
# TARGET
# =====================================

y = data["fraud"]

# =====================================
# MODEL
# =====================================

model = XGBClassifier(

    n_estimators=100,

    max_depth=4,

    learning_rate=0.1
)

# =====================================
# TRAIN
# =====================================

model.fit(X, y)

# =====================================
# SAVE MODEL
# =====================================

joblib.dump(

    model,

    "models/fraud_model.pkl"
)

print(

    "Fraud model trained successfully"
)