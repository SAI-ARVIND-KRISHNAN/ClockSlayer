from pydantic import BaseModel, Field

class RecommendationRequest(BaseModel):
    user_id: str = Field(..., description="The unique ID of the user to generate task recommendation for.")
