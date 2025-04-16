import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger

# ----------------------------------------
# Setup Logging (write to file, rotate daily)
# ----------------------------------------

logger.add("logs/score.log", rotation="500 KB", retention="7 days", enqueue=True)
logger.info("Starting DB and environment configuration...")

# ----------------------------------------
# Load .env from project root
# ----------------------------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
dotenv_path = os.path.join(BASE_DIR, ".env")

if not os.path.exists(dotenv_path):
    logger.warning(f".env not found at {dotenv_path}, trying fallback...")
    dotenv_path = os.path.abspath(".env")

load_dotenv(dotenv_path)
logger.success(f"Loaded environment variables from {dotenv_path}")

# ----------------------------------------
# MongoDB Setup (Async with Motor)
# ----------------------------------------

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    logger.critical("MONGO_URI is not set in the environment!")
    raise RuntimeError("Environment variable MONGO_URI not set!")

try:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["test"]
    users = db["users"]
    tasks = db["tasks"]
    logger.success("Connected to MongoDB successfully.")
except Exception as e:
    logger.exception(f"Failed to initialize MongoDB client: {e}")
    raise e

# ----------------------------------------
# Model File Paths
# ----------------------------------------

MODEL_DIR = os.path.join(BASE_DIR, "models", "scoring")
MODEL_REGISTRY_PATH = os.path.join(BASE_DIR, "models", "model_registry.json")

logger.debug(f"Model directory set to: {MODEL_DIR}")
logger.debug(f"Model registry path set to: {MODEL_REGISTRY_PATH}")
