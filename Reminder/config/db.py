import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger

# Load .env file
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
dotenv_path = os.path.join(BASE_DIR, ".env")
if not os.path.exists(dotenv_path):
    logger.warning(f".env not found at {dotenv_path}, trying fallback...")
    dotenv_path = os.path.abspath(".env")

load_dotenv(dotenv_path)
logger.success(f"Loaded environment variables from {dotenv_path}")

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    logger.critical("MONGO_URI not set in environment.")
    raise RuntimeError("Missing MONGO_URI in .env")

try:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["test"]
    users = db["users"]
    tasks = db["tasks"]
    logs = db["logs"]
    logger.success("Connected to MongoDB successfully.")
except Exception as e:
    logger.exception(f"MongoDB connection failed: {e}")
    raise e
