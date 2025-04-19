import hashlib
from loguru import logger

def compute_task_hash(task_list: list) -> str:
    """
    Computes a hash of the task list based on task ID and updatedAt timestamp.
    Used to detect changes in user task history.
    """
    try:
        joined = ''.join([
            str(task.get("_id", "")) + str(task.get("updatedAt", ""))
            for task in task_list
        ])
        task_hash = hashlib.md5(joined.encode()).hexdigest()
        logger.debug(f"[HASH] Computed hash for {len(task_list)} tasks → {task_hash}")
        return task_hash

    except Exception as e:
        logger.error(f"[HASH] Failed to compute task hash: {e}")
        return ""
