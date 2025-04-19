import pandas as pd
import numpy as np

def prepare_dataframe(tasks: list) -> pd.DataFrame:
    df = pd.DataFrame(tasks)

    # Timestamps
    df["completedAt"] = pd.to_datetime(df["completedAt"], errors="coerce")
    df["createdAt"] = pd.to_datetime(df["createdAt"], errors="coerce")
    df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce")

    # Title features
    df["titleLength"] = df["title"].apply(lambda x: len(x.split()) if isinstance(x, str) else 0)
    df["taskLength"] = df["titleLength"].apply(
        lambda l: "Short" if l < 3 else "Medium" if l < 6 else "Long")

    # Time-of-day features
    df["hour"] = df["completedAt"].dt.hour
    df["tod"] = df["hour"].apply(
        lambda h: "Morning" if h < 12 else "Afternoon" if h < 18 else "Evening")

    # Day-of-week
    df["weekday"] = df["completedAt"].dt.weekday
    df["isWeekend"] = df["weekday"].isin([5, 6])

    # Deadline pressure
    df["deadlineGap"] = (df["deadline"] - df["createdAt"]).dt.total_seconds() / 3600

    # Efficiency metric
    df["efficiency"] = df["productivityScore"] / df["actualTimeSpent"].replace(0, np.nan)

    return df
