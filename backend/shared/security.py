import uuid
from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database import get_async_db
from shared.models import User, APIKey

# 1. Hashing Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 2. OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

import bcrypt

# ==========================================
# PASSWORD HASHING
# ==========================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify standard plain text password against salted bcrypt hash using direct secure C-bindings."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Generate secure salted bcrypt hash for storage using direct secure C-bindings."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

# ==========================================
# TOKEN MANAGEMENT
# ==========================================

def create_access_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    """Generate JWT Access Token for standard authentication."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire, 
        "sub": str(subject),
        "role": role
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    """Generate secure JWT Refresh Token for session renewals."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode = {
        "exp": expire, 
        "sub": str(subject),
        "role": role
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str, secret_key: str) -> dict:
    """Safely decode JWT using the specified symmetric signature key."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ==========================================
# FASTAPI DEPENDENCY SECURITY
# ==========================================

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_async_db)
) -> User:
    """Security dependency to fetch currently authenticated user from DB via JWT sub."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Query user
    result = await db.execute(select(User).filter(User.id == uuid.UUID(user_id)))
    user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    
    return user

async def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Security dependency to enforce Role-based Access Control (RBAC) specifically for Admins."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="The user does not have enough privileges"
        )
    return current_user

# ==========================================
# API KEY MANAGEMENT (Optional Extension)
# ==========================================

def generate_raw_api_key() -> str:
    """Generate a high-entropy cryptographically secure random API key."""
    # Format: nex_key_[UUID4_Hex]
    return f"nex_key_{uuid.uuid4().hex}{uuid.uuid4().hex}"

def hash_api_key(key: str) -> str:
    """Hash API key for secure verification storage in database."""
    # We can use standard SHA256 since API keys don't require slow bcrypt hashes
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()
