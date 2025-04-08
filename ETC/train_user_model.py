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
client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsAllowInvalidCertificates=True  # ✅ Dev only
)
db = client["test"]
tasks_collection = db["tasks"]

def generate_user_dummy_data(user_id):
    now = datetime.utcnow()
    dummy_tasks = [
        {
            "user": ObjectId(user_id),
            "type": "Work",
            "priority": "High",
            "completed": True,
            "actualTimeSpent": 90,
            "createdAt": now,
            "deadline": now + timedelta(hours=4)
        },
        {
            "user": ObjectId(user_id),
            "type": "Study",
            "priority": "Medium",
            "completed": True,
            "actualTimeSpent": 120,
            "createdAt": now - timedelta(hours=2),
            "deadline": now + timedelta(hours=6)
        },
        {
            "user": ObjectId(user_id),
            "type": "Personal",
            "priority": "Low",
            "completed": True,
            "actualTimeSpent": 60,
            "createdAt": now - timedelta(hours=1),
            "deadline": now + timedelta(hours=3)
        }
    ]

    tasks_collection.insert_many(dummy_tasks)
    print(f"✅ Dummy data created for user: {user_id}")

def train_user(user_id):
    user_obj_id = ObjectId(user_id)
    query = {
        "user": user_obj_id,
        "actualTimeSpent": {"$ne": None},
        "completed": True
    }

    tasks = list(tasks_collection.find(query))
    print(f"📊 Found {len(tasks)} tasks for user {user_id}")

    if len(tasks) < 3:
        print(f"❌ Not enough data to train for {user_id}.")
        return

    df = pd.DataFrame(tasks)
    df["user"] = df["user"].astype(str)  # Important: convert ObjectId to str
    df["createdAt"] = pd.to_datetime(df["createdAt"])
    df["deadline"] = pd.to_datetime(df["deadline"])
    df["deadline_gap"] = (df["deadline"] - df["createdAt"]).dt.total_seconds() / 3600

    label_encoders = {}
    for col in ["user", "type", "priority"]:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])
        label_encoders[col] = le

    X = df[["user", "type", "priority", "deadline_gap"]]
    y = df["actualTimeSpent"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = xgb.XGBRegressor(objective="reg:squarederror", n_estimators=100)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mse = mean_squared_error(y_test, preds)
    print(f"✅ Model trained for '{user_id}'. MSE: {mse:.2f}")

    os.makedirs("models", exist_ok=True)
    os.makedirs("encoders", exist_ok=True)
    joblib.dump(model, f"models/{user_id}_model.pkl")
    joblib.dump(label_encoders, f"encoders/{user_id}_encoders.pkl")
