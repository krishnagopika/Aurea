from beanie import PydanticObjectId
from src.models.assessment import PropertyAssessment


async def save_assessment(assessment: PropertyAssessment) -> PropertyAssessment:
    await assessment.insert()
    return assessment


async def get_assessments_by_user(user_id: PydanticObjectId) -> list[PropertyAssessment]:
    return await PropertyAssessment.find(PropertyAssessment.user_id == user_id).to_list()
