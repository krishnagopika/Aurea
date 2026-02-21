"""
EnvironmentalDataAgent
======================
Responsible for:
  1. Fetching EPC (Energy Performance Certificate) data from the EPC open data API
  2. Extracting property age band and property type
  3. Scoring property age risk using a lookup table

This agent provides the "building quality / vintage" risk dimension.
"""

import re
import httpx
from src.agents.state.assessment_state import AssessmentState
from src.config.settings import settings

EPC_SEARCH_URL = f"{settings.EPC_API_URL}/api/v1/domestic/search"

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
        if not resp.content:
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
            if not resp2.content or resp2.status_code != 200:
                return {}
            return resp2.json()
        return resp.json()


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
        rows = raw.get("rows", [])
        print(f"[EnvironmentalDataAgent] Tool response: {len(rows)} EPC record(s) found")
        if rows:
            print(f"[EnvironmentalDataAgent]   Record: {str(rows[0])[:300]}")
    except Exception as e:
        errors.append(f"EPC data fetch failed: {e}")
        raw = {}
        rows = []
        print(f"[EnvironmentalDataAgent] Tool error: {e}")

    age_band = "unknown"
    prop_type = "unknown"

    if rows:
        row = rows[0]
        age_band = row.get("construction-age-band", "unknown") or "unknown"
        prop_type = row.get("property-type", "unknown") or "unknown"

    score = float(_score_age_band(age_band))
    summary = (
        f"Property type: {prop_type}. "
        f"Construction age band: {age_band}. "
        f"Property age risk score: {score}/100."
    )

    print(f"[EnvironmentalDataAgent] Done — age_band={age_band!r} type={prop_type!r} score={score}")

    return {
        "raw_epc_data": raw,
        "property_age_band": age_band,
        "property_type": prop_type,
        "property_age_risk_score": score,
        "property_profile_summary": summary,
        "data_collection_errors": errors,
    }
