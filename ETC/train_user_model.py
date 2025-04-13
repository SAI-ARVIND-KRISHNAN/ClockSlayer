import os
import joblib
import pandas as pd
import xgboost as xgb
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error
from pymongo import MongoClient
from bson import ObjectId

MONGO_URI = "mongodb+srv://vercettitommy018:M0qLrkDnJnemBbta@cluster0.xxart2t.mongodb.net/"
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["test"]
tasks_collection = db["tasks"]
users_collection = db["users"]

def save_training_count(user_id, count):
    os.makedirs("training_meta", exist_ok=True)
    with open(f"training_meta/{user_id}_count.txt", "w") as f:
        f.write(str(count))

def load_training_count(user_id):
    try:
        with open(f"training_meta/{user_id}_count.txt") as f:
            return int(f.read())
    except FileNotFoundError:
        return 0

def generate_dummy_tasks(user_id, now):
    return [
        {
            "user": user_id,
            "type": "Work",
            "priority": "High",
            "urgency": "Urgent",
            "timeOfDay": "Morning",
            "taskLength": "Short",
            "titleLength": 3,
            "hasDescription": 1,
            "dayOfWeek": now.weekday(),
            "hourOfDay": 9,
            "isWeekend": 0,
            "actualTimeSpent": 45,
            "productivityScore": 60,
            "distractionScore": 30,
            "deadline_gap": 4
        },
        {
            "user": user_id,
            "type": "Study",
            "priority": "Medium",
            "urgency": "Soon",
            "timeOfDay": "Afternoon",
            "taskLength": "Medium",
            "titleLength": 5,
            "hasDescription": 1,
            "dayOfWeek": now.weekday(),
            "hourOfDay": 14,
            "isWeekend": 0,
            "actualTimeSpent": 90,
            "productivityScore": 70,
            "distractionScore": 40,
            "deadline_gap": 8
        },
        {
            "user": user_id,
            "type": "Personal",
            "priority": "Low",
            "urgency": "Low",
            "timeOfDay": "Evening",
            "taskLength": "Long",
            "titleLength": 7,
            "hasDescription": 0,
            "dayOfWeek": now.weekday(),
            "hourOfDay": 20,
            "isWeekend": 1,
            "actualTimeSpent": 60,
            "productivityScore": 50,
            "distractionScore": 60,
            "deadline_gap": 12
        }
    ]

def train_user(user_id):
    user_obj_id = ObjectId(user_id)
    now = datetime.utcnow()

    tasks = list(tasks_collection.find({
        "user": user_obj_id,
        "completed": True,
        "actualTimeSpent": {"$ne": None}
    }))

    if len(tasks) < 3:
        print(f"⚠️ Not enough data for {user_id}, using dummy data.")
        tasks.extend(generate_dummy_tasks(user_id, now))

    current_count = len(tasks)
    model_path = f"models/{user_id}_model.pkl"
    encoder_path = f"encoders/{user_id}_encoders.pkl"
    prev_count = load_training_count(user_id)

    if current_count <= prev_count and os.path.exists(model_path) and os.path.exists(encoder_path):
        print(f"⏭️ No new data and model already exists for {user_id}, skipping retrain.")
        return True

    user = users_collection.find_one({"_id": user_obj_id})
    if not user:
        print(f"❌ User {user_id} not found.")
        return False

    default_productivity = user.get("baselineProductivityScore", 50)
    default_distraction = user.get("baselineDistractionScore", 50)

    for task in tasks:
        task["productivityScore"] = task.get("productivityScore", default_productivity)
        task["distractionScore"] = task.get("distractionScore", default_distraction)

    df = pd.DataFrame(tasks)
    df["user"] = user_id
    df["deadline_gap"] = df.get("deadline_gap", 4)
    df["hasDescription"] = df.get("hasDescription", 0)
    df["titleLength"] = df.get("titleLength", 5)
    df["taskLength"] = df.get("taskLength", "Medium")
    df["dayOfWeek"] = df.get("dayOfWeek", now.weekday())
    df["hourOfDay"] = df.get("hourOfDay", now.hour)
    df["isWeekend"] = df.get("isWeekend", 0)
    df["timeOfDay"] = df.get("timeOfDay", "Afternoon")
    df["urgency"] = pd.Categorical(df.get("urgency", "Soon"), categories=["Urgent", "Soon", "Low"])

    # Label encoding
    label_encoders = {}
    for col in ["user", "type", "priority", "urgency", "taskLength", "timeOfDay"]:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])
        label_encoders[col] = le

    # Train the ETC model with productivityScore and distractionScore as input features
    features = [
        "user", "type", "priority", "deadline_gap", "dayOfWeek", "hourOfDay",
        "isWeekend", "timeOfDay", "hasDescription", "titleLength",
        "urgency", "taskLength", "productivityScore", "distractionScore"
    ]

    X = df[features].astype(float)
    y = df["actualTimeSpent"].astype(float)

    model = xgb.XGBRegressor(objective="reg:squarederror", n_estimators=100)
    model.fit(X, y)

    os.makedirs("models", exist_ok=True)
    os.makedirs("encoders", exist_ok=True)
    joblib.dump(model, model_path)
    joblib.dump(label_encoders, encoder_path)
    save_training_count(user_id, current_count)

    print(f"✅ Model trained for user {user_id} — MSE: {mean_squared_error(y, model.predict(X)):.2f}")
    return True
