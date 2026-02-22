"""
EnvironmentalDataAgent
======================
Responsible for:
  1. Fetching EPC (Energy Performance Certificate) data from the EPC open data API
  2. Extracting property age band, property type, and energy rating
  3. Scoring property risk using a composite of age (70%) + energy rating (30%)

Energy rating insurance relevance:
  G/F — very poor insulation, likely older heating systems, higher risk of burst
        pipes, damp, and structural deterioration → risk penalty
  E   — below average, moderate uplift
  D   — average, neutral
  C   — good, slight reduction
  A/B — excellent, modern fabric, reduction applied

This agent provides the "building quality / vintage" risk dimension.
"""

import json
import re
import httpx
from src.agents.state.assessment_state import AssessmentState
from src.config.settings import settings

EPC_SEARCH_URL = f"{settings.EPC_API_URL}/api/v1/domestic/search"

# Energy rating → risk score (0–100). G is worst, A is best.
# Rated as a standalone score; blended 30% into the final composite.
ENERGY_RATING_SCORES: dict[str, int] = {
    "A": 5,
    "B": 15,
    "C": 30,
    "D": 50,   # UK average
    "E": 65,
    "F": 80,
    "G": 95,
}

AGE_BAND_SCORES: dict[str, int] = {
    "England and Wales: before 1900": 80,
    "England and Wales: 1900-1929": 65,
    "England and Wales: 1930-1949": 55,
    "England and Wales: 1950-1966": 45,
    "England and Wales: 1967-1975": 40,
    "England and Wales: 1976-1982": 35,
    "England and Wales: 1983-1990": 30,
    "England and Wales: 1991-1995": 25,
    "England and Wales: 1996-2002": 20,
    "England and Wales: 2003-2006": 15,
    "England and Wales: 2007-2011": 12,
    "England and Wales: 2012 onwards": 10,
}


async def _fetch_epc(postcode: str) -> dict:
    # EPC API requires no space in postcode (e.g. "M145TL" not "M14 5TL")
    postcode_clean = postcode.replace(" ", "").upper()
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        resp = await client.get(
            EPC_SEARCH_URL,
            params={"postcode": postcode_clean, "size": 5},
            headers={
                "Authorization": f"Basic {settings.EPC_API_KEY}",
                "Accept": "application/json",
            },
        )
        print(f"[EnvironmentalDataAgent] EPC HTTP {resp.status_code} — {len(resp.content)} bytes (postcode={postcode_clean!r})")
        if resp.status_code != 200:
            print(f"[EnvironmentalDataAgent] EPC error: {resp.text[:400]}")
            return {}
        if not resp.content.strip():
            # Retry with outward code only (e.g. "M145TL" → "M14")
            outward = postcode_clean[:-3] if len(postcode_clean) > 3 else postcode_clean
            print(f"[EnvironmentalDataAgent] Empty body — retrying with outward code {outward!r}")
            resp2 = await client.get(
                EPC_SEARCH_URL,
                params={"postcode": outward, "size": 5},
                headers={
                    "Authorization": f"Basic {settings.EPC_API_KEY}",
                    "Accept": "application/json",
                },
            )
            print(f"[EnvironmentalDataAgent] EPC retry HTTP {resp2.status_code} — {len(resp2.content)} bytes")
            if resp2.status_code != 200 or not resp2.content.strip():
                return {}
            try:
                return resp2.json()
            except Exception as e:
                print(f"[EnvironmentalDataAgent] EPC retry JSON parse error: {e}")
                return {}
        try:
            return resp.json()
        except Exception as e:
            print(f"[EnvironmentalDataAgent] EPC JSON parse error: {e}")
            return {}


def _score_age_band(age_band: str) -> int:
    # Exact match
    score = AGE_BAND_SCORES.get(age_band)
    if score is not None:
        return score

    # Partial match
    for key, val in AGE_BAND_SCORES.items():
        if age_band and age_band.lower() in key.lower():
            return val

    # Year extraction fallback
    years = re.findall(r"\d{4}", age_band or "")
    if years:
        year = int(years[0])
        if year < 1900:
            return 80
        elif year < 1930:
            return 65
        elif year < 1950:
            return 55
        elif year < 1975:
            return 40
        elif year < 2000:
            return 25
        else:
            return 12

    return 30  # mid-range default when age is unknown


async def environmental_data_agent(state: AssessmentState) -> AssessmentState:
    """EnvironmentalDataAgent: fetch EPC data and score property age risk."""
    errors: list[str] = []
    postcode = state.get("postcode", "")

    print(f"\n{'='*60}")
    print(f"[EnvironmentalDataAgent] Starting")
    print(f"  postcode = {postcode!r}")
    print(f"{'='*60}")

    epc_url = f"{EPC_SEARCH_URL}?postcode={postcode}&size=1"
    print(f"[EnvironmentalDataAgent] Tool: EPC API GET {epc_url}")

    try:
        raw = await _fetch_epc(postcode)
        print(f"[EnvironmentalDataAgent] EPC RAW JSON:\n{json.dumps(raw, indent=2)}")
        rows = raw.get("rows", [])
        print(f"[EnvironmentalDataAgent] Tool response: {len(rows)} EPC record(s) found")
    except Exception as e:
        errors.append(f"EPC data fetch failed: {e}")
        raw = {}
        rows = []
        print(f"[EnvironmentalDataAgent] Tool error: {e}")

    age_band = "unknown"
    prop_type = "unknown"
    energy_rating = "unknown"
    property_details: dict = {}

    if rows:
        row = rows[0]
        age_band = row.get("construction-age-band", "unknown") or "unknown"
        prop_type = row.get("property-type", "unknown") or "unknown"
        energy_rating = (row.get("current-energy-rating", "") or "").strip().upper() or "unknown"

        def _clean(v) -> str:
            return str(v).strip() if v else "unknown"

        # Build a structured property profile from EPC fields
        floor_area_raw = row.get("total-floor-area")
        try:
            floor_area = float(floor_area_raw) if floor_area_raw else None
        except (ValueError, TypeError):
            floor_area = None

        habitable_rooms_raw = row.get("number-habitable-rooms")
        try:
            habitable_rooms = int(float(habitable_rooms_raw)) if habitable_rooms_raw else None
        except (ValueError, TypeError):
            habitable_rooms = None

        # Confirmed address from EPC record
        addr_parts = [
            row.get("address1"), row.get("address2"), row.get("address3"),
            row.get("posttown"),
        ]
        confirmed_address = ", ".join(p for p in addr_parts if p and p.strip())

        property_details = {
            "property_type": _clean(prop_type),
            "built_form": _clean(row.get("built-form")),             # Detached / Semi-Detached / Terraced
            "age_band": _clean(age_band),
            "epc_rating": energy_rating,
            "floor_area_m2": floor_area,
            "habitable_rooms": habitable_rooms,
            "wall_type": _clean(row.get("walls-description")),       # e.g. "Cavity wall, as built, no insulation"
            "roof_type": _clean(row.get("roof-description")),        # e.g. "Pitched, 270 mm loft insulation"
            "floor_type": _clean(row.get("floor-description")),
            "glazing": _clean(row.get("glazed-type")),               # "double glazing", "single glazing"
            "heating": _clean(row.get("mainheat-description")),
            "confirmed_address": confirmed_address or "unknown",
        }
        print(f"[EnvironmentalDataAgent] Property details: {property_details}")

    age_score = float(_score_age_band(age_band))
    energy_score = float(ENERGY_RATING_SCORES.get(energy_rating, 50))  # 50 = neutral if unknown

    # Composite: 70% age risk + 30% energy rating risk
    if energy_rating == "unknown":
        score = age_score  # fall back to age-only if no rating available
        score_note = "energy rating unavailable — age-only score applied"
    else:
        score = round(age_score * 0.70 + energy_score * 0.30, 1)
        score_note = f"composite: age {age_score} × 70% + energy {energy_score} × 30%"

    score = min(score, 100.0)

    summary = (
        f"Property type: {prop_type}. "
        f"Construction age band: {age_band} (age risk: {age_score}/100). "
        f"EPC energy rating: {energy_rating} (energy risk: {energy_score}/100). "
        f"Composite property risk score: {score}/100 ({score_note})."
    )

    print(f"[EnvironmentalDataAgent] Done — age_band={age_band!r} energy_rating={energy_rating!r} type={prop_type!r} score={score}")

    return {
        "raw_epc_data": raw,
        "property_age_band": age_band,
        "property_type": prop_type,
        "property_age_risk_score": score,
        "property_profile_summary": summary,
        "property_details": property_details,
        "data_collection_errors": errors,
    }
