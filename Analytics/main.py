from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from bson import ObjectId
from Analytics.config.db import users
from Analytics.schemas.analytics import AnalyticsRequest
from Analytics.services.queue import start_worker, analyze_task
import Analytics.utils.logger_setup

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_worker()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/analyze")
async def analyze(req: AnalyticsRequest):
    uid = req.user_id

    if not ObjectId.is_valid(uid):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = await users.find_one({"_id": ObjectId(uid)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return await analyze_task(req)


