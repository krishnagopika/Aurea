"""
ExplainabilityAgent
===================
The final agent in the pipeline. It:
  1. Receives the full state (all scores + CoordinatorAgent decision)
  2. Calls AWS Bedrock (claude-sonnet-4-6) to produce structured explainability output:
     - risk_factors list (name, score, weight, reasoning per factor)
     - policy_citations (which policy sections informed the decision)
     - plain_english_narrative (3-5 sentences for the customer)

Falls back to a structured deterministic output if Bedrock is unavailable.
"""

import json
import boto3
from src.agents.state.assessment_state import AssessmentState
from src.config.settings import settings


def _bedrock_client():
    return boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def _fallback_explanation(state: AssessmentState) -> dict:
    flood_score = state.get("flood_risk_score", 0)
    planning_score = state.get("planning_risk_score", 0)
    age_score = state.get("property_age_risk_score", 0)
    locality_score = state.get("locality_safety_score", 25.0)
    overall = state.get("overall_risk_score", 0)
    decision = state.get("decision", "refer")
    multiplier = state.get("premium_multiplier", 1.0)

    return {
        "risk_factors": [
            {
                "name": "Flood Risk",
                "score": flood_score,
                "weight": 0.40,
                "reasoning": state.get("flood_risk_reasoning", f"Flood Zone {state.get('flood_zone', 'unknown')}."),
            },
            {
                "name": "Property Age Risk",
                "score": age_score,
                "weight": 0.25,
                "reasoning": state.get("property_profile_summary", f"Age band: {state.get('property_age_band', 'unknown')}."),
            },
            {
                "name": "Planning & Development Risk",
                "score": planning_score,
                "weight": 0.20,
                "reasoning": state.get("planning_risk_reasoning", f"Density: {state.get('planning_density_label', 'unknown')}."),
            },
            {
                "name": "Locality & Crime Risk",
                "score": locality_score,
                "weight": 0.15,
                "reasoning": state.get("locality_safety_reasoning", f"Crime level: {state.get('locality_safety_label', 'unknown')}."),
            },
        ],
        "policy_citations": [],
        "plain_english_narrative": (
            f"Your property has been assessed with an overall risk score of {overall:.0f}/100. "
            f"The underwriting decision is: {decision.upper()}. "
            f"A premium multiplier of {multiplier:.2f}x applies. "
            f"The key risk factors considered were flood zone classification, "
            f"property construction age, nearby planning activity, and local crime levels."
        ),
    }


async def explainability_agent(state: AssessmentState) -> AssessmentState:
    """ExplainabilityAgent: produce structured risk breakdown and plain-English narrative."""
    print(f"\n{'='*60}")
    print(f"[ExplainabilityAgent] Starting — generating customer-facing explanation")
    print(f"  address        = {state.get('address', 'N/A')!r}")
    print(f"  decision       = {state.get('decision', 'N/A')!r}")
    print(f"  overall_score  = {state.get('overall_risk_score', 0)}")
    print(f"  multiplier     = {state.get('premium_multiplier', 1.0):.2f}x")
    print(f"  flood_score    = {state.get('flood_risk_score', 0)} (Zone {state.get('flood_zone', 'N/A')})")
    print(f"  planning_score = {state.get('planning_risk_score', 0)}")
    print(f"  age_score      = {state.get('property_age_risk_score', 0)}")
    print(f"  locality_score = {state.get('locality_safety_score', 25.0)} ({state.get('locality_safety_label', 'N/A')})")
    print(f"{'='*60}")

    policy_context_str = "\n".join(state.get("policy_context") or ["None"])

    user_prompt = f"""You are an AI assistant explaining an insurance underwriting decision to a customer.

Assessment data:
- Address: {state.get('address', 'N/A')}
- Decision: {state.get('decision', 'N/A').upper()}
- Overall Risk Score: {state.get('overall_risk_score', 0)}/100
- Premium Multiplier: {state.get('premium_multiplier', 1.0):.2f}x
- FloodRiskAgent score: {state.get('flood_risk_score', 0)}/100 (Zone {state.get('flood_zone', 'N/A')}) — {state.get('flood_risk_reasoning', '')}
- PropertyValuationAgent score: {state.get('planning_risk_score', 0)}/100 ({state.get('planning_density_label', 'N/A')} planning density) — {state.get('planning_risk_reasoning', '')}
- EnvironmentalDataAgent score: {state.get('property_age_risk_score', 0)}/100 ({state.get('property_age_band', 'N/A')}) — {state.get('property_profile_summary', '')}
- LocalitySafetyAgent score: {state.get('locality_safety_score', 25.0)}/100 ({state.get('locality_safety_label', 'N/A')}) — {state.get('locality_safety_reasoning', '')}
- CoordinatorAgent reasoning: {state.get('underwriter_reasoning', 'N/A')}

Policy guidelines used:
{policy_context_str}

Return ONLY this JSON (no markdown):
{{
  "risk_factors": [
    {{"name": "Flood Risk", "score": <0-100>, "weight": 0.40, "reasoning": "<1 sentence from FloodRiskAgent findings>"}},
    {{"name": "Property Age Risk", "score": <0-100>, "weight": 0.25, "reasoning": "<1 sentence from EnvironmentalDataAgent findings>"}},
    {{"name": "Planning & Development Risk", "score": <0-100>, "weight": 0.20, "reasoning": "<1 sentence from PropertyValuationAgent findings>"}},
    {{"name": "Locality & Crime Risk", "score": <0-100>, "weight": 0.15, "reasoning": "<1 sentence from LocalitySafetyAgent findings>"}}
  ],
  "policy_citations": ["<PolicyName – Section>"],
  "plain_english_narrative": "<3-5 sentences explaining the decision in plain English for the customer>"
}}"""

    print(f"[ExplainabilityAgent] Tool: AWS Bedrock invoke_model ({settings.BEDROCK_MODEL_ID})")

    try:
        client = _bedrock_client()
        response = client.invoke_model(
            modelId=settings.BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": user_prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )
        body = json.loads(response["body"].read())
        text = body["content"][0]["text"].strip()
        print(f"[ExplainabilityAgent] Tool response (raw): {text[:400]}{'...' if len(text) > 400 else ''}")
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        factors = result.get("risk_factors", [])
        print(f"[ExplainabilityAgent] Parsed {len(factors)} risk factor(s)")
        for f in factors:
            print(f"[ExplainabilityAgent]   {f.get('name')}: score={f.get('score')} weight={f.get('weight')}")
        narrative = result.get("plain_english_narrative", "")
        print(f"[ExplainabilityAgent] Narrative: {narrative[:200]}{'...' if len(narrative) > 200 else ''}")
    except Exception as e:
        print(f"[ExplainabilityAgent] Bedrock error: {e} — using deterministic fallback")
        result = _fallback_explanation(state)

    print(f"[ExplainabilityAgent] Done")

    return {
        "risk_factors": result.get("risk_factors", []),
        "policy_citations": result.get("policy_citations", []),
        "plain_english_narrative": result.get("plain_english_narrative", ""),
    }
