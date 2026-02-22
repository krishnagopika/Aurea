# Aurea — AI-Powered Residential Insurance Underwriting

Aurea is a multi-agent AI system that automates the underwriting of UK residential property insurance. Given a property address and postcode, Aurea runs a parallel pipeline of specialised agents — each pulling from a different authoritative data source — to produce a risk score, a premium multiplier, and a plain-English decision (accept / refer / decline) within seconds.

Built at Hack London 2025.

---

## The Problem

Traditional home insurance underwriting is slow, manual, and inconsistent. Underwriters must individually consult flood maps, planning portals, crime databases, and EPC registers — a process that can take hours per application and introduces significant human variability. Smaller insurers lack the tooling to do this at scale, leading to mispriced risk and poor customer experience.

**Aurea solves this by automating the entire data collection and decision pipeline** using a graph of specialised AI agents, each responsible for a single risk dimension, coordinated by a Claude-powered LLM synthesis layer.

---

[live demo] (http://ec2-18-208-224-149.compute-1.amazonaws.com)

## Architecture Overview

The system is a **LangGraph agent graph** running on a FastAPI backend. Data agents run in parallel; the LLM synthesis layer runs sequentially after.

```
Input (address + postcode)
         │
         ▼
┌─────────────────────────────────────────────────────┐
│              Parallel Data Collection               │
│                                                     │
│  PropertyValuationAgent  │  FloodRiskAgent          │
│  EnvironmentalDataAgent  │  LocalitySafetyAgent     │
└──────────────┬──────────────────────────────────────┘
               │  all scores + raw data
               ▼
         PolicyAgent  (RAG — MongoDB Atlas Vector Search)
               │  relevant policy chunks
               ▼
       CoordinatorAgent  (AWS Bedrock / Claude)
               │  decision + overall score
               ▼
      ExplainabilityAgent  (AWS Bedrock / Claude)
               │
               ▼
         API Response
```

---

## Agents

### 1. PropertyValuationAgent
Assesses **planning & development risk** using the [IBEX Planning API](https://ibex.seractech.co.uk) by Serac Technologies.

**Data retrieved:**
- Nearby planning applications within 500 m (heading, decision, appeals, new houses, floor area, project type, comment count)
- Council-level statistics (activity level, approval rate, refusal rate, new homes approved, application counts by type)
- Full details for flagged high-risk applications (conditional — demolition, hazardous materials, 10+ houses, active appeals)

**Flow:**
1. Geocode address → lat/lon via Nominatim
2. `IBEX POST /search` (500 m radius) — fetch nearby applications + extract `council_id`
   - Fallback A: postcodes.io → council name lookup map
   - Fallback B: `IBEX POST /search` (2000 m wide radius)
3. `IBEX POST /stats` (council_id) — fetch council-level development statistics
4. `IBEX POST /applications-by-id` (conditional) — full details for up to 5 flagged applications
5. **LLM construction risk analysis** — all application headings passed to Claude Sonnet 4.6 via AWS Bedrock; Claude identifies instances of demolition, excavation, hazardous materials, large-scale development, and change-of-use, scoring each by severity (low / medium / high); returns a calibrated `risk_score` (0–30) and a list of identified risk instances

**Risk score (0–100):**
```
base score        = council activity level  (low=5, moderate=15, high=35, very high=60)
stats bonus       = +8 if >500 new homes approved
                  + +4 if >200 new homes approved
                  + +4 if refusal rate >20%
llm_construction  = Claude-assigned score 0–30 (demolition/excavation/hazardous/large-scale)
appeal bonus      = appeals × 3, capped at 12
final score       = base + stats_bonus + llm_construction + appeal_bonus
```

| Score | Label |
|-------|-------|
| 0–24 | Low |
| 25–49 | Moderate |
| 50–74 | High |
| 75–100 | Very High |

---

### 2. FloodRiskAgent
Assesses **flood risk** using the DEFRA CYLTFR methodology, augmented with IBEX planning data.

**Data retrieved:**
- DEFRA Flood Risk Zone polygons at the property's exact coordinates (planning.data.gov.uk)
- Live EA flood warnings and alerts within 5 km (EA Flood Monitoring API)
- Nearby planning applications within 500 m that mention flood risk in their heading (IBEX)

**Flow:**
1. Query `planning.data.gov.uk` for flood-risk-zone entities at the property coordinates
   - Zone 2/3 polygon present → classify accordingly
   - No polygon returned → implicitly Zone 1 (DEFRA only publishes elevated-risk polygons)
2. Query EA Flood Monitoring API for active warnings within 5 km
3. `IBEX POST /search` (500 m radius) — count applications mentioning flood risk, drainage assessments, SUDS, sequential test in heading

**Risk score (0–100):**
```
base score     = flood zone  (Zone 1=5, Zone 2=45, Zone 3=85, unknown=20)
warning uplift = +10 flood alert  |  +20 flood warning  |  +30 severe warning
ibex uplift    = +4 if 1 nearby flood-risk app  |  +8 if 2–4  |  +15 if 5+
final score    = min(base + warning_uplift + ibex_uplift, 100)
```

| Zone | Risk Level | Annual Probability |
|------|------------|--------------------|
| 1 | Very Low | < 0.1% |
| 2 | Low to Medium | 0.1% – 1% |
| 3 | High | > 1% |

---

### 3. EnvironmentalDataAgent
Assesses **property age and building quality risk** using EPC certificate data. Also extracts a full structured property profile returned to the frontend as informational display.

**Data retrieved:**
- Construction age band (e.g. "before 1900", "2012 onwards")
- Property type (House, Flat, Maisonette, Bungalow)
- Built form (Detached, Semi-Detached, Mid-Terrace, End-Terrace)
- Current EPC energy rating (A–G)
- Total floor area (m²)
- Number of habitable rooms
- Wall construction description (e.g. "Cavity wall, as built, no insulation")
- Roof description (e.g. "Pitched, 270 mm loft insulation")
- Floor description
- Glazing type (double / single)
- Main heating system description
- Confirmed address from EPC record

**Flow:**
1. Query MHCLG EPC Open Data API (`/api/v1/domestic/search`) by postcode — up to 5 records
2. If empty body returned, retry with outward code only (e.g. `M145TL` → `M14`)
3. Extract all EPC fields from most recent record; build structured `property_details` dict
4. Score age band and energy rating separately; blend into composite risk score
5. `property_details` is passed through to the API response and displayed in the frontend as a Property Details card (sourced from the EPC Register)

**Risk score (0–100):**
```
age score     = lookup table (pre-1900=80, 1900–29=65, ..., 2012+=10)
energy score  = A=5, B=15, C=30, D=50, E=65, F=80, G=95
final score   = age_score × 70% + energy_score × 30%
              (falls back to age-only if energy rating unavailable)
```

---

### 4. LocalitySafetyAgent
Assesses **crime and neighbourhood safety risk**.

**Data retrieved:**
- All street-level crimes within 1-mile radius over the past 12 months (Police UK API)
- Crime categories: burglary, criminal damage/arson, robbery, vehicle crime, theft from person, and all other categories

**Flow:**
1. Probe up to 4 months back to find the most recent available month (API has 2–3 month publication lag)
2. Fetch all 12 months in parallel using `asyncio.gather`
3. Aggregate all crimes and apply category weights

**Risk score (0–100):**
```
weighted_total = Σ (crime_count × weight)
  weights: burglary=3.0, criminal-damage-arson=2.5, robbery=1.5,
           vehicle-crime=1.0, theft-from-person=0.8, other=0.3
final score = min(weighted_total / 96, 100)
  divisor 96 = 8 per month × 12 months
```

| Score | Label |
|-------|-------|
| 0–19 | Very Low Crime |
| 20–39 | Low Crime |
| 40–59 | Moderate Crime |
| 60–79 | High Crime |
| 80–100 | Very High Crime |

---

### 5. PolicyAgent
Retrieves **relevant insurance policy guidelines** using RAG.

**Data retrieved:**
- Top 3 most semantically relevant policy chunks from MongoDB Atlas Vector Search
- Embeddings generated via Amazon Titan Embed Text v2

**Flow:**
1. Build a natural-language query from all four risk scores and labels
2. Embed the query and search MongoDB Atlas Vector Search
3. Return top-3 policy chunks to the CoordinatorAgent as context

---

### 6. CoordinatorAgent
**LLM synthesis** of all sub-agent scores into a single underwriting decision.

**Data received:**
- All four risk scores and labels from data agents
- Retrieved policy context from PolicyAgent

**Flow:**
1. Construct prompt with all scores, labels, and policy guidelines
2. Invoke Claude Sonnet 4.6 via AWS Bedrock
3. Parse structured JSON response
4. Falls back to deterministic weighted average if Bedrock is unavailable

**Final risk score (fallback formula):**
```
overall_risk_score = flood×0.40 + planning×0.20 + age×0.25 + crime×0.15
premium_multiplier = 1.0 + (overall_risk_score / 100) × 2.0  (clamped 0.80–3.00)
```

**Decision thresholds:**

| Overall Score | Decision |
|---------------|----------|
| < 60 | Accept |
| 60–79 | Refer |
| ≥ 80 | Decline |

---

### 7. ExplainabilityAgent
Generates a **customer-facing explanation** of the decision.

**Flow:**
1. Invoke Claude Sonnet 4.6 via AWS Bedrock with the full decision context
2. Produce structured JSON: `risk_factors` (name, score, weight, one-sentence reasoning per factor), `policy_citations`, `plain_english_narrative`
3. Falls back to a deterministic template if Bedrock is unavailable

---

## Data Sources

| Source | What it provides | Agent |
|--------|-----------------|-------|
| [IBEX Planning API — Serac Technologies](https://ibex.seractech.co.uk) | Nearby planning applications, council-level development statistics, appeals data | PropertyValuationAgent |
| [Nominatim / OpenStreetMap](https://nominatim.org) | Free address geocoding (lat/lon) | PropertyValuationAgent |
| [postcodes.io](https://postcodes.io) | Postcode metadata, council district resolution | PropertyValuationAgent |
| [planning.data.gov.uk](https://www.planning.data.gov.uk) | DEFRA Flood Risk Zone polygons — MHCLG authoritative source | FloodRiskAgent |
| [EA Flood Monitoring API](https://environment.data.gov.uk/flood-monitoring/doc/reference) | Live EA flood warnings and alerts (free, no auth) | FloodRiskAgent |
| [EPC Open Data — MHCLG](https://epc.opendatacommunities.org) | Energy Performance Certificate records — construction age, property type | EnvironmentalDataAgent |
| [Police UK API](https://data.police.uk) | Street-level crime data by month (free, no auth) | LocalitySafetyAgent |
| [MongoDB Atlas Vector Search](https://www.mongodb.com/atlas) | Semantic policy document retrieval (RAG) | PolicyAgent |
| [AWS Bedrock — Claude Sonnet 4.6](https://aws.amazon.com/bedrock) | LLM construction risk analysis from planning headings; underwriting synthesis; plain-English explanation | PropertyValuationAgent, CoordinatorAgent, ExplainabilityAgent |
| [Amazon Titan Embed Text v2](https://aws.amazon.com/bedrock) | Generating embeddings for RAG policy retrieval | PolicyAgent / PolicyService |

---

## Tech Stack

**Backend**
- Python 3.11+
- FastAPI + Uvicorn
- LangGraph (agent orchestration)
- Beanie ODM + MongoDB Atlas (policy store + vector search)
- AWS Bedrock (Claude Sonnet 4.6 + Amazon Titan Embeddings)
- httpx (async HTTP client)

**Frontend**
- Next.js 14 (TypeScript)
- Tailwind CSS
- Framer Motion
- React Leaflet (interactive map)

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- A MongoDB Atlas cluster with vector search enabled
- AWS account with Bedrock access (Claude Sonnet 4.6 + Titan Embeddings v2 in `us-east-1`)
- API keys for IBEX and the MHCLG EPC Open Data API

### 1. Clone the repository

```bash
git clone https://github.com/your-org/aurea.git
cd aurea
```

### 2. Configure environment variables

Create `backend/.env`:

```env
# MongoDB
MONGO_USER=your_mongo_user
MONGODB_PASSWORD=your_mongo_password
MONGO_CLUSTER=your-cluster.mongodb.net
MONGO_APPNAME=aurea
MONGO_DB=aurea

# AWS Bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6
BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0

# IBEX Planning API (Serac Technologies)
IBEX_API_URL=https://ibex.seractech.co.uk
IBEX_API_KEY=your_ibex_key

# EPC Open Data API (MHCLG)
# Key is your email:password encoded as Base64
EPC_API_URL=https://epc.opendatacommunities.org
EPC_API_KEY=your_base64_encoded_credentials

# JWT (change in production)
JWT_SECRET_KEY=change_me_in_production

# CORS (comma-separated origins, or * for development)
ALLOW_ORIGINS=http://localhost:3000
```

### 3. Start the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.
Interactive docs (Swagger UI): `http://localhost:8000/docs`

On first startup, the server automatically seeds the MongoDB collection with policy document chunks and registers them in the vector search index.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`.

---

## API Usage

### Authenticate

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'
```

Returns a JWT token. Pass it as `Authorization: Bearer <token>` on subsequent requests.

### Run an underwriting assessment (blocking)

```bash
curl -X POST http://localhost:8000/api/v1/underwriting/assess \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "122, Leadenhall Street, City of London",
    "postcode": "EC3V 4AB"
  }'
```

### Run an assessment with real-time agent streaming (SSE)

The frontend uses this endpoint to display live agent progress as each node in the pipeline completes.

```bash
curl -X POST http://localhost:8000/api/v1/underwriting/assess-stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "122, Leadenhall Street, City of London",
    "postcode": "EC3V 4AB"
  }'
```

Returns `text/event-stream` with one JSON payload per line:

```
data: {"type": "agent_start", "agent": "PropertyValuationAgent"}
data: {"type": "agent_end",   "agent": "PropertyValuationAgent"}
data: {"type": "agent_start", "agent": "FloodRiskAgent"}
data: {"type": "agent_start", "agent": "EnvironmentalDataAgent"}
data: {"type": "agent_start", "agent": "LocalitySafetyAgent"}
data: {"type": "agent_end",   "agent": "FloodRiskAgent"}
data: {"type": "agent_end",   "agent": "EnvironmentalDataAgent"}
data: {"type": "agent_end",   "agent": "LocalitySafetyAgent"}
data: {"type": "agent_start", "agent": "PolicyAgent"}
...
data: {"type": "result", "data": { ...AssessmentResponse... }}
data: [DONE]
```

The three parallel agents (`FloodRiskAgent`, `EnvironmentalDataAgent`, `LocalitySafetyAgent`) emit their `agent_start` events simultaneously when `PropertyValuationAgent` completes, accurately reflecting the LangGraph fan-out.

**Example response:**

```json
{
  "decision": "accept",
  "overall_risk_score": 42.5,
  "premium_multiplier": 1.35,
  "flood_zone": "1",
  "flood_risk_score": 5.0,
  "planning_risk_score": 12.0,
  "property_age_risk_score": 65.0,
  "locality_safety_score": 38.5,
  "locality_safety_label": "Low Crime",
  "risk_factors": [
    {
      "name": "Flood Risk",
      "score": 5,
      "weight": 0.40,
      "reasoning": "Property is in DEFRA Flood Zone 1 — very low probability of flooding."
    }
  ],
  "policy_citations": ["Standard Home Policy v2 – Flood Zone 1 Standard Terms"],
  "plain_english_narrative": "Your property at 122 Leadenhall Street has been assessed as low risk overall...",
  "underwriter_reasoning": "..."
}
```

### Example addresses to test

These addresses are chosen to exercise each risk dimension of the pipeline. Use them during demos to show the full range of underwriting outcomes.

#### Low Risk — Easy Accept

| Address | Postcode | Why |
|---------|----------|-----|
| 1 Kidbrooke Park Road, London | SE3 9FU | Modern new-build (Kidbrooke Village regeneration), Zone 1 flood, low crime suburban SE London |

---

#### High Planning & Development Risk

High council development activity, large-scale nearby schemes, or high volumes of planning applications — drives up `planning_risk_score`.

| Address | Postcode | Why |
|---------|----------|-----|
| Battersea Power Station, London | SW8 5BN | Nine Elms regeneration zone — one of Europe's largest active development sites |
| 10 Wimpole Street, London | W1G 9SP | Prime Marylebone, medium planning, modern refurb, well-managed area, very low flood risk |
| 10 Old Street, London | EC1V 9BD | Tech City / Silicon Roundabout — low - medium planning application density |

---

#### High Flood Risk (Zone 3)

These locations fall within or near DEFRA Flood Zone 3 (>1% annual probability of flooding from rivers or sea).

| Address | Postcode | Why |
|---------|----------|-----|
| Skeldergate, York | YO1 6HH | Riverside York — Skeldergate sits directly on the Ouse flood plain; regularly inundated during winter events |
| The Quayside, Newcastle upon Tyne | NE1 3DE | Tyne riverside — Zone 2/3 boundary, tidal flood risk |
| Riverside Road, Norwich | NR1 1SR | Wensum flood plain; historically Zone 3 in large sections |

---

#### High Crime Risk

Dense urban areas with high Police UK recorded crime counts — drives up `locality_safety_score`.

| Address | Postcode | Why |
|---------|----------|-----|
| Soho Road, Handsworth, Birmingham | B21 9SX | Among the highest burglary and violent crime rates in the West Midlands |
| Pembury Road, Hackney, London | E5 8AN | High theft, robbery and criminal damage counts; consistently elevated in Police UK data |
| Church Street, Croydon | CR0 1RN | Croydon town centre — high vehicle crime, theft and antisocial behaviour |
| Moss Lane East, Moss Side, Manchester | M14 4PX | Historically one of Manchester's highest crime-density postcodes |
| Granby Street, Leicester | LE1 6FB | City centre — high footfall crime, theft from person and shoplifting volumes |

---

#### High Property Age / Environmental Risk

Pre-1900 or early 20th-century stock scores highest on `property_age_risk_score` (80/100 for pre-1900, 65/100 for 1900–1929).

| Address | Postcode | Why |
|---------|----------|-----|
| Gambier Terrace, Liverpool | L1 7BN | Georgian terraces, mostly pre-1900; EPC records consistently show oldest age band |
| Brady Street, Whitechapel, London | E1 5DJ | Victorian East End terraces; high proportion of pre-1900 EPC records |
| Pollard Street, Ancoats, Manchester | M4 7AQ | Victorian mill district; some of Manchester's oldest surviving residential stock |
| Tredegar Square, Bow, London | E3 5AD | Victorian conservation area; well-preserved but aged housing stock |
| Horton Street, Halifax | HX1 1QE | West Yorkshire mill town; predominantly pre-1920 stone-built terraces |


notes: 

- home owners and tenants variation 
