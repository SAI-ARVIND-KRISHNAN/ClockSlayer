import os
import json
import pandas as pd
import joblib
from datetime import datetime
from xgboost import XGBRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_absolute_error

from loguru import logger
from Score.config.db import tasks, MODEL_DIR
from Score.core.constants import *
from Score.utils.model_loader import cleanup_old_versions

# Registry file path
REGISTRY_PATH = os.path.join(MODEL_DIR, "model_registry.json")

def get_model_version(user_id: str) -> int:
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r") as f:
            registry = json.load(f)
        return registry.get(user_id, {}).get("version", 0) + 1
    return 1

def update_model_registry(user_id: str, version: int, task_count: int, is_baseline: bool) -> None:
    registry = {}
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r") as f:
            registry = json.load(f)

    registry[user_id] = {
        "version": version,
        "trained_at": datetime.utcnow().isoformat(),
        "task_count": task_count,
        "is_baseline": is_baseline
    }

    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)

    logger.info(f"[REGISTRY] Updated model registry for user {user_id} → v{version}")

async def train_user_model(user_id: str, task_list: list = None) -> None:
    is_baseline_model = False

    if not task_list:
        logger.warning(f"[BOOTSTRAP] No tasks for user {user_id}. Falling back to global completed tasks.")
        try:
            cursor = tasks.find({"completed": True, "user": {"$ne": user_id}}).limit(1000)
            task_list = await cursor.to_list(length=1000)
        except Exception as e:
            logger.error(f"[BOOTSTRAP] MongoDB fallback fetch failed for user {user_id}: {e}")
            raise RuntimeError(f"MongoDB fallback fetch failed: {str(e)}")

        if not task_list:
            logger.critical(f"[TRAIN] No global fallback tasks available. Training aborted.")
            raise RuntimeError("No global completed tasks available.")
        is_baseline_model = True

    df = pd.DataFrame(task_list)
    logger.debug(f"[TRAIN] Task DataFrame created for user {user_id} with {len(df)} entries")

    # Feature engineering
    df["titleLength"] = df["title"].apply(lambda x: len(x.split()) if isinstance(x, str) else 0)
    df["hasDescription"] = df["description"].apply(lambda x: 1 if isinstance(x, str) and x.strip() else 0)
    df["createdAt"] = pd.to_datetime(df["createdAt"], errors="coerce").fillna(datetime.utcnow())
    df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce").fillna(df["createdAt"] + pd.Timedelta(hours=4))
    df["dayOfWeek"] = df["createdAt"].dt.weekday
    df["hourOfDay"] = df["createdAt"].dt.hour
    df["isWeekend"] = df["dayOfWeek"].isin([5, 6]).astype(int)
    df["timeOfDay"] = df["hourOfDay"].apply(lambda h: "Morning" if h < 12 else "Afternoon" if h < 18 else "Evening")
    df["deadlineGap"] = (df["deadline"] - df["createdAt"]).dt.total_seconds() / 3600
    df["urgency"] = df["deadlineGap"].apply(lambda h: "Urgent" if h < 12 else "Soon" if h < 24 else "Low")
    df["taskLength"] = df["titleLength"].apply(lambda l: "Short" if l < 3 else "Medium" if l < 6 else "Long")
    df["currentEnergyLevel"] = df.get("currentEnergyLevel", DEFAULT_ENERGY)
    df["currentMood"] = df.get("currentMood", DEFAULT_MOOD)

    df = df[MODEL_FEATURES + ["productivityScore", "distractionScore"]]

    encoders = {}
    for col in CATEGORICAL_COLUMNS:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    X = df[MODEL_FEATURES]
    y_prod = df["productivityScore"]
    y_dist = df["distractionScore"]

    prod_model = XGBRegressor()
    dist_model = XGBRegressor()
    prod_model.fit(X, y_prod)
    dist_model.fit(X, y_dist)

    os.makedirs(MODEL_DIR, exist_ok=True)
    version = get_model_version(user_id)

    joblib.dump(prod_model, f"{MODEL_DIR}/{user_id}_v{version}{PRODUCTIVITY_SUFFIX}")
    joblib.dump(dist_model, f"{MODEL_DIR}/{user_id}_v{version}{DISTRACTION_SUFFIX}")
    joblib.dump(encoders, f"{MODEL_DIR}/{user_id}_v{version}{ENCODER_SUFFIX}")

    logger.success(f"[SAVE] Saved model v{version} for user {user_id} ({'baseline' if is_baseline_model else 'personal'})")

    # Training section (already trained)
    prod_model.fit(X, y_prod)
    dist_model.fit(X, y_dist)

    # Predict on training data (you could also use a held-out validation split)
    y_prod_pred = prod_model.predict(X)
    y_dist_pred = dist_model.predict(X)

    # Evaluate
    prod_r2 = r2_score(y_prod, y_prod_pred)
    prod_mae = mean_absolute_error(y_prod, y_prod_pred)

    dist_r2 = r2_score(y_dist, y_dist_pred)
    dist_mae = mean_absolute_error(y_dist, y_dist_pred)

    # Log it
    logger.info(f"[EVAL] Productivity Model → R²: {prod_r2:.4f}, MAE: {prod_mae:.4f}")
    logger.info(f"[EVAL] Distraction Model → R²: {dist_r2:.4f}, MAE: {dist_mae:.4f}")
    
    update_model_registry(user_id, version, len(df), is_baseline_model)
    cleanup_old_versions(user_id, keep_last=2)
