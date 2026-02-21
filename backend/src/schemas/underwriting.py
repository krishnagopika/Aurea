from pydantic import BaseModel
from typing import List, Any


class AssessmentRequest(BaseModel):
    address: str
    postcode: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "address": "10 Downing Street, London",
                    "postcode": "SW1A 2AA",
                },
                {
                    "address": "1 Flooding Lane, York",
                    "postcode": "YO1 9HH",
                },
                {
                    "address": "42 Victoria Road, Manchester",
                    "postcode": "M14 5TL",
                },
            ]
        }
    }


class RiskFactorSchema(BaseModel):
    name: str
    score: float
    weight: float
    reasoning: str


class AssessmentResponse(BaseModel):
    assessment_id: str
    decision: str
    overall_risk_score: float
    premium_multiplier: float
    flood_risk_score: float
    planning_risk_score: float
    property_age_risk_score: float
    locality_safety_score: float = 25.0
    risk_factors: List[Any] = []
    plain_english_narrative: str = ""
    data_warnings: List[str] = []

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "assessment_id": "6657a1b2c3d4e5f678901234",
                    "decision": "refer",
                    "overall_risk_score": 62.5,
                    "premium_multiplier": 1.75,
                    "flood_risk_score": 45.0,
                    "planning_risk_score": 30.0,
                    "property_age_risk_score": 65.0,
                    "risk_factors": [
                        {
                            "name": "Flood Risk",
                            "score": 45.0,
                            "weight": 0.45,
                            "reasoning": "Flood Zone 2 — medium probability of flooding, elevated premium applies.",
                        },
                        {
                            "name": "Property Age Risk",
                            "score": 65.0,
                            "weight": 0.30,
                            "reasoning": "Pre-1930 construction requires structural survey before acceptance.",
                        },
                        {
                            "name": "Planning & Development Risk",
                            "score": 30.0,
                            "weight": 0.25,
                            "reasoning": "Moderate planning activity with 8 nearby applications; no major developments.",
                        },
                    ],
                    "plain_english_narrative": (
                        "Your property at 10 Downing Street has been assessed with an overall risk score of 63/100. "
                        "The main concern is its location in Flood Risk Zone 2, which means there is a medium "
                        "probability of flooding. The property's pre-1930 construction also adds a degree of "
                        "structural risk. We are referring this application to a senior underwriter for manual "
                        "review. A premium multiplier of 1.75× applies, pending final confirmation."
                    ),
                    "data_warnings": [],
                },
                {
                    "assessment_id": "7768b2c3d4e5f67890123456",
                    "decision": "accept",
                    "overall_risk_score": 18.0,
                    "premium_multiplier": 0.9,
                    "flood_risk_score": 5.0,
                    "planning_risk_score": 12.0,
                    "property_age_risk_score": 10.0,
                    "risk_factors": [
                        {
                            "name": "Flood Risk",
                            "score": 5.0,
                            "weight": 0.45,
                            "reasoning": "Flood Zone 1 — low probability; standard terms apply.",
                        },
                        {
                            "name": "Property Age Risk",
                            "score": 10.0,
                            "weight": 0.30,
                            "reasoning": "Post-2012 construction in excellent condition, modern building standards.",
                        },
                        {
                            "name": "Planning & Development Risk",
                            "score": 12.0,
                            "weight": 0.25,
                            "reasoning": "Low planning activity; 3 minor applications, no appeals or large developments.",
                        },
                    ],
                    "plain_english_narrative": (
                        "Your property at 42 Victoria Road has received a low overall risk score of 18/100. "
                        "It sits comfortably in Flood Zone 1 with minimal flood risk, and its modern construction "
                        "means structural risk is very low. We are pleased to offer standard coverage with a "
                        "discounted premium multiplier of 0.9×."
                    ),
                    "data_warnings": [],
                },
                {
                    "assessment_id": "8879c3d4e5f6789012345678",
                    "decision": "decline",
                    "overall_risk_score": 84.0,
                    "premium_multiplier": 3.0,
                    "flood_risk_score": 85.0,
                    "planning_risk_score": 66.0,
                    "property_age_risk_score": 80.0,
                    "risk_factors": [
                        {
                            "name": "Flood Risk",
                            "score": 85.0,
                            "weight": 0.45,
                            "reasoning": "Flood Zone 3 — high probability of flooding; policy exclusion applies.",
                        },
                        {
                            "name": "Property Age Risk",
                            "score": 80.0,
                            "weight": 0.30,
                            "reasoning": "Pre-1900 construction; mandatory structural survey required.",
                        },
                        {
                            "name": "Planning & Development Risk",
                            "score": 66.0,
                            "weight": 0.25,
                            "reasoning": "High planning activity with 2 active appeals and 1 large development nearby.",
                        },
                    ],
                    "plain_english_narrative": (
                        "Unfortunately we are unable to offer standard coverage for this property at 1 Flooding Lane. "
                        "The property is located in Flood Risk Zone 3, which represents a high annual probability of "
                        "flooding and falls outside our standard policy terms. Combined with its pre-1900 construction "
                        "and significant nearby development activity, the overall risk score of 84/100 exceeds our "
                        "acceptance threshold. We recommend contacting the Flood Re scheme for specialist coverage."
                    ),
                    "data_warnings": ["IBEX planning data returned limited results for this postcode"],
                },
            ]
        }
    }
