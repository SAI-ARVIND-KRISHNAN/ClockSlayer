# Filename: main.py

from fastapi import FastAPI
from Recommender.services.queue import start_worker, recommend
from Recommender.schemas.request import RecommendationRequest
from Recommender.utils.logger_setup import setup_logger

# ----------------------------------------
# Initialize FastAPI
# ----------------------------------------

app = FastAPI(
    title="Recommender Service",
    version="1.0.0",
    description="Task recommendation engine based on productivity score"
)

# ----------------------------------------
# Setup logger
# ----------------------------------------

setup_logger()

# ----------------------------------------
# Start async worker on startup
# ----------------------------------------

@app.on_event("startup")
async def startup_event():
    await start_worker()

# ----------------------------------------
# Routes
# ----------------------------------------

@app.post("/recommend")
async def recommend_task(req: RecommendationRequest):
    return await recommend(req)
