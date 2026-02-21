from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from src.config.settings import settings
from src.models.user import User
from src.models.assessment import PropertyAssessment
from src.models.underwriting import UnderwritingResult
from src.models.policy import PolicyChunk

_client: AsyncIOMotorClient | None = None


async def init_db() -> None:
    """Connect to MongoDB Atlas and initialise Beanie ODM."""
    global _client

    print(f"Connecting to MongoDB cluster: {settings.MONGO_CLUSTER} ...")

    _client = AsyncIOMotorClient(
        settings.mongo_url,
        serverSelectionTimeoutMS=settings.MONGO_TIMEOUT_MS if hasattr(settings, "MONGO_TIMEOUT_MS") else 5000,
    )

    db = _client[settings.MONGO_DB]

    # Verify connection
    await _client.admin.command("ping")
    print(f"Connected to MongoDB: {settings.MONGO_DB}")

    await init_beanie(
        database=db,
        document_models=[User, PropertyAssessment, UnderwritingResult, PolicyChunk],
    )
    print("Beanie ODM initialised")


async def close_db() -> None:
    """Close the MongoDB connection gracefully."""
    global _client
    if _client:
        _client.close()
        _client = None
        print("MongoDB connection closed")


async def check_connection() -> bool:
    """Return True if the MongoDB connection is alive."""
    if _client is None:
        return False
    try:
        await _client.admin.command("ping")
        return True
    except Exception:
        return False
