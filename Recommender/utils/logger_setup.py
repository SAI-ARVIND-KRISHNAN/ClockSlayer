# Filename: logger_setup.py

from loguru import logger
import sys
import os

def setup_logger():
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level="DEBUG" if os.getenv("DEBUG", "0") == "1" else "INFO",
        backtrace=True,
        diagnose=True
    )
