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

import json
import boto3
import httpx
from datetime import date, timedelta
from src.agents.state.assessment_state import AssessmentState
from src.config.settings import settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
POSTCODES_IO_URL = "https://api.postcodes.io/postcodes"
IBEX_SEARCH_URL = f"{settings.IBEX_API_URL}/search"
IBEX_STATS_URL = f"{settings.IBEX_API_URL}/stats"
IBEX_APPS_BY_ID_URL = f"{settings.IBEX_API_URL}/applications-by-id"

# Complete IBEX council_id lookup — keyed by lowercase council name.
# Used to resolve council_id directly from postcodes.io admin_district name
# without needing a wide-radius /search fallback.
IBEX_COUNCIL_IDS: dict[str, int] = {
    "bolton": 1, "bradford": 2, "bury": 3, "calderdale": 4, "doncaster": 5,
    "gateshead": 6, "knowsley": 7, "north tyneside": 8, "oldham": 9, "rochdale": 10,
    "salford": 11, "sandwell": 12, "sefton": 13, "solihull": 14, "st helens": 15,
    "stockport": 16, "trafford": 17, "wakefield": 18, "wigan": 19, "wirral": 20,
    "islington": 231, "ealing": 280, "barking and dagenham": 366,
    "adur": 32, "adur and worthing": 32, "aylesbury vale": 33,
    "babergh": 34, "babergh and mid-suffolk": 34, "basildon": 35,
    "basingstoke and deane": 36, "bassetlaw": 37, "blaby": 38, "bolsover": 39,
    "braintree": 40, "brentwood": 41, "brighton and hove": 153, "bristol": 154,
    "bromley": 23, "bromsgrove": 113, "bromsgrove and redditch": 113,
    "broxtowe": 467, "broxbourne": 445, "brent": 281, "burnley": 43,
    "carlisle": 44, "castlepoint": 45, "chelmsford": 46, "cheltenham": 47,
    "chesterfield": 48, "chichester": 49, "chorley": 51, "corby": 52,
    "cotswold": 53, "craven": 54, "dacorum": 55, "dartford": 56,
    "darlington": 158, "derby": 159, "derbyshire dales": 57, "dover": 58,
    "durham": 157, "east cambridgeshire": 59, "east devon": 60,
    "east hampshire": 61, "east hertfordshire": 62, "east lindsey": 63,
    "east northamptonshire": 64, "east riding of yorkshire": 160,
    "east suffolk": 65, "east renfrewshire": 284, "east staffordshire": 228,
    "eastbourne": 468, "eastleigh": 469, "epsom and ewell": 67, "epsom ewell": 67,
    "epping forest": 229, "erewash": 348, "exeter": 68,
    "falkirk": 206, "fareham": 335, "fenland": 69, "fife": 207,
    "folkestone and hythe": 70, "forest of dean": 71, "fylde": 72,
    "gedling": 73, "gloucester city": 74, "gloucestershire": 291,
    "gosport": 75, "gravesham": 76, "guildford": 77, "hackney": 230,
    "hambleton": 78, "hammersmith and fulham": 275, "hammersmith & fulham": 275,
    "harborough": 79, "haringey": 254, "harlow": 80, "harrogate": 81,
    "harrow": 257, "hart": 82, "hartlepool": 255, "hastings": 83,
    "havant": 84, "havering": 245, "hertsmere": 277,
    "high peak": 270, "highland": 209, "hillingdon": 246,
    "hinckley and bosworth": 85, "horsham": 86, "hounslow": 262,
    "huntingdonshire": 87, "hyndburn": 696, "inverclyde": 210,
    "ipswich": 380, "isle of anglesey": 454, "isle of wight": 161,
    "isles of scilly": 700, "kettering": 411, "kings lynn and west norfolk": 293,
    "kings lynn & west norfolk": 293, "kingston": 276, "kensington and chelsea": 261,
    "kensington & chelsea": 261, "kirklees": 342, "lambeth": 26,
    "lancaster": 89, "leeds": 294, "leeds city": 294,
    "leicester city": 332, "lewes": 66, "lewisham": 27,
    "lichfield": 91, "lincoln": 92, "liverpool city": 232, "luton": 162,
    "maidstone": 132, "maidstone and swale": 132, "maldon": 94,
    "malvern hills": 687, "manchester city": 295, "mansfield": 95,
    "medway": 163, "melton": 96, "mendip": 97, "merton": 233,
    "mid devon": 98, "mid ulster": 684, "middlesbrough": 164,
    "midlothian": 211, "milton keynes": 165, "milton-keynes": 165,
    "mole valley": 319, "moray": 415,
    "newark and sherwood": 107, "newham": 28, "new forest": 106,
    "newcastle upon tyne": 424, "newcastle-under-lyme": 108,
    "newcastle upon tyne city": 424, "north ayrshire": 212,
    "north devon": 340, "north east derbyshire": 101,
    "north east lincolnshire": 166, "north hertfordshire": 102,
    "north kesteven": 103, "north lanarkshire": 213,
    "north lincolnshire": 455, "north norfolk": 104,
    "north somerset": 167, "north tyneside": 8,
    "north warwickshire": 271, "north west leicestershire": 105,
    "north york moors": 241, "north yorkshire": 724,
    "northumberland": 168, "norwich": 109,
    "nottingham city": 169, "nuneaton and bedworth": 407,
    "oadby and wigston": 110, "orkney islands": 214, "oxford": 111,
    "pembrokeshire": 450, "pendle": 112, "perth and kinross": 215,
    "peterborough": 170, "plymouth": 171, "poole": 299,
    "portsmouth": 172, "preston": 457,
    "reading": 328, "redbridge": 256, "redcar and cleveland": 458,
    "reigate and banstead": 114, "renfrewshire": 216,
    "ribble valley": 459, "richmond upon thames": 260, "richmondshire": 115,
    "rochford": 431, "rossendale": 116, "rother": 247,
    "rotherham": 327, "royal greenwich": 25, "rushcliffe": 117,
    "rushmoor": 118, "rutland": 173, "ryedale": 119,
    "salford": 11, "scarborough": 125, "scottish borders": 217,
    "sedgemoor": 460, "selby": 126, "sevenoaks": 127,
    "sheffield city": 302, "shetland islands": 218,
    "shropshire": 174, "slough": 321, "south ayrshire": 219,
    "south cambridgeshire": 287, "south derbyshire": 694,
    "south gloucestershire": 177, "south hams": 341,
    "south holland": 248, "south kesteven": 692,
    "south lanarkshire": 220, "south norfolk": 121, "south norfolk and broadland": 121,
    "south oxfordshire": 317, "south ribble": 122, "south somerset": 123,
    "south staffordshire": 124, "south tyneside": 235,
    "southampton": 175, "southend on sea": 176, "southend-on-sea": 176,
    "southwark": 29, "spelthorne": 449, "st albans": 258, "st albans city": 258,
    "stafford": 128, "staffordshire moorlands": 379,
    "stevenage": 129, "stirling": 221, "stockton-on-tees": 178,
    "stoke-on-trent": 179, "stratford-on-avon": 461, "stroud": 130,
    "sunderland": 309, "surrey heath": 131, "sutton": 30,
    "swansea": 188, "swindon": 180,
    "tameside": 311, "tamworth": 236, "tandridge": 448,
    "taunton": 666, "teignbridge": 344, "telford and wrekin": 470,
    "telford & wrekin": 470, "tendring": 133, "test valley": 134,
    "tewkesbury": 135, "thanet": 136, "three rivers": 278,
    "thurrock": 181, "tonbridge and malling": 137, "torbay": 182,
    "torridge": 138, "tower hamlets": 31, "tunbridge wells": 139,
    "uttlesford": 140, "vale of glamorgan": 463,
    "vale of white horse": 318, "walsall": 324, "waltham forest": 259,
    "wandsworth": 237, "warrington": 320, "warwick": 141,
    "watford": 279, "waverley": 336, "wealden": 432,
    "wellingborough": 142, "welwyn hatfield": 331,
    "west berkshire": 183, "west devon": 436,
    "west dunbartonshire": 451, "west lancashire": 285,
    "west lindsey": 452, "west lothian": 222,
    "west northamptonshire": 697, "west oxfordshire": 143,
    "west suffolk": 144, "westminster": 273,
    "westmorland and furness": 326, "westmorland & furness": 326,
    "winchester": 145, "windsor and maidenhead": 184,
    "woking": 146, "wokingham": 325, "wolverhampton": 286,
    "worcester city": 333, "wychavon": 434, "wyre": 149, "wyre forest": 464,
    "york": 185, "yorkshire dales": 435,
    # Scotland
    "aberdeen city": 194, "aberdeenshire": 195, "angus": 196,
    "argyll and bute": 197, "cairngorms national park": 693,
    "clackmannanshire": 198, "dumfries and galloway": 199,
    "dundee": 200, "east ayrshire": 201, "east dunbartonshire": 202,
    "east lothian": 203, "edinburgh": 204, "glasgow": 208,
    "na h-eileanan siar": 416, "north lanarkshire": 213,
    "perth and kinross": 215, "loch lomond and the trossachs": 421,
    # Wales
    "blaenau gwent": 702, "brecon beacons national park": 413,
    "bridgend": 428, "caerphilly": 186, "cardiff": 187,
    "carmarthenshire": 462, "ceredigion": 423, "conwy": 238,
    "denbighshire": 447, "flintshire": 440, "gwynedd": 422,
    "merthyr tydfil": 189, "monmouthshire": 190,
    "neath port talbot": 417, "newport": 337, "pembrokeshire coast national park": 691,
    "powys": 191, "rhondda cynon taf": 192, "snowdonia national park": 430,
    "torfaen": 193, "vale of glamorgan": 463, "wrexham": 439,
    # National Parks & Special
    "city of london": 414, "dartmoor national park": 686,
    "ebbsfleet": 685, "exmoor national park": 441,
    "lake district national park": 429, "london legacy development": 688,
    "new forest national park": 689, "north yorkshire moors": 241,
    "old oak and park royal": 690, "peak district": 699,
    "south downs national park": 419, "the broads authority": 420,
    # London Boroughs
    "barking and dagenham": 366, "barnet": 272, "bexley": 22,
    "camden": 240, "croydon": 274, "enfield": 24,
    "hackney": 230, "haringey": 254, "harrow": 257,
    "hounslow": 262, "lambeth": 26, "lewisham": 27,
    "newham": 28, "redbridge": 256, "richmond upon thames": 260,
    "southwark": 29, "tower hamlets": 31, "waltham forest": 259,
    # Combined/Unitary
    "barnsley": 427, "blackburn with darwen": 225,
    "blackpool": 151, "bournemouth": 338,
    "bournemouth christchurch and poole": 721, "bournemouth, christchurch, poole": 721,
    "bracknell forest": 152, "buckinghamshire": 120, "chiltern and south bucks": 120,
    "central and south bedfordshire": 456, "central & south bedfordshire": 456,
    "cheshire east": 683, "cheshire west and chester": 155,
    "copeland": 453, "cornwall": 156, "coventry city": 250,
    "dudley": 322, "guernsey": 251, "halton": 695, "hull city": 292,
    "north northamptonshire": 727,
    "northern ireland": 223,
    "somerset west and taunton": 303,
}

_ACTIVITY_LEVEL_SCORES: dict[str, float] = {
    "low": 5.0,
    "moderate": 15.0,
    "high": 35.0,
    "very high": 60.0,
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
            "heading": True,
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
        raw = resp.json()
        print(f"[PropertyValuationAgent] IBEX /search RAW JSON:\n{json.dumps(raw, indent=2)}")
        # API returns a bare list or a dict with an "applications" / "results" key
        if isinstance(raw, list):
            applications = raw
            data = {"applications": applications}
        else:
            applications = raw.get("applications", raw.get("results", []))
            data = raw
        n = len(applications) if isinstance(applications, list) else 0
        print(f"[PropertyValuationAgent] IBEX /search: {n} applications returned")
        if isinstance(applications, list) and applications:
            app = applications[0]
            print(f"[PropertyValuationAgent]   --- Sample application (first of {n}) ---")
            print(f"[PropertyValuationAgent]   council        : {app.get('council_name')}")
            print(f"[PropertyValuationAgent]   reference      : {app.get('planning_reference')}")
            print(f"[PropertyValuationAgent]   heading        : {app.get('heading')}")
            print(f"[PropertyValuationAgent]   type           : {app.get('normalised_application_type')}")
            print(f"[PropertyValuationAgent]   project_type   : {app.get('project_type')}")
            print(f"[PropertyValuationAgent]   decision       : {app.get('normalised_decision')}")
            print(f"[PropertyValuationAgent]   decided_date   : {app.get('decided_date')}")
            print(f"[PropertyValuationAgent]   new_houses     : {app.get('num_new_houses')}")
            print(f"[PropertyValuationAgent]   floor_area     : {app.get('proposed_floor_area')}")
            print(f"[PropertyValuationAgent]   appeal_status  : {app.get('appeal_status')}")
            print(f"[PropertyValuationAgent]   num_comments   : {app.get('num_comments_received')}")
            print(f"[PropertyValuationAgent]   proposal       : {str(app.get('proposal', ''))[:120]}")

            # Flag high-risk keywords in headings across all applications
            risk_keywords = ["demolition", "demolish", "hazardous", "contaminated", "basement excavation", "flood risk"]
            flagged = [
                f"{a.get('heading','')[:60]} ({a.get('normalised_decision')})"
                for a in applications
                if any(kw in (a.get("heading") or a.get("proposal") or "").lower() for kw in risk_keywords)
            ]
            if flagged:
                print(f"[PropertyValuationAgent]   ⚠ Risk keyword matches ({len(flagged)}):")
                for f in flagged[:5]:
                    print(f"[PropertyValuationAgent]     - {f}")
            else:
                print(f"[PropertyValuationAgent]   No risk keyword matches in headings")
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

    # Strategy 2: postcodes.io → name lookup in IBEX_COUNCIL_IDS map
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

            # Try direct name lookup first (fast, no extra API call)
            cid = IBEX_COUNCIL_IDS.get(admin_name.lower().strip())
            if cid:
                print(f"[PropertyValuationAgent] council_id={cid} ({admin_name}) resolved from name lookup map")
                return cid

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
                    wide_raw = wide_resp.json()
                    if isinstance(wide_raw, list):
                        wide_apps = wide_raw
                    else:
                        wide_apps = wide_raw.get("applications", wide_raw.get("results", []))
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
        print(f"[PropertyValuationAgent] IBEX /stats RAW JSON:\n{json.dumps(data, indent=2)}")
        _ar = data.get('approval_rate', 0) or 0
        _rr = data.get('refusal_rate', 0) or 0
        print(f"[PropertyValuationAgent] IBEX /stats response:")
        print(f"[PropertyValuationAgent]   activity_level   : {data.get('council_development_activity_level')}")
        print(f"[PropertyValuationAgent]   approval_rate    : {_ar * 100:.1f}%")
        print(f"[PropertyValuationAgent]   refusal_rate     : {_rr * 100:.1f}%")
        print(f"[PropertyValuationAgent]   new_homes        : {data.get('number_of_new_homes_approved')}")
        app_counts = data.get('number_of_applications', {})
        total = sum(app_counts.values()) if isinstance(app_counts, dict) else 0
        print(f"[PropertyValuationAgent]   total_apps       : {total}")
        if isinstance(app_counts, dict):
            top = sorted(app_counts.items(), key=lambda x: x[1], reverse=True)[:4]
            print(f"[PropertyValuationAgent]   top_app_types    : {', '.join(f'{k}({v})' for k,v in top)}")
        avg_times = data.get('average_decision_time', {})
        if isinstance(avg_times, dict):
            print(f"[PropertyValuationAgent]   avg_decision_days: {', '.join(f'{k}={round(v)}d' for k,v in list(avg_times.items())[:3])}")
        return data
    except Exception as e:
        print(f"[PropertyValuationAgent] IBEX /stats exception: {e}")
        return {}


async def _fetch_ibex_applications_by_id(
    client: httpx.AsyncClient,
    applications: list[tuple[int, str]],  # [(council_id, planning_reference), ...]
) -> list[dict]:
    """POST /applications-by-id — fetch full details for specific applications.
    Body format: {"applications": [[council_id, ref], ...], "extensions": {...}}
    """
    if not applications:
        return []
    body = {
        "applications": [[cid, ref] for cid, ref in applications],
        "extensions": {
            "documents": True,
            "appeals": True,
            "project_type": True,
            "heading": True,
        },
    }
    print(f"[PropertyValuationAgent] IBEX /applications-by-id POST — {len(applications)} app(s): {applications}")
    try:
        resp = await client.post(
            IBEX_APPS_BY_ID_URL,
            json=body,
            headers=_IBEX_HEADERS,
            timeout=15.0,
        )
        print(f"[PropertyValuationAgent] IBEX /applications-by-id HTTP {resp.status_code} — {len(resp.content)} bytes")
        if resp.status_code != 200:
            print(f"[PropertyValuationAgent] IBEX /applications-by-id error: {resp.text[:400]}")
            return []
        data = resp.json()
        print(f"[PropertyValuationAgent] IBEX /applications-by-id RAW JSON:\n{json.dumps(data, indent=2)}")
        results = data if isinstance(data, list) else data.get("applications", [])
        print(f"[PropertyValuationAgent] /applications-by-id: {len(results)} result(s)")
        for r in results:
            docs = r.get("documents") or []
            print(f"[PropertyValuationAgent]   ref={r.get('planning_reference')} heading={r.get('heading')} "
                  f"decision={r.get('normalised_decision')} docs={len(docs)}")
        return results
    except Exception as e:
        print(f"[PropertyValuationAgent] IBEX /applications-by-id exception: {e}")
        return []


def _analyse_construction_risk_with_llm(applications: list[dict]) -> dict:
    """
    Pass nearby planning application headings to Claude via Bedrock.
    Identifies demolition, excavation, hazardous materials, contamination,
    and large-scale construction — understanding context, not just keywords.

    Returns:
      {
        "risk_score": 0–30,       # contribution to final planning score
        "risk_instances": [...],  # list of identified risky activities
        "summary": "..."          # one-sentence summary
      }
    """
    if not applications:
        return {"risk_score": 0, "risk_instances": [], "summary": "No nearby applications to analyse."}

    # Build a compact list of headings for the LLM
    headings = []
    for app in applications[:20]:  # cap at 20 to keep prompt lean
        heading = app.get("heading") or app.get("proposal") or ""
        ref = app.get("planning_reference", "")
        decision = app.get("normalised_decision", "")
        if heading:
            headings.append(f"- [{ref}] {heading} ({decision})")

    if not headings:
        return {"risk_score": 0, "risk_instances": [], "summary": "No headings available to analyse."}

    prompt = f"""You are an expert insurance underwriter analysing nearby planning applications for a UK residential property insurance assessment.

Review the following planning application headings from within 500m of the subject property and identify activities that pose elevated risk to adjacent properties.

Risk categories:
- DEMOLITION: Full/partial demolition of structures (severity varies: shed=low, multi-storey=high)
- EXCAVATION: Basement excavation, underground works, deep foundations, piling
- HAZARDOUS: Asbestos removal, contaminated land remediation, hazardous material handling
- LARGE_SCALE: Major developments (10+ units, large commercial, significant infrastructure)
- CHANGE_OF_USE: Industrial/commercial to residential conversion (contamination risk)

Applications (within 500m):
{chr(10).join(headings)}

Return ONLY this JSON (no markdown, no explanation):
{{
  "risk_instances": [
    {{"reference": "...", "heading": "...", "risk_type": "DEMOLITION|EXCAVATION|HAZARDOUS|LARGE_SCALE|CHANGE_OF_USE", "severity": "low|medium|high", "reasoning": "one sentence"}}
  ],
  "risk_score": <integer 0-30>,
  "summary": "one sentence summarising construction risk near this property"
}}

Risk score guide: 0=no risk, 5=minor works only, 10=moderate construction, 20=major demolition/excavation, 30=hazardous/large-scale activity."""

    try:
        client = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)
        response = client.invoke_model(
            modelId=settings.BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": "You are an insurance underwriting specialist. Respond only with valid JSON.",
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )
        body = json.loads(response["body"].read())
        text = body["content"][0]["text"].strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        print(f"[PropertyValuationAgent] LLM construction risk: score={result.get('risk_score')} instances={len(result.get('risk_instances', []))}")
        print(f"[PropertyValuationAgent] LLM summary: {result.get('summary', '')}")
        for inst in result.get("risk_instances", []):
            print(f"[PropertyValuationAgent]   {inst.get('risk_type')} ({inst.get('severity')}) — {inst.get('heading', '')[:80]}")
        return result
    except Exception as e:
        print(f"[PropertyValuationAgent] LLM construction analysis failed: {e} — falling back to keyword scoring")
        return {"risk_score": 0, "risk_instances": [], "summary": f"LLM analysis unavailable: {e}"}


def _score_planning(stats: dict, search: dict, llm_construction: dict | None = None) -> tuple[float, str, str]:
    """Score planning risk 0-100 using stats (primary) + local search (supplement)."""
    # --- Stats-based score ---
    activity_level = str(stats.get("council_development_activity_level", "")).lower()
    base_score = _ACTIVITY_LEVEL_SCORES.get(activity_level, 0.0)

    new_homes = int(stats.get("number_of_new_homes_approved", 0) or 0)
    approval_rate = float(stats.get("approval_rate", 0) or 0)
    refusal_rate = float(stats.get("refusal_rate", 0) or 0)
    app_counts = stats.get("number_of_applications", {})
    total_apps = sum(app_counts.values()) if isinstance(app_counts, dict) else 0

    # API returns rates as decimals (0.0–1.0); convert to % for display
    approval_pct = approval_rate * 100
    refusal_pct = refusal_rate * 100
    print(f"[PropertyValuationAgent] Stats: activity={activity_level!r} total_apps={total_apps} "
          f"new_homes={new_homes} approval={approval_pct:.1f}% refusal={refusal_pct:.1f}%")

    stats_bonus = 0.0
    if new_homes > 500:
        stats_bonus += 8.0
    elif new_homes > 200:
        stats_bonus += 4.0
    if refusal_rate > 0.20:
        stats_bonus += 4.0

    # --- LLM construction risk (local radius) ---
    # Replaces keyword matching — Claude analyses headings in context and returns
    # a calibrated 0–30 score based on actual instances and their scale/severity.
    construction = llm_construction or {}
    construction_score = float(construction.get("risk_score", 0) or 0)
    construction_summary = construction.get("summary", "")
    risk_instances = construction.get("risk_instances", [])

    # Appeals still counted directly — LLM doesn't assess appeal risk
    applications = search.get("applications", search.get("results", []))
    local_count = len(applications) if isinstance(applications, list) else 0
    appeals = sum(1 for a in (applications or []) if a.get("appeal_status") or a.get("appeal_decision"))
    appeal_bonus = min(appeals * 3, 12.0)

    print(f"[PropertyValuationAgent] Construction: llm_score={construction_score} appeals={appeals} appeal_bonus={appeal_bonus}")
    print(f"[PropertyValuationAgent] Risk instances: {len(risk_instances)}")

    # --- Combine ---
    if base_score > 0:
        score = min(base_score + stats_bonus + construction_score + appeal_bonus, 100.0)
    else:
        score = min(construction_score + appeal_bonus, 100.0)

    if score < 25:
        label = "Low"
    elif score < 50:
        label = "Moderate"
    elif score < 75:
        label = "High"
    else:
        label = "Very High"

    reasoning = (
        f"Council activity: {activity_level or 'unknown'}. "
        f"{total_apps} council-level applications; {new_homes} new homes approved. "
        f"Approval rate {approval_pct:.1f}%, refusal rate {refusal_pct:.1f}%. "
        f"Local construction risk (LLM analysis of {local_count} applications within 500 m): {construction_summary} "
        f"{len(risk_instances)} risk instance(s) identified. {appeals} appeal(s)."
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

        # 4. Fetch full details for flagged high-risk applications via /applications-by-id
        risk_keywords = ["demolition", "demolish", "hazardous", "contaminated", "basement excavation", "flood risk"]
        applications_list = search_raw.get("applications", search_raw.get("results", []))
        flagged_apps: list[tuple[int, str]] = []
        if isinstance(applications_list, list):
            for app in applications_list:
                cid = app.get("council_id")
                ref = app.get("planning_reference")
                heading = (app.get("heading") or app.get("proposal") or "").lower()
                has_appeal = bool(app.get("appeal_status") or app.get("appeal_decision"))
                num_houses = int(app.get("num_new_houses") or 0)
                is_risky = (
                    any(kw in heading for kw in risk_keywords)
                    or has_appeal
                    or num_houses >= 10
                )
                if cid and ref and is_risky:
                    flagged_apps.append((int(cid), ref))
        flagged_apps = flagged_apps[:5]
        detailed_apps: list[dict] = []
        if flagged_apps:
            print(f"[PropertyValuationAgent] Tool: IBEX POST /applications-by-id — {len(flagged_apps)} flagged app(s)")
            detailed_apps = await _fetch_ibex_applications_by_id(client, flagged_apps)
        else:
            print(f"[PropertyValuationAgent] No flagged applications — skipping /applications-by-id")

    # 5. LLM construction risk analysis
    print(f"[PropertyValuationAgent] Tool: Claude (Bedrock) — LLM construction risk analysis")
    apps_for_llm = applications_list if isinstance(applications_list, list) else []
    llm_construction = _analyse_construction_risk_with_llm(apps_for_llm)

    # 6. Score
    score, label, reasoning = _score_planning(stats_raw, search_raw, llm_construction=llm_construction)
    applications = search_raw.get("applications", search_raw.get("results", []))
    local_count = len(applications) if isinstance(applications, list) else 0

    llm_summary = llm_construction.get("summary", "") if llm_construction else ""
    risk_instances = llm_construction.get("risk_instances", []) if llm_construction else []
    summary = (
        f"Property at ({lat:.4f}, {lon:.4f}). "
        f"Council planning activity: {label}. "
        f"{local_count} applications within 500 m. "
        f"Construction risk: {llm_summary} "
        f"({len(risk_instances)} risk instance(s) identified by LLM analysis)."
    )

    print(f"[PropertyValuationAgent] Done — score={score} label={label!r}")
    print(f"  reasoning: {reasoning}")

    return {
        "latitude": lat,
        "longitude": lon,
        "raw_planning_data": {
            "stats": stats_raw,
            "search": search_raw,
            "detailed_applications": detailed_apps,
            "llm_construction_risk": llm_construction,
        },
        "planning_risk_score": score,
        "planning_density_label": label,
        "planning_risk_reasoning": reasoning,
        "property_valuation_summary": summary,
        "data_collection_errors": errors,
    }
