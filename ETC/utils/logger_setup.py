from loguru import logger
import os

def setup_logger(service_name: str = "ETC"):
    """
    Configures the global logger for the ETC service.

    Logs are stored in 'logs/etc.log' with rotation and retention.

    Args:
        service_name (str): Name of the microservice (default: "ETC").
    """
    os.makedirs("logs", exist_ok=True)

    logger.remove()
    logger.add(
        f"logs/{service_name.lower()}.log",
        rotation="1 MB",               # Rotate log file after 1MB
        retention="7 days",            # Keep logs for 7 days
        level="DEBUG",                 # Set default log level
        backtrace=True,
        diagnose=True,
        enqueue=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>"
    )
    logger.debug("[LOGGER] Logger configured for ETC service")
