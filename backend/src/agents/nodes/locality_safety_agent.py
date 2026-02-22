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

import asyncio
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


def _prev_month(year: int, month: int) -> tuple[int, int]:
    month -= 1
    if month == 0:
        month = 12
        year -= 1
    return year, month


def _build_month_list(year: int, month: int, count: int) -> list[str]:
    """Build a list of `count` month strings going backwards from year/month."""
    months = []
    y, m = year, month
    for _ in range(count):
        months.append(f"{y}-{m:02d}")
        y, m = _prev_month(y, m)
    return months


async def _fetch_one_month(
    client: httpx.AsyncClient, lat: float, lon: float, month_str: str
) -> tuple[str, list]:
    """Fetch crimes for a single month. Returns (month_str, crimes_list)."""
    try:
        resp = await client.get(
            POLICE_API_URL,
            params={"lat": lat, "lng": lon, "date": month_str},
            timeout=15.0,
        )
        print(f"[LocalitySafetyAgent] {month_str} — HTTP {resp.status_code} {len(resp.content)} bytes")
        if resp.status_code == 200 and resp.content:
            crimes = resp.json()
            if isinstance(crimes, list):
                print(f"[LocalitySafetyAgent] {month_str} — {len(crimes)} crimes")
                return month_str, crimes
    except Exception as e:
        print(f"[LocalitySafetyAgent] {month_str} — error: {e}")
    return month_str, []


async def _fetch_crimes(client: httpx.AsyncClient, lat: float, lon: float) -> tuple[list, str, str]:
    """
    Fetch 12 months of crimes from Police UK API in parallel.

    Step 1 — probe sequentially to find the most recent available month
              (API has 2–3 month publication lag).
    Step 2 — fire all 12 months concurrently with asyncio.gather.

    Returns:
      (all_crimes, first_month, last_month)
    """
    today = date.today()
    year, month = today.year, today.month

    # Step 1: find latest available month (sequential — need a confirmed start)
    latest_year, latest_month = year, month
    found_start = False
    for _ in range(4):
        month_str = f"{latest_year}-{latest_month:02d}"
        print(f"[LocalitySafetyAgent] Probing latest available month: {month_str}")
        try:
            resp = await client.get(
                POLICE_API_URL,
                params={"lat": lat, "lng": lon, "date": month_str},
                timeout=15.0,
            )
            if resp.status_code == 200 and resp.content:
                crimes = resp.json()
                if isinstance(crimes, list) and crimes:
                    print(f"[LocalitySafetyAgent] Latest available: {month_str} ({len(crimes)} crimes)")
                    found_start = True
                    break
        except Exception as e:
            print(f"[LocalitySafetyAgent] Probe error {month_str}: {e}")
        latest_year, latest_month = _prev_month(latest_year, latest_month)

    if not found_start:
        print("[LocalitySafetyAgent] Could not find any available month")
        return [], f"{year}-{month:02d}", f"{year}-{month:02d}"

    # Step 2: build 12-month list and fetch all in parallel
    months = _build_month_list(latest_year, latest_month, 12)
    print(f"[LocalitySafetyAgent] Fetching {len(months)} months in parallel: {months[0]} → {months[-1]}")

    results = await asyncio.gather(
        *[_fetch_one_month(client, lat, lon, m) for m in months]
    )

    all_crimes: list = []
    months_with_data = []
    for month_str, crimes in results:
        if crimes:
            all_crimes.extend(crimes)
            months_with_data.append(month_str)

    first_month = months[-1] if months else ""
    last_month = months[0] if months else ""
    print(f"[LocalitySafetyAgent] Total: {len(all_crimes)} crimes across {len(months_with_data)} months ({first_month} → {last_month})")
    return all_crimes, first_month, last_month


def _score_crimes(crimes: list) -> tuple[float, dict[str, int]]:
    """
    Return (score_0_to_100, category_counts_dict).
    Divisor scaled for 12 months of data (8 per month × 12 = 96).
    """
    category_counts: dict[str, int] = {}
    weighted_total = 0.0
    for crime in crimes:
        cat = crime.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        weighted_total += CATEGORY_WEIGHTS.get(cat, DEFAULT_WEIGHT)
    score = min(round(weighted_total / 96, 1), 100)
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
            crimes, first_month, last_month = await _fetch_crimes(client, lat, lon)
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
            "raw_crime_data": {"period": "unavailable", "count": 0},
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
        f"Police UK data ({first_month} to {last_month}, 12 months): "
        f"{len(crimes)} recorded crimes near this location. "
        f"Top categories: {top_str}. "
        f"Weighted crime score: {score}/100 ({label}). "
        f"Burglary and criminal damage/arson carry the highest weighting as direct insurance risk factors."
    )

    print(f"[LocalitySafetyAgent] Done — {len(crimes)} crimes over 12 months, score={score}, label={label!r}")
    print(f"  {reasoning}")

    return {
        "raw_crime_data": {
            "period": f"{first_month} to {last_month}",
            "months": 12,
            "count": len(crimes),
            "categories": category_counts,
        },
        "locality_safety_score": score,
        "locality_safety_label": label,
        "locality_safety_reasoning": reasoning,
        "data_collection_errors": errors,
    }
