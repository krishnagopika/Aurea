"""
LocalitySafetyAgent
===================
Responsible for:
  1. Querying the Police UK API (data.police.uk) for street-level crimes
     near the property location
  2. Weighting crimes by insurance relevance (burglary, arson > vehicle crime > other)
  3. Returning a deterministic locality safety score (0–100)

Primary source: https://data.police.uk/api/crimes-street/all-crime
  — Free, no auth, official UK Home Office data

Crime weighting rationale (insurance relevance):
  burglary                3.0  — direct property risk
  criminal-damage-arson   2.5  — fire / structural damage
  robbery                 1.5  — area security indicator
  vehicle-crime           1.0  — area risk indicator
  theft-from-the-person   0.8  — neighbourhood safety
  all other categories    0.3  — general area crime

Score formula: min(weighted_count / 8, 100)
  → ~800 weighted crime-points → score 100 (very high crime area)
"""

import httpx
from datetime import date
from src.agents.state.assessment_state import AssessmentState

POLICE_API_URL = "https://data.police.uk/api/crimes-street/all-crime"

CATEGORY_WEIGHTS: dict[str, float] = {
    "burglary": 3.0,
    "criminal-damage-arson": 2.5,
    "robbery": 1.5,
    "vehicle-crime": 1.0,
    "theft-from-the-person": 0.8,
}
DEFAULT_WEIGHT = 0.3

LABEL_VERY_LOW = "Very Low Crime"
LABEL_LOW = "Low Crime"
LABEL_MODERATE = "Moderate Crime"
LABEL_HIGH = "High Crime"
LABEL_VERY_HIGH = "Very High Crime"

SCORE_LABELS = [
    (20, LABEL_VERY_LOW),
    (40, LABEL_LOW),
    (60, LABEL_MODERATE),
    (80, LABEL_HIGH),
    (101, LABEL_VERY_HIGH),
]


def _label(score: float) -> str:
    for threshold, label in SCORE_LABELS:
        if score < threshold:
            return label
    return LABEL_VERY_HIGH


async def _fetch_crimes(client: httpx.AsyncClient, lat: float, lon: float) -> tuple[list, str]:
    """
    Fetch crimes from Police UK API.
    Tries the most recent 4 months in descending order — the API has a
    typical 2–3 month publication lag, so current month is often empty.

    Returns:
      (crimes_list, "YYYY-MM") — first month that returns data
      ([], last_month_tried)   — if all attempts empty
    """
    today = date.today()
    year, month = today.year, today.month

    for _ in range(4):
        month_str = f"{year}-{month:02d}"
        print(f"[LocalitySafetyAgent] Querying Police UK API — month={month_str}")
        try:
            resp = await client.get(
                POLICE_API_URL,
                params={"lat": lat, "lng": lon, "date": month_str},
                timeout=15.0,
            )
            print(f"[LocalitySafetyAgent] HTTP {resp.status_code} — {len(resp.content)} bytes")
            if resp.status_code == 200 and resp.content:
                crimes = resp.json()
                if isinstance(crimes, list) and crimes:
                    print(f"[LocalitySafetyAgent] Got {len(crimes)} crimes for {month_str}")
                    return crimes, month_str
                print(f"[LocalitySafetyAgent] Empty results for {month_str} — trying previous month")
        except Exception as e:
            print(f"[LocalitySafetyAgent] Request error for {month_str}: {e}")

        # Step back one month
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    print("[LocalitySafetyAgent] All month attempts returned no data")
    return [], month_str


def _score_crimes(crimes: list) -> tuple[float, dict[str, int]]:
    """Return (score_0_to_100, category_counts_dict)."""
    category_counts: dict[str, int] = {}
    weighted_total = 0.0
    for crime in crimes:
        cat = crime.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        weighted_total += CATEGORY_WEIGHTS.get(cat, DEFAULT_WEIGHT)
    score = min(round(weighted_total / 8, 1), 100)
    return score, category_counts


async def locality_safety_agent(state: AssessmentState) -> AssessmentState:
    """LocalitySafetyAgent: Police UK crime data → locality safety score."""
    errors: list[str] = []
    lat = state.get("latitude")
    lon = state.get("longitude")

    print("\n" + "="*60)
    print("[LocalitySafetyAgent] Starting")
    print(f"  lat={lat}, lon={lon}")
    print("="*60)

    if lat is None or lon is None:
        print("[LocalitySafetyAgent] No coordinates — locality safety unable to evaluate")
        return {
            "raw_crime_data": {},
            "locality_safety_score": 25.0,
            "locality_safety_label": LABEL_LOW,
            "locality_safety_reasoning": "No coordinates available — locality safety cannot be evaluated.",
            "data_collection_errors": ["Locality safety evaluation skipped: no coordinates."],
        }

    async with httpx.AsyncClient(timeout=20.0) as client:
        print(f"[LocalitySafetyAgent] Tool: Police UK API — crimes near ({lat}, {lon})")
        try:
            crimes, month_used = await _fetch_crimes(client, lat, lon)
        except Exception as e:
            print(f"[LocalitySafetyAgent] API error: {e}")
            errors.append(f"Locality safety data unavailable: Police UK API error — {e}")
            return {
                "raw_crime_data": {},
                "locality_safety_score": 25.0,
                "locality_safety_label": LABEL_LOW,
                "locality_safety_reasoning": (
                    "Locality safety data unavailable (Police UK API error). "
                    "A neutral holding score of 25.0/100 has been applied."
                ),
                "data_collection_errors": errors,
            }

    if not crimes:
        errors.append("Locality safety: Police UK API returned no crime data for this location.")
        return {
            "raw_crime_data": {"month": month_used, "count": 0},
            "locality_safety_score": 25.0,
            "locality_safety_label": LABEL_LOW,
            "locality_safety_reasoning": (
                "No crime data returned from Police UK API for this location. "
                "A neutral holding score of 25.0/100 has been applied."
            ),
            "data_collection_errors": errors,
        }

    score, category_counts = _score_crimes(crimes)
    label = _label(score)

    # Build human-readable category breakdown (top 4)
    top = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:4]
    top_str = ", ".join(f"{cat.replace('-', ' ')} ({cnt})" for cat, cnt in top)

    reasoning = (
        f"Police UK data ({month_used}): {len(crimes)} recorded crimes near this location. "
        f"Top categories: {top_str}. "
        f"Weighted crime score: {score}/100 ({label}). "
        f"Burglary and criminal damage/arson carry the highest weighting as direct insurance risk factors."
    )

    print(f"[LocalitySafetyAgent] Done — {len(crimes)} crimes, score={score}, label={label!r}")
    print(f"  {reasoning}")

    return {
        "raw_crime_data": {"month": month_used, "count": len(crimes), "categories": category_counts},
        "locality_safety_score": score,
        "locality_safety_label": label,
        "locality_safety_reasoning": reasoning,
        "data_collection_errors": errors,
    }
