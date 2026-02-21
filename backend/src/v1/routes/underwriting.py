from fastapi import APIRouter, Depends, Body
from typing import List

from src.schemas.underwriting import AssessmentRequest, AssessmentResponse
from src.services.underwriting_service import run_assessment, get_assessment_history
from src.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/underwriting", tags=["underwriting"])


@router.post("/assess", response_model=AssessmentResponse)
async def assess(
    req: AssessmentRequest = Body(
        openapi_examples={
            "low_risk_accept": {
                "summary": "Low risk — ACCEPT (modern property, Flood Zone 1)",
                "value": {
                    "address": "42 Victoria Road, Manchester",
                    "postcode": "M14 5TL",
                },
            },
            "medium_risk_refer": {
                "summary": "Medium risk — REFER (Flood Zone 2, older property)",
                "value": {
                    "address": "10 Downing Street, London",
                    "postcode": "SW1A 2AA",
                },
            },
            "high_risk_decline": {
                "summary": "High risk — DECLINE (Flood Zone 3, pre-1900)",
                "value": {
                    "address": "1 Flooding Lane, York",
                    "postcode": "YO1 9HH",
                },
            },
        }
    ),
    user_id: str = Depends(get_current_user),
):
    return await run_assessment(req.address, req.postcode, user_id)


@router.get("/history", response_model=List[AssessmentResponse])
async def history(user_id: str = Depends(get_current_user)):
    return await get_assessment_history(user_id)
