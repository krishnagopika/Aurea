"""
PropertyValuationAgent
======================
Responsible for:
  1. Geocoding the address via Nominatim (OpenStreetMap)
  2. Resolving council_id via:
       a) postcodes.io  →  admin_district_code  →  IBEX council_id lookup via /search
       b) Fallback: extract council_id from /search results directly
  3. Fetching nearby planning applications via IBEX POST /search
  4. Fetching council-level statistics via IBEX POST /stats (using council_id)
  5. Scoring planning activity using council_development_activity_level, new homes,
     application volume, and local search results
  6. Producing a human-readable property valuation summary

IBEX API uses POST with JSON bodies. Coordinates are [longitude, latitude].
"""

import httpx
from datetime import date, timedelta
from src.agents.state.assessment_state import AssessmentState
from src.config.settings import settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
POSTCODES_IO_URL = "https://api.postcodes.io/postcodes"
IBEX_SEARCH_URL = f"{settings.IBEX_API_URL}/search"
IBEX_STATS_URL = f"{settings.IBEX_API_URL}/stats"

_ACTIVITY_LEVEL_SCORES: dict[str, float] = {
    "low": 10.0,
    "moderate": 35.0,
    "high": 65.0,
    "very high": 85.0,
}

# Rolling 2-year window for IBEX queries
_DATE_TO = date.today().isoformat()
_DATE_FROM = (date.today() - timedelta(days=730)).isoformat()

_IBEX_HEADERS = {
    "Authorization": f"Bearer {settings.IBEX_API_KEY}",
    "Content-Type": "application/json",
}


async def _geocode(client: httpx.AsyncClient, address: str, postcode: str = ""):
    # Try full address first
    for query in [address, f"{address}, UK", postcode, f"{postcode}, UK"]:
        if not query or not query.strip():
            continue
        resp = await client.get(
            NOMINATIM_URL,
            params={"q": query.strip(), "format": "json", "limit": 1, "countrycodes": "gb"},
            headers={"User-Agent": "Aurea-Underwriting/1.0"},
        )
        print(f"[PropertyValuationAgent] Nominatim query={query!r} HTTP {resp.status_code} — {len(resp.content)} bytes")
        data = resp.json()
        print(f"[PropertyValuationAgent] Nominatim raw response: {str(data)[:400]}")
        if data:
            hit = data[0]
            print(f"[PropertyValuationAgent] Nominatim matched: {hit.get('display_name', '')[:120]}")
            return float(hit["lat"]), float(hit["lon"])
        print(f"[PropertyValuationAgent] Nominatim: no results for {query!r}")
    return None, None


async def _fetch_ibex_search(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    """POST /search — nearby planning applications within 500 m."""
    body = {
        "input": {
            "srid": 4326,
            "coordinates": [lon, lat],   # GeoJSON order: [longitude, latitude]
            "radius": 500,
            "date_from": _DATE_FROM,
            "date_to": _DATE_TO,
        },
        "extensions": {
            "appeals": True,
            "project_type": True,
            "num_new_houses": True,
            "proposed_floor_area": True,
            "num_comments_received": True,
        },
    }
    print(f"[PropertyValuationAgent] IBEX /search POST body: {body}")
    try:
        resp = await client.post(
            IBEX_SEARCH_URL,
            json=body,
            headers=_IBEX_HEADERS,
            timeout=15.0,
        )
        print(f"[PropertyValuationAgent] IBEX /search HTTP {resp.status_code} — {len(resp.content)} bytes")
        if resp.status_code != 200:
            print(f"[PropertyValuationAgent] IBEX /search error: {resp.text[:400]}")
            return {}
        data = resp.json()
        applications = data.get("applications", data.get("results", []))
        print(f"[PropertyValuationAgent] IBEX /search: {len(applications) if isinstance(applications, list) else 0} applications returned")
        if isinstance(applications, list) and applications:
            print(f"[PropertyValuationAgent]   Sample: council={applications[0].get('council_name')} type={applications[0].get('normalised_application_type')} decision={applications[0].get('normalised_decision')}")
        return data
    except Exception as e:
        print(f"[PropertyValuationAgent] IBEX /search exception: {e}")
        return {}


async def _resolve_council_id(client: httpx.AsyncClient, postcode: str, search_data: dict) -> int | None:
    """
    Resolve IBEX council_id using two strategies:
      1. Extract from /search results (fastest — already fetched)
      2. postcodes.io → admin_district_code then wide-radius /search to pick up council_id
    """
    # Strategy 1: council_id already present in search results
    applications = search_data.get("applications", search_data.get("results", []))
    if isinstance(applications, list):
        for app in applications:
            cid = app.get("council_id")
            if cid:
                print(f"[PropertyValuationAgent] council_id={cid} ({app.get('council_name', '?')}) from /search results")
                return int(cid)

    # Strategy 2: postcodes.io lookup
    postcode_clean = postcode.replace(" ", "").upper()
    print(f"[PropertyValuationAgent] No council_id in search results — querying postcodes.io for {postcode_clean!r}")
    try:
        resp = await client.get(
            f"{POSTCODES_IO_URL}/{postcode_clean}",
            timeout=8.0,
        )
        print(f"[PropertyValuationAgent] postcodes.io HTTP {resp.status_code} — {len(resp.content)} bytes")
        if resp.status_code == 200:
            data = resp.json().get("result", {})
            admin_code = data.get("codes", {}).get("admin_district", "")
            admin_name = data.get("admin_district", "")
            lat = data.get("latitude")
            lon = data.get("longitude")
            print(f"[PropertyValuationAgent] postcodes.io: admin_district={admin_name!r} code={admin_code!r} lat={lat} lon={lon}")

            # Use postcodes.io lat/lon to do a wide-radius search to find council_id
            if lat and lon:
                wide_body = {
                    "input": {
                        "srid": 4326,
                        "coordinates": [lon, lat],
                        "radius": 2000,
                        "date_from": _DATE_FROM,
                        "date_to": _DATE_TO,
                    },
                    "extensions": {},
                }
                print(f"[PropertyValuationAgent] IBEX wide-radius search (2000m) for council_id")
                wide_resp = await client.post(
                    IBEX_SEARCH_URL,
                    json=wide_body,
                    headers=_IBEX_HEADERS,
                    timeout=15.0,
                )
                print(f"[PropertyValuationAgent] IBEX wide search HTTP {wide_resp.status_code} — {len(wide_resp.content)} bytes")
                if wide_resp.status_code == 200 and wide_resp.content:
                    wide_data = wide_resp.json()
                    wide_apps = wide_data.get("applications", wide_data.get("results", []))
                    if isinstance(wide_apps, list):
                        for app in wide_apps:
                            cid = app.get("council_id")
                            if cid:
                                print(f"[PropertyValuationAgent] council_id={cid} ({app.get('council_name', '?')}) from wide search")
                                return int(cid)
    except Exception as e:
        print(f"[PropertyValuationAgent] council_id resolution error: {e}")

    print(f"[PropertyValuationAgent] Could not resolve council_id — /stats will be skipped")
    return None


async def _fetch_ibex_stats(client: httpx.AsyncClient, council_id: int) -> dict:
    """POST /stats — council-level statistics for the given council_id."""
    body = {
        "input": {
            "council_id": council_id,
            "date_from": _DATE_FROM,
            "date_to": _DATE_TO,
        }
    }
    print(f"[PropertyValuationAgent] IBEX /stats POST body: {body}")
    try:
        resp = await client.post(
            IBEX_STATS_URL,
            json=body,
            headers=_IBEX_HEADERS,
            timeout=15.0,
        )
        print(f"[PropertyValuationAgent] IBEX /stats HTTP {resp.status_code} — {len(resp.content)} bytes")
        if resp.status_code != 200:
            print(f"[PropertyValuationAgent] IBEX /stats error: {resp.text[:400]}")
            return {}
        data = resp.json()
        print(f"[PropertyValuationAgent] IBEX /stats keys: {list(data.keys())}")
        return data
    except Exception as e:
        print(f"[PropertyValuationAgent] IBEX /stats exception: {e}")
        return {}


def _score_planning(stats: dict, search: dict) -> tuple[float, str, str]:
    """Score planning risk 0-100 using stats (primary) + local search (supplement)."""
    # --- Stats-based score ---
    activity_level = str(stats.get("council_development_activity_level", "")).lower()
    base_score = _ACTIVITY_LEVEL_SCORES.get(activity_level, 0.0)

    new_homes = int(stats.get("number_of_new_homes_approved", 0) or 0)
    approval_rate = float(stats.get("approval_rate", 0) or 0)
    refusal_rate = float(stats.get("refusal_rate", 0) or 0)
    app_counts = stats.get("number_of_applications", {})
    total_apps = sum(app_counts.values()) if isinstance(app_counts, dict) else 0

    print(f"[PropertyValuationAgent] Stats: activity={activity_level!r} total_apps={total_apps} "
          f"new_homes={new_homes} approval={approval_rate:.1f}% refusal={refusal_rate:.1f}%")

    stats_bonus = 0.0
    if new_homes > 500:
        stats_bonus += 10.0
    elif new_homes > 200:
        stats_bonus += 5.0
    if refusal_rate > 20:
        stats_bonus += 5.0

    # --- Search-based score (local radius) ---
    applications = search.get("applications", search.get("results", []))
    local_count = len(applications) if isinstance(applications, list) else 0
    appeals = 0
    large_devs = 0
    if isinstance(applications, list):
        for app in applications:
            if app.get("appeal_status") or app.get("appeal_decision"):
                appeals += 1
            num_houses = int(app.get("num_new_houses", 0) or 0)
            floor_area = float(app.get("proposed_floor_area", 0) or 0)
            if num_houses >= 10 or floor_area >= 1000:
                large_devs += 1

    search_score = min(local_count * 3 + appeals * 8 + large_devs * 10, 40.0)
    print(f"[PropertyValuationAgent] Search: local={local_count} appeals={appeals} large_devs={large_devs} search_score={search_score}")

    # --- Combine ---
    if base_score > 0:
        score = min(base_score + stats_bonus + search_score * 0.3, 100.0)
        label = activity_level.title() if activity_level else "Low"
        if label not in ("Low", "Moderate", "High", "Very High"):
            label = "Low"
    else:
        score = min(local_count * 3 + appeals * 8 + large_devs * 10, 100.0)
        label = "Low" if score < 20 else ("Moderate" if score < 50 else ("High" if score < 75 else "Very High"))

    reasoning = (
        f"Council activity: {activity_level or 'unknown'}. "
        f"{total_apps} council-level applications; {new_homes} new homes approved. "
        f"Approval rate {approval_rate:.1f}%, refusal rate {refusal_rate:.1f}%. "
        f"Locally: {local_count} applications within 500 m, {appeals} appeals, {large_devs} large developments."
    )
    return float(round(score, 1)), label, reasoning


async def property_valuation_agent(state: AssessmentState) -> AssessmentState:
    """PropertyValuationAgent: geocode → IBEX /search → IBEX /stats → planning score."""
    errors: list[str] = []
    address = state.get("address", "")
    postcode = state.get("postcode", "")

    print(f"\n{'='*60}")
    print(f"[PropertyValuationAgent] Starting")
    print(f"  address  = {address!r}")
    print(f"  postcode = {postcode!r}")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Geocode
        print(f"[PropertyValuationAgent] Tool: Nominatim geocoding")
        try:
            lat, lon = await _geocode(client, address, postcode)
            print(f"[PropertyValuationAgent] Tool response: lat={lat}, lon={lon}")
        except Exception as e:
            errors.append(f"Geocoding failed: {e}")
            lat, lon = None, None
            print(f"[PropertyValuationAgent] Geocoding error: {e}")

        if lat is None or lon is None:
            errors.append("Could not geocode address.")
            return {
                "latitude": None,
                "longitude": None,
                "raw_planning_data": {},
                "planning_risk_score": 10.0,
                "planning_density_label": "Low",
                "planning_risk_reasoning": "No coordinates — defaulting to low planning risk.",
                "property_valuation_summary": "Location unknown.",
                "data_collection_errors": errors,
            }

        # 2. IBEX /search — local applications (also gives us council_id)
        print(f"[PropertyValuationAgent] Tool: IBEX POST /search — lat={lat} lon={lon} radius=500m")
        search_raw = await _fetch_ibex_search(client, lat, lon)

        # 3. Resolve council_id then fetch /stats
        stats_raw = {}
        council_id = await _resolve_council_id(client, postcode, search_raw)
        if council_id:
            print(f"[PropertyValuationAgent] Tool: IBEX POST /stats — council_id={council_id}")
            stats_raw = await _fetch_ibex_stats(client, council_id)
        else:
            print(f"[PropertyValuationAgent] Skipping /stats — no council_id available")

    # 4. Score
    score, label, reasoning = _score_planning(stats_raw, search_raw)
    applications = search_raw.get("applications", search_raw.get("results", []))
    local_count = len(applications) if isinstance(applications, list) else 0

    summary = (
        f"Property at ({lat:.4f}, {lon:.4f}). "
        f"Council planning activity: {label}. "
        f"{local_count} applications within 500 m."
    )

    print(f"[PropertyValuationAgent] Done — score={score} label={label!r}")
    print(f"  reasoning: {reasoning}")

    return {
        "latitude": lat,
        "longitude": lon,
        "raw_planning_data": {"stats": stats_raw, "search": search_raw},
        "planning_risk_score": score,
        "planning_density_label": label,
        "planning_risk_reasoning": reasoning,
        "property_valuation_summary": summary,
        "data_collection_errors": errors,
    }
