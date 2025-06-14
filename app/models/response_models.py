from pydantic import BaseModel, Field, EmailStr, HttpUrl, ConfigDict,field_validator
from typing import List, Optional, Union, Any, Dict as TypingDict # Renamed Dict to TypingDict
from datetime import datetime, date, time

# --- Base for User/Interviewer in Token Responses ---
class UserBaseInToken(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)

# --- User Auth & Profile Responses ---
class UserPublicProfile(BaseModel): # What other users or interviewers might see
    id: int
    full_name: Optional[str] = None
    profile_picture_url: Optional[HttpUrl] = None # Example if you add this

    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserBaseInToken): # Full user profile for self or admin
    profile_picture: Optional[HttpUrl] = None
    is_google_user: bool
    is_linkedin_user: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel): # For user login
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int # In seconds
    user: UserResponse


# --- Interviewer Auth & Profile Responses ---
class InterviewerPublicProfile(BaseModel):
    id: int
    full_name: str
    profile_headline: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[HttpUrl] = None
    linkedin_url: Optional[HttpUrl] = None
    years_of_experience: Optional[int] = None
    areas_of_expertise: Optional[str] = None # Comma-separated string

    model_config = ConfigDict(from_attributes=True)

class InterviewerResponse(InterviewerPublicProfile): # Full profile for self or admin
    email: EmailStr
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime # Can add if needed

class InterviewerTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int # In seconds
    interviewer: InterviewerResponse


# --- Scheduling Responses ---
class AvailabilitySlotResponse(BaseModel):
    id: int
    interviewer_id: int
    slot_date_utc: date # Display as YYYY-MM-DD (date part of DateTime)
    start_time_utc: time # Display as HH:MM:SS
    end_time_utc: time
    is_booked: bool
    # Optionally include interviewer's public profile if listing slots generally
    interviewer: Optional[InterviewerPublicProfile] = None 

    model_config = ConfigDict(from_attributes=True)


class ScheduledInterviewResponse(BaseModel):
    id: int
    interview_datetime_utc: datetime
    duration_minutes: int
    status: str # Value from InterviewStatus enum
    meeting_link: Optional[HttpUrl] = None
    
    user: Optional[UserPublicProfile] = None # Public info of the user
    interviewer: Optional[InterviewerPublicProfile] = None # Public info of the interviewer
    
    # For user's own view, they might see more details about themselves.
    # For interviewer's own view, they might see more details about themselves.

    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- DSA & Core Problem Responses (Existing, with Pydantic V2 Config) ---
class DSAQuestion(BaseModel):
    problem_id: Optional[Union[str, int]] = Field(None)
    question_title: str
    question_text: Optional[str] = None
    topic_tagged_text: Optional[str] = None
    difficulty_level: Optional[str] = None
    hints: Optional[List[str]] = None # Changed to List[str]

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class DSAResponse(BaseModel):
    questions: List[DSAQuestion]

class GeneratedTestCaseData(BaseModel):
    input_config: TypingDict[str,Any] # The structured input parameters
    expected_stdout: str          # The direct expected string output

class TestCaseResponse(BaseModel):
    question_hash: str
    testcase: GeneratedTestCaseData
    message: str
    company: Optional[str] = None

class EvaluationResponse(BaseModel):
    compile_error: Optional[str] = None
    runtime_error: Optional[str] = None
    execution_stdout: Optional[str] = None
    execution_stderr: Optional[str] = None
    passed_testcase: Optional[bool] = None
    logical_correctness: Optional[str] = None
    complexity_analysis: Optional[str] = None
    edge_cases: Optional[str] = None
    readability: Optional[str] = None
    suggestions: Optional[str] = None
    score_and_verdict: Optional[str] = None # e.g. "85/100"
    raw_llm_response: Optional[str] = Field(None, alias="raw") # Alias for "raw"
    evaluation_error: Optional[str] = Field(None, alias="error") # Alias for "error"

    model_config = ConfigDict(populate_by_name=True) # To allow alias usage

class DSASubmissionResponse(BaseModel):
    id: int
    question: str 
    language: str
    difficulty: Optional[str] 
    topic: Optional[str]      
    passed_testcases: str
    total_testcases:Optional[int] 
    score: Optional[int]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)