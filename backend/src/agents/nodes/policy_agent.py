"""
PolicyAgent
===========
Responsible for:
  1. Building a semantic query from the current risk scores
  2. Querying MongoDB Atlas Vector Search to retrieve the top-3 relevant policy chunks
  3. Providing policy context to the CoordinatorAgent

This is the RAG (Retrieval-Augmented Generation) agent in the pipeline.
"""

from src.agents.state.assessment_state import AssessmentState
from src.services.policy_service import retrieve_relevant_policies


async def policy_agent(state: AssessmentState) -> AssessmentState:
    """PolicyAgent: semantic retrieval of relevant insurance policy guidelines."""
    flood_zone = state.get("flood_zone", "unknown")
    flood_score = state.get("flood_risk_score", 0)
    planning_label = state.get("planning_density_label", "unknown")
    age_band = state.get("property_age_band", "unknown")

    print(f"\n{'='*60}")
    print(f"[PolicyAgent] Starting — RAG retrieval from MongoDB Atlas Vector Search")
    print(f"  flood_zone     = {flood_zone!r}")
    print(f"  flood_score    = {flood_score}")
    print(f"  planning_label = {planning_label!r}")
    print(f"  age_band       = {age_band!r}")
    print(f"{'='*60}")

    # Build a descriptive query that captures the property's risk profile
    query = (
        f"flood zone {flood_zone} property "
        f"flood risk score {flood_score} "
        f"planning density {planning_label} "
        f"property age band {age_band} "
        f"UK residential insurance policy"
    )
    print(f"[PolicyAgent] Tool: MongoDB Atlas Vector Search")
    print(f"  query = {query!r}")

    errors: list[str] = []

    try:
        chunks = await retrieve_relevant_policies(query, top_k=3)
        print(f"[PolicyAgent] Tool response: {len(chunks)} policy chunk(s) retrieved")
        for i, chunk in enumerate(chunks, 1):
            print(f"[PolicyAgent]   [{i}] {chunk[:120]}{'...' if len(chunk) > 120 else ''}")
    except Exception as e:
        errors.append(f"PolicyAgent retrieval failed: {e}")
        chunks = []
        print(f"[PolicyAgent] Tool error: {e}")

    print(f"[PolicyAgent] Done — {len(chunks)} chunk(s) added to policy context")

    return {"policy_context": chunks, "errors": errors}
