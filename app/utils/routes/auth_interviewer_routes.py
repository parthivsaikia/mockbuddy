# app/routes/auth_interviewer_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone

from app.db import database, crud_interviewer
from app.models import request_models as rm
from app.models import response_models as resp_m
from app.models.db_models import Interviewer
from app.services.auth_service_interviewer import AuthServiceInterviewer 
from app.config import settings

router = APIRouter(tags=["Interviewer Authentication"])

@router.post("/interviewers/signup", response_model=resp_m.InterviewerResponse, status_code=status.HTTP_201_CREATED)
def signup_interviewer_route(
    interviewer_in: rm.InterviewerCreate, 
    db: Session = Depends(database.get_db)
):
    db_interviewer = crud_interviewer.get_interviewer_by_email(db, email=interviewer_in.email)
    if db_interviewer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered by an interviewer."
        )
    new_interviewer_db_obj = crud_interviewer.create_interviewer(db=db, interviewer_in=interviewer_in)
    return resp_m.InterviewerResponse.model_validate(new_interviewer_db_obj) # CHANGED

@router.post("/interviewers/login", response_model=resp_m.InterviewerTokenResponse)
async def login_interviewer_for_access_token_route(
    db: Session = Depends(database.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    interviewer_db_obj = crud_interviewer.get_interviewer_by_email(db, email=form_data.username)
    if not interviewer_db_obj or not AuthServiceInterviewer.verify_password(form_data.password, interviewer_db_obj.hashed_password): # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password for interviewer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not interviewer_db_obj.is_active: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interviewer account is inactive.")

    access_token_expires = timedelta(minutes=settings.INTERVIEWER_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthServiceInterviewer.create_access_token(
        data={"sub": interviewer_db_obj.email}, expires_delta=access_token_expires
    )
    
    refresh_token_str = AuthServiceInterviewer.create_refresh_token(
        interviewer_id=interviewer_db_obj.id,  # type: ignore
        db=db
    )
    
    return resp_m.InterviewerTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        interviewer=resp_m.InterviewerResponse.model_validate(interviewer_db_obj) # CHANGED
    )

@router.post("/interviewers/token/refresh", response_model=resp_m.InterviewerTokenResponse)
async def refresh_interviewer_access_token(
    refresh_token_data: rm.TokenRefresh,
    db: Session = Depends(database.get_db)
):
    stored_refresh_token = crud_interviewer.get_interviewer_refresh_token(db, token=refresh_token_data.refresh_token)
    if not stored_refresh_token or stored_refresh_token.is_revoked or stored_refresh_token.expires_at < datetime.now(timezone.utc): # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token for interviewer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    interviewer_db_obj = crud_interviewer.get_interviewer_by_id(db, interviewer_id=stored_refresh_token.interviewer_id) # type: ignore
    if not interviewer_db_obj or not interviewer_db_obj.is_active: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Interviewer not found or inactive",
        )

    crud_interviewer.revoke_interviewer_refresh_token(db, token=stored_refresh_token.token) # type: ignore
    
    new_access_token_expires = timedelta(minutes=settings.INTERVIEWER_ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = AuthServiceInterviewer.create_access_token(
        data={"sub": interviewer_db_obj.email}, expires_delta=new_access_token_expires
    )
    
    new_refresh_token_str = AuthServiceInterviewer.create_refresh_token(
        interviewer_id=interviewer_db_obj.id, # type: ignore
        db=db
    )

    return resp_m.InterviewerTokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token_str,
        token_type="bearer",
        expires_in=int(new_access_token_expires.total_seconds()),
        interviewer=resp_m.InterviewerResponse.model_validate(interviewer_db_obj) # CHANGED
    )