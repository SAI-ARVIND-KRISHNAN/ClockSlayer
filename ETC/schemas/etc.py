# Filename: schemas/etc.py

from pydantic import BaseModel

class TaskRequest(BaseModel):
    user_id: str
    type: str
    priority: str = "Medium"
    deadline_gap: float
    dayOfWeek: int
    hourOfDay: int
    isWeekend: bool
    timeOfDay: str = "Afternoon"
    hasDescription: bool = True
    titleLength: int = 5
    urgency: str = "Soon"
    taskLength: str = "Medium"
    productivityScore: float = 50.0
    distractionScore: float = 50.0
