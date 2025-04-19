# File: core/constants.py

# Mood scale mapping for correlation
MOOD_MAP = {
    "Tired": 1,
    "Stressed": 2,
    "Neutral": 3,
    "Happy": 4,
    "Motivated": 5
}

# Time of Day Labels
TIME_OF_DAY_LABELS = ["Morning", "Afternoon", "Evening"]

# Task Length Buckets
TASK_LENGTH_RULES = {
    "Short": lambda l: l < 3,
    "Medium": lambda l: 3 <= l < 6,
    "Long": lambda l: l >= 6
}

# Logging & Insight Labels
PRODUCTIVITY_TREND_EMOJI = {
    "positive": "📈 Improving",
    "negative": "📉 Declining",
    "neutral": "➖ Stable"
}

ENERGY_TREND_EMOJI = {
    "positive": "⬆️ Improving",
    "negative": "⬇️ Declining",
    "neutral": "➖ Stable"
}

DISTRACTION_SEVERITY = {
    "High": "🚨 High",
    "Moderate": "⚠️ Moderate",
    "Low": "✅ Low"
}

