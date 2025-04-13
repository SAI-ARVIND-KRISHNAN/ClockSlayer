# Filename: main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
from collections import defaultdict, Counter
from datetime import datetime
import pandas as pd
import numpy as np
from scipy.stats import linregress
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

class AnalyticsRequest(BaseModel):
    user_id: str

def analyze_user_data(user_id: str):
    user_obj = users.find_one({"_id": ObjectId(user_id)})
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found.")

    completed_tasks = list(tasks.find({"user": ObjectId(user_id), "completed": True}))
    if not completed_tasks:
        raise HTTPException(status_code=404, detail="No completed tasks found.")

    df = pd.DataFrame(completed_tasks)
    df["completedAt"] = pd.to_datetime(df["completedAt"], errors="coerce")
    df["createdAt"] = pd.to_datetime(df["createdAt"], errors="coerce")
    df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce")
    if "title" in df.columns:
        df["titleLength"] = df["title"].apply(lambda x: len(x.split()) if isinstance(x, str) else 0)
        df["taskLength"] = df["titleLength"].apply(
            lambda l: "Short" if l < 3 else "Medium" if l < 6 else "Long"
        )
    df["hour"] = df["completedAt"].dt.hour
    df["tod"] = df["hour"].apply(lambda h: "Morning" if h < 12 else "Afternoon" if h < 18 else "Evening")
    df["weekday"] = df["completedAt"].dt.weekday
    df["deadlineGap"] = (df["deadline"] - df["createdAt"]).dt.total_seconds() / 3600
    df["isWeekend"] = df["weekday"].isin([5, 6])
    df["efficiency"] = df["productivityScore"] / df["actualTimeSpent"].replace(0, np.nan)

    insights = {}

    try: insights["best_productivity_day"] = df.groupby("weekday")["productivityScore"].mean().idxmax()
    except: insights["best_productivity_day"] = None

    if "currentEnergyLevel" in df.columns:
        insights["energy_productivity_correlation"] = round(df["currentEnergyLevel"].corr(df["productivityScore"]) or 0, 2)

    if "currentMood" in df.columns:
        mood_map = {"Tired": 1, "Stressed": 2, "Neutral": 3, "Happy": 4, "Motivated": 5}
        df["moodScore"] = df["currentMood"].map(mood_map)
        insights["mood_productivity_correlation"] = round(df["moodScore"].corr(df["productivityScore"]) or 0, 2)

    try: insights["best_time_of_day"] = df.groupby("tod")["productivityScore"].mean().idxmax()
    except: insights["best_time_of_day"] = None

    insights["missed_deadline_count"] = len(df[df["completedAt"] > df["deadline"]])

    df_sorted = df.sort_values("completedAt")
    if len(df_sorted) > 1:
        x = (df_sorted["completedAt"] - df_sorted["completedAt"].min()).dt.days
        if x.nunique() > 1:
            slope, *_ = linregress(x, df_sorted["productivityScore"])
            insights["productivity_trend"] = "📈 Improving" if slope > 0 else "📉 Declining" if slope < 0 else "➖ Stable"
        else:
            insights["productivity_trend"] = "Not enough variation in task dates to determine trend"

    insights["avg_time_spent"] = round(df["actualTimeSpent"].mean(), 2)
    active_days = df["completedAt"].dt.date.nunique()
    total_days = (df["completedAt"].max() - df["completedAt"].min()).days + 1
    insights["consistency_score"] = round((active_days / total_days) * 100, 2) if total_days > 0 else 0
    insights["productivity_by_type"] = df.groupby("type")["productivityScore"].mean().round(2).to_dict()

    distractions = df["distractionScore"].dropna()
    if len(distractions):
        avg_distr = distractions.mean()
        insights["avg_distraction_score"] = round(avg_distr, 2)
        insights["distraction_severity"] = "🚨 High" if avg_distr > 70 else "⚠️ Moderate" if avg_distr > 40 else "✅ Low"

    insights["most_common_task_type"] = df["type"].mode().values[0]
    insights["productivity_by_task_length"] = df.groupby("taskLength")["productivityScore"].mean().round(2).to_dict()
    insights["deadline_pressure_impact"] = round(df["deadlineGap"].corr(df["productivityScore"]) or 0, 2)
    insights["hourly_productivity"] = df.groupby("hour")["productivityScore"].mean().round(2).to_dict()

    weekend_prod = df.groupby("isWeekend")["productivityScore"].mean()
    insights["weekend_vs_weekday_productivity"] = {
        "Weekend": round(weekend_prod.get(True, 0), 2),
        "Weekday": round(weekend_prod.get(False, 0), 2)
    }

    insights["coach_feedback_entries"] = logs.count_documents({"user": ObjectId(user_id), "type": "coachFeedback"})

    if "currentEnergyLevel" in df.columns:
        slope, *_ = linregress(np.arange(len(df)), df["currentEnergyLevel"])
        insights["energy_trend"] = "⬆️ Improving" if slope > 0 else "⬇️ Declining" if slope < 0 else "➖ Stable"

    insights["time_vs_productivity_corr"] = round(df["actualTimeSpent"].corr(df["productivityScore"]) or 0, 2)

    if "distractionScore" in df.columns:
        insights["least_distracting_type"] = df.groupby("type")["distractionScore"].mean().idxmin()

    insights["high_impact_hours"] = df.groupby("hour")["productivityScore"].mean().sort_values(ascending=False).head(3).index.tolist()
    insights["avg_title_length"] = round(df["titleLength"].mean(), 2)
    total_tasks = tasks.count_documents({"user": ObjectId(user_id)})
    insights["completion_rate"] = round((len(df) / total_tasks) * 100, 2) if total_tasks else 0

    if "currentEnergyLevel" in df.columns:
        insights["energy_distribution"] = df["currentEnergyLevel"].value_counts().sort_index().to_dict()
    if "currentMood" in df.columns:
        insights["mood_distribution"] = df["currentMood"].value_counts().to_dict()
        insights["best_mood"] = df.groupby("currentMood")["productivityScore"].mean().idxmax()

    insights["most_common_time_block"] = df["tod"].mode().values[0]
    insights["productivity_variability"] = round(df["productivityScore"].std(), 2)
    top_task = df.loc[df["productivityScore"].idxmax()]
    insights["most_productive_task_title"] = top_task.get("title", "N/A")
    insights["least_productive_type"] = df.groupby("type")["productivityScore"].mean().idxmin()

    block_eff = df.groupby("tod")["efficiency"].mean()
    insights["most_efficient_time_block"] = block_eff.idxmax()

    for key, value in insights.items():
        if isinstance(value, (np.integer, np.int32, np.int64)):
            insights[key] = int(value)
        elif isinstance(value, (np.floating, np.float32, np.float64)):
            insights[key] = float(value)
        elif isinstance(value, np.bool_):
            insights[key] = bool(value)
        elif isinstance(value, np.ndarray):
            insights[key] = value.tolist()

    return {"user_id": user_id, "insights": insights}

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(process_queue())

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        try:
            result = analyze_user_data(req_data.user_id)
            response_map[req_id].set_result(result)
        except Exception as e:
            traceback.print_exc()
            response_map[req_id].set_exception(HTTPException(status_code=500, detail=str(e)))
        finally:
            task_queue.task_done()

@app.post("/analyze")
async def analyze(req: AnalyticsRequest):
    req_id = id(req)
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
