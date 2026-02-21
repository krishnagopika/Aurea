"""
Standalone policy seeder script
================================
Run from the backend/ directory:

    cd backend
    python -m scripts.seed_policies

This creates the `policy_chunks` collection in MongoDB Atlas and embeds all
policy text using Amazon Titan Embed Text v2 via AWS Bedrock.

After running, go to MongoDB Atlas → Browse Collections → policy_chunks to
confirm the documents exist, then create the vector search index (see below).

=============================================================================
ATLAS VECTOR SEARCH INDEX — create this in Atlas UI or via Atlas CLI
=============================================================================

Index name : policy_vector_index
Collection : aurea.policy_chunks

Definition JSON:
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "policy_name"
    },
    {
      "type": "filter",
      "path": "section"
    }
  ]
}

Steps in Atlas UI:
  1. Go to Atlas → your cluster → Search Indexes
  2. Click "Create Search Index"
  3. Choose "Vector Search" (not the full-text one)
  4. Select database: aurea, collection: policy_chunks
  5. Name it: policy_vector_index
  6. Paste the JSON definition above
  7. Click Create — it takes ~1 minute to build
=============================================================================
"""

import asyncio
import json
import sys
import os

# Allow running as `python -m scripts.seed_policies` from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB_NAME", "aurea")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

POLICY_SEED_DATA = [
    {
        "policy_name": "Standard Home Policy v2",
        "section": "Flood Exclusions",
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
        "section": "Pre-1900 Property Conditions",
        "content": (
            "Properties constructed before 1900 require a full structural survey before acceptance. "
            "Subsidence, settlement, and roof condition must be confirmed satisfactory. "
            "A minimum premium loading of 1.3x applies. Refer to senior underwriter if overall score exceeds 70."
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
            "zone data, listed buildings, recent subsidence claims, or unusual construction methods."
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
        "policy_name": "Commercial Conversion Policy v1",
        "section": "Mixed Use Property",
        "content": (
            "Properties converted from commercial to residential use require confirmation of building "
            "regulations compliance post-conversion. A risk score loading of 1.2x applies to account "
            "for potential legacy structural or environmental issues."
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
        "section": "Appeals and Planning Disputes",
        "content": (
            "Proximity to active planning appeals (within 500 m) indicates contested development and "
            "potential neighbourhood change risk. Each active appeal adds to the planning risk score. "
            "More than 3 active appeals in the area triggers mandatory senior underwriter review."
        ),
    },
]


def embed_text(text: str) -> list[float]:
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    response = client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text, "dimensions": 1536, "normalize": True}),
        contentType="application/json",
        accept="application/json",
    )
    body = json.loads(response["body"].read())
    return body["embedding"]


async def main():
    from src.models.policy import PolicyChunk

    print(f"Connecting to MongoDB: {MONGODB_URI[:40]}...")
    client = AsyncIOMotorClient(MONGODB_URI)
    await init_beanie(database=client[MONGODB_DB], document_models=[PolicyChunk])

    existing = await PolicyChunk.count()
    if existing > 0:
        print(f"Collection already has {existing} documents. Use --force to re-seed.")
        if "--force" not in sys.argv:
            return

        print("Force re-seeding: deleting existing documents...")
        await PolicyChunk.delete_all()

    print(f"Seeding {len(POLICY_SEED_DATA)} policy chunks with Titan embeddings...\n")
    for i, chunk_data in enumerate(POLICY_SEED_DATA, 1):
        print(f"  [{i}/{len(POLICY_SEED_DATA)}] Embedding: {chunk_data['policy_name']} – {chunk_data['section']}")
        try:
            embedding = embed_text(chunk_data["content"])
        except Exception as e:
            print(f"    WARNING: Bedrock embedding failed ({e}); using zero vector.")
            embedding = [0.0] * 1536

        chunk = PolicyChunk(
            policy_name=chunk_data["policy_name"],
            section=chunk_data["section"],
            content=chunk_data["content"],
            embedding=embedding,
        )
        await chunk.insert()
        print(f"    ✓ Inserted (embedding dim={len(embedding)})")

    final_count = await PolicyChunk.count()
    print(f"\n Done. {final_count} documents in policy_chunks collection.")
    print("\nNext step: Create the Atlas Vector Search index.")
    print("See the instructions at the top of this file.\n")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
