from fastapi import HTTPException, status
from src.repositories.user_repository import get_user_by_email, create_user
from src.utils.security import hash_password, verify_password
from src.utils.jwt import create_access_token


async def register_user(email: str, password: str) -> str:
    existing = await get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    hashed = hash_password(password)
    user = await create_user(email, hashed)
    return create_access_token({"sub": str(user.id), "email": user.email})


async def login_user(email: str, password: str) -> str:
    user = await get_user_by_email(email)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return create_access_token({"sub": str(user.id), "email": user.email})
