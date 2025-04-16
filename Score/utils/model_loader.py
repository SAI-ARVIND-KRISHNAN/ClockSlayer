import os
import re
import glob
import json
import joblib

from loguru import logger
from Score.config.db import MODEL_DIR, MODEL_REGISTRY_PATH
from Score.core.constants import PRODUCTIVITY_SUFFIX, DISTRACTION_SUFFIX, ENCODER_SUFFIX

SUFFIXES = [PRODUCTIVITY_SUFFIX, DISTRACTION_SUFFIX, ENCODER_SUFFIX]


def get_latest_version(user_id: str) -> int:
    """
    Returns the latest available model version on disk for a given user.
    Falls back to 1 if nothing found.
    """
    version_pattern = re.compile(rf"{user_id}_v(\d+)_.*\.pkl")
    max_version = 0

    try:
        for filename in os.listdir(MODEL_DIR):
            match = version_pattern.match(filename)
            if match:
                version = int(match.group(1))
                max_version = max(max_version, version)
    except Exception as e:
        logger.warning(f"Could not scan model directory for user {user_id}: {e}")

    return max_version or 1


def model_file(user_id: str, version: int, suffix: str) -> str:
    """Returns the full file path for a given user, version, and model type."""
    return os.path.join(MODEL_DIR, f"{user_id}_v{version}{suffix}")


def load_model_files(user_id: str, suffixes: list[str]) -> dict:
    """
    Loads model files (e.g., productivity, distraction, encoders) for a user.
    Raises FileNotFoundError if any expected file is missing.
    """
    version = get_latest_version(user_id)
    files = {}

    for suffix in suffixes:
        path = model_file(user_id, version, suffix)
        if not os.path.exists(path):
            logger.error(f"Model file not found: {path}")
            raise FileNotFoundError(f"Model file missing: {path}")

        try:
            files[suffix] = joblib.load(path)
            logger.debug(f"Loaded model file: {path}")
        except Exception as e:
            logger.error(f"Failed to load model file {path}: {e}")
            raise e

    logger.info(f"All model files for user {user_id} (v{version}) loaded successfully")
    return files


def cleanup_old_versions(user_id: str, keep_last: int = 2) -> None:
    """
    Deletes old model versions for a user, keeping only the most recent `keep_last` versions.
    """
    pattern = re.compile(rf"{user_id}_v(\d+).*\.pkl")
    version_map = {}

    for file in glob.glob(os.path.join(MODEL_DIR, f"{user_id}_v*")):
        match = pattern.search(os.path.basename(file))
        if match:
            version = int(match.group(1))
            version_map.setdefault(version, []).append(file)

    sorted_versions = sorted(version_map.keys())
    versions_to_remove = sorted_versions[:-keep_last]

    for v in versions_to_remove:
        for f in version_map[v]:
            try:
                os.remove(f)
                logger.debug(f"[CLEANUP] Deleted old model file: {f}")
            except Exception as e:
                logger.warning(f"[CLEANUP] Failed to delete {f}: {e}")
