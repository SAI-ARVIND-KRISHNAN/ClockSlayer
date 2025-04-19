from loguru import logger
import os

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../logs"))
os.makedirs(LOG_DIR, exist_ok=True)

logger.add(
    os.path.join(LOG_DIR, "reminder.log"),
    rotation="500 KB",
    retention="7 days",
    enqueue=True,
    backtrace=True,
    diagnose=True,
    level="DEBUG"
)

logger.info("[LOGGER] Logger initialized for Reminder service.")