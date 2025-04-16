import pandas as pd
import joblib
from datetime import datetime, timedelta
from bson import ObjectId
from loguru import logger

from Score.config.db import users, tasks, MODEL_DIR
from Score.core.constants import *
from Score.utils.encoder import encode_with_fallback
from Score.services.trainer import train_user_model
from Score.utils.model_loader import load_model_files

async def predict_scores(user_id: str, task_id: str) -> dict:
    logger.debug(f"[PREDICT] Starting prediction for user={user_id}, task={task_id}")

    # Fetch task and user data
    task = await tasks.find_one({"_id": ObjectId(task_id)})
    user = await users.find_one({"_id": ObjectId(user_id)})

    if not task or not user:
        logger.warning(f"[PREDICT] Task or user not found in DB (user={user_id}, task={task_id})")
        return {
            "productivity_score": -1,
            "distraction_score": -1,
            "error": "User or task not found in database."
        }

    # Extract or default timestamps
    created = pd.to_datetime(task.get("createdAt") or task.get("startedAt") or datetime.utcnow(), errors="coerce")
    created = created if not pd.isna(created) else datetime.utcnow()

    deadline = pd.to_datetime(task.get("deadline"), errors="coerce")
    deadline = deadline if not pd.isna(deadline) else created + timedelta(hours=4)

    # Derived features
    deadline_gap = (deadline - created).total_seconds() / 3600
    title_length = len(task.get("title", "").split())
    has_description = 1 if task.get("description", "").strip() else 0
    day_of_week = created.weekday()
    hour_of_day = created.hour
    is_weekend = int(day_of_week in [5, 6])
    time_of_day = "Morning" if hour_of_day < 12 else "Afternoon" if hour_of_day < 18 else "Evening"
    task_length = "Short" if title_length < 3 else "Medium" if title_length < 6 else "Long"
    urgency = "Urgent" if deadline_gap < 12 else "Soon" if deadline_gap < 24 else "Low"

    # Feature row
    row = pd.DataFrame([{
        "user": user_id,
        "type": task.get("type", "Unknown"),
        "priority": task.get("priority", "Medium"),
        "urgency": urgency,
        "taskLength": task_length,
        "titleLength": title_length,
        "hasDescription": has_description,
        "dayOfWeek": day_of_week,
        "hourOfDay": hour_of_day,
        "isWeekend": is_weekend,
        "timeOfDay": time_of_day,
        "actualTimeSpent": float(task.get("actualTimeSpent") or 0),
        "currentEnergyLevel": float(user.get("currentEnergyLevel", DEFAULT_ENERGY)),
        "currentMood": user.get("currentMood", DEFAULT_MOOD)
    }])

    # Load models or retrain
    try:
        models = load_model_files(user_id, [PRODUCTIVITY_SUFFIX, DISTRACTION_SUFFIX, ENCODER_SUFFIX])
    except FileNotFoundError as e:
        logger.warning(f"[MODEL] Model missing for user {user_id}. Attempting retrain…")
        try:
            history = await tasks.find({"user": ObjectId(user_id), "completed": True}).to_list(length=1000)
            await train_user_model(user_id, history)
            models = load_model_files(user_id, [PRODUCTIVITY_SUFFIX, DISTRACTION_SUFFIX, ENCODER_SUFFIX])
            logger.success(f"[MODEL] Retrained model successfully for user {user_id}")
        except Exception as err:
            logger.error(f"[FAIL] Retraining failed for user {user_id}: {err}")
            return {
                "productivity_score": -1,
                "distraction_score": -1,
                "error": f"Prediction failed after retrain: {str(err)}"
            }

    # Extract trained components
    prod_model = models[PRODUCTIVITY_SUFFIX]
    dist_model = models[DISTRACTION_SUFFIX]
    encoders = models[ENCODER_SUFFIX]

    # Encode categorical features
    for col in CATEGORICAL_COLUMNS:
        encode_with_fallback(row, col, encoders)

    row = row[MODEL_FEATURES]

    # Final prediction
    try:
        ps = float(round(prod_model.predict(row)[0], 2))
        ds = float(round(dist_model.predict(row)[0], 2))
        logger.info(f"[PREDICT] Score → Productivity: {ps}, Distraction: {ds} (user={user_id})")
    except Exception as e:
        logger.exception(f"[PREDICT] Model inference failed for user {user_id}")
        return {
            "productivity_score": -1,
            "distraction_score": -1,
            "error": f"Prediction failed: {str(e)}"
        }


    logger.debug(f"[DB] Scores updated in task {task_id}")

    return {
        "productivity_score": ps,
        "distraction_score": ds
    }
