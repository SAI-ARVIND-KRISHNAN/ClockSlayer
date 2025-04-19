import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger

# Load .env variables
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
dotenv_path = os.path.join(BASE_DIR, ".env")

if not os.path.exists(dotenv_path):
    logger.warning(f".env not found at {dotenv_path}, trying local fallback...")
    dotenv_path = os.path.abspath(".env")

load_dotenv(dotenv_path)
logger.success(f"Loaded environment variables from {dotenv_path}")

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    logger.critical("MONGO_URI is not set in the environment!")
    raise RuntimeError("Environment variable MONGO_URI not set!")

try:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["test"]  # default DB name
    users = db["users"]
    tasks = db["tasks"]
    logs = db["logs"]
    logger.success("Connected to MongoDB successfully.")
except Exception as e:
    logger.exception(f"Failed to initialize MongoDB client: {e}")
    raise
