import os
from datetime import datetime, timedelta, timezone 
from typing import Optional, Dict, Any, cast, Union
import jwt 
from jose import JWTError

from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, ValidationError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.models.db_models import User, RefreshToken 
from app.models.request_models import UserCreate
from app.db.database import get_db 
from app.db import crud_user
from app.config import settings 

# --- Password Hashing Context ---
from app.db.crud_user import pwd_context_user

pwd_context_user = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- OAuth2 Scheme for User Login ---
oauth2_scheme_user = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/users/login") # Use settings for prefix

# --- Pydantic Model for Token Data (claims within the JWT) ---
class TokenDataUser(BaseModel):
    email: Optional[EmailStr] = None
    type: Optional[str] = None # To validate the "type" claim from JWT


class AuthService:

    @staticmethod
    def generate_email_verification_token(email: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(hours=getattr(settings, 'EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS', 24))
        payload = {"sub": email, "exp": expire, "type": "email_verification"}
        # Use python-jose's jwt for consistency if other token methods use it
        return jwt.encode(payload, settings.USER_SECRET_KEY, algorithm=settings.USER_ALGORITHM)

    @staticmethod
    def verify_email_token(token: str) -> Optional[str]: # Return email on success, "expired", or None on other errors
        try:
            payload = jwt.decode(token, settings.USER_SECRET_KEY, algorithms=[settings.USER_ALGORITHM])
            if payload.get("type") != "email_verification":
                return None # Invalid token type
            email: Optional[str] = payload.get("sub")
            return email
        except jwt.ExpiredSignatureError:
            return "expired" # Specific marker for expired token
        except JWTError: # Catch other PyJWTError/JWTError from python-jose
            return None # Generic invalid token

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a user's password against its hash."""
        return pwd_context_user.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a user's password."""
        return pwd_context_user.hash(password)

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token for a user."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.USER_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "sub": str(data.get("sub")), # Ensure sub is string
            "type": "user_access"       # Add type claim for user access tokens
        })
        encoded_jwt = jwt.encode(to_encode, settings.USER_SECRET_KEY, algorithm=settings.USER_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token_opaque_and_store(user_id: int, db: Session) -> str: 
        """Create an opaque refresh token, store it in DB, and return the token string."""
        import secrets
        token_value = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.USER_REFRESH_TOKEN_EXPIRE_DAYS)
        
        crud_user.create_user_refresh_token(db, user_id=user_id, token=token_value, expires_at=expires_at)
        return token_value

    @staticmethod
    def verify_token_payload(token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return its payload if valid. Uses USER_SECRET_KEY."""
        try:
            payload_raw = jwt.decode(token, settings.USER_SECRET_KEY, algorithms=[settings.USER_ALGORITHM])
            return cast(Dict[str, Any], payload_raw)
        except JWTError: 
            return None

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email (delegates to CRUD)."""
        return crud_user.get_user_by_email(db, email=email)
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID (delegates to CRUD)."""
        return crud_user.get_user_by_id(db, user_id=user_id)
    
    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User: # Renamed user to user_in
        """Create new user with email/password (delegates to CRUD)."""
        # crud_user.create_user should handle hashing and checking if email exists
        return crud_user.create_user(db=db, user_in=user_in)
    
    # OAuth methods can remain if they are distinct enough or also delegate to specific CRUDs
    @staticmethod
    def create_oauth_user(db: Session, email: str, full_name: str, profile_picture: Optional[str], # Made pic optional
                         provider: str, provider_id: str) -> User:
        """Create new OAuth user (could delegate to a specific crud_user function)."""
       
        user_data = {
            "email": email, "full_name": full_name, "profile_picture": profile_picture,
            "is_verified": True, "is_google_user": False, "is_linkedin_user": False,
            "hashed_password": None 
        }
        if provider.lower() == "google":
            user_data["is_google_user"] = True
            user_data["google_id"] = provider_id
        elif provider.lower() == "linkedin":
            user_data["is_linkedin_user"] = True
            user_data["linkedin_id"] = provider_id
        
        db_user = User(**user_data)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def get_oauth_user(db: Session, provider: str, provider_id: str) -> Optional[User]:
        """Get user by provider and provider ID (delegates to CRUD or specific queries)."""
        # This can also be moved to crud_user.py as specific query methods
        if provider.lower() == "google":
            return db.query(User).filter(User.google_id == provider_id).first()
        elif provider.lower() == "linkedin":
            return db.query(User).filter(User.linkedin_id == provider_id).first()
        return None


# --- FastAPI Dependency Functions (defined in the same file, outside the class) ---

async def get_current_user(
    token: str = Depends(oauth2_scheme_user), 
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current user from a JWT access token.
    Verifies token type is 'user_access'.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate user credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = AuthService.verify_token_payload(token) # Use the static method
    if payload is None: # Token is invalid or expired
        raise credentials_exception

    email_any: Any = payload.get("sub") 
    token_type_any: Any = payload.get("type")

    if not isinstance(email_any, str) or not email_any: # Check if 'sub' is a non-empty string
        raise credentials_exception
    
    email: str = email_any # Now we know it's a string

    if token_type_any != "user_access": # Check for correct token type
        raise credentials_exception
    
    # Optional: Validate with Pydantic model for stricter payload checking
    try:
        TokenDataUser(email=email, type=token_type_any) # Validates types and presence if model is strict
    except ValidationError:
        raise credentials_exception

    user = crud_user.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency that ensures the current user (from token) is active.
    """
    if not current_user.is_active: # type: ignore 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account.")
   
    if not current_user.is_verified: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="User email not verified. Please verify your email to proceed."
        )
    return current_user