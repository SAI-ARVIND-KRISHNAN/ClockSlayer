import joblib
import pandas as pd
from datetime import datetime
from xgboost import XGBRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_absolute_error

from loguru import logger
from bson import ObjectId

from ETC.config.db import tasks, users, MODEL_DIR
from ETC.core.constants import ETC_FEATURES, CATEGORICAL_COLUMNS, MODEL_SUFFIX, ENCODER_SUFFIX
from ETC.utils.model_loader import get_model_registry, cleanup_old_versions, update_model_registry


def generate_dummy_tasks(user_id: str):
    now = datetime.utcnow()
    return [
        {
            "user": user_id,
            "type": "Work",
            "priority": "High",
            "urgency": "Urgent",
            "taskLength": "Short",
            "timeOfDay": "Morning",
            "titleLength": 3,
            "hasDescription": 1,
            "dayOfWeek": 2,
            "hourOfDay": 9,
            "isWeekend": 0,
            "productivityScore": 70,
            "distractionScore": 20,
            "actualTimeSpent": 45,
            "createdAt": now,
            "deadline": now + pd.Timedelta(hours=4)
        },
        {
            "user": user_id,
            "type": "Study",
            "priority": "Medium",
            "urgency": "Soon",
            "taskLength": "Medium",
            "timeOfDay": "Afternoon",
            "titleLength": 6,
            "hasDescription": 0,
            "dayOfWeek": 3,
            "hourOfDay": 14,
            "isWeekend": 0,
            "productivityScore": 60,
            "distractionScore": 35,
            "actualTimeSpent": 90,
            "createdAt": now,
            "deadline": now + pd.Timedelta(hours=8)
        }
    ]


def train_user_model(user_id: str, task_list: list) -> None:
    logger.info(f"[TRAINING] Starting ETC model training for user: {user_id}")
    is_baseline_model = False

    if not task_list:
        logger.warning(f"[BOOTSTRAP] No tasks found for {user_id}. Using global fallback.")
        try:
            task_list = list(tasks.find({"completed": True, "user": {"$ne": ObjectId(user_id)}}).limit(1000))
        except Exception as e:
            logger.error(f"[BOOTSTRAP] Failed to fetch fallback tasks: {e}")
            raise RuntimeError("No fallback data available.")
        if not task_list:
            raise RuntimeError("Training aborted: insufficient fallback data.")
        is_baseline_model = True

    df = pd.DataFrame(task_list)
    now = datetime.utcnow()

    df["createdAt"] = pd.to_datetime(df.get("createdAt"), errors="coerce").fillna(now)
    df["deadline"] = pd.to_datetime(df.get("deadline"), errors="coerce")
    df["deadline"] = df["deadline"].fillna(df["createdAt"] + pd.Timedelta(hours=4))
    df["deadline_gap"] = (df["deadline"] - df["createdAt"]).dt.total_seconds() / 3600

    defaults = {
        "hasDescription": 0,
        "titleLength": 5,
        "taskLength": "Medium",
        "dayOfWeek": now.weekday(),
        "hourOfDay": now.hour,
        "isWeekend": 0,
        "timeOfDay": "Afternoon",
        "urgency": "Soon",
        "productivityScore": 50,
        "distractionScore": 50
    }

    for col, val in defaults.items():
        df[col] = df.get(col, val)
        df[col] = df[col].fillna(val)

    try:
        df["hasDescription"] = df["hasDescription"].astype(int)
        df["titleLength"] = df["titleLength"].astype(int)
        df["dayOfWeek"] = df["dayOfWeek"].astype(int)
        df["hourOfDay"] = df["hourOfDay"].astype(int)
        df["isWeekend"] = df["isWeekend"].astype(int)
        df["productivityScore"] = df["productivityScore"].astype(float)
        df["distractionScore"] = df["distractionScore"].astype(float)
    except Exception as e:
        raise ValueError(f"[TRAINING] Feature type conversion failed: {e}")

    df = df[df["actualTimeSpent"] > 0]
    if len(df) < 2:
        logger.warning(f"[TRAINING] Not enough training rows with valid actualTimeSpent. Injecting dummy tasks.")
        task_list += generate_dummy_tasks(user_id)
        return train_user_model(user_id, task_list)

    df = df[ETC_FEATURES + ["actualTimeSpent"]]
    encoders = {}
    for col in CATEGORICAL_COLUMNS:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le
        logger.debug(f"[ENCODING] Encoded '{col}': {list(le.classes_)}")

    X = df[ETC_FEATURES]
    y = df["actualTimeSpent"]

    model = XGBRegressor(objective="reg:squarederror")
    model.fit(X, y)

    y_pred = model.predict(X)
    r2 = round(r2_score(y, y_pred), 3)
    mae = round(mean_absolute_error(y, y_pred), 2)

    logger.info(f"[EVALUATION] ETC model R²: {r2}, MAE: {mae}")
    logger.debug("[FEATURE IMPORTANCES]")
    for feat, imp in zip(ETC_FEATURES, model.feature_importances_):
        logger.debug(f"   - {feat}: {round(imp, 3)}")

    version = get_model_registry(user_id)
    model_path = f"{MODEL_DIR}/{user_id}_v{version}{MODEL_SUFFIX}"
    encoder_path = f"{MODEL_DIR}/{user_id}_v{version}{ENCODER_SUFFIX}"

    joblib.dump(model, model_path)
    joblib.dump(encoders, encoder_path)

    logger.info(f"[SAVE] Model saved to: {model_path}")
    logger.info(f"[SAVE] Encoders saved to: {encoder_path}")

    update_model_registry(user_id, version, len(df), is_baseline_model)
    cleanup_old_versions(user_id, keep_last=2)

    logger.success(
        f"[MODEL] Trained ETC model v{version} for {user_id} "
        f"({'baseline' if is_baseline_model else 'personal'}) — R²: {r2} | MAE: {mae}"
    )
