"""
PolicyService
=============
Handles:
  - Seeding the MongoDB policy_chunks collection with pre-written policy text on startup
  - Embedding text using Amazon Titan Embed Text v2 via AWS Bedrock
  - Retrieving relevant policy chunks using MongoDB Atlas Vector Search ($vectorSearch)
  - Falling back to simple .find().limit() if the vector index is not yet configured
"""

import json
import boto3
from src.models.policy import PolicyChunk
from src.config.settings import settings

POLICY_SEED_DATA = [
    # ── Standard Home Policy v2 ──────────────────────────────────────────────
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Flood Zone 3 Decline Rule",
        "content": (
            "Properties located in Flood Risk Zone 3 (high probability of flooding, >1% annual chance) "
            "are DECLINED for standard coverage. No exceptions apply unless substantial flood defences "
            "are confirmed in writing by the Environment Agency."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Flood Zone 2 Elevated Premium",
        "content": (
            "Properties in Flood Risk Zone 2 (medium probability, 0.1%–1% annual chance) are accepted "
            "with an elevated premium multiplier of 1.5x to 2.0x depending on overall risk profile. "
            "A flood excess of £2,500 applies to all flood-related claims."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Flood Zone 1 Standard Terms",
        "content": (
            "Properties in Flood Risk Zone 1 (low probability, <0.1% annual chance) qualify for standard "
            "flood coverage with no additional loading. Standard flood excess of £500 applies."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Pre-1900 Property Conditions",
        "content": (
            "Properties constructed before 1900 require a full structural survey before acceptance. "
            "Subsidence, settlement, and roof condition must be confirmed satisfactory. "
            "A minimum premium loading of 1.3x applies. Refer to senior underwriter if overall score exceeds 70."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Modern Construction Discount",
        "content": (
            "Properties built after 2000 with an EPC rating of C or above qualify for a premium discount "
            "of up to 10%. Modern construction standards, better insulation, and regulatory compliance "
            "reduce structural and environmental risk significantly."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "High Development Density Conditions",
        "content": (
            "Areas with high or very high planning activity (planning score > 50) indicate significant nearby "
            "construction risk including subsidence, ground movement, and increased claims frequency. "
            "Apply a planning risk loading of 1.15x to the base premium."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Appeals and Planning Disputes",
        "content": (
            "Proximity to active planning appeals (within 500 m) indicates contested development and "
            "potential neighbourhood change risk. Each active appeal adds to the planning risk score. "
            "More than 3 active appeals in the area triggers mandatory senior underwriter review."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Standard Acceptance Criteria",
        "content": (
            "Properties with an overall risk score below 40 qualify for standard rates with a premium "
            "multiplier of 0.8x to 1.0x. These are typically properties in Flood Zone 1, with modern "
            "construction (post-2000), and low planning activity in the vicinity."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Refer to Underwriter Conditions",
        "content": (
            "Any property scoring 60–79 overall must be referred to a senior underwriter for manual review. "
            "The automated decision is advisory only. Mandatory referral triggers include: conflicting flood "
            "zone data, listed buildings, recent subsidence claims, flood zone data unavailable, "
            "or unusual construction methods."
        ),
    },
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Flood Zone Data Unavailable",
        "content": (
            "Where flood zone classification cannot be confirmed from Environment Agency or planning data sources, "
            "the property must be referred for manual underwriter review. A neutral holding score applies and "
            "the automated accept/decline decision must not be issued without verified flood zone data."
        ),
    },

    # ── High Value Home Policy v1 ────────────────────────────────────────────
    {
        "policy_name": "High Value Home Policy v1",
        "section": "Eligibility",
        "content": (
            "Designed for residential properties with a rebuild value exceeding £750,000 or contents value "
            "exceeding £100,000. Provides agreed-value buildings cover, all-risks contents, and fine art cover. "
            "Requires a professional rebuild valuation no older than 3 years."
        ),
    },
    {
        "policy_name": "High Value Home Policy v1",
        "section": "Flood Risk Acceptance",
        "content": (
            "High Value properties in Flood Zone 2 may be accepted subject to a premium multiplier of 1.8x–2.5x "
            "and a minimum flood excess of £5,000. Properties in Flood Zone 3 are declined unless a flood "
            "resilience survey confirms defences rated for a 1-in-200-year event."
        ),
    },
    {
        "policy_name": "High Value Home Policy v1",
        "section": "Listed and Heritage Buildings",
        "content": (
            "Grade I and Grade II* listed buildings require specialist reinstatement cover. Standard rebuilding "
            "cost calculators do not apply. A mandatory 1.4x premium loading and senior underwriter sign-off "
            "are required. Properties in conservation areas carry an additional 1.1x loading."
        ),
    },
    {
        "policy_name": "High Value Home Policy v1",
        "section": "Pre-1900 High Value Conditions",
        "content": (
            "High-value properties built before 1900 must provide a structural engineer's report within the "
            "last 5 years confirming no active subsidence or foundation movement. Premium loading of 1.5x "
            "applies. Roof replacement history required if original or pre-1950 materials present."
        ),
    },

    # ── Landlord Buy-to-Let Policy v1 ────────────────────────────────────────
    {
        "policy_name": "Landlord Buy-to-Let Policy v1",
        "section": "Eligibility and Property Types",
        "content": (
            "Covers residential properties let on AST (Assured Shorthold Tenancy) agreements in England and Wales. "
            "HMOs (Houses in Multiple Occupation) of up to 6 bedrooms are eligible. Student lets, DSS tenants, "
            "and short-term holiday lets require declaration at inception."
        ),
    },
    {
        "policy_name": "Landlord Buy-to-Let Policy v1",
        "section": "Flood Zone Restrictions",
        "content": (
            "Buy-to-let properties in Flood Zone 3 are declined. Flood Zone 2 properties are accepted at "
            "2.0x–2.5x multiplier with a £3,500 flood excess and mandatory flood resilience measures confirmed "
            "by the letting agent or property manager within the last 12 months."
        ),
    },
    {
        "policy_name": "Landlord Buy-to-Let Policy v1",
        "section": "High Planning Activity Areas",
        "content": (
            "Landlord properties in high or very high planning activity areas (planning score > 60) carry "
            "increased risk of void periods due to construction noise and access disruption. "
            "Apply a 1.1x planning loading and note the risk factor in the underwriting rationale."
        ),
    },
    {
        "policy_name": "Landlord Buy-to-Let Policy v1",
        "section": "Property Age and Condition",
        "content": (
            "Pre-1950 rental properties must have electrical installation condition reports (EICR) and gas safety "
            "certificates no older than 1 year. Pre-1900 properties require structural survey. "
            "Missing compliance documents result in automatic referral to senior underwriter."
        ),
    },

    # ── New Build Warranty Policy v1 ─────────────────────────────────────────
    {
        "policy_name": "New Build Warranty Policy v1",
        "section": "Eligibility",
        "content": (
            "Covers newly constructed residential properties (build completion within last 10 years) with a "
            "valid NHBC Buildmark, Premier Guarantee, or equivalent structural warranty. Provides buildings "
            "cover at standard rates with reduced excess given modern construction standards."
        ),
    },
    {
        "policy_name": "New Build Warranty Policy v1",
        "section": "Flood Zone Terms",
        "content": (
            "New build properties in Flood Zone 1 qualify for the lowest available premium band (0.75x multiplier). "
            "New builds in Flood Zone 2 require confirmation that the development's drainage infrastructure was "
            "approved under SuDS (Sustainable Drainage Systems) regulations — multiplier 1.2x. "
            "New builds in Flood Zone 3 are declined regardless of individual flood resilience measures."
        ),
    },
    {
        "policy_name": "New Build Warranty Policy v1",
        "section": "High Development Density",
        "content": (
            "New build properties within high-density planning areas benefit from reduced construction risk "
            "(modern materials and compliance) but may face elevated ground movement risk from adjacent "
            "development. A precautionary 1.05x loading applies where planning score exceeds 70."
        ),
    },

    # ── Commercial Conversion Policy v1 ──────────────────────────────────────
    {
        "policy_name": "Commercial Conversion Policy v1",
        "section": "Mixed Use Property",
        "content": (
            "Properties converted from commercial to residential use require confirmation of building "
            "regulations compliance post-conversion. A risk score loading of 1.2x applies to account "
            "for potential legacy structural or environmental issues."
        ),
    },
    {
        "policy_name": "Commercial Conversion Policy v1",
        "section": "Environmental Contamination",
        "content": (
            "Former industrial or commercial sites must provide a Phase 1 Environmental Site Assessment "
            "confirming no ground contamination. Properties with confirmed contamination are declined. "
            "Sites with low environmental risk carry a 1.15x loading and mandatory annual review."
        ),
    },
    {
        "policy_name": "Commercial Conversion Policy v1",
        "section": "Flood Risk for Converted Properties",
        "content": (
            "Commercial conversions in Flood Zone 2 or 3 carry combined risk from flood exposure and legacy "
            "structural uncertainty. Zone 2 conversions require both a structural survey and flood risk "
            "assessment. Zone 3 conversions are declined under this policy."
        ),
    },
]


def _bedrock_client():
    return boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def embed_text(text: str) -> list[float]:
    """Embed a text string using Amazon Titan Embed Text v2."""
    client = _bedrock_client()
    response = client.invoke_model(
        modelId=settings.BEDROCK_EMBED_MODEL_ID,
        body=json.dumps({"inputText": text}),
        contentType="application/json",
        accept="application/json",
    )
    body = json.loads(response["body"].read())
    return body["embedding"]


async def seed_policies_if_empty() -> None:
    """Insert policy chunks with embeddings on first startup. Re-seeds if stale."""
    count = await PolicyChunk.count()
    expected = len(POLICY_SEED_DATA)

    if count > 0:
        sample = await PolicyChunk.find_one()
        wrong_dims = sample and sample.embedding and len(sample.embedding) != 1024
        stale_count = count != expected

        if wrong_dims:
            print(f"[PolicyService] Wrong embedding dims ({len(sample.embedding)}) — re-seeding")
            await PolicyChunk.delete_all()
        elif stale_count:
            print(f"[PolicyService] Policy count changed ({count} → {expected}) — re-seeding")
            await PolicyChunk.delete_all()
        else:
            print(f"[PolicyService] {count} policy chunks already seeded — skipping")
            return

    print(f"[PolicyService] Seeding {expected} policy chunks...")
    for chunk_data in POLICY_SEED_DATA:
        try:
            embedding = embed_text(chunk_data["content"])
        except Exception:
            embedding = [0.0] * 1024  # zero vector fallback (correct dims)

        chunk = PolicyChunk(
            policy_name=chunk_data["policy_name"],
            section=chunk_data["section"],
            content=chunk_data["content"],
            embedding=embedding,
        )
        await chunk.insert()


async def retrieve_relevant_policies(query: str, top_k: int = 3) -> list[str]:
    """Retrieve top-k policy chunks relevant to the query via vector search."""
    try:
        query_embedding = embed_text(query)
        print(f"[PolicyService] Embedding generated ({len(query_embedding)} dims)")
    except Exception as e:
        print(f"[PolicyService] Embedding failed: {e} — falling back to find().limit()")
        chunks = await PolicyChunk.find().limit(top_k).to_list()
        return [f"[{c.policy_name} – {c.section}]: {c.content}" for c in chunks]

    pipeline = [
        {
            "$vectorSearch": {
                "index": "policy_vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 50,
                "limit": top_k,
            }
        },
        {"$project": {"policy_name": 1, "section": 1, "content": 1}},
    ]

    try:
        results = await PolicyChunk.aggregate(pipeline).to_list()
        if not results:
            raise ValueError("Empty vector search results")
        print(f"[PolicyService] Vector search returned {len(results)} chunk(s) — SEMANTIC MATCH")
        return [f"[{r['policy_name']} – {r['section']}]: {r['content']}" for r in results]
    except Exception as e:
        print(f"[PolicyService] Vector search failed: {e} — falling back to find().limit()")
        chunks = await PolicyChunk.find().limit(top_k).to_list()
        return [f"[{c.policy_name} – {c.section}]: {c.content}" for c in chunks]
