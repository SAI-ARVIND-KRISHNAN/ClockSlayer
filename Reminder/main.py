from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from bson import ObjectId

from Reminder.schemas.reminder import ReminderRequest
from Reminder.services.queue import start_worker, reminder_task
from Reminder.config.db import users
import Reminder.utils.logger_setup

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_worker()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/dynamic_reminder")
async def dynamic_reminder(req: ReminderRequest):
    uid = req.user_id
    if not ObjectId.is_valid(uid):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    if not await users.find_one({"_id": ObjectId(uid)}):
        raise HTTPException(status_code=404, detail="User not found")

    return await reminder_task(req)