# app/db/crud_user.py
from sqlalchemy.orm import Session
from typing import Optional, List
from passlib.context import CryptContext
from datetime import datetime, timezone, timedelta 
from pydantic import HttpUrl
from app.models.db_models import User, RefreshToken
from app.models.request_models import UserCreate 
from app.models.request_models import UserProfileUpdate

pwd_context_user = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def create_user(db: Session, user_in: UserCreate) -> User:
    """Create new user with email/password, hashes password."""
    hashed_password = pwd_context_user.hash(user_in.password)
    db_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hashed_password,
        is_active=True, 
        is_verified=False 
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_profile(
    db: Session, 
    user_id: int, 
    user_update_in: UserProfileUpdate 
) -> Optional[User]:
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update_in.model_dump(exclude_unset=True)
    
    made_changes = False
    for key, value in update_data.items():
        if hasattr(db_user, key):
            value_to_set = str(value) if isinstance(value, HttpUrl) else value
            if getattr(db_user, key) != value_to_set:
                setattr(db_user, key, value_to_set)
                made_changes = True
    
    if made_changes:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    return db_user

def create_user_refresh_token(db: Session, user_id: int, token: str, expires_at: datetime) -> RefreshToken:
   
    db_refresh_token = RefreshToken(
        user_id=user_id, 
        interviewer_id=None, 
        token=token, 
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(db_refresh_token)
    db.commit()
    db.refresh(db_refresh_token)
    return db_refresh_token

def get_user_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    """Fetches a non-revoked user refresh token."""
    return db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.user_id != None,
        RefreshToken.is_revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc)
    ).first()

def revoke_user_refresh_token(db: Session, token_str: str) -> bool: 
    """Revokes a specific user refresh token."""
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == token_str,
        RefreshToken.user_id != None
    ).first()
    if db_token and not db_token.is_revoked: # type: ignore
        db_token.is_revoked = True # type: ignore
        
        db.commit()
        return True
    return False

def revoke_all_refresh_tokens_for_user(db: Session, user_id: int) -> int:
    """Revokes all active refresh tokens for a given user."""
    num_revoked = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False
    ).update({"is_revoked": True, "expires_at": datetime.now(timezone.utc)})
    db.commit()
    return num_revoked

