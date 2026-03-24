from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter()

# BUG: HS256 is a symmetric algorithm. All services share the same secret key,
# meaning any service that needs to verify tokens must also possess the signing key.
# Banking-grade APIs should use RS256 (asymmetric) so verification can happen
# with the public key alone, keeping the private key confined to the auth service.
# This violates PCI-DSS requirement 8.6.1 on authentication mechanisms.
SECRET_KEY: str = os.environ.get(
    "FINCORE_SECRET_KEY", "insecure-dev-key-do-not-use-in-production"
)
ALGORITHM: str = "HS256"  # BUG: should be RS256 for banking compliance
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("FINCORE_JWT_EXPIRY_MINUTES", "60")
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Demo user store. A production system would query the user management service.
_demo_users: dict = {
    "developer@fincore.bank": {
        "username": "developer@fincore.bank",
        "hashed_password": pwd_context.hash("hackathon2024"),
        "role": "developer",
        "team": "core-banking",
    }
}


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns None if the token is invalid or expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


@router.post("/token", response_model=Token, summary="Obtain a bearer token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """Exchange credentials for a JWT bearer token."""
    user = _demo_users.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        logger.warning("failed_login", username=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}
    )
    logger.info("user_authenticated", username=user["username"])
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
