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
from sklearn.metrics import mean_squared_error

app = FastAPI()

# MongoDB setup
client = MongoClient("mongodb+srv://vercettitommy018:M0qLrkDnJnemBbta@cluster0.xxart2t.mongodb.net/", tls=True, tlsAllowInvalidCertificates=True)
db = client["test"]
users = db["users"]
tasks = db["tasks"]

task_queue = asyncio.Queue()
response_map = {}

class TaskRequest(BaseModel):
    user_id: str
    type: str
    priority: str = "Medium"
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

# Function to generate dummy tasks in case of insufficient data
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
            "deadline_gap": 4,
            "urgency": "Urgent"
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
            "deadline_gap": 8,
            "urgency": "Soon"
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
            "deadline_gap": 10,
            "urgency": "Low"
        }
    ]

# Function to save training count metadata
def save_training_count(user_id, count):
    os.makedirs("training_meta", exist_ok=True)
    with open(f"training_meta/{user_id}_count.txt", "w") as f:
        f.write(str(count))

# Function to load previous training count
def load_training_count(user_id):
    try:
        with open(f"training_meta/{user_id}_count.txt") as f:
            return int(f.read())
    except FileNotFoundError:
        return 0

# Function to train the model for a user
def train_user(user_id: str):
    now = datetime.utcnow()
    user_obj_id = ObjectId(user_id)

    # Fetch user from DB
    user = db["users"].find_one({"_id": user_obj_id})
    if not user:
        print(f"❌ User {user_id} not found.")
        return False

    tasks_data = list(tasks.find({
        "user": user_obj_id,
        "completed": True,
        "actualTimeSpent": {"$ne": None}
    }))

    # If not enough data, use dummy data
    if len(tasks_data) < 3:
        print(f"⚠️ Not enough data for {user_id}, using dummy data.")
        tasks_data.extend(generate_dummy_tasks(user_id, now))

    # Create DataFrame from task data
    df = pd.DataFrame(tasks_data)
    df["user"] = user_id  # Ensure consistent string ID

    # Convert 'createdAt' and 'deadline' from datetime to numeric (hours difference)
    df["createdAt"] = pd.to_datetime(df["createdAt"], errors='coerce')
    df["deadline"] = pd.to_datetime(df["deadline"], errors='coerce')

    df["createdAt"] = df["createdAt"].fillna(now)
    df["deadline"] = df["deadline"].fillna(now)

    df["deadline_gap"] = (df["deadline"] - df["createdAt"]).dt.total_seconds() / 3600  # In hours


    df["hasDescription"] = df.get("hasDescription", 0)
    df["titleLength"] = df.get("titleLength", 5)
    df["taskLength"] = df.get("taskLength", "Medium")
    df["dayOfWeek"] = df.get("dayOfWeek", now.weekday())
    df["hourOfDay"] = df.get("hourOfDay", now.hour)
    df["isWeekend"] = df.get("isWeekend", 0)
    df["timeOfDay"] = df.get("timeOfDay", "Afternoon")

    # Ensure 'urgency' column exists and handle missing values
    if "urgency" not in df.columns:
        df["urgency"] = "Soon"  # Assign default value if not present

    # Convert 'urgency' to categorical and include all potential categories
    df["urgency"] = pd.Categorical(df["urgency"], categories=["Urgent", "Soon", "Low"])

    # Label encoding for categorical features
    label_encoders = {}
    for col in ["user", "type", "priority", "urgency", "taskLength", "timeOfDay"]:
        le = LabelEncoder()

        if col == "urgency":
            possible_classes = ["Urgent", "Soon", "Low"]
            le = LabelEncoder()
            le.fit(possible_classes)
            df[col] = df[col].apply(lambda x: x if x in possible_classes else "Soon")
            df[col] = le.transform(df[col])
        else:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col])

        df[col] = le.fit_transform(df[col])  # Apply encoding to the column
        label_encoders[col] = le  # Save encoder for later use

    # Features and target variable
    features = [
        "user", "type", "priority", "deadline_gap", "dayOfWeek", "hourOfDay",
        "isWeekend", "timeOfDay", "hasDescription", "titleLength",
        "urgency", "taskLength", "productivityScore"
    ]

    # Ensure all required columns exist in the data
    for feature in features:
        if feature not in df.columns:
            df[feature] = 0  # Fill missing columns with default value

    X = df[features].astype(float)
    y = df["actualTimeSpent"].astype(float)

    # Train model
    model = xgb.XGBRegressor(objective="reg:squarederror", n_estimators=100)
    model.fit(X, y)

    # Save model and encoders
    os.makedirs("models", exist_ok=True)
    os.makedirs("encoders", exist_ok=True)
    joblib.dump(model, f"models/{user_id}_model.pkl")
    joblib.dump(label_encoders, f"encoders/{user_id}_encoders.pkl")

    save_training_count(user_id, len(tasks_data))

    print(f"✅ Model trained for user {user_id} — MSE: {mean_squared_error(y, model.predict(X)):.2f}")
    return True


# Function to handle unseen labels in encoding
def encode_column(df, col, encoder):
    if col not in df.columns or col not in encoder:
        return

    le = encoder[col]
    encoded = []
    for val in df[col]:
        # Ensure we handle unseen labels
        if val in le.classes_:
            encoded.append(le.transform([val])[0])
        else:
            # Handle unseen labels by using a fallback value
            fallback_val = le.classes_[0]  # Default to the first class
            encoded.append(le.transform([fallback_val])[0])
    df[col] = encoded


# Function to load models and encoders
def load_model_and_encoders(user_id: str):
    model_path = f"models/{user_id}_model.pkl"
    encoder_path = f"encoders/{user_id}_encoders.pkl"

    # Ensure model and encoder paths exist
    if not os.path.exists(model_path) or not os.path.exists(encoder_path):
        print(f"⚠️ Model or encoders missing for user {user_id}, retraining...")
        success = train_user(user_id)  # Capture return value
        if not success:
            raise HTTPException(
                status_code=422,
                detail=f"Not enough task data to train ETC model for user {user_id}."
            )

    # After training, add the missing categories (if new ones exist)
    if os.path.exists(encoder_path):
        encoders = joblib.load(encoder_path)
        if "urgency" in encoders:
            encoders["urgency"] = LabelEncoder()  # Update the urgency encoder

    if not os.path.exists(model_path) or not os.path.exists(encoder_path):
        raise HTTPException(status_code=500, detail=f"Missing trained model or encoder for user {user_id}.")

    model = joblib.load(model_path)
    encoders = joblib.load(encoder_path)
    return model, encoders


# Function to process the request queue and predict ETC
async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        try:
            model, encoders = load_model_and_encoders(req_data.user_id)

            # Build the feature row
            feature_data = {
                "user": req_data.user_id,
                "type": req_data.type,
                "priority": req_data.priority,
                "urgency": req_data.urgency,
                "taskLength": req_data.taskLength,
                "timeOfDay": req_data.timeOfDay,
                "dayOfWeek": req_data.dayOfWeek,
                "hourOfDay": req_data.hourOfDay,
                "isWeekend": req_data.isWeekend,
                "hasDescription": int(req_data.hasDescription),
                "titleLength": req_data.titleLength,
                "productivityScore": req_data.productivityScore,
                "deadline_gap": req_data.deadline_gap
            }

            # Encoding categorical data
            for col in ["user", "type", "priority", "urgency", "taskLength", "timeOfDay"]:
                try:
                    feature_data[col] = encoders[col].transform([feature_data[col]])[0]
                except ValueError:
                    # Fallback to first class (e.g., most common/default)
                    print(f"[⚠️ Warning] Unseen label '{feature_data[col]}' for {col}, using fallback.")
                    feature_data[col] = encoders[col].transform([encoders[col].classes_[0]])[0]

            # Create a DataFrame
            feature_df = pd.DataFrame([feature_data])

            # Reorder the columns to match training
            ordered_columns = [
                "user", "type", "priority", "deadline_gap", "dayOfWeek", "hourOfDay",
                "isWeekend", "timeOfDay", "hasDescription", "titleLength",
                "urgency", "taskLength", "productivityScore"
            ]
            feature_df = feature_df[ordered_columns]

            def format_time(minutes: float) -> str:
                minutes = int(round(minutes))
                if minutes <= 0:
                    return "less than a minute"
                hours, mins = divmod(minutes, 60)
                parts = []
                if hours:
                    parts.append(f"{hours} hr{'s' if hours != 1 else ''}")
                if mins:
                    parts.append(f"{mins} min{'s' if mins != 1 else ''}")
                return " ".join(parts)

            # Predict ETC (Estimated Time of Completion)
            etc_minutes = float(model.predict(feature_df)[0])
            formatted_etc = format_time(etc_minutes)

            response_map[req_id].set_result({
                "Estimated Time of Completion (in minutes)": etc_minutes,
                "Formatted ETC": formatted_etc
            })

            # Optionally, retrain the model with new data
            train_user(req_data.user_id)

        except Exception as e:
            traceback.print_exc()
            response_map[req_id].set_exception(HTTPException(status_code=500, detail=str(e)))

        task_queue.task_done()



@app.on_event("startup")
async def start_worker():
    asyncio.create_task(process_queue())

@app.post("/predict")
async def predict_etc(req: TaskRequest):
    req_id = id(req)
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
