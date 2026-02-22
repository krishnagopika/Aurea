from urllib.parse import quote_plus
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── MongoDB ──────────────────────────────────────────────────────────────
    MONGO_USER: str
    MONGODB_PASSWORD: str
    MONGO_CLUSTER: str
    MONGO_APPNAME: str
    MONGO_DB: str

    @property
    def mongo_url(self) -> str:
        user = quote_plus(self.MONGO_USER)
        pwd = quote_plus(self.MONGODB_PASSWORD)
        return (
            f"mongodb+srv://{user}:{pwd}"
            f"@{self.MONGO_CLUSTER}/?appName={self.MONGO_APPNAME}"
            f"&retryWrites=true&w=majority"
        )

    # ── AWS / Bedrock ─────────────────────────────────────────────────────────
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    BEDROCK_MODEL_ID: str = "us.anthropic.claude-sonnet-4-6"
    BEDROCK_EMBED_MODEL_ID: str = "amazon.titan-embed-text-v2:0"

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    # ── External APIs ─────────────────────────────────────────────────────────
    IBEX_API_URL: str = "https://ibex.seractech.co.uk"
    IBEX_API_KEY: str = ""
    EPC_API_URL: str = "https://epc.opendatacommunities.org"
    EPC_API_KEY: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOW_ORIGINS: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        if self.ALLOW_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOW_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
