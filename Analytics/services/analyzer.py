import pandas as pd
import numpy as np
from bson import ObjectId
from loguru import logger

from Analytics.config.db import users, tasks
from Analytics.utils.transform import prepare_dataframe
from Analytics.utils.derive import extract_insights


async def analyze_user_data(user_id: str) -> dict:
    logger.debug(f"[ANALYZE] Starting analysis for user={user_id}")

    if not ObjectId.is_valid(user_id):
        raise ValueError("Invalid user ID format.")

    # Fetch user
    user_obj = await users.find_one({"_id": ObjectId(user_id)})
    if not user_obj:
        raise ValueError("User not found.")

    # Fetch completed tasks
    completed_tasks = await tasks.find({
        "user": ObjectId(user_id),
        "completed": {"$in": [True, "true", 1]}  # handle bool, string, int
    }).to_list(length=1000)

    if not completed_tasks:
        logger.warning(f"[ANALYZE] No completed tasks found for user={user_id}")
        raise ValueError("No completed tasks found.")

    logger.debug(f"[ANALYZE] Retrieved {len(completed_tasks)} completed tasks")

    # Transform
    df = prepare_dataframe(completed_tasks)

    # Extract insights
    insights = await extract_insights(df, user_id)

    # Normalize numpy types
    for key, value in insights.items():
        if isinstance(value, (np.integer, np.int32, np.int64)):
            insights[key] = int(value)
        elif isinstance(value, (np.floating, np.float32, np.float64)):
            insights[key] = float(value)
        elif isinstance(value, np.bool_):
            insights[key] = bool(value)
        elif isinstance(value, np.ndarray):
            insights[key] = value.tolist()

    logger.success(f"[ANALYZE] Extracted {len(insights)} insights for user={user_id}")
    return {"user_id": user_id, "insights": insights}
