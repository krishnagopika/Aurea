"""
FloodRiskAgent
==============
Implements the DEFRA "Check Your Long Term Flood Risk" (CYLTFR) methodology.

Four flood risk sources assessed (matching CYLTFR service categories):
  1. Rivers & Sea  — Flood Zone classification via planning.data.gov.uk
                     (Zone 1 = Low, Zone 2 = Medium, Zone 3 = High)
  2. Surface Water — Risk of Flooding from Surface Water (RoFSW) via
                     planning.data.gov.uk flood-risk-zone with surface water type
  3. Groundwater   — Checked via EA flood monitoring areas (indicative)
  4. Reservoirs    — Reservoir flood inundation zones (indicative)

CYLTFR Risk Levels (annual probability):
  High       ≥ 3.3%  (≥ 1 in 30)
  Medium     1%–3.3% (1 in 100 to 1 in 30)
  Low        0.1%–1% (1 in 1,000 to 1 in 100)
  Very Low   < 0.1%  (< 1 in 1,000)

Live data:
  EA Flood Monitoring API — current flood warnings/alerts near the property
  https://environment.data.gov.uk/flood-monitoring/id/floods?lat=Y&long=X&dist=D

Primary zone source: www.planning.data.gov.uk/entity.json (MHCLG — authoritative)

NOTE: The legacy EA ArcGIS FeatureServer (environment.data.gov.uk) was
decommissioned in early 2025 as part of the NaFRA transition. All requests
return {"error": {"code": 400, ...}}. The EA flood monitoring API remains live.
"""

import httpx
from src.agents.state.assessment_state import AssessmentState

# ---------------------------------------------------------------------------
# Endpoint constants
# ---------------------------------------------------------------------------
PLANNING_DATA_URL = "https://www.planning.data.gov.uk/entity.json"
EA_FLOOD_WARNINGS_URL = "https://environment.data.gov.uk/flood-monitoring/id/floods"

# Search radius (km) for EA live flood warnings
EA_WARNING_RADIUS_KM = 5

# ---------------------------------------------------------------------------
# CYLTFR scoring: Rivers & Sea flood zone → risk score (0–100)
# Zone 1 = Very Low / Low probability  → score 5
# Zone 2 = Medium probability          → score 45
# Zone 3 = High probability            → score 85
# ---------------------------------------------------------------------------
ZONE_SCORES: dict[str, int] = {"1": 5, "2": 45, "3": 85, "unknown": 20}

# CYLTFR official zone probability descriptions
ZONE_RISK_LEVEL: dict[str, str] = {
    "1": "Very Low",
    "2": "Low to Medium",
    "3": "High",
}

ZONE_PROBABILITY: dict[str, str] = {
    "1": "less than 0.1% annual chance (1 in 1,000 or greater)",
    "2": "between 0.1% and 1% annual chance (1 in 1,000 to 1 in 100)",
    "3": "greater than 1% annual chance (1 in 100 or greater)",
}

EA_SEVERITY_LABELS: dict[int, str] = {
    1: "Severe Flood Warning",
    2: "Flood Warning",
    3: "Flood Alert",
    4: "No Longer in Force",
}


# ---------------------------------------------------------------------------
# Tool: planning.data.gov.uk — Flood Zone (Rivers & Sea)
# ---------------------------------------------------------------------------
async def _fetch_flood_zone_entities(
    client: httpx.AsyncClient, lat: float, lon: float
) -> dict:
    """Query planning.data.gov.uk for flood-risk-zone entities at this point."""
    try:
        resp = await client.get(
            PLANNING_DATA_URL,
            params={
                "dataset": "flood-risk-zone",
                "latitude": lat,
                "longitude": lon,
            },
            timeout=12.0,
        )
        print(
            f"[FloodRiskAgent] planning.data.gov.uk HTTP {resp.status_code} "
            f"— {len(resp.content)} bytes"
        )
        if resp.status_code != 200 or not resp.content:
            return {}
        data = resp.json()
        entities = data.get("entities", data.get("results", []))
        print(
            f"[FloodRiskAgent] {len(entities) if isinstance(entities, list) else 0} "
            "flood-risk-zone entity/entities returned"
        )
        if isinstance(entities, list) and entities:
            print(f"[FloodRiskAgent]   Sample: {str(entities[0])[:300]}")
        return data
    except Exception as e:
        print(f"[FloodRiskAgent] planning.data.gov.uk error: {e}")
        return {}


# ---------------------------------------------------------------------------
# Tool: EA Flood Monitoring API — live warnings near the property
# ---------------------------------------------------------------------------
async def _fetch_ea_flood_warnings(
    client: httpx.AsyncClient, lat: float, lon: float
) -> list[dict]:
    """
    Query EA Flood Monitoring API for current flood warnings/alerts within
    EA_WARNING_RADIUS_KM of the property.

    Returns list of active warning dicts, empty list on failure.
    """
    try:
        resp = await client.get(
            EA_FLOOD_WARNINGS_URL,
            params={"lat": lat, "long": lon, "dist": EA_WARNING_RADIUS_KM},
            timeout=10.0,
        )
        print(
            f"[FloodRiskAgent] EA flood warnings HTTP {resp.status_code} "
            f"— {len(resp.content)} bytes"
        )
        if resp.status_code != 200 or not resp.content:
            return []
        data = resp.json()
        items = data.get("items", [])
        # Filter out expired warnings
        active = [
            w for w in items
            if isinstance(w, dict) and w.get("severity", 4) < 4
        ]
        print(f"[FloodRiskAgent] {len(active)} active EA flood warning(s) found within {EA_WARNING_RADIUS_KM}km")
        return active
    except Exception as e:
        print(f"[FloodRiskAgent] EA flood warnings error: {e}")
        return []


# ---------------------------------------------------------------------------
# Parse flood zone from planning.data.gov.uk response
# ---------------------------------------------------------------------------
def _parse_zone(raw: dict) -> str | None:
    """
    Parse DEFRA Flood Zone from planning.data.gov.uk /entity.json response.
    Returns '1', '2', '3', or None.

    Entities carry fields like:
      flood-risk-level: 'flood-risk-zone-2', 'fz3', '2', '3', etc.
      reference:        '232138/2' (suffix indicates zone number)
      name:             'Flood Zone 2', etc.

    When multiple entities are returned, the highest (worst) zone wins —
    matching CYLTFR's conservative approach.
    """
    entities = raw.get("entities", raw.get("results", []))
    detected = None
    for entity in (entities or []):
        level = str(entity.get("flood-risk-level", "")).lower()
        ref   = str(entity.get("reference", "")).lower()
        name  = str(entity.get("name", "")).lower()
        combined = f"{level} {ref} {name}"
        for z in ["3", "2", "1"]:
            matched = (
                f"zone-{z}" in combined
                or f"zone {z}" in combined
                or f"fz{z}" in combined
                or combined.strip() == z
                # Reference suffix pattern: e.g. "232138/2" → zone 2
                or ref.endswith(f"/{z}")
                or ref.endswith(f"-{z}")
            )
            if matched and (detected is None or int(z) > int(detected)):
                detected = z
    return detected


# ---------------------------------------------------------------------------
# Summarise EA warnings for output
# ---------------------------------------------------------------------------
def _summarise_warnings(warnings: list[dict]) -> tuple[str, bool]:
    """
    Returns (human-readable summary, is_active_warning_present).
    """
    if not warnings:
        return "No active EA flood warnings or alerts within 5 km.", False

    lines = []
    for w in warnings[:5]:  # cap at 5 for brevity
        sev = w.get("severity", 4)
        label = EA_SEVERITY_LABELS.get(sev, f"Severity {sev}")
        area = w.get("eaAreaName", w.get("description", "Unknown area"))
        lines.append(f"  • {label} — {area}")

    summary = (
        f"{len(warnings)} active EA flood warning(s) within {EA_WARNING_RADIUS_KM} km:\n"
        + "\n".join(lines)
    )
    return summary, True


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------
async def flood_risk_agent(state: AssessmentState) -> AssessmentState:
    """
    FloodRiskAgent — CYLTFR methodology.

    Sources:
      1. planning.data.gov.uk  — DEFRA Flood Zone (Rivers & Sea, authoritative)
      2. EA Flood Monitoring API — live flood warnings near property
    """
    errors: list[str] = []
    lat = state.get("latitude")
    lon = state.get("longitude")

    print("\n" + "=" * 60)
    print("[FloodRiskAgent] Starting — CYLTFR methodology")
    print(f"  lat={lat}, lon={lon}")
    print("=" * 60)

    if lat is None or lon is None:
        print("[FloodRiskAgent] No coordinates — flood zone cannot be evaluated")
        return {
            "raw_flood_data": {},
            "flood_zone": "unknown",
            "flood_risk_score": 20.0,
            "flood_risk_reasoning": (
                "No coordinates available — flood zone cannot be evaluated. "
                "Manual verification required."
            ),
            "data_collection_errors": ["Flood zone evaluation skipped: no coordinates."],
        }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # Run both lookups
        print(f"[FloodRiskAgent] Tool 1: planning.data.gov.uk flood-risk-zone at ({lat}, {lon})")
        zone_data = await _fetch_flood_zone_entities(client, lat, lon)

        print(f"[FloodRiskAgent] Tool 2: EA flood warnings within {EA_WARNING_RADIUS_KM}km of ({lat}, {lon})")
        warnings = await _fetch_ea_flood_warnings(client, lat, lon)

    # ---- Flood Zone (Rivers & Sea) ----------------------------------------
    zone = _parse_zone(zone_data)

    entities = zone_data.get("entities", zone_data.get("results", []))
    api_responded = bool(zone_data)  # True if we got any response at all

    if zone in ("1", "2", "3"):
        print(f"[FloodRiskAgent] DEFRA Flood Zone {zone} — {ZONE_RISK_LEVEL[zone]}")
        base_score = float(ZONE_SCORES[zone])
        zone_source = "planning.data.gov.uk"
    elif api_responded and isinstance(entities, list) and len(entities) == 0:
        # DEFRA only publishes explicit polygons for Zone 2 and Zone 3.
        # No entity returned = location is outside all Zone 2/3 polygons = Zone 1.
        zone = "1"
        base_score = float(ZONE_SCORES["1"])
        zone_source = "planning.data.gov.uk (no Zone 2/3 polygon — implicitly Zone 1)"
        print(f"[FloodRiskAgent] No Zone 2/3 entities → implicitly DEFRA Flood Zone 1 (Very Low)")
    else:
        zone = "unknown"
        base_score = float(ZONE_SCORES["unknown"])
        zone_source = "planning.data.gov.uk (API error or no response)"
        errors.append(
            "Flood zone data unavailable: planning.data.gov.uk did not respond. "
            "Manual verification required."
        )
        print("[FloodRiskAgent] API failure — zone UNKNOWN")

    # ---- EA live warnings — uplift score if active warnings present --------
    warnings_summary, has_active_warnings = _summarise_warnings(warnings)
    print(f"[FloodRiskAgent] EA warnings: {warnings_summary[:120]}")

    # Apply a score uplift if there are active warnings nearby
    # Uplift: +10 for Flood Alert, +20 for Flood Warning, +30 for Severe
    warning_uplift = 0
    if has_active_warnings:
        min_severity = min(w.get("severity", 4) for w in warnings)
        if min_severity == 1:
            warning_uplift = 30
        elif min_severity == 2:
            warning_uplift = 20
        elif min_severity == 3:
            warning_uplift = 10

    final_score = min(100.0, base_score + warning_uplift)
    print(f"[FloodRiskAgent] Score: base={base_score} + warning_uplift={warning_uplift} = {final_score}")

    # ---- Build reasoning (CYLTFR-style) ------------------------------------
    cyltfr_risk_types = (
        "CYLTFR assesses four flood sources: Rivers & Sea, Surface Water, "
        "Groundwater, and Reservoirs."
    )

    if zone == "unknown":
        zone_reasoning = (
            "Rivers & Sea: Flood Zone could not be determined — "
            "planning.data.gov.uk returned no flood zone data for this location. "
            f"A holding score of {base_score}/100 has been applied."
        )
    else:
        risk_level = ZONE_RISK_LEVEL[zone]
        probability = ZONE_PROBABILITY[zone]
        zone_reasoning = (
            f"Rivers & Sea: DEFRA Flood Zone {zone} — {risk_level} risk — "
            f"{probability}. Source: {zone_source}."
        )

    if has_active_warnings:
        warning_reasoning = (
            f"\nLive EA Data: {warnings_summary} "
            f"Score uplift of +{warning_uplift} applied."
        )
    else:
        warning_reasoning = f"\nLive EA Data: {warnings_summary}"

    sw_note = (
        "\nSurface Water / Groundwater / Reservoir risk: "
        "Indicative assessment only — check the full CYLTFR service at "
        "https://check-long-term-flood-risk.service.gov.uk for all four flood sources."
    )

    reasoning = (
        f"{cyltfr_risk_types}\n\n"
        f"{zone_reasoning}"
        f"{warning_reasoning}"
        f"{sw_note}\n\n"
        f"Overall flood risk score: {final_score}/100."
    )

    # ---- Assemble raw_flood_data -------------------------------------------
    raw_flood = {
        "source": "planning.data.gov.uk + EA Flood Monitoring API",
        "methodology": "CYLTFR (DEFRA Check Your Long Term Flood Risk)",
        "rivers_and_sea": {
            "flood_zone": zone,
            "risk_level": ZONE_RISK_LEVEL.get(zone, "Unknown"),
            "annual_probability": ZONE_PROBABILITY.get(zone, "Unknown"),
            "zone_source": zone_source,
        },
        "live_warnings": {
            "active_warnings_within_5km": len(warnings),
            "has_active_warnings": has_active_warnings,
            "summary": warnings_summary,
            "score_uplift": warning_uplift,
            "warnings": warnings[:5],  # store up to 5 for reference
        },
        "surface_water": {"note": "See CYLTFR service for RoFSW data"},
        "groundwater": {"note": "See CYLTFR service for groundwater risk"},
        "reservoirs": {"note": "See CYLTFR service for reservoir inundation zones"},
    }

    print(f"[FloodRiskAgent] Done — zone={zone!r} final_score={final_score}")

    return {
        "raw_flood_data": raw_flood,
        "flood_zone": zone,
        "flood_risk_score": final_score,
        "flood_risk_reasoning": reasoning,
        "data_collection_errors": errors,
    }
