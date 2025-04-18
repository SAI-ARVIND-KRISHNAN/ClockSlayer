from pydantic import BaseModel

class AnalyticsRequest(BaseModel):
    user_id: str
