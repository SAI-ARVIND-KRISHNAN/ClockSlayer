import pandas as pd
from datetime import datetime
from bson import ObjectId
from loguru import logger

from ETC.config.db import tasks, users
from ETC.utils.encoder import encode_with_fallback
from ETC.utils.model_loader import load_model_files
from ETC.core.constants import ETC_FEATURES, CATEGORICAL_COLUMNS, MODEL_SUFFIX, ENCODER_SUFFIX


async def predict_etc(user_id: str, req_data) -> dict:
    logger.debug(f"[ETC] Predicting ETC for user={user_id}")

    try:
        created = datetime.utcnow()
        deadline = created + pd.Timedelta(hours=req_data.deadline_gap or 4)

        row = pd.DataFrame([{
            "user": user_id,
            "type": req_data.type,
            "priority": req_data.priority,
            "deadline_gap": req_data.deadline_gap,
            "dayOfWeek": req_data.dayOfWeek,
            "hourOfDay": req_data.hourOfDay,
            "isWeekend": int(req_data.isWeekend),
            "timeOfDay": req_data.timeOfDay,
            "hasDescription": int(req_data.hasDescription),
            "titleLength": req_data.titleLength,
            "urgency": req_data.urgency,
            "taskLength": req_data.taskLength,
            "productivityScore": float(req_data.productivityScore),
            "distractionScore": float(req_data.distractionScore)
        }])

        logger.debug("[ETC] Raw input row:\n" + row.to_string(index=False))

    except Exception as e:
        logger.error(f"[ETC] Failed to construct input row: {e}")
        return {
            "etc_minutes": -1,
            "formatted_etc": None,
            "error": f"Input preparation failed: {str(e)}"
        }

    try:
        models = load_model_files(user_id, [MODEL_SUFFIX, ENCODER_SUFFIX])
        model = models[MODEL_SUFFIX]
        encoders = models[ENCODER_SUFFIX]
        logger.debug("[ETC] Model and encoder successfully loaded.")
    except Exception as e:
        logger.error(f"[ETC] Model load failed: {str(e)}")
        return {
            "etc_minutes": -1,
            "formatted_etc": None,
            "error": f"Model load failed: {str(e)}"
        }

    try:
        for col in CATEGORICAL_COLUMNS:
            encode_with_fallback(row, col, encoders)
        logger.debug("[ETC] Encoded row:\n" + row[ETC_FEATURES].head(1).to_string(index=False))
    except Exception as e:
        logger.error(f"[ETC] Encoding failed: {str(e)}")
        return {
            "etc_minutes": -1,
            "formatted_etc": None,
            "error": f"Encoding failed: {str(e)}"
        }

    try:
        X = row[ETC_FEATURES]
        minutes = float(model.predict(X)[0])
        logger.info(f"[ETC] Predicted ETC={minutes:.2f} min for user={user_id}")
    except Exception as e:
        logger.exception("[ETC] Model prediction failed")
        return {
            "etc_minutes": -1,
            "formatted_etc": None,
            "error": f"ETC prediction failed: {str(e)}"
        }

    def format_time(minutes: float) -> str:
        minutes = int(round(minutes))
        if minutes <= 0:
            return "less than a minute"
        hours, mins = divmod(minutes, 60)
        return f"{hours}h {mins}m" if hours else f"{mins} min"

    return {
        "etc_minutes": round(minutes, 2),
        "formatted_etc": format_time(minutes)
    }
