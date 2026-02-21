from beanie import Document, PydanticObjectId
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone


class RiskFactor(BaseModel):
    name: str
    score: float
    weight: float
    reasoning: str


class PropertyAssessment(Document):
    user_id: PydanticObjectId
    address: str
    postcode: str
    decision: str
    overall_risk_score: float
    premium_multiplier: float
    flood_risk_score: float
    planning_risk_score: float
    property_age_risk_score: float
    locality_safety_score: float = 25.0
    risk_factors: List[RiskFactor] = []
    plain_english_narrative: str = ""
    data_warnings: List[str] = []
    created_at: datetime = datetime.now(timezone.utc)

    class Settings:
        name = "property_assessments"
