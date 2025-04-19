import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger

# ----------------------------------------
# Load environment variables from .env
# ----------------------------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
dotenv_path = os.path.join(BASE_DIR, ".env")

if not os.path.exists(dotenv_path):
    dotenv_path = os.path.abspath(".env")  # fallback

load_dotenv(dotenv_path)

# ----------------------------------------
# MongoDB Setup
# ----------------------------------------

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("Environment variable MONGO_URI not set!")

client = AsyncIOMotorClient(MONGO_URI)
db = client["test"]

# Collections
users = db["users"]
tasks = db["tasks"]

# ----------------------------------------
# Model Directory Setup
# ----------------------------------------

MODEL_DIR = os.path.join(BASE_DIR, "models", "etc")
MODEL_REGISTRY_PATH = os.path.join(MODEL_DIR, "model_registry.json")

logger.debug(f"Model registry path set to: {MODEL_REGISTRY_PATH}")
