# Filename: core/constants.py

# Suffixes for saved models
MODEL_SUFFIX = "_etc_model.pkl"
ENCODER_SUFFIX = "_etc_encoders.pkl"

# Features expected during model training & prediction
ETC_FEATURES = [
    "user",
    "type",
    "priority",
    "deadline_gap",
    "dayOfWeek",
    "hourOfDay",
    "isWeekend",
    "timeOfDay",
    "hasDescription",
    "titleLength",
    "urgency",
    "taskLength",
    "productivityScore",
    "distractionScore"
]

# Columns that need Label Encoding
CATEGORICAL_COLUMNS = [
    "user",
    "type",
    "priority",
    "urgency",
    "taskLength",
    "timeOfDay"
]

# Fallback defaults
DEFAULT_URGENCY = "Soon"
DEFAULT_TASKLENGTH = "Medium"
DEFAULT_TIMEDAY = "Afternoon"
DEFAULT_PRIORITY = "Medium"
DEFAULT_ENERGY = 5
DEFAULT_MOOD = "Neutral"
