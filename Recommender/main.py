from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import joblib
import os
import asyncio
import traceback
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
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

data_hash_map = {}
task_queue = asyncio.Queue()
response_map = {}

class RecommendationRequest(BaseModel):
    user_id: str

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
            encoded.append(le.transform([fallback_val])[0])
    df[col] = encoded

def compute_hash(task_list):
    data_string = ''.join([str(task.get("_id")) + str(task.get("updatedAt")) for task in task_list])
    return hashlib.md5(data_string.encode()).hexdigest()

def train_model_for_user(user_id):
    completed_tasks = list(tasks.find({
        "user": ObjectId(user_id),
        "completed": True,
        "productivityScore": {"$ne": None}
    }))

    if len(completed_tasks) == 0:
        print("⚠️ No completed tasks. Using dummy data.")
        completed_tasks = [{
            "user": user_id,
            "type": "Study", "priority": "High", "urgency": "Urgent", "taskLength": "Medium",
            "titleLength": 5, "hasDescription": 1, "dayOfWeek": 1, "hourOfDay": 10,
            "isWeekend": 0, "timeOfDay": "Morning", "currentEnergyLevel": 6,
            "currentMood": "Neutral", "productivityScore": 80
        } for _ in range(10)]

    else:
        data_hash_map[user_id] = compute_hash(completed_tasks)

    df = pd.DataFrame(completed_tasks)
    df["user"] = user_id
    df["titleLength"] = df["title"].apply(lambda x: len(x.split()) if isinstance(x, str) else 0)
    df["hasDescription"] = df["description"].apply(lambda x: 1 if x and x.strip() else 0)
    df["dayOfWeek"] = pd.to_datetime(df["createdAt"]).dt.weekday
    df["hourOfDay"] = pd.to_datetime(df["createdAt"]).dt.hour
    df["isWeekend"] = df["dayOfWeek"].isin([5, 6]).astype(int)
    df["timeOfDay"] = df["hourOfDay"].apply(
        lambda h: "Morning" if h < 12 else "Afternoon" if h < 18 else "Evening"
    )
    df["taskLength"] = df["titleLength"].apply(lambda l: "Short" if l < 3 else "Medium" if l < 6 else "Long")

    df["currentEnergyLevel"] = df.get("currentEnergyLevel", 5)
    df["currentMood"] = df.get("currentMood", "Neutral")

    features = [
        "user", "type", "priority", "taskLength", "titleLength", "hasDescription",
        "dayOfWeek", "hourOfDay", "isWeekend", "timeOfDay", "currentEnergyLevel", "currentMood"
    ]
    target = "productivityScore"

    # Ensure all required columns exist
    for col in features + [target]:
        if col not in df.columns:
            df[col] = 0

    df = df[features + [target]]

    cat_cols = ["user", "type", "priority", "taskLength", "timeOfDay", "currentMood"]
    encoders = {}
    for col in cat_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    X = df[features]
    y = df[target]

    model = RandomForestRegressor()
    model.fit(X, y)

    os.makedirs("recommender_models", exist_ok=True)
    joblib.dump(model, f"recommender_models/{user_id}_model.pkl")
    joblib.dump(encoders, f"recommender_models/{user_id}_encoders.pkl")
    print(f"✅ Recommender model trained for user {user_id}.")

def load_model_and_encoders(user_id):
    model_path = f"recommender_models/{user_id}_model.pkl"
    encoder_path = f"recommender_models/{user_id}_encoders.pkl"

    if not os.path.exists(model_path) or not os.path.exists(encoder_path):
        print("🔁 Model missing or outdated. Retraining...")
        train_model_for_user(user_id)

    model = joblib.load(model_path)
    encoders = joblib.load(encoder_path)
    return model, encoders

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        try:
            user_id = req_data.user_id
            user_obj = users.find_one({"_id": ObjectId(user_id)})
            if not user_obj:
                raise HTTPException(status_code=404, detail="User not found.")

            pending_tasks = list(tasks.find({
                "user": ObjectId(user_id),
                "completed": False
            }))

            if not pending_tasks:
                response_map[req_id].set_result({"recommendation": None})
                task_queue.task_done()
                continue

            model, encoders = load_model_and_encoders(user_id)

            predictions = []
            for task in pending_tasks:
                created = task.get("createdAt", datetime.utcnow())
                title_length = len(task.get("title", "").split())
                has_description = 1 if task.get("description", "").strip() else 0
                day_of_week = created.weekday()
                hour_of_day = created.hour
                is_weekend = int(day_of_week in [5, 6])
                time_of_day = "Morning" if hour_of_day < 12 else "Afternoon" if hour_of_day < 18 else "Evening"
                task_length = "Short" if title_length < 3 else "Medium" if title_length < 6 else "Long"

                row = pd.DataFrame([{
                    "user": user_id,
                    "type": task["type"],
                    "priority": task["priority"],
                    "taskLength": task_length,
                    "titleLength": title_length,
                    "hasDescription": has_description,
                    "dayOfWeek": day_of_week,
                    "hourOfDay": hour_of_day,
                    "isWeekend": is_weekend,
                    "timeOfDay": time_of_day,
                    "currentEnergyLevel": float(user_obj.get("currentEnergyLevel", 5)),
                    "currentMood": user_obj.get("currentMood", "Neutral")
                }])

                for col in ["user", "type", "priority", "taskLength", "timeOfDay", "currentMood"]:
                    encode_column(row, col, encoders)

                row = row.astype({
                    "titleLength": int,
                    "hasDescription": int,
                    "dayOfWeek": int,
                    "hourOfDay": int,
                    "isWeekend": int,
                    "currentEnergyLevel": float
                })

                score = model.predict(row)[0]
                predictions.append((task["_id"], score))

            best_task = max(predictions, key=lambda x: x[1])[0]
            response_map[req_id].set_result({"recommended_task_id": str(best_task)})

        except Exception as e:
            traceback.print_exc()
            response_map[req_id].set_exception(HTTPException(status_code=500, detail=str(e)))
        finally:
            task_queue.task_done()

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(process_queue())

@app.post("/recommend")
async def recommend(req: RecommendationRequest):
    req_id = id(req)
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
