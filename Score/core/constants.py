CATEGORICAL_COLUMNS = ["user", "type", "priority", "urgency", "taskLength", "timeOfDay", "currentMood"]
MODEL_FEATURES = [
    "user", "type", "priority", "urgency", "taskLength", "titleLength", "hasDescription",
    "dayOfWeek", "hourOfDay", "isWeekend", "timeOfDay", "actualTimeSpent",
    "currentEnergyLevel", "currentMood"
]

PRODUCTIVITY_SUFFIX = "_productivity.pkl"
DISTRACTION_SUFFIX = "_distraction.pkl"
ENCODER_SUFFIX = "_encoders.pkl"

DEFAULT_ENERGY = 5
DEFAULT_MOOD = "Neutral"
