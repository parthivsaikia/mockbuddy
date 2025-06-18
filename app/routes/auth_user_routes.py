# app/routes/auth_user_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone # Ensure timezone for utcnow()
from pydantic import BaseModel, ConfigDict 
from app.db import database, crud_user
from app.models import request_models as rm
from app.models import response_models as resp_m
from app.models.db_models import User # For type hint
from app.services import auth_services
from app.config import settings

router = APIRouter(tags=["User Authentication"])

@router.post("/users/signup", response_model=resp_m.UserResponse, status_code=status.HTTP_201_CREATED)
def signup_user_route(
    user_in: rm.UserCreate, 
    db: Session = Depends(database.get_db)
):
    db_user = crud_user.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )
    new_user = auth_services.AuthService.create_user(db=db, user_in=user_in)
    return resp_m.UserResponse.model_validate(new_user)


@router.post("/users/login", response_model=resp_m.TokenResponse)
async def login_for_access_token_user_route(
    response: Response,
    db: Session = Depends(database.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    # Use AuthService methods if they encapsulate logic beyond simple CRUD
    user = auth_services.AuthService.get_user_by_email(db, email=form_data.username)
    if not user or not auth_services.AuthService.verify_password(form_data.password, user.hashed_password): # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account.")

    access_token_expires = timedelta(minutes=settings.USER_ACCESS_TOKEN_EXPIRE_MINUTES)
    # Use AuthService.create_access_token which now uses settings.USER_SECRET_KEY
    access_token = auth_services.AuthService.create_access_token(
        data={"sub": user.email, "type": "user_access"}, # Added type claim
        expires_delta=access_token_expires
    )
    
    # Use your existing AuthService.create_refresh_token method
    # It handles DB storage internally.
    refresh_token_str = auth_services.AuthService.create_refresh_token_opaque_and_store(
        user_id=user.id,  # type: ignore
        db=db
    )
    
    # Set cookies for both access and refresh tokens
    # Access token cookie - httpOnly for security, secure in production
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=int(access_token_expires.total_seconds()),
        httponly=True,  # Prevents XSS attacks
        secure=getattr(settings, 'COOKIE_SECURE', False),  # Set to True in production with HTTPS
        samesite="lax",  # CSRF protection while allowing normal navigation
        path="/"
    )
    
    # Refresh token cookie - longer expiration, also httpOnly
    refresh_token_expires = timedelta(days=getattr(settings, 'USER_REFRESH_TOKEN_EXPIRE_DAYS', 30))
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_str,
        max_age=int(refresh_token_expires.total_seconds()),
        httponly=True,
        secure=getattr(settings, 'COOKIE_SECURE', False),
        samesite="lax",
        path="/"
    )
    
    return resp_m.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str, # This is the opaque token from DB
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        user=resp_m.UserResponse.model_validate(user)
    )

@router.post("/users/token/refresh", response_model=resp_m.TokenResponse)
async def refresh_user_access_token(
    response: Response,
    refresh_token_data: rm.TokenRefresh,
    db: Session = Depends(database.get_db)
):
    # crud_user.get_user_refresh_token validates and fetches the stored opaque token
    stored_refresh_token = crud_user.get_user_refresh_token(db, token=refresh_token_data.refresh_token)
    
    if not stored_refresh_token or stored_refresh_token.is_revoked or stored_refresh_token.expires_at < datetime.now(timezone.utc): # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # The user_id is on the stored_refresh_token object
    user = crud_user.get_user_by_id(db, user_id=stored_refresh_token.user_id) # type: ignore # Make sure user_id is not None
    if not user or not user.is_active: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive for this refresh token",
        )

    # Standard practice: revoke the used refresh token
    crud_user.revoke_user_refresh_token(db, token=stored_refresh_token.token) # type: ignore
    
    # Issue a new access token
    new_access_token_expires = timedelta(minutes=settings.USER_ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = auth_services.AuthService.create_access_token(
        data={"sub": user.email, "type": "user_access"}, # Added type claim
        expires_delta=new_access_token_expires
    )
    
    # Issue a new refresh token (rotation)
    new_refresh_token_str = auth_services.AuthService.create_refresh_token_opaque_and_store(
        user_id=user.id, # type: ignore
        db=db
    )

    # Update cookies with new tokens
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        max_age=int(new_access_token_expires.total_seconds()),
        httponly=True,
        secure=getattr(settings, 'COOKIE_SECURE', False),
        samesite="lax",
        path="/"
    )
    
    refresh_token_expires = timedelta(days=getattr(settings, 'USER_REFRESH_TOKEN_EXPIRE_DAYS', 30))
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token_str,
        max_age=int(refresh_token_expires.total_seconds()),
        httponly=True,
        secure=getattr(settings, 'COOKIE_SECURE', False),
        samesite="lax",
        path="/"
    )

    return resp_m.TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token_str,
        token_type="bearer",
        expires_in=int(new_access_token_expires.total_seconds()),
        user=resp_m.UserResponse.model_validate(user)
    )

@router.post("/users/logout")
async def logout_user(
    response: Response,
    refresh_token_data: rm.TokenRefresh,
    db: Session = Depends(database.get_db)
):
    """Logout user by revoking refresh token and clearing cookies"""
    try:
        # Revoke the refresh token in the database
        crud_user.revoke_user_refresh_token(db, token=refresh_token_data.refresh_token)
    except Exception:
        # Even if token revocation fails, we should clear cookies
        pass
    
    # Clear the cookies
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    
    return {"message": "Successfully logged out"}

@router.get("/users/me", response_model=resp_m.UserResponse)
async def read_users_me(current_user: User = Depends(auth_services.get_current_active_user)):
    return resp_m.UserResponse.model_validate(current_user)
