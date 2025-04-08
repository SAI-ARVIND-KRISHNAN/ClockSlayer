from fastapi import FastAPI, HTTPException, Request
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

# MongoDB Setup
MONGO_URI = "mongodb+srv://vercettitommy018:M0qLrkDnJnemBbta@cluster0.xxart2t.mongodb.net/"
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["test"]
tasks_collection = db["tasks"]

# Queue for sequential processing
task_queue = asyncio.Queue()
response_map = {}

# Schema
class TaskRequest(BaseModel):
    user_id: str
    type: str
    priority: Optional[str] = "Medium"
    deadline: str
    createdAt: str

# Format ETC
def format_time(minutes):
    if minutes < 60:
        return f"{int(minutes)} minute{'s' if int(minutes) != 1 else ''}"
    days = int(minutes // (24 * 60))
    hours = int((minutes % (24 * 60)) // 60)
    parts = []
    if days: parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    return ", ".join(parts)

# Load model/encoder or train if missing
def load_model_and_encoders(user_id):
    model_path = f"models/{user_id}_model.pkl"
    encoder_path = f"encoders/{user_id}_encoders.pkl"

    if not os.path.exists(model_path) or not os.path.exists(encoder_path):
        print(f"⚠️ No model/encoder for user '{user_id}', attempting to train...")

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

    return joblib.load(model_path), joblib.load(encoder_path)

# Async prediction task handler
async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        try:
            created = pd.to_datetime(req_data.createdAt)
            deadline = pd.to_datetime(req_data.deadline)
            deadline_gap = (deadline - created).total_seconds() / 3600

            model, encoders = load_model_and_encoders(req_data.user_id)
            model_features = model.feature_names_in_.tolist()

            type_val = req_data.type.capitalize()
            priority_val = (req_data.priority or "Medium").capitalize()

            encoded = {}
            if "user" in model_features:
                encoded["user"] = encoders["user"].transform([req_data.user_id])[0]
            if "type" in model_features:
                encoded["type"] = encoders["type"].transform([type_val])[0]
            if "priority" in model_features:
                encoded["priority"] = encoders["priority"].transform([priority_val])[0]

            encoded["deadline_gap"] = deadline_gap

            row = [encoded[feat] for feat in model_features]
            df = pd.DataFrame([row], columns=model_features)

            prediction = model.predict(df)[0]
            etc_minutes = round(float(prediction), 2)
            formatted = format_time(etc_minutes)

            response_map[req_id].set_result({
                "Estimated Time of Completion (in minutes)": etc_minutes,
                "Formatted ETC": formatted
            })

        except Exception as e:
            traceback.print_exc()
            response_map[req_id].set_exception(HTTPException(status_code=500, detail=str(e)))

        task_queue.task_done()

# Start queue worker in background
@app.on_event("startup")
async def start_queue_worker():
    asyncio.create_task(process_queue())

# Endpoint to enqueue prediction
@app.post("/predict")
async def predict_etc(req: TaskRequest):
    req_id = id(req)
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
