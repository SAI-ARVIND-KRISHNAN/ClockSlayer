from pydantic import BaseModel

class ReminderRequest(BaseModel):
    user_id: str
