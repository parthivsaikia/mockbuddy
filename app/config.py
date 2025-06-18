# app/core/config.py
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List

load_dotenv(dotenv_path='/home/parthiv/repos/mockbuddy/mockbuddy.env') # Adjust path as needed from where app runs

class Settings(BaseSettings):
    PROJECT_NAME: str = "MockBuddy"
    API_V1_STR: str = "/api/v1" # Example API prefix

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost/mockbuddy")

    # JWT Settings for Users
    USER_SECRET_KEY: str = os.getenv("USER_SECRET_KEY", "a_very_secret_key_for_users_change_me")
    USER_ALGORITHM: str = "HS256"
    USER_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day
    USER_REFRESH_TOKEN_EXPIRE_DAYS: int = 7 # 7 days

    # JWT Settings for Interviewers
    INTERVIEWER_SECRET_KEY: str = os.getenv("INTERVIEWER_SECRET_KEY", "a_different_secret_key_for_interviewers_change_me")
    INTERVIEWER_ALGORITHM: str = "HS256"
    INTERVIEWER_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day
    INTERVIEWER_REFRESH_TOKEN_EXPIRE_DAYS: int = 7 # 7 days
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost", "http://localhost:3000", "http://localhost:8080", "http://localhost:5173"] # Add your frontend origins

    # Gemini API Key
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

    # Piston API URL (if you were to configure it)
    # PISTON_API_URL: str = "https://emkc.org/api/v2/piston/execute"

    class Config:
        case_sensitive = True
        # env_file = ".env" # If you prefer pydantic-settings to load it directly without python-dotenv

settings = Settings()
