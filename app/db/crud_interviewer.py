from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from passlib.context import CryptContext
from datetime import datetime, timezone
from pydantic import HttpUrl
from app.models.db_models import Interviewer, RefreshToken
from app.models.request_models import InterviewerCreate, InterviewerUpdate

pwd_context_interviewer = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_interviewer_by_email(db: Session, email: str) -> Optional[Interviewer]:
    return db.query(Interviewer).filter(Interviewer.email == email).first()

def get_interviewer_by_id(db: Session, interviewer_id: int) -> Optional[Interviewer]:
    return db.query(Interviewer).filter(Interviewer.id == interviewer_id).first()

def create_interviewer(db: Session, interviewer_in: InterviewerCreate) -> Interviewer:
    hashed_password = pwd_context_interviewer.hash(interviewer_in.password)
    db_interviewer = Interviewer(
        email=interviewer_in.email,
        hashed_password=hashed_password,
        full_name=interviewer_in.full_name,
        profile_headline=interviewer_in.profile_headline,
        bio=interviewer_in.bio,
        linkedin_url=str(interviewer_in.linkedin_url) if interviewer_in.linkedin_url else None,
        years_of_experience=interviewer_in.years_of_experience,
        areas_of_expertise=interviewer_in.areas_of_expertise,
        is_active=True, 
        is_verified=False 
    )
    db.add(db_interviewer)
    db.commit()
    db.refresh(db_interviewer)
    return db_interviewer

def update_interviewer_profile(
    db: Session, 
    interviewer_id: int, 
    profile_data_in: InterviewerUpdate 
) -> Optional[Interviewer]:
    db_interviewer = get_interviewer_by_id(db, interviewer_id)
    if not db_interviewer:
        return None
    
    update_data = profile_data_in.model_dump(exclude_unset=True)
    
    made_changes = False
    for key, value in update_data.items():
        if hasattr(db_interviewer, key):
            value_to_set = str(value) if isinstance(value, HttpUrl) else value
            if getattr(db_interviewer, key) != value_to_set:
                setattr(db_interviewer, key, value_to_set)
                made_changes = True
    
    if made_changes:
        db.add(db_interviewer)
        db.commit()
        db.refresh(db_interviewer)
    return db_interviewer

def get_active_verified_interviewers(db: Session, skip: int = 0, limit: int = 20) -> List[Interviewer]:
    return db.query(Interviewer).filter(
        Interviewer.is_active == True,
        Interviewer.is_verified == True # Only list verified ones publicly
    ).order_by(Interviewer.full_name).offset(skip).limit(limit).all()

# --- Interviewer Refresh Token CRUD ---
def create_interviewer_refresh_token(db: Session, interviewer_id: int, token: str, expires_at: datetime) -> RefreshToken:
    db_refresh_token = RefreshToken(
        interviewer_id=interviewer_id,
        user_id=None, # Explicitly None for interviewer
        token=token,
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(db_refresh_token)
    db.commit()
    db.refresh(db_refresh_token)
    return db_refresh_token

def get_interviewer_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    """Fetches a non-revoked interviewer refresh token."""
    return db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.interviewer_id != None, # Ensure it's an interviewer token
        RefreshToken.is_revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc)
    ).first()

def revoke_interviewer_refresh_token(db: Session, token_str: str) -> bool:
    """Revokes a specific interviewer refresh token."""
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == token_str,
        RefreshToken.interviewer_id != None
    ).first()
    if db_token and not db_token.is_revoked: # type: ignore
        db_token.is_revoked = True # type: ignore
        db_token.expires_at = datetime.now(timezone.utc) # type: ignore # Optional: expire immediately
        db.commit()
        return True
    return False

def revoke_all_refresh_tokens_for_interviewer(db: Session, interviewer_id: int) -> int:
    """Revokes all active refresh tokens for a given interviewer."""
    num_revoked = db.query(RefreshToken).filter(
        RefreshToken.interviewer_id == interviewer_id,
        RefreshToken.is_revoked == False
    ).update({"is_revoked": True, "expires_at": datetime.now(timezone.utc)})
    db.commit()
    return num_revoked

