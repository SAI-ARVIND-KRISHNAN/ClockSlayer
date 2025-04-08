from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
import os
import traceback
import asyncio
from train_user_model import train_user, generate_user_dummy_data
from pymongo import MongoClient
from bson import ObjectId
from typing import Optional

app = FastAPI()

MONGO_URI = "mongodb+srv://vercettitommy018:M0qLrkDnJnemBbta@cluster0.xxart2t.mongodb.net/"
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["test"]
tasks_collection = db["tasks"]

task_queue = asyncio.Queue()
response_map = {}

class TaskRequest(BaseModel):
    user_id: str
    type: str
    priority: Optional[str] = "Medium"
    deadline_gap: float
    dayOfWeek: int
    hourOfDay: int
    isWeekend: bool
    timeOfDay: str
    hasDescription: bool
    titleLength: int
    urgency: str
    taskLength: str
    productivityScore: int

def format_time(minutes):
    if minutes < 60:
        return f"{int(minutes)} minute{'s' if int(minutes) != 1 else ''}"
    days = int(minutes // (24 * 60))
    hours = int((minutes % (24 * 60)) // 60)
    parts = []
    if days: parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    return ", ".join(parts)

def load_model_and_encoders(user_id):
    model_path = f"models/{user_id}_model.pkl"
    encoder_path = f"encoders/{user_id}_encoders.pkl"

    if not os.path.exists(model_path) or not os.path.exists(encoder_path):
        print(f"⚠️ No model for user '{user_id}', generating...")
        existing_tasks = list(tasks_collection.find({
            "user": ObjectId(user_id),
            "completed": True,
            "actualTimeSpent": {"$ne": None}
        }))
        if len(existing_tasks) < 3:
            generate_user_dummy_data(user_id)
        train_user(user_id)

    if not os.path.exists(model_path) or not os.path.exists(encoder_path):
        raise HTTPException(status_code=500, detail=f"Still missing model/encoder for {user_id}.")

    model = joblib.load(model_path)
    encoders = joblib.load(encoder_path)
    return model, encoders

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        try:
            model, encoders = load_model_and_encoders(req_data.user_id)
            model_features = model.feature_names_in_.tolist()

            encoded = {}

            for feat in ["user", "type", "priority", "urgency", "timeOfDay", "taskLength"]:
                if feat in model_features:
                    value = req_data.user_id if feat == "user" else getattr(req_data, feat)
                    if value in encoders[feat].classes_:
                        encoded[feat] = encoders[feat].transform([value])[0]
                    else:
                        encoded[feat] = encoders[feat].transform([encoders[feat].classes_[0]])[0]

            for feat in ["deadline_gap", "dayOfWeek", "hourOfDay", "productivityScore", "titleLength"]:
                if feat in model_features:
                    encoded[feat] = getattr(req_data, feat)

            if "isWeekend" in model_features:
                encoded["isWeekend"] = int(req_data.isWeekend)
            if "hasDescription" in model_features:
                encoded["hasDescription"] = int(req_data.hasDescription)

            df = pd.DataFrame([[encoded[feat] for feat in model_features]], columns=model_features)

            prediction = model.predict(df)[0]
            etc_minutes = round(float(prediction), 2)
            formatted = format_time(etc_minutes)

            response_map[req_id].set_result({
                "Estimated Time of Completion (in minutes)": etc_minutes,
                "Formatted ETC": formatted
            })

            # ✅ Retrain after prediction (only if new data exists)
            train_user(req_data.user_id)

        except Exception as e:
            traceback.print_exc()
            response_map[req_id].set_exception(HTTPException(status_code=500, detail=str(e)))

        task_queue.task_done()

@app.on_event("startup")
async def start_queue_worker():
    asyncio.create_task(process_queue())

@app.post("/predict")
async def predict_etc(req: TaskRequest):
    req_id = id(req)
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
