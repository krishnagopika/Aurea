# Aurea — AI-Powered Residential Insurance Underwriting

Aurea is a multi-agent AI system that automates the underwriting of UK residential property insurance. Given a property address and postcode, Aurea runs a parallel pipeline of specialised agents — each pulling from a different authoritative data source — to produce a risk score, a premium multiplier, and a plain-English decision (accept / refer / decline) within seconds.

Built at Hack London 2025.

---

## The Problem

Traditional home insurance underwriting is slow, manual, and inconsistent. Underwriters must individually consult flood maps, planning portals, crime databases, and EPC registers — a process that can take hours per application and introduces significant human variability. Smaller insurers lack the tooling to do this at scale, leading to mispriced risk and poor customer experience.

**Aurea solves this by automating the entire data collection and decision pipeline** using a graph of specialised AI agents, each responsible for a single risk dimension, coordinated by a Claude-powered LLM synthesis layer.

---

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
Assesses **planning & development risk** around the property.

**Steps:**
1. Geocodes the address using Nominatim (OpenStreetMap)
2. Resolves the local council identifier via postcodes.io
3. Queries the IBEX Planning API (`POST /search`) for planning applications within a 500 m radius over the last 2 years
4. Queries the IBEX Planning API (`POST /stats`) for council-level development activity statistics
5. Scores planning risk (0–100) based on council activity level, new homes approved, appeal volumes, and large development proximity

**Risk output:** `planning_risk_score`, `planning_density_label` (Low / Moderate / High / Very High)

---

### 2. FloodRiskAgent
Assesses **flood risk** using the DEFRA "Check Your Long Term Flood Risk" (CYLTFR) methodology.

**Steps:**
1. Queries `planning.data.gov.uk/entity.json` for Flood Risk Zone entities at the property's coordinates
2. If no Zone 2 or Zone 3 polygon covers the point, the property is implicitly classified as Zone 1 — DEFRA only publishes explicit polygons for elevated-risk zones, so no entity returned means low risk
3. Queries the EA Flood Monitoring API for live flood warnings and alerts within 5 km
4. Applies a score uplift if active warnings are present (+10 alert, +20 warning, +30 severe)

**CYLTFR Zone definitions:**

| Zone | Risk Level | Annual Probability |
|------|------------|--------------------|
| 1 | Very Low | < 0.1% (< 1 in 1,000) |
| 2 | Low to Medium | 0.1% – 1% (1 in 1,000 to 1 in 100) |
| 3 | High | > 1% (> 1 in 100) |

**Risk output:** `flood_zone` (1 / 2 / 3 / unknown), `flood_risk_score`

---

### 3. EnvironmentalDataAgent
Assesses **property age and structural risk** using EPC certificate data.

**Steps:**
1. Queries the MHCLG EPC Open Data API for the property's postcode
2. Extracts the construction age band and property type from the most recent EPC record
3. Scores age risk using a lookup table (pre-1900 buildings score 80/100; 2012 onwards score 10/100)

**Risk output:** `property_age_band`, `property_type`, `property_age_risk_score`

---

### 4. LocalitySafetyAgent
Assesses **crime and neighbourhood safety risk**.

**Steps:**
1. Queries the Police UK API for all street-level crimes within a 1-mile radius
2. Tries up to 4 recent months to work around the API's typical 2–3 month publication lag
3. Weights crimes by insurance relevance: burglary (3.0×), criminal damage/arson (2.5×), robbery (1.5×), vehicle crime (1.0×), theft from person (0.8×), other (0.3×)
4. Applies the formula `min(weighted_total / 8, 100)` — approximately 800 weighted crime-points corresponds to the maximum score of 100

**Risk output:** `locality_safety_score`, `locality_safety_label` (Very Low / Low / Moderate / High / Very High Crime)

---

### 5. PolicyAgent
Retrieves **relevant insurance policy guidelines** using RAG (Retrieval-Augmented Generation).

**Steps:**
1. Builds a natural-language query from all current risk scores and labels
2. Queries MongoDB Atlas Vector Search (embeddings via Amazon Titan Embed v2) for the top-3 most relevant policy chunks
3. Policy chunks cover rules such as Zone 3 decline thresholds, Zone 2 elevated premiums, age-related excesses, and high-crime loadings

**Output:** `policy_context` — list of policy text chunks passed to the CoordinatorAgent

---

### 6. CoordinatorAgent
**LLM-powered synthesis** of all sub-agent scores into a single underwriting decision.

- Model: `claude-sonnet-4-6` via AWS Bedrock
- Receives all four risk scores, their labels, and the retrieved policy context
- Produces: `overall_risk_score`, `premium_multiplier` (0.80× – 3.00×), `decision` (accept / refer / decline), and `underwriter_reasoning`
- Falls back to a deterministic weighted average if Bedrock is unavailable

**Score weights:** Flood 40% · Property Age 25% · Planning 20% · Crime 15%

**Decision thresholds:**

| Score | Decision |
|-------|----------|
| < 60 | Accept |
| 60–79 | Refer |
| ≥ 80 | Decline |

---

### 7. ExplainabilityAgent
Generates a **structured, customer-facing explanation** of the decision.

- Model: `claude-sonnet-4-6` via AWS Bedrock
- Produces a `risk_factors` breakdown (name, score, weight, one-sentence reasoning per factor), `policy_citations`, and a `plain_english_narrative` (3–5 sentences for the customer)
- Falls back to a deterministic template if Bedrock is unavailable

---

## Data Sources

| Source | What it provides | Agent |
|--------|-----------------|-------|
| [IBEX Planning API](https://ibex.co.uk) | Nearby planning applications, council-level development statistics, appeals data | PropertyValuationAgent |
| [Nominatim / OpenStreetMap](https://nominatim.org) | Free address geocoding (lat/lon) | PropertyValuationAgent |
| [postcodes.io](https://postcodes.io) | Postcode metadata, council district resolution | PropertyValuationAgent |
| [planning.data.gov.uk](https://www.planning.data.gov.uk) | DEFRA Flood Risk Zone polygons — MHCLG authoritative source | FloodRiskAgent |
| [EA Flood Monitoring API](https://environment.data.gov.uk/flood-monitoring/doc/reference) | Live EA flood warnings and alerts (free, no auth) | FloodRiskAgent |
| [EPC Open Data — MHCLG](https://epc.opendatacommunities.org) | Energy Performance Certificate records — construction age, property type | EnvironmentalDataAgent |
| [Police UK API](https://data.police.uk) | Street-level crime data by month (free, no auth) | LocalitySafetyAgent |
| [MongoDB Atlas Vector Search](https://www.mongodb.com/atlas) | Semantic policy document retrieval (RAG) | PolicyAgent |
| [AWS Bedrock — Claude Sonnet 4.6](https://aws.amazon.com/bedrock) | LLM underwriting synthesis and plain-English explanation | CoordinatorAgent, ExplainabilityAgent |
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

# IBEX Planning API
IBEX_API_URL=https://api.ibex.co.uk
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

### Run an underwriting assessment

```bash
curl -X POST http://localhost:8000/api/v1/underwriting/assess \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "122, Leadenhall Street, City of London",
    "postcode": "EC3V 4AB"
  }'
```

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
| 10 Wimpole Street, London | W1G 9SP | Prime Marylebone, modern refurb, well-managed area, very low flood and crime risk |

---

#### High Planning & Development Risk

High council development activity, large-scale nearby schemes, or high volumes of planning applications — drives up `planning_risk_score`.

| Address | Postcode | Why |
|---------|----------|-----|
| Battersea Power Station, London | SW8 5BN | Nine Elms regeneration zone — one of Europe's largest active development sites |
| 1 Olympic Way, Stratford, London | E20 1EJ | Post-Olympics development corridor, ongoing residential and commercial applications |
| 10 Old Street, London | EC1V 9BD | Tech City / Silicon Roundabout — extremely high planning application density |
| 1 Spinningfields, Manchester | M3 3AP | Major Manchester regeneration area, very high council development activity |

---

#### High Flood Risk (Zone 3)

These locations fall within or near DEFRA Flood Zone 3 (>1% annual probability of flooding from rivers or sea).

| Address | Postcode | Why |
|---------|----------|-----|
| High Street, Tewkesbury | GL20 5AD | Tewkesbury is one of England's most flood-prone towns — at the confluence of the Severn and Avon |
| King's Staith, York | YO1 9SN | Riverside York — regularly inundated; Ouse flood events are well-documented |
| Thames Street, Windsor | SL4 1PL | Thames riverside Zone 3; flooding during 2014 and 2020 events |
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

