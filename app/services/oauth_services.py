import os
import httpx
import secrets
from typing import Optional, Dict, Any
from urllib.parse import urlencode
from sqlalchemy.orm import Session
from app.services.auth_services import AuthService
from app.models.db_models import User

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/auth/linkedin/callback")

class OAuthService:
    
    # Google OAuth URLs
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    # LinkedIn OAuth URLs
    LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    LINKEDIN_USER_INFO_URL = "https://api.linkedin.com/v2/people/~:(id,firstName,lastName,emailAddress,profilePicture(displayImage~:playableStreams))"
    
    @staticmethod
    def get_google_auth_url() -> Dict[str, str]:
        """Generate Google OAuth authorization URL"""
        state = secrets.token_urlsafe(32)
        
        params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'scope': 'openid email profile',
            'response_type': 'code',
            'state': state,
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        authorization_url = f"{OAuthService.GOOGLE_AUTH_URL}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        return {
            "authorization_url": authorization_url,
            "state": state
        }
    
    @staticmethod
    def get_linkedin_auth_url() -> Dict[str, str]:
        """Generate LinkedIn OAuth authorization URL"""
        state = secrets.token_urlsafe(32)
        
        params = {
            'client_id': LINKEDIN_CLIENT_ID,
            'redirect_uri': LINKEDIN_REDIRECT_URI,
            'scope': 'r_liteprofile r_emailaddress',
            'response_type': 'code',
            'state': state
        }
        
        authorization_url = f"{OAuthService.LINKEDIN_AUTH_URL}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        return {
            "authorization_url": authorization_url,
            "state": state
        }
    
    @staticmethod
    async def handle_google_callback(code: str, db: Session) -> Optional[User]:
        """Handle Google OAuth callback"""
        try:
            # Exchange code for token
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    OAuthService.GOOGLE_TOKEN_URL,
                    data={
                        'client_id': GOOGLE_CLIENT_ID,
                        'client_secret': GOOGLE_CLIENT_SECRET,
                        'code': code,
                        'grant_type': 'authorization_code',
                        'redirect_uri': GOOGLE_REDIRECT_URI,
                    }
                )
                
                if token_response.status_code != 200:
                    return None
                
                token_data = token_response.json()
                access_token = token_data.get('access_token')
                
                if not access_token:
                    return None
                
                # Get user info
                user_response = await client.get(
                    OAuthService.GOOGLE_USER_INFO_URL,
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                
                if user_response.status_code != 200:
                    return None
                
                user_data = user_response.json()
                
                # Check if user exists
                google_id = user_data.get('id')
                email = user_data.get('email')
                
                existing_user = AuthService.get_oauth_user(db, 'google', google_id)
                if existing_user:
                    return existing_user
                
                # Check if user exists with same email
                existing_email_user = AuthService.get_user_by_email(db, email)
                if existing_email_user:
                    # Link Google account to existing user
                    existing_email_user.is_google_user = True  # type: ignore
                    existing_email_user.google_id = google_id
                    existing_email_user.profile_picture = user_data.get('picture', existing_email_user.profile_picture)
                    db.commit()
                    db.refresh(existing_email_user)
                    return existing_email_user
                
                # Create new user
                full_name = user_data.get('name', '')
                profile_picture = user_data.get('picture', '')
                
                new_user = AuthService.create_oauth_user(
                    db, email, full_name, profile_picture, 'google', google_id
                )
                
                return new_user
                
        except Exception as e:
            print(f"Google OAuth error: {e}")
            return None
    
    @staticmethod
    async def handle_linkedin_callback(code: str, db: Session) -> Optional[User]:
        """Handle LinkedIn OAuth callback"""
        try:
            # Exchange code for token
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    OAuthService.LINKEDIN_TOKEN_URL,
                    data={
                        'client_id': LINKEDIN_CLIENT_ID,
                        'client_secret': LINKEDIN_CLIENT_SECRET,
                        'code': code,
                        'grant_type': 'authorization_code',
                        'redirect_uri': LINKEDIN_REDIRECT_URI,
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                
                if token_response.status_code != 200:
                    return None
                
                token_data = token_response.json()
                access_token = token_data.get('access_token')
                
                if not access_token:
                    return None
                
                # Get user profile
                profile_response = await client.get(
                    "https://api.linkedin.com/v2/people/~:(id,firstName,lastName,profilePicture(displayImage~:playableStreams))",
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                
                # Get user email
                email_response = await client.get(
                    "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                
                if profile_response.status_code != 200 or email_response.status_code != 200:
                    return None
                
                profile_data = profile_response.json()
                email_data = email_response.json()
                
                # Extract user info
                linkedin_id = profile_data.get('id')
                first_name = profile_data.get('firstName', {}).get('localized', {}).get('en_US', '')
                last_name = profile_data.get('lastName', {}).get('localized', {}).get('en_US', '')
                full_name = f"{first_name} {last_name}".strip()
                
                email = email_data.get('elements', [{}])[0].get('handle~', {}).get('emailAddress', '')
                
                profile_picture = ""
                profile_pic_data = profile_data.get('profilePicture', {}).get('displayImage~', {}).get('elements', [])
                if profile_pic_data:
                    profile_picture = profile_pic_data[0].get('identifiers', [{}])[0].get('identifier', '')
                
                # Check if user exists
                existing_user = AuthService.get_oauth_user(db, 'linkedin', linkedin_id)
                if existing_user:
                    return existing_user
                
                # Check if user exists with same email
                existing_email_user = AuthService.get_user_by_email(db, email)
                if existing_email_user:
                    # Link LinkedIn account to existing user
                    existing_email_user.is_linkedin_user = True  # type: ignore
                    existing_email_user.linkedin_id = linkedin_id
                    existing_email_user.profile_picture = profile_picture or existing_email_user.profile_picture
                    db.commit()
                    db.refresh(existing_email_user)
                    return existing_email_user
                
                # Create new user
                new_user = AuthService.create_oauth_user(
                    db, email, full_name, profile_picture, 'linkedin', linkedin_id
                )
                
                return new_user
                
        except Exception as e:
            print(f"LinkedIn OAuth error: {e}")
            return None