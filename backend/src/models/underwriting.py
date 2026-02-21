from beanie import Document, PydanticObjectId
from datetime import datetime, timezone


class UnderwritingResult(Document):
    assessment_id: PydanticObjectId
    underwriter_reasoning: str = ""
    policy_citations: list[str] = []
    created_at: datetime = datetime.now(timezone.utc)

    class Settings:
        name = "underwriting_results"
