import os
import json
import glob
import re
import joblib
from pathlib import Path
from datetime import datetime
from loguru import logger

from ETC.config.db import MODEL_DIR
from ETC.core.constants import MODEL_SUFFIX, ENCODER_SUFFIX

# Registry file path
REGISTRY_PATH = Path(MODEL_DIR) / "model_registry.json"


def model_file(user_id: str, suffix: str, version: int) -> str:
    """
    Returns the full path for the model/encoder file.
    """
    return str(Path(MODEL_DIR) / f"{user_id}_v{version}{suffix}")


def get_model_registry(user_id: str) -> int:
    """
    Returns the latest available model version on disk for a given user.
    Defaults to version 1 if nothing found.
    """
    pattern = re.compile(rf"{re.escape(user_id)}_v(\d+).*\.pkl$")
    max_version = 0

    try:
        for filename in Path(MODEL_DIR).glob(f"{user_id}_v*.pkl"):
            match = pattern.match(filename.name)
            if match:
                version = int(match.group(1))
                max_version = max(max_version, version)
    except Exception as e:
        logger.warning(f"[MODEL] Failed to determine latest version for {user_id}: {e}")

    return max_version if max_version > 0 else 1


def load_model_files(user_id: str, suffixes: list[str]) -> dict:
    """
    Loads model/encoder files from disk for a user and version.
    Keys will be MODEL_SUFFIX and ENCODER_SUFFIX so that downstream code doesn't break.
    """
    version = get_model_registry(user_id)
    files = {}

    suffix_key_map = {
        MODEL_SUFFIX: MODEL_SUFFIX,
        ENCODER_SUFFIX: ENCODER_SUFFIX,
        "_etc_model.pkl": MODEL_SUFFIX,      # fallback mapping
        "_encoders.pkl": ENCODER_SUFFIX,     # fallback mapping
    }

    for suffix in suffixes:
        true_suffix = suffix_key_map.get(suffix, suffix)
        full_path = model_file(user_id, true_suffix, version)
        try:
            files[true_suffix] = joblib.load(full_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"[MODEL] Missing file: {full_path}")
        except Exception as e:
            raise RuntimeError(f"[MODEL] Failed to load {full_path}: {str(e)}")

    logger.debug(f"[MODEL] Loaded model v{version} for user {user_id}")
    return files


def cleanup_old_versions(user_id: str, keep_last: int = 2):
    """
    Deletes old model and encoder versions for a user.
    Keeps only the latest `keep_last` versions.
    """
    pattern = re.compile(rf"{re.escape(user_id)}_v(\d+).*\.pkl$")
    version_map = {}

    for file in glob.glob(str(Path(MODEL_DIR) / f"{user_id}_v*.pkl")):
        match = pattern.search(Path(file).name)
        if match:
            version = int(match.group(1))
            version_map.setdefault(version, []).append(file)

    sorted_versions = sorted(version_map.keys())
    versions_to_delete = sorted_versions[:-keep_last]

    for version in versions_to_delete:
        for file_path in version_map[version]:
            try:
                Path(file_path).unlink()
                logger.debug(f"[CLEANUP] Deleted old model: {file_path}")
            except Exception as e:
                logger.warning(f"[CLEANUP] Failed to delete {file_path}: {e}")


def update_model_registry(user_id: str, version: int, task_count: int, is_baseline: bool) -> None:
    """
    Updates the model registry file with metadata about the trained model.
    """
    registry = {}

    if REGISTRY_PATH.exists():
        try:
            with open(REGISTRY_PATH, "r") as f:
                registry = json.load(f)
        except Exception as e:
            logger.warning(f"[REGISTRY] Failed to load existing registry: {e}")

    registry[user_id] = {
        "version": version,
        "trained_at": datetime.utcnow().isoformat(),
        "task_count": task_count,
        "is_baseline": is_baseline
    }

    try:
        os.makedirs(REGISTRY_PATH.parent, exist_ok=True)
        with open(REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2)
        logger.info(f"[REGISTRY] Updated registry for {user_id} → v{version}")
    except Exception as e:
        logger.error(f"[REGISTRY] Failed to write registry for {user_id}: {e}")
