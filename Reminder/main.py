from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import asyncio
import traceback

app = FastAPI()

# MongoDB setup
client = MongoClient("mongodb+srv://vercettitommy018:M0qLrkDnJnemBbta@cluster0.xxart2t.mongodb.net/", tls=True, tlsAllowInvalidCertificates=True)
db = client["test"]
users = db["users"]
tasks = db["tasks"]
logs = db["logs"]

task_queue = asyncio.Queue()
response_map = {}

class ReminderRequest(BaseModel):
    user_id: str

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(process_queue())

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        try:
            result = generate_dynamic_reminders(req_data.user_id)
            response_map[req_id].set_result(result)
        except Exception as e:
            traceback.print_exc()
            response_map[req_id].set_exception(HTTPException(status_code=500, detail=str(e)))
        finally:
            task_queue.task_done()

@app.post("/dynamic_reminder")
async def dynamic_reminder(req: ReminderRequest):
    req_id = id(req)
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future

def generate_dynamic_reminders(user_id: str):
    user_obj = users.find_one({"_id": ObjectId(user_id)})
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found.")

    # Fetch incomplete tasks with future deadlines
    # Fetch incomplete tasks
    incomplete_tasks = list(tasks.find({
        "user": ObjectId(user_id),
        "completed": False
    }))

    now = datetime.utcnow()

    # Sort tasks: overdue first, then by closest deadline
    incomplete_tasks.sort(key=lambda t: (
        t["deadline"] < now,  # True becomes 1 → so we reverse this logic
        abs((t["deadline"] - now).total_seconds()) if t.get("deadline") else float('inf')
    ), reverse=True)

    if not incomplete_tasks:
        return {"message": "No incomplete tasks needing reminders."}

    # Analyze completed tasks for productivity patterns
    completed_tasks = list(tasks.find({
        "user": ObjectId(user_id),
        "completed": True,
        "productivityScore": {"$ne": None}
    }))

    if not completed_tasks:
        return {"message": "No past task history to base reminders on."}

    df = pd.DataFrame(completed_tasks)
    df["completedAt"] = pd.to_datetime(df["completedAt"], errors="coerce")
    df["hour"] = df["completedAt"].dt.hour

    # Calculate top 3 productive hours
    productive_hours = df.groupby("hour")["productivityScore"].mean().sort_values(ascending=False).head(3).index.tolist()

    now = datetime.utcnow()
    reminders = []

    for task in incomplete_tasks:
        task_id = str(task["_id"])
        title = task.get("title", "Unnamed Task")
        deadline = task.get("deadline")
        predicted_score = task.get("predictedProductivityScore", 50)

        # Strategy:
        # - Send reminder 1–2 hours before the deadline
        # - Prefer one of the user's productive hours
        # - Never send in the past
        best_time = None
        for hour in productive_hours:
            tentative_time = deadline.replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(hours=1)
            if tentative_time > now:
                best_time = tentative_time
                break

        # Fallback to 2 hours before deadline
        if not best_time:
            best_time = deadline - timedelta(hours=2)
            if best_time < now:
                best_time = now + timedelta(minutes=5)

        message = f"Hey! You usually focus well around this time. Start your '{title}' task now for a productivity boost!"
        if deadline < now:
            message = "🔥 Overdue task – deadline already passed!"

        reminders.append({
            "user_id": user_id,
            "task_id": task_id,
            "reminder_time": best_time.isoformat(),
            "message": message
        })

    return {"reminders": reminders}
