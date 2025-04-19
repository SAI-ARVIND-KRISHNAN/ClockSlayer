# Filename: services/trainer.py

import os
import joblib
import pandas as pd
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_absolute_error

from loguru import logger
from bson import ObjectId

from Recommender.config.db import tasks, users, MODEL_DIR
from Recommender.core.constants import (
    RECOMMENDER_FEATURES,
    CATEGORICAL_COLUMNS,
    MODEL_SUFFIX,
    ENCODER_SUFFIX,
)
from Recommender.utils.model_loader import (
    get_model_registry,
    cleanup_old_versions,
    update_model_registry,
)


def generate_dummy_tasks(user_id: str):
    now = datetime.utcnow()
    return [
        {
            "user": user_id,
            "type": "Work",
            "priority": "High",
            "taskLength": "Short",
            "timeOfDay": "Morning",
            "titleLength": 3,
            "hasDescription": 1,
            "dayOfWeek": 2,
            "hourOfDay": 9,
            "isWeekend": 0,
            "currentEnergyLevel": 6,
            "currentMood": "Neutral",
            "productivityScore": 80,
        },
        {
            "user": user_id,
            "type": "Study",
            "priority": "Medium",
            "taskLength": "Medium",
            "timeOfDay": "Afternoon",
            "titleLength": 6,
            "hasDescription": 0,
            "dayOfWeek": 3,
            "hourOfDay": 14,
            "isWeekend": 0,
            "currentEnergyLevel": 5,
            "currentMood": "Neutral",
            "productivityScore": 65,
        },
    ]


def train_user_model(user_id: str, task_list: list) -> None:
    logger.info(f"[TRAINING] Starting Recommender model training for user: {user_id}")
    is_baseline_model = False

    if not task_list:
        logger.warning(f"[BOOTSTRAP] No tasks found for user={user_id}. Fetching fallback tasks.")
        try:
            task_list = list(
                tasks.find({"completed": True, "user": {"$ne": ObjectId(user_id)}}).limit(1000)
            )
        except Exception as e:
            logger.error(f"[BOOTSTRAP] Fallback fetch failed: {e}")
            raise RuntimeError("Training failed: no fallback data available.")
        if not task_list:
            raise RuntimeError("Training aborted: no tasks to train on.")
        is_baseline_model = True

    df = pd.DataFrame(task_list)
    now = datetime.utcnow()

    df["titleLength"] = df.get("title", "").apply(lambda x: len(x.split()) if isinstance(x, str) else 0)
    df["hasDescription"] = df.get("description", "").apply(lambda x: 1 if x and str(x).strip() else 0)
    df["createdAt"] = pd.to_datetime(df.get("createdAt"), errors="coerce").fillna(now)
    df["dayOfWeek"] = df["createdAt"].dt.weekday
    df["hourOfDay"] = df["createdAt"].dt.hour
    df["isWeekend"] = df["dayOfWeek"].isin([5, 6]).astype(int)
    df["timeOfDay"] = df["hourOfDay"].apply(
        lambda h: "Morning" if h < 12 else "Afternoon" if h < 18 else "Evening"
    )
    df["taskLength"] = df["titleLength"].apply(
        lambda l: "Short" if l < 3 else "Medium" if l < 6 else "Long"
    )

    # Default fill values
    defaults = {
        "type": "Other",
        "priority": "Medium",
        "titleLength": 5,
        "hasDescription": 0,
        "taskLength": "Medium",
        "timeOfDay": "Afternoon",
        "currentEnergyLevel": 5,
        "currentMood": "Neutral",
        "dayOfWeek": now.weekday(),
        "hourOfDay": now.hour,
        "isWeekend": 0,
        "productivityScore": 50,
    }

    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val  # just assign the default directly
        else:
            df[col] = df[col].fillna(val)

    try:
        df["titleLength"] = df["titleLength"].astype(int)
        df["hasDescription"] = df["hasDescription"].astype(int)
        df["dayOfWeek"] = df["dayOfWeek"].astype(int)
        df["hourOfDay"] = df["hourOfDay"].astype(int)
        df["isWeekend"] = df["isWeekend"].astype(int)
        df["currentEnergyLevel"] = df["currentEnergyLevel"].astype(float)
        df["productivityScore"] = df["productivityScore"].astype(float)
    except Exception as e:
        raise ValueError(f"[TRAINING] Data type conversion failed: {e}")

    df = df[df["productivityScore"] > 0]
    if len(df) < 2:
        logger.warning(f"[TRAINING] Insufficient data — injecting dummy tasks")
        task_list += generate_dummy_tasks(user_id)
        return train_user_model(user_id, task_list)

    df = df[RECOMMENDER_FEATURES + ["productivityScore"]]

    # Encode categorical features
    encoders = {}
    for col in CATEGORICAL_COLUMNS:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le
        logger.debug(f"[ENCODING] Encoded '{col}': {list(le.classes_)}")

    X = df[RECOMMENDER_FEATURES]
    y = df["productivityScore"]

    model = RandomForestRegressor()
    model.fit(X, y)

    y_pred = model.predict(X)
    r2 = round(r2_score(y, y_pred), 3)
    mae = round(mean_absolute_error(y, y_pred), 2)

    logger.info(f"[EVALUATION] Recommender model R²: {r2}, MAE: {mae}")

    version = get_model_registry(user_id)
    model_path = os.path.join(MODEL_DIR, f"{user_id}_v{version}{MODEL_SUFFIX}")
    encoder_path = os.path.join(MODEL_DIR, f"{user_id}_v{version}{ENCODER_SUFFIX}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, model_path)
    joblib.dump(encoders, encoder_path)

    logger.info(f"[SAVE] Model: {model_path}")
    logger.info(f"[SAVE] Encoders: {encoder_path}")

    update_model_registry(user_id, version, len(df), is_baseline_model)
    cleanup_old_versions(user_id, keep_last=2)

    logger.success(
        f"[MODEL] Trained Recommender model v{version} for {user_id} "
        f"({'baseline' if is_baseline_model else 'personal'}) — R²: {r2} | MAE: {mae}"
    )
