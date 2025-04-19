# Filename: services/recommender.py

import pandas as pd
from datetime import datetime
from bson import ObjectId
from loguru import logger

from Recommender.config.db import tasks, users
from Recommender.utils.encoder import encode_with_fallback
from Recommender.utils.model_loader import load_model_files
from Recommender.core.constants import RECOMMENDER_FEATURES, CATEGORICAL_COLUMNS, MODEL_SUFFIX, ENCODER_SUFFIX


async def get_recommendation(user_id: str, pending_task: dict) -> dict:
    logger.debug(f"[RECOMMENDER] Predicting score for user={user_id}")

    try:
        created = pending_task.get("createdAt", datetime.utcnow())
        title_length = len(pending_task.get("title", "").split())
        has_description = 1 if pending_task.get("description", "").strip() else 0
        day_of_week = created.weekday()
        hour_of_day = created.hour
        is_weekend = int(day_of_week in [5, 6])
        time_of_day = (
            "Morning" if hour_of_day < 12
            else "Afternoon" if hour_of_day < 18
            else "Evening"
        )

        user_obj = await users.find_one({"_id": ObjectId(user_id)})
        if not user_obj:
            raise ValueError("User not found")

        row = pd.DataFrame([{
            "user": user_id,
            "type": pending_task["type"],
            "priority": pending_task["priority"],
            "taskLength": "Short" if title_length < 3 else "Medium" if title_length < 6 else "Long",
            "titleLength": title_length,
            "hasDescription": has_description,
            "dayOfWeek": day_of_week,
            "hourOfDay": hour_of_day,
            "isWeekend": is_weekend,
            "timeOfDay": time_of_day,
            "currentEnergyLevel": float(user_obj.get("currentEnergyLevel", 5)),
            "currentMood": user_obj.get("currentMood", "Neutral")
        }])

        logger.debug("[RECOMMENDER] Raw input row:\n" + row.to_string(index=False))

    except Exception as e:
        logger.error(f"[RECOMMENDER] Failed to prepare input: {e}")
        return {"recommended_task_id": None, "error": f"Input preparation failed: {str(e)}"}

    try:
        models = load_model_files(user_id)
        model = models[MODEL_SUFFIX]
        encoders = models[ENCODER_SUFFIX]
        logger.debug("[RECOMMENDER] Model and encoders loaded.")
    except Exception as e:
        logger.error(f"[RECOMMENDER] Model load failed: {e}")
        return {"recommended_task_id": None, "error": f"Model load failed: {str(e)}"}

    try:
        for col in CATEGORICAL_COLUMNS:
            encode_with_fallback(row, col, encoders)
        logger.debug("[RECOMMENDER] Encoded input:\n" + row[RECOMMENDER_FEATURES].head(1).to_string(index=False))
    except Exception as e:
        logger.error(f"[RECOMMENDER] Encoding failed: {e}")
        return {"recommended_task_id": None, "error": f"Encoding failed: {str(e)}"}

    try:
        X = row[RECOMMENDER_FEATURES]
        predicted_score = float(model.predict(X)[0])
        logger.info(f"[RECOMMENDER] Predicted productivity score={predicted_score:.2f} for user={user_id}")
        return {"score": predicted_score}
    except Exception as e:
        logger.exception("[RECOMMENDER] Model prediction failed")
        return {"recommended_task_id": None, "error": f"Recommender prediction failed: {str(e)}"}
