# app/models/request_models.py
from pydantic import BaseModel, EmailStr, HttpUrl, Field, field_validator
from typing import Optional, List, Any
from datetime import date, time, datetime

# --- User Auth & Profile ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, min_length=1)

class UserProfileUpdate(BaseModel): 
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    profile_picture_url: Optional[HttpUrl] = None 

class UserLogin(BaseModel):
    email: EmailStr # Or username, if you support that
    password: str

class TokenRefresh(BaseModel):
    refresh_token: str

# --- Interviewer Auth & Profile ---
class InterviewerCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1)
    profile_headline: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    linkedin_url: Optional[HttpUrl] = None
    years_of_experience: Optional[int] = Field(None, ge=0, le=50)
    areas_of_expertise: Optional[str] = None # Comma-separated or client sends as string

class InterviewerUpdate(BaseModel): # For PUT /interviewers/me
    full_name: Optional[str] = Field(None, min_length=1)
    profile_headline: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    linkedin_url: Optional[HttpUrl] = None
    years_of_experience: Optional[int] = Field(None, ge=0, le=50)
    areas_of_expertise: Optional[str] = None
    # Password change should be a separate endpoint for security

class InterviewerLogin(BaseModel): # Re-using name, context will differentiate
    email: EmailStr
    password: str


# --- Scheduling ---
class AvailabilitySlotCreate(BaseModel):
    slot_date: date # YYYY-MM-DD
    start_time: time # HH:MM or HH:MM:SS (Pydantic parses from string)
    end_time: time   # HH:MM or HH:MM:SS
    # Consider timezone input if interviewers are in different timezones than your server's UTC assumption
    # timezone_str: Optional[str] = Field("UTC", description="Timezone of start/end times, e.g., 'America/New_York'")

    @field_validator('end_time')
    def end_time_must_be_after_start_time(cls, v, values):
        # Pydantic v2: 'values' is a FieldValidationInfo object
        # Use values.data to get the dict of other fields
        start_time_val = values.data.get('start_time')
        if start_time_val and v <= start_time_val:
            raise ValueError('End time must be after start time')
        return v

class BookInterviewSlotRequest(BaseModel): # User requests to book
    availability_slot_id: int
    # user_id comes from authenticated user token

class InterviewActionRequest(BaseModel): # For interviewer confirming/cancelling etc.
    meeting_link: Optional[HttpUrl] = None
    cancellation_reason: Optional[str] = None # If interviewer cancels

class InterviewFeedback(BaseModel):
    # rating: Optional[int] = Field(None, ge=1, le=5) # Example if you add ratings
    feedback_text: str = Field(..., min_length=10)


# --- DSA & Core Problem Requests (Existing) ---
class DSARequest(BaseModel):
    company: str
    total_required: int = Field(3, ge=1, le=10)

class ProblemStatementRequest(BaseModel): # For test case generation
    problem_description: str
    company: Optional[str] = None

class EvaluationRequest(BaseModel): # For code submission
    user_id: int # This might be better derived from authenticated user in route
    problem_statement: str
    candidate_code: str
    language: str
    version: str = Field("3.10.0", pattern=r"^\d+\.\d+\.\d+$") # Example pattern