from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from bson import ObjectId
from Score.services.queue import start_worker, score_task
from Score.schemas.score import ScoreRequest
from Score.config.db import users
import Score.utils.logger_setup

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_worker()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/score")
async def score(req: ScoreRequest):
    uid = req.user_id
    if not ObjectId.is_valid(uid):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    if not users.find_one({"_id": ObjectId(uid)}):
        raise HTTPException(status_code=404, detail="User not found")

    return await score_task(req)
