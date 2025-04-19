import hashlib
import json
from loguru import logger

def compute_task_hash(tasks: list[dict]) -> str:
    """
    Computes a SHA256 hash of the task list based on relevant features for model training.
    This helps detect when the task history has changed and retraining is needed.
    """
    if not tasks:
        return "EMPTY"

    try:
        # Consider only a subset of keys that impact training
        filtered = [
            {
                "type": t.get("type"),
                "priority": t.get("priority"),
                "actualTimeSpent": t.get("actualTimeSpent"),
                "productivityScore": t.get("productivityScore"),
                "distractionScore": t.get("distractionScore"),
                "deadline_gap": t.get("deadline_gap"),
                "taskLength": t.get("taskLength"),
                "titleLength": t.get("titleLength"),
                "hasDescription": t.get("hasDescription"),
                "dayOfWeek": t.get("dayOfWeek"),
                "hourOfDay": t.get("hourOfDay"),
                "isWeekend": t.get("isWeekend"),
                "timeOfDay": t.get("timeOfDay"),
                "urgency": t.get("urgency")
            }
            for t in tasks
        ]

        # Serialize and hash
        serialized = json.dumps(filtered, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    except Exception as e:
        logger.error(f"[HASH] Failed to compute task hash: {e}")
        return "ERROR"
