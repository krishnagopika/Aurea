from fastapi import APIRouter, Body
from src.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from src.services.auth_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest = Body(
        openapi_examples={
            "standard": {
                "summary": "New user registration",
                "value": {"email": "jane.smith@example.com", "password": "SecurePass123!"},
            }
        }
    ),
):
    token = await register_user(req.email, req.password)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest = Body(
        openapi_examples={
            "standard": {
                "summary": "Existing user login",
                "value": {"email": "jane.smith@example.com", "password": "SecurePass123!"},
            }
        }
    ),
):
    token = await login_user(req.email, req.password)
    return TokenResponse(access_token=token)
