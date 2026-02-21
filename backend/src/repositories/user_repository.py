from src.models.user import User


async def get_user_by_email(email: str) -> User | None:
    return await User.find_one(User.email == email)


async def create_user(email: str, hashed_password: str) -> User:
    user = User(email=email, hashed_password=hashed_password)
    await user.insert()
    return user
