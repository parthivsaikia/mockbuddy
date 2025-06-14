import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any,cast

from jose import JWTError, jwt
from passlib.context import CryptContext # Ensure this is the same instance as in crud_interviewer
from pydantic import BaseModel, EmailStr, ValidationError # For TokenDataInterviewer if used

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer # No OAuth2PasswordRequestForm here, that's for routes
from sqlalchemy.orm import Session

# Use specific CRUD for interviewers
from app.db import crud_interviewer
from app.models.db_models import Interviewer, RefreshToken # Assuming RefreshToken is shared or has interviewer_id
from app.models.request_models import InterviewerCreate # For type hinting
from app.db.database import get_db
from app.config import settings # Import your application settings

# --- Password Hashing Context ---
# This should be THE SINGLE INSTANCE used for interviewer passwords.
# If crud_interviewer.py defines pwd_context_interviewer, import it.
# from app.db.crud_interviewer import pwd_context_interviewer
# Otherwise, define it here ensuring it's identical:
pwd_context_interviewer = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- OAuth2 Scheme for Interviewer Login (used by FastAPI for docs and dependency) ---
# The tokenUrl should point to your actual interviewer login endpoint.
oauth2_scheme_interviewer = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/interviewers/login")


# --- Pydantic Model for Token Data (claims within the JWT) ---
class TokenDataInterviewer(BaseModel):
    email: Optional[EmailStr] = None
    # Add other claims like 'type' if you validate them strictly here
    # type: Optional[str] = None 

class AuthServiceInterviewer:

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify an interviewer's password against its hash."""
        return pwd_context_interviewer.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash an interviewer's password."""
        return pwd_context_interviewer.hash(password)

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token for an interviewer."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.INTERVIEWER_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "sub": str(data.get("sub")), # Subject is usually email for interviewers
            "type": "interviewer_access" # Differentiate from user tokens
        })
        encoded_jwt = jwt.encode(to_encode, settings.INTERVIEWER_SECRET_KEY, algorithm=settings.INTERVIEWER_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(interviewer_id: int, db: Session) -> str:
        """Create and store a refresh token for an interviewer."""
        import secrets
        token_value = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.INTERVIEWER_REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Assumes RefreshToken model has 'interviewer_id' and 'user_id' (nullable)
        db_refresh_token = RefreshToken(
            interviewer_id=interviewer_id,
            user_id=None, # Explicitly None for interviewer refresh token
            token=token_value,
            expires_at=expires_at,
            is_revoked=False
        )
        db.add(db_refresh_token)
        db.commit()
        db.refresh(db_refresh_token)
        return token_value

    @staticmethod
    def verify_token_payload(token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return its payload if valid."""
        try:
            payload_raw = jwt.decode(token, settings.INTERVIEWER_SECRET_KEY, algorithms=[settings.INTERVIEWER_ALGORITHM])
            # At runtime, payload_raw is expected to be a dict with string keys
            # We cast it to satisfy the type checker for the return type.
            return cast(Dict[str, Any], payload_raw)
        except JWTError:
            return None

async def get_current_interviewer( # DEFINED OUTSIDE THE CLASS
    token: str = Depends(oauth2_scheme_interviewer), 
    db: Session = Depends(get_db)
) -> Interviewer:
    """
    FastAPI dependency: Decodes Interviewer JWT, validates type, fetches Interviewer from DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate interviewer credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Use the static method from AuthServiceInterviewer for token verification
    payload = AuthServiceInterviewer.verify_token_payload(token) 
    
    if payload is None: # Token is invalid, expired, or malformed
        raise credentials_exception

    # Safely get claims from payload
    email_any: Any = payload.get("sub") 
    token_type_any: Any = payload.get("type")

    # Validate claims
    if not (isinstance(email_any, str) and email_any):
        raise credentials_exception
    
    email: str = email_any # Safe to use 'email' now

    if token_type_any != "interviewer_access": # Ensure it's an interviewer access token
        raise credentials_exception
    
    # Optional: Stricter validation of payload using Pydantic TokenDataInterviewer model
    # try:
    #     TokenDataInterviewer(email=email, type=token_type_any)
    # except ValidationError:
    #     raise credentials_exception

    interviewer = crud_interviewer.get_interviewer_by_email(db, email=email)
    if interviewer is None:
        raise credentials_exception
    return interviewer


async def get_current_active_interviewer( # DEFINED OUTSIDE THE CLASS
    current_interviewer: Interviewer = Depends(get_current_interviewer) # Depends on the function above
) -> Interviewer:
    """
    FastAPI dependency: Ensures the interviewer fetched by get_current_interviewer is active.
    """
    # Your `type: ignore` for current_interviewer.is_active was here.
    # It should not be needed if `get_current_interviewer` is correctly hinted to return `Interviewer`.
    if not current_interviewer.is_active: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive interviewer account.")
    
    # Optional: Enforce verification status for most actions
    # if not current_interviewer.is_verified:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, 
    #         detail="Interviewer account is not verified."
    #     )
    return current_interviewer

