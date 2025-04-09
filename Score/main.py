from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import joblib
import os
import asyncio
import traceback
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder
from sympy import false
import hashlib

app = FastAPI()

# MongoDB setup
client = MongoClient(
    "mongodb+srv://vercettitommy018:M0qLrkDnJnemBbta@cluster0.xxart2t.mongodb.net/",
    tls=True, tlsAllowInvalidCertificates=True
)
db = client["test"]
users = db["users"]
tasks = db["tasks"]

# Metadata cache to detect new data
data_hash_map = {}

task_queue = asyncio.Queue()
response_map = {}

class ScoreRequest(BaseModel):
    user_id: str
    task_id: str

def encode_column(df, col, encoder):
    if col not in df.columns or col not in encoder:
        return
    le = encoder[col]
    encoded = []
    for val in df[col]:
        if val in le.classes_:
            encoded.append(le.transform([val])[0])
        else:
            fallback_val = le.classes_[0]
            print(f"[Encoding fallback] {col}: '{val}' → '{fallback_val}'")
            encoded.append(le.transform([fallback_val])[0])
    df[col] = encoded

def compute_hash(task_list):
    data_string = ''.join([str(task.get("_id")) + str(task.get("updatedAt")) for task in task_list])
    return hashlib.md5(data_string.encode()).hexdigest()

def train_model_for_user(user_id):
    past_tasks = list(tasks.find({
        "user": ObjectId(user_id),
        "completed": True
    }))

    if len(past_tasks) == 0:
        print("⚠️ No real user data found — using dummy data for training.")
        past_tasks = [{
            "user": user_id,
            "type": "Study", "priority": "Medium", "urgency": "Soon", "taskLength": "Medium",
            "titleLength": 4, "hasDescription": 1, "dayOfWeek": 1, "hourOfDay": 14, "isWeekend": 0,
            "timeOfDay": "Afternoon", "actualTimeSpent": 1.5, "currentEnergyLevel": 5,
            "currentMood": "Neutral", "productivityScore": 60, "distractionScore": 40
        } for _ in range(20)]
    else:
        # Update user hash
        data_hash_map[user_id] = compute_hash(past_tasks)

    df = pd.DataFrame(past_tasks)

    if "user" not in df.columns and "userId" in df.columns:
        df["user"] = df["userId"].astype(str)

    df["titleLength"] = df["title"].apply(lambda x: len(x.split()) if isinstance(x, str) else 0)
    df["hasDescription"] = df["description"].apply(lambda x: 1 if isinstance(x, str) and x.strip() else 0)
    df["dayOfWeek"] = pd.to_datetime(df["createdAt"]).dt.weekday
    df["hourOfDay"] = pd.to_datetime(df["createdAt"]).dt.hour
    df["isWeekend"] = df["dayOfWeek"].isin([5, 6]).astype(int)
    df["timeOfDay"] = df["hourOfDay"].apply(
        lambda h: "Morning" if h < 12 else "Afternoon" if h < 18 else "Evening"
    )

    df["deadlineGap"] = (
        (pd.to_datetime(df["deadline"]) - pd.to_datetime(df["createdAt"])).dt.total_seconds() / 3600
    )
    df["urgency"] = df["deadlineGap"].apply(
        lambda h: "Urgent" if h < 12 else "Soon" if h < 24 else "Low"
    )
    df["taskLength"] = df["titleLength"].apply(
        lambda l: "Short" if l < 3 else "Medium" if l < 6 else "Long"
    )

    df["currentEnergyLevel"] = df.get("currentEnergyLevel", 5)
    df["currentMood"] = df.get("currentMood", "Neutral")

    df = df[[
        "user", "type", "priority", "urgency", "taskLength", "titleLength",
        "hasDescription", "dayOfWeek", "hourOfDay", "isWeekend", "timeOfDay",
        "actualTimeSpent", "currentEnergyLevel", "currentMood",
        "productivityScore", "distractionScore"
    ]]

    cat_cols = ["user", "type", "priority", "urgency", "taskLength", "timeOfDay", "currentMood"]
    encoders = {}
    for col in cat_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    X = df.drop(columns=["productivityScore", "distractionScore"])
    y_prod = df["productivityScore"]
    y_dist = df["distractionScore"]

    prod_model = xgb.XGBRegressor()
    dist_model = xgb.XGBRegressor()
    prod_model.fit(X, y_prod)
    dist_model.fit(X, y_dist)

    os.makedirs("models", exist_ok=True)
    joblib.dump(prod_model, f"models/{user_id}_productivity_model.pkl")
    joblib.dump(dist_model, f"models/{user_id}_distraction_model.pkl")
    joblib.dump(encoders, f"models/{user_id}_scoring_encoders.pkl")
    print(f"✅ Trained and saved models for user {user_id}.")

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        try:
            user_id = req_data.user_id
            task_id = req_data.task_id

            prod_path = f"models/{user_id}_productivity_model.pkl"
            dist_path = f"models/{user_id}_distraction_model.pkl"
            enc_path = f"models/{user_id}_scoring_encoders.pkl"

            # Fetch past tasks and detect changes
            past_tasks = list(tasks.find({"user": ObjectId(user_id), "completed": True}))
            current_hash = compute_hash(past_tasks)
            if user_id not in data_hash_map or data_hash_map[user_id] != current_hash:
                print("🔁 Detected new data — retraining model...")
                train_model_for_user(user_id)

            prod_model = joblib.load(prod_path)
            distract_model = joblib.load(dist_path)
            encoders = joblib.load(enc_path)

            task = tasks.find_one({"_id": ObjectId(task_id)})
            user = users.find_one({"_id": ObjectId(user_id)})
            if not task or not user:
                raise HTTPException(status_code=404, detail="User or task not found.")

            if task.get("productivityScore") is not None and task.get("distractionScore") is not None:
                response_map[req_id].set_result({
                    "productivity_score": task["productivityScore"],
                    "distraction_score": task["distractionScore"]
                })
                task_queue.task_done()
                continue

            now = datetime.utcnow()
            created = task.get("createdAt") or task.get("startedAt") or now
            deadline = task.get("deadline") or now + timedelta(hours=4)
            deadline_gap = (deadline - created).total_seconds() / 3600
            title_length = len(task.get("title", "").split())
            has_description = 1 if task.get("description", "").strip() else 0
            day_of_week = created.weekday()
            hour_of_day = created.hour
            is_weekend = int(day_of_week in [5, 6])
            time_of_day = "Morning" if hour_of_day < 12 else "Afternoon" if hour_of_day < 18 else "Evening"
            task_length = "Short" if title_length < 3 else "Medium" if title_length < 6 else "Long"
            urgency = "Urgent" if deadline_gap < 12 else "Soon" if deadline_gap < 24 else "Low"

            row = pd.DataFrame([{
                "user": user_id,
                "type": task["type"],
                "priority": task["priority"],
                "urgency": urgency,
                "taskLength": task_length,
                "titleLength": title_length,
                "hasDescription": has_description,
                "dayOfWeek": day_of_week,
                "hourOfDay": hour_of_day,
                "isWeekend": is_weekend,
                "timeOfDay": time_of_day,
                "actualTimeSpent": float(task.get("actualTimeSpent") or 0),
                "currentEnergyLevel": float(user.get("currentEnergyLevel", 5)),
                "currentMood": user.get("currentMood", "Neutral")
            }])

            for col in ["user", "type", "priority", "urgency", "taskLength", "timeOfDay", "currentMood"]:
                encode_column(row, col, encoders)

            row = row.astype({
                "titleLength": int,
                "hasDescription": int,
                "dayOfWeek": int,
                "hourOfDay": int,
                "isWeekend": int,
                "actualTimeSpent": float,
                "currentEnergyLevel": float
            })

            Xp = row[prod_model.feature_names_in_]
            Xd = row[distract_model.feature_names_in_]

            ps = float(round(prod_model.predict(Xp)[0], 2))
            ds = float(round(distract_model.predict(Xd)[0], 2))

            tasks.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {
                    "predictedProductivityScore": ps,
                    "predictedDistractionScore": ds
                }}
            )

            response_map[req_id].set_result({
                "productivity_score": ps,
                "distraction_score": ds
            })

        except Exception as e:
            traceback.print_exc()
            response_map[req_id].set_exception(HTTPException(status_code=500, detail=str(e)))
        finally:
            task_queue.task_done()

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(process_queue())

@app.post("/score")
async def score_task(req: ScoreRequest):
    req_id = id(req)
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future