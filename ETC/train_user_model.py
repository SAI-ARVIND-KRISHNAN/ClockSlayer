import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error
import joblib
import os
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId

MONGO_URI = "mongodb+srv://vercettitommy018:M0qLrkDnJnemBbta@cluster0.xxart2t.mongodb.net/"
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["test"]
tasks_collection = db["tasks"]

def generate_user_dummy_data(user_id):
    now = datetime.utcnow()
    dummy_tasks = [
        {
            "user": ObjectId(user_id),
            "type": "Work",
            "priority": "High",
            "urgency": "Urgent",
            "timeOfDay": "Morning",
            "taskLength": "Short",
            "productivityScore": 60,
            "completed": True,
            "actualTimeSpent": 90,
            "title": "Finish report",
            "description": "Prepare the final draft",
            "createdAt": now,
            "deadline": now + timedelta(hours=4)
        },
        {
            "user": ObjectId(user_id),
            "type": "Study",
            "priority": "Medium",
            "urgency": "Soon",
            "timeOfDay": "Afternoon",
            "taskLength": "Medium",
            "productivityScore": 70,
            "completed": True,
            "actualTimeSpent": 120,
            "title": "Revise ML notes",
            "description": "",
            "createdAt": now - timedelta(hours=2),
            "deadline": now + timedelta(hours=6)
        },
        {
            "user": ObjectId(user_id),
            "type": "Personal",
            "priority": "Low",
            "urgency": "Low",
            "timeOfDay": "Evening",
            "taskLength": "Long",
            "productivityScore": 50,
            "completed": True,
            "actualTimeSpent": 60,
            "title": "Grocery shopping and cleaning",
            "description": "Buy essentials and clean the house",
            "createdAt": now - timedelta(hours=1),
            "deadline": now + timedelta(hours=3)
        }
    ]
    tasks_collection.insert_many(dummy_tasks)
    print(f"✅ Dummy data created for user: {user_id}")

# Helpers for training metadata
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

def train_user(user_id):
    user_obj_id = ObjectId(user_id)
    tasks = list(tasks_collection.find({
        "user": user_obj_id,
        "completed": True,
        "actualTimeSpent": {"$ne": None}
    }))

    current_count = len(tasks)

    if current_count < 3:
        print(f"❌ Not enough data to train for {user_id}")
        return

    prev_count = load_training_count(user_id)
    if current_count <= prev_count:
        print(f"⏭️ No new data for user {user_id}, skipping retraining.")
        return

    user = db["users"].find_one({"_id": user_obj_id})
    productivity_score = user.get("productivityScore", 50)

    for task in tasks:
        task["productivityScore"] = productivity_score

    df = pd.DataFrame(tasks)
    df["user"] = df["user"].astype(str)
    df["createdAt"] = pd.to_datetime(df["createdAt"])
    df["deadline"] = pd.to_datetime(df["deadline"])
    df["deadline_gap"] = (df["deadline"] - df["createdAt"]).dt.total_seconds() / 3600

    if "description" not in df.columns:
        df["description"] = ""
    if "title" not in df.columns:
        df["title"] = ""

    df["hasDescription"] = df["description"].apply(lambda d: 1 if str(d).strip() else 0)
    df["titleLength"] = df["title"].apply(lambda t: len(str(t).strip().split()))
    df["taskLength"] = df["titleLength"].apply(lambda l: "Short" if l < 3 else "Medium" if l < 6 else "Long")
    df["dayOfWeek"] = df["createdAt"].dt.dayofweek
    df["hourOfDay"] = df["createdAt"].dt.hour
    df["isWeekend"] = df["dayOfWeek"].isin([5, 6]).astype(int)
    df["timeOfDay"] = df["hourOfDay"].apply(lambda h: "Morning" if h < 12 else "Afternoon" if h < 18 else "Evening")

    df["timeToDeadline"] = (df["deadline"] - datetime.utcnow()).dt.total_seconds() / 3600

    df["urgency"] = df["timeToDeadline"].apply(
        lambda x: "Urgent" if x < 12 else "Soon" if x < 24 else "Low"
    )
    urgency_levels = ["Urgent", "Soon", "Low"]
    df["urgency"] = pd.Categorical(df["urgency"], categories=urgency_levels)

    label_encoders = {}
    for col in ["user", "type", "priority", "urgency", "taskLength", "timeOfDay"]:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])
        label_encoders[col] = le

    features = [
        "user", "type", "priority", "deadline_gap", "dayOfWeek", "hourOfDay",
        "isWeekend", "timeOfDay", "hasDescription", "titleLength",
        "urgency", "taskLength", "productivityScore"
    ]
    X = df[features]
    y = df["actualTimeSpent"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = xgb.XGBRegressor(objective="reg:squarederror", n_estimators=100)
    model.fit(X_train, y_train)

    os.makedirs("models", exist_ok=True)
    os.makedirs("encoders", exist_ok=True)
    joblib.dump(model, f"models/{user_id}_model.pkl")
    joblib.dump(label_encoders, f"encoders/{user_id}_encoders.pkl")
    save_training_count(user_id, current_count)

    preds = model.predict(X_test)
    mse = mean_squared_error(y_test, preds)
    print(f"✅ Model trained for user {user_id} — MSE: {mse:.2f}")
