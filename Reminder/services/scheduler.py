from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException
import pandas as pd

from Reminder.config.db import users, tasks

async def generate_dynamic_reminders(user_id: str) -> dict:
    user_obj = await users.find_one({"_id": ObjectId(user_id)})
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found.")

    now = datetime.utcnow()

    # Fetch incomplete tasks
    incomplete_tasks = await tasks.find({
        "user": ObjectId(user_id),
        "completed": False
    }).to_list(length=1000)

    # Sort tasks: overdue first, then by closest deadline
    incomplete_tasks.sort(key=lambda t: (
        t.get("deadline", now) < now,
        abs((t.get("deadline", now) - now).total_seconds())
    ), reverse=True)

    if not incomplete_tasks:
        return {"message": "No incomplete tasks needing reminders."}

    # Fetch completed tasks
    completed_tasks = await tasks.find({
        "user": ObjectId(user_id),
        "completed": True,
        "productivityScore": {"$ne": None}
    }).to_list(length=1000)

    if not completed_tasks:
        return {"message": "No past task history to base reminders on."}

    df = pd.DataFrame(completed_tasks)
    df["completedAt"] = pd.to_datetime(df["completedAt"], errors="coerce")
    df["hour"] = df["completedAt"].dt.hour

    productive_hours = df.groupby("hour")["productivityScore"]\
        .mean().sort_values(ascending=False).head(3).index.tolist()

    reminders = []

    for task in incomplete_tasks:
        task_id = str(task.get("_id"))
        title = task.get("title", "Unnamed Task")
        deadline = task.get("deadline")
        if not isinstance(deadline, datetime):
            continue

        best_time = None
        for hour in productive_hours:
            tentative_time = deadline.replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(hours=1)
            if tentative_time > now:
                best_time = tentative_time
                break

        if not best_time:
            best_time = deadline - timedelta(hours=2)
            if best_time < now:
                best_time = now + timedelta(minutes=5)

        message = f"Hey! You usually focus well around this time. Start your '{title}' task now for a productivity boost!"
        if deadline < now:
            message = "Overdue task – deadline already passed!"

        reminders.append({
            "user_id": user_id,
            "task_id": task_id,
            "reminder_time": best_time.isoformat(),
            "message": message
        })

    return {"reminders": reminders}
