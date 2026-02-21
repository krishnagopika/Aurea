import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config.settings import settings
from src.db.session import init_db, close_db
from src.services.policy_service import seed_policies_if_empty
from src.v1.routes.auth import router as auth_router
from src.v1.routes.underwriting import router as underwriting_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_policies_if_empty()
    yield
    await close_db()


app = FastAPI(
    title="Aurea Underwriting API",
    version="1.0.0",
    description="Multi-agent UK residential property insurance underwriting system",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal server error"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


app.include_router(auth_router, prefix="/api/v1")
app.include_router(underwriting_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "aurea-underwriting"}
