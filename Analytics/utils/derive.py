import numpy as np
import pandas as pd
from scipy.stats import linregress
from bson import ObjectId
from Analytics.config.db import tasks, logs


async def extract_insights(df: pd.DataFrame, user_id: str) -> dict:
    insights = {}

    try:
        insights["best_productivity_day"] = df.groupby("weekday")["productivityScore"].mean().idxmax()
    except:
        insights["best_productivity_day"] = None

    if "currentEnergyLevel" in df.columns:
        insights["energy_productivity_correlation"] = round(df["currentEnergyLevel"].corr(df["productivityScore"]) or 0, 2)

    if "currentMood" in df.columns:
        mood_map = {"Tired": 1, "Stressed": 2, "Neutral": 3, "Happy": 4, "Motivated": 5}
        df["moodScore"] = df["currentMood"].map(mood_map)
        insights["mood_productivity_correlation"] = round(df["moodScore"].corr(df["productivityScore"]) or 0, 2)

    try:
        insights["best_time_of_day"] = df.groupby("tod")["productivityScore"].mean().idxmax()
    except:
        insights["best_time_of_day"] = None

    insights["missed_deadline_count"] = len(df[df["completedAt"] > df["deadline"]])

    df_sorted = df.sort_values("completedAt")
    if len(df_sorted) > 1:
        x = (df_sorted["completedAt"] - df_sorted["completedAt"].min()).dt.days
        if x.nunique() > 1:
            slope, *_ = linregress(x, df_sorted["productivityScore"])
            insights["productivity_trend"] = "📈 Improving" if slope > 0 else "📉 Declining" if slope < 0 else "➖ Stable"
        else:
            insights["productivity_trend"] = "Not enough variation in task dates"

    insights["avg_time_spent"] = round(df["actualTimeSpent"].mean(), 2)
    active_days = df["completedAt"].dt.date.nunique()
    total_days = (df["completedAt"].max() - df["completedAt"].min()).days + 1
    insights["consistency_score"] = round((active_days / total_days) * 100, 2) if total_days > 0 else 0

    insights["productivity_by_type"] = df.groupby("type")["productivityScore"].mean().round(2).to_dict()

    distractions = df["distractionScore"].dropna()
    if len(distractions):
        avg_distr = distractions.mean()
        insights["avg_distraction_score"] = round(avg_distr, 2)
        insights["distraction_severity"] = "🚨 High" if avg_distr > 70 else "⚠️ Moderate" if avg_distr > 40 else "✅ Low"

    insights["most_common_task_type"] = df["type"].mode().values[0]
    insights["productivity_by_task_length"] = df.groupby("taskLength")["productivityScore"].mean().round(2).to_dict()
    insights["deadline_pressure_impact"] = round(df["deadlineGap"].corr(df["productivityScore"]) or 0, 2)
    insights["hourly_productivity"] = df.groupby("hour")["productivityScore"].mean().round(2).to_dict()

    weekend_prod = df.groupby("isWeekend")["productivityScore"].mean()
    insights["weekend_vs_weekday_productivity"] = {
        "Weekend": round(weekend_prod.get(True, 0), 2),
        "Weekday": round(weekend_prod.get(False, 0), 2)
    }

    insights["coach_feedback_entries"] = await logs.count_documents({"user": ObjectId(user_id), "type": "coachFeedback"})

    if "currentEnergyLevel" in df.columns:
        slope, *_ = linregress(np.arange(len(df)), df["currentEnergyLevel"])
        insights["energy_trend"] = "⬆️ Improving" if slope > 0 else "⬇️ Declining" if slope < 0 else "➖ Stable"

    insights["time_vs_productivity_corr"] = round(df["actualTimeSpent"].corr(df["productivityScore"]) or 0, 2)

    if "distractionScore" in df.columns:
        insights["least_distracting_type"] = df.groupby("type")["distractionScore"].mean().idxmin()

    insights["high_impact_hours"] = df.groupby("hour")["productivityScore"].mean().sort_values(ascending=False).head(3).index.tolist()
    insights["avg_title_length"] = round(df["titleLength"].mean(), 2)

    total_tasks = await tasks.count_documents({"user": ObjectId(user_id)})
    insights["completion_rate"] = round((len(df) / total_tasks) * 100, 2) if total_tasks else 0

    if "currentEnergyLevel" in df.columns:
        insights["energy_distribution"] = df["currentEnergyLevel"].value_counts().sort_index().to_dict()

    if "currentMood" in df.columns:
        insights["mood_distribution"] = df["currentMood"].value_counts().to_dict()
        insights["best_mood"] = df.groupby("currentMood")["productivityScore"].mean().idxmax()

    insights["most_common_time_block"] = df["tod"].mode().values[0]
    insights["productivity_variability"] = round(df["productivityScore"].std(), 2)
    top_task = df.loc[df["productivityScore"].idxmax()]
    insights["most_productive_task_title"] = top_task.get("title", "N/A")
    insights["least_productive_type"] = df.groupby("type")["productivityScore"].mean().idxmin()

    block_eff = df.groupby("tod")["efficiency"].mean()
    insights["most_efficient_time_block"] = block_eff.idxmax()

    for key, value in insights.items():
        if isinstance(value, (np.integer, np.int32, np.int64)):
            insights[key] = int(value)
        elif isinstance(value, (np.floating, np.float32, np.float64)):
            insights[key] = float(value)
        elif isinstance(value, np.bool_):
            insights[key] = bool(value)
        elif isinstance(value, np.ndarray):
            insights[key] = value.tolist()

    return insights