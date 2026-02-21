import hashlib
import base64
import bcrypt


def _prehash(password: str) -> bytes:
    """
    SHA-256 prehash → base64 so bcrypt always receives ≤44 ASCII bytes.
    This lets passwords of any length work safely within bcrypt's 72-byte limit.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)  # always 44 ASCII bytes


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prehash(plain), hashed.encode("utf-8"))
