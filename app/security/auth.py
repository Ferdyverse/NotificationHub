from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
http_basic = HTTPBasic(auto_error=False)


def hash_secret(secret: str) -> str:
    return pwd_context.hash(secret)


def verify_secret(secret: str, secret_hash: str) -> bool:
    return pwd_context.verify(secret, secret_hash)


def require_ui_basic_auth(
    credentials: HTTPBasicCredentials | None = Depends(http_basic),
):
    if settings.ui_basic_auth_user is None or settings.ui_basic_auth_pass is None:
        return

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    if (
        credentials.username != settings.ui_basic_auth_user
        or credentials.password != settings.ui_basic_auth_pass
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
