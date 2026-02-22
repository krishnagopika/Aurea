import json
from typing import AsyncIterator

from beanie import PydanticObjectId
from src.agents.graph import assessment_graph
from src.agents.state.assessment_state import AssessmentState
from src.models.assessment import PropertyAssessment, RiskFactor
from src.models.underwriting import UnderwritingResult
from src.schemas.underwriting import AssessmentResponse

# Agents that run in parallel after PropertyValuationAgent completes
_PARALLEL_AGENTS = {"FloodRiskAgent", "EnvironmentalDataAgent", "LocalitySafetyAgent"}

# All known agent node names (for filtering stream events)
_AGENT_IDS = {
    "PropertyValuationAgent", "FloodRiskAgent", "EnvironmentalDataAgent",
    "LocalitySafetyAgent", "PolicyAgent", "CoordinatorAgent", "ExplainabilityAgent",
}

# List fields that accumulate across agents (operator.add in state TypedDict)
_LIST_APPEND_FIELDS = {"data_collection_errors", "errors", "policy_context", "risk_factors", "policy_citations"}


def _initial_state(address: str, postcode: str, user_id: str) -> AssessmentState:
    return {
        "address": address,
        "postcode": postcode,
        "user_id": user_id,
        "data_collection_errors": [],
        "errors": [],
        "policy_context": [],
        "risk_factors": [],
        "policy_citations": [],
    }


def _merge(state: dict, update: dict) -> dict:
    """Merge a node's output into the accumulated state, appending list fields."""
    result = dict(state)
    for k, v in update.items():
        if k in _LIST_APPEND_FIELDS and isinstance(v, list):
            result[k] = list(result.get(k) or []) + v
        else:
            result[k] = v
    return result


async def _save_and_build_response(
    final_state: dict, address: str, postcode: str, user_id: str
) -> AssessmentResponse:
    """Persist assessment to MongoDB and return the API response."""
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
        property_details=final_state.get("property_details") or None,
    )


async def run_assessment(address: str, postcode: str, user_id: str) -> AssessmentResponse:
    final_state = await assessment_graph.ainvoke(_initial_state(address, postcode, user_id))
    return await _save_and_build_response(final_state, address, postcode, user_id)


async def run_assessment_streaming(
    address: str, postcode: str, user_id: str
) -> AsyncIterator[str]:
    """
    Run the assessment graph and yield SSE events for each agent start/end,
    then yield the final result.

    SSE event shapes:
      {"type": "agent_start", "agent": "AgentName"}
      {"type": "agent_end",   "agent": "AgentName"}
      {"type": "result",      "data": {...AssessmentResponse...}}
    """
    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    state = dict(_initial_state(address, postcode, user_id))
    completed_parallel: set[str] = set()

    # PropertyValuationAgent always runs first — mark it running immediately
    yield _sse({"type": "agent_start", "agent": "PropertyValuationAgent"})

    async for update in assessment_graph.astream(state, stream_mode="updates"):
        for node_name, node_output in update.items():
            # Merge into accumulated state
            if isinstance(node_output, dict):
                state = _merge(state, node_output)

            if node_name not in _AGENT_IDS:
                continue

            if node_name == "PropertyValuationAgent":
                yield _sse({"type": "agent_end", "agent": "PropertyValuationAgent"})
                # Fan-out: all three parallel agents start simultaneously
                for a in _PARALLEL_AGENTS:
                    yield _sse({"type": "agent_start", "agent": a})

            elif node_name in _PARALLEL_AGENTS:
                yield _sse({"type": "agent_end", "agent": node_name})
                completed_parallel.add(node_name)
                if completed_parallel >= _PARALLEL_AGENTS:
                    yield _sse({"type": "agent_start", "agent": "PolicyAgent"})

            elif node_name == "PolicyAgent":
                yield _sse({"type": "agent_end", "agent": "PolicyAgent"})
                yield _sse({"type": "agent_start", "agent": "CoordinatorAgent"})

            elif node_name == "CoordinatorAgent":
                yield _sse({"type": "agent_end", "agent": "CoordinatorAgent"})
                yield _sse({"type": "agent_start", "agent": "ExplainabilityAgent"})

            elif node_name == "ExplainabilityAgent":
                yield _sse({"type": "agent_end", "agent": "ExplainabilityAgent"})

    # Save to DB and emit final result
    response = await _save_and_build_response(state, address, postcode, user_id)
    yield _sse({"type": "result", "data": response.model_dump()})
    yield "data: [DONE]\n\n"


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
