"""
CoordinatorAgent
================
The LLM-powered synthesis agent. It:
  1. Receives all risk scores from the three data agents
  2. Receives retrieved policy context from the PolicyAgent
  3. Calls AWS Bedrock (claude-sonnet-4-6) to produce a holistic underwriting decision
  4. Outputs: overall_risk_score, premium_multiplier, decision (accept/refer/decline),
     and underwriter_reasoning

Falls back to a weighted-average deterministic decision if Bedrock is unavailable.
"""

import json
import boto3
from src.agents.state.assessment_state import AssessmentState
from src.config.settings import settings


def _bedrock_client():
    return boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def _fallback_decision(flood_score: float, planning_score: float, age_score: float, locality_score: float, error: str) -> dict:
    overall = round(flood_score * 0.40 + planning_score * 0.20 + age_score * 0.25 + locality_score * 0.15, 1)
    multiplier = round(1.0 + (overall / 100) * 2.0, 2)
    decision = "accept" if overall < 60 else ("refer" if overall < 80 else "decline")
    return {
        "overall_risk_score": overall,
        "premium_multiplier": max(0.8, min(multiplier, 3.0)),
        "decision": decision,
        "underwriter_reasoning": f"Deterministic fallback applied (LLM unavailable: {error[:120]}). "
                                  f"Weighted average of sub-scores used.",
    }


async def coordinator_agent(state: AssessmentState) -> AssessmentState:
    """CoordinatorAgent: LLM-powered underwriting decision synthesis."""
    print(f"\n{'='*60}")
    print(f"[CoordinatorAgent] Initialising inputs from sub-agents")
    print(f"{'='*60}")
    flood_score = state.get("flood_risk_score", 20.0)
    flood_zone = state.get("flood_zone", "unknown")
    planning_score = state.get("planning_risk_score", 10.0)
    planning_label = state.get("planning_density_label", "unknown")
    age_score = state.get("property_age_risk_score", 30.0)
    age_band = state.get("property_age_band", "unknown")
    locality_score = state.get("locality_safety_score", 25.0)
    locality_label = state.get("locality_safety_label", "unknown")
    policy_context = "\n\n".join(state.get("policy_context") or ["No policy guidelines available."])

    system_prompt = "You are an expert UK home insurance underwriter. Respond only with valid JSON."
    user_prompt = f"""Use these policy guidelines:

{policy_context}

Sub-agent risk scores:
- FloodRiskAgent:           {flood_score}/100  (Zone {flood_zone})
- PropertyValuationAgent:   {planning_score}/100 (Planning density: {planning_label})
- EnvironmentalDataAgent:   {age_score}/100   (Age band: {age_band})
- LocalitySafetyAgent:      {locality_score}/100 (Crime level: {locality_label})

Decision thresholds (based on overall_risk_score):
  accept  → score < 60
  refer   → score 60–79
  decline → score ≥ 80

Premium multiplier range: 0.80x – 3.00x

Return ONLY this JSON (no markdown):
{{
  "overall_risk_score": <0-100>,
  "premium_multiplier": <0.8-3.0>,
  "decision": "<accept|refer|decline>",
  "underwriter_reasoning": "<2-3 sentence synthesis of all sub-agent findings>"
}}"""

    print(f"\n{'='*60}")
    print(f"[CoordinatorAgent] Starting — Bedrock LLM synthesis")
    print(f"  flood_score    = {flood_score} (Zone {flood_zone})")
    print(f"  planning_score = {planning_score} ({planning_label})")
    print(f"  age_score      = {age_score} ({age_band})")
    print(f"  locality_score = {locality_score} ({locality_label})")
    print(f"  policy chunks  = {len(state.get('policy_context') or [])} loaded")
    print(f"{'='*60}")
    print(f"[CoordinatorAgent] Tool: AWS Bedrock invoke_model ({settings.BEDROCK_MODEL_ID})")
    print(f"[CoordinatorAgent] Prompt:\n{user_prompt[:600]}{'...' if len(user_prompt) > 600 else ''}")

    try:
        client = _bedrock_client()
        response = client.invoke_model(
            modelId=settings.BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )
        body = json.loads(response["body"].read())
        text = body["content"][0]["text"].strip()
        print(f"[CoordinatorAgent] Tool response (raw): {text[:400]}{'...' if len(text) > 400 else ''}")
        # Strip markdown code fences if present
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        print(f"[CoordinatorAgent] Decision — score={result.get('overall_risk_score')} decision={result.get('decision')!r} multiplier={result.get('premium_multiplier')}")
    except Exception as e:
        print(f"[CoordinatorAgent] Bedrock error: {e} — using deterministic fallback")
        result = _fallback_decision(flood_score, planning_score, age_score, locality_score, str(e))
        print(f"[CoordinatorAgent] Fallback decision — score={result['overall_risk_score']} decision={result['decision']!r}")

    print(f"[CoordinatorAgent] Done — reasoning: {result.get('underwriter_reasoning', '')[:150]}")

    return {
        "overall_risk_score": float(result.get("overall_risk_score", 50)),
        "premium_multiplier": float(result.get("premium_multiplier", 1.0)),
        "decision": result.get("decision", "refer"),
        "underwriter_reasoning": result.get("underwriter_reasoning", ""),
    }
