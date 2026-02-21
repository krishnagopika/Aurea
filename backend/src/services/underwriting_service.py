from beanie import PydanticObjectId
from src.agents.graph import assessment_graph
from src.agents.state.assessment_state import AssessmentState
from src.models.assessment import PropertyAssessment, RiskFactor
from src.models.underwriting import UnderwritingResult
from src.schemas.underwriting import AssessmentResponse


async def run_assessment(address: str, postcode: str, user_id: str) -> AssessmentResponse:
    initial_state: AssessmentState = {
        "address": address,
        "postcode": postcode,
        "user_id": user_id,
        "data_collection_errors": [],
        "errors": [],
        "policy_context": [],
        "risk_factors": [],
        "policy_citations": [],
    }

    final_state = await assessment_graph.ainvoke(initial_state)

    risk_factors = [
        RiskFactor(
            name=rf.get("name", ""),
            score=float(rf.get("score", 0)),
            weight=float(rf.get("weight", 0)),
            reasoning=rf.get("reasoning", ""),
        )
        for rf in (final_state.get("risk_factors") or [])
    ]

    assessment = PropertyAssessment(
        user_id=PydanticObjectId(user_id),
        address=address,
        postcode=postcode,
        decision=final_state.get("decision", "refer"),
        overall_risk_score=float(final_state.get("overall_risk_score", 50)),
        premium_multiplier=float(final_state.get("premium_multiplier", 1.0)),
        flood_risk_score=float(final_state.get("flood_risk_score", 20)),
        planning_risk_score=float(final_state.get("planning_risk_score", 10)),
        property_age_risk_score=float(final_state.get("property_age_risk_score", 30)),
        locality_safety_score=float(final_state.get("locality_safety_score", 25)),
        risk_factors=risk_factors,
        plain_english_narrative=final_state.get("plain_english_narrative", ""),
        data_warnings=(final_state.get("data_collection_errors") or []) + (final_state.get("errors") or []),
    )
    await assessment.insert()

    underwriting_result = UnderwritingResult(
        assessment_id=assessment.id,
        underwriter_reasoning=final_state.get("underwriter_reasoning", ""),
        policy_citations=final_state.get("policy_citations", []),
    )
    await underwriting_result.insert()

    return AssessmentResponse(
        assessment_id=str(assessment.id),
        decision=assessment.decision,
        overall_risk_score=assessment.overall_risk_score,
        premium_multiplier=assessment.premium_multiplier,
        flood_risk_score=assessment.flood_risk_score,
        planning_risk_score=assessment.planning_risk_score,
        property_age_risk_score=assessment.property_age_risk_score,
        locality_safety_score=assessment.locality_safety_score,
        risk_factors=[
            {"name": rf.name, "score": rf.score, "weight": rf.weight, "reasoning": rf.reasoning}
            for rf in risk_factors
        ],
        plain_english_narrative=assessment.plain_english_narrative,
        data_warnings=assessment.data_warnings,
    )


async def get_assessment_history(user_id: str) -> list[AssessmentResponse]:
    assessments = await PropertyAssessment.find(
        PropertyAssessment.user_id == PydanticObjectId(user_id)
    ).to_list()
    return [
        AssessmentResponse(
            assessment_id=str(a.id),
            decision=a.decision,
            overall_risk_score=a.overall_risk_score,
            premium_multiplier=a.premium_multiplier,
            flood_risk_score=a.flood_risk_score,
            planning_risk_score=a.planning_risk_score,
            property_age_risk_score=a.property_age_risk_score,
            locality_safety_score=a.locality_safety_score,
            risk_factors=[
                {"name": rf.name, "score": rf.score, "weight": rf.weight, "reasoning": rf.reasoning}
                for rf in a.risk_factors
            ],
            plain_english_narrative=a.plain_english_narrative,
            data_warnings=a.data_warnings,
        )
        for a in assessments
    ]
