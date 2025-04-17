# Suffixes for saved models
MODEL_SUFFIX = "_recommender_model.pkl"
ENCODER_SUFFIX = "_recommender_encoders.pkl"

# Features used during model training & prediction
RECOMMENDER_FEATURES = [
    "user",
    "type",
    "priority",
    "taskLength",
    "titleLength",
    "hasDescription",
    "dayOfWeek",
    "hourOfDay",
    "isWeekend",
    "timeOfDay",
    "currentEnergyLevel",
    "currentMood"
]

# Columns that require Label Encoding
CATEGORICAL_COLUMNS = [
    "user",
    "type",
    "priority",
    "taskLength",
    "timeOfDay",
    "currentMood"
]

# Default fallbacks (if needed)
DEFAULT_ENERGY = 5
DEFAULT_MOOD = "Neutral"
DEFAULT_TASKLENGTH = "Medium"
DEFAULT_TIMEDAY = "Afternoon"
DEFAULT_PRIORITY = "Medium"
