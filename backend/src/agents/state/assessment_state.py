import operator
from typing import Annotated, TypedDict, Optional, List


class AssessmentState(TypedDict, total=False):
    # Input
    address: str
    postcode: str
    user_id: str

    # --- PropertyValuationAgent (IBEX) outputs ---
    latitude: Optional[float]
    longitude: Optional[float]
    raw_planning_data: Optional[dict]
    property_valuation_summary: str

    # --- FloodRiskAgent outputs ---
    raw_flood_data: Optional[dict]
    flood_zone: str                          # "1", "2", "3", "unknown"
    flood_risk_score: float                  # 0-100
    flood_risk_reasoning: str

    # --- EnvironmentalDataAgent (EPC) outputs ---
    raw_epc_data: Optional[dict]
    property_age_band: str
    property_type: str
    property_age_risk_score: float           # 0-100
    property_profile_summary: str

    # --- Planning scoring (PropertyValuationAgent) ---
    planning_risk_score: float               # 0-100
    planning_risk_reasoning: str
    planning_density_label: str              # Low / Moderate / High / Very High

    # --- LocalitySafetyAgent outputs ---
    raw_crime_data: Optional[dict]
    locality_safety_score: float             # 0-100
    locality_safety_label: str              # Very Low / Low / Moderate / High / Very High Crime
    locality_safety_reasoning: str

    # --- PolicyAgent (RAG) outputs ---
    policy_context: List[str]

    # --- CoordinatorAgent (LLM) outputs ---
    overall_risk_score: float
    premium_multiplier: float
    decision: str                            # accept | refer | decline
    underwriter_reasoning: str

    # --- ExplainabilityAgent outputs ---
    risk_factors: List[dict]
    policy_citations: List[str]
    plain_english_narrative: str

    # List fields written by multiple parallel agents — use operator.add to merge
    data_collection_errors: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]
