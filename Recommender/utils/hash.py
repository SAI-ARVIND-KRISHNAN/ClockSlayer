# Filename: recommender/utils/hash.py

import hashlib
from typing import List


def compute_task_hash(task_list: List[dict]) -> str:
    """
    Computes a hash based on task _id and updatedAt fields.

    Args:
        task_list (List[dict]): List of task dictionaries.

    Returns:
        str: MD5 hash string representing the data state.
    """
    data_string = ''.join([
        str(task.get("_id", "")) + str(task.get("updatedAt", ""))
        for task in task_list
    ])
    return hashlib.md5(data_string.encode()).hexdigest()
