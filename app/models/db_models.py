# app/models/db_models.py
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, DateTime, Time, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)
    is_google_user = Column(Boolean, default=False)
    is_linkedin_user = Column(Boolean, default=False)
    google_id = Column(String, nullable=True, unique=True)
    linkedin_id = Column(String, nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False) # User email verification
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    dsa_submissions = relationship("DSAEvaluation", back_populates="user", cascade="all, delete-orphan")
    core_submissions = relationship("CoreEvaluation", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    scheduled_interviews_as_interviewee = relationship("ScheduledInterview", back_populates="user", foreign_keys="ScheduledInterview.user_id", cascade="all, delete-orphan")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True) # Can be user or interviewer
    interviewer_id = Column(Integer, ForeignKey("interviewers.id", ondelete="CASCADE"), nullable=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_revoked = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="refresh_tokens")
    interviewer = relationship("Interviewer", back_populates="refresh_tokens")


class Interviewer(Base):
    __tablename__ = "interviewers"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    profile_headline = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    profile_picture_url = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    years_of_experience = Column(Integer, nullable=True)
    areas_of_expertise = Column(Text, nullable=True) # Store as JSON string or comma-separated
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False) # Admin verification
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    availability_slots = relationship("AvailabilitySlot", back_populates="interviewer", cascade="all, delete-orphan")
    scheduled_interviews_as_interviewer = relationship("ScheduledInterview", back_populates="interviewer", foreign_keys="ScheduledInterview.interviewer_id", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="interviewer", cascade="all, delete-orphan")


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    id = Column(Integer, primary_key=True, index=True)
    interviewer_id = Column(Integer, ForeignKey("interviewers.id", ondelete="CASCADE"), nullable=False)
    slot_date_utc = Column(DateTime(timezone=True), nullable=False) # Store specific date (e.g., YYYY-MM-DD 00:00:00 UTC)
    start_time_utc = Column(Time(timezone=True), nullable=False) # Store time as UTC
    end_time_utc = Column(Time(timezone=True), nullable=False)   # Store time as UTC
    is_booked = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    interviewer = relationship("Interviewer", back_populates="availability_slots")
    scheduled_interview = relationship("ScheduledInterview", back_populates="availability_slot", uselist=False, cascade="all, delete-orphan")


class InterviewStatus(str, enum.Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED_BY_USER = "cancelled_by_user"
    CANCELLED_BY_INTERVIEWER = "cancelled_by_interviewer"
    # Add more statuses like NO_SHOW etc.

class ScheduledInterview(Base):
    __tablename__ = "scheduled_interviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    interviewer_id = Column(Integer, ForeignKey("interviewers.id", ondelete="SET NULL"), nullable=True, index=True)
    availability_slot_id = Column(Integer, ForeignKey("availability_slots.id", ondelete="SET NULL"), nullable=True, unique=True) # A slot can only be for one interview
    interview_datetime_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes = Column(Integer, default=60)
    status = Column(SQLAlchemyEnum(InterviewStatus), default=InterviewStatus.PENDING_CONFIRMATION, nullable=False, index=True)
    meeting_link = Column(String, nullable=True)
    user_feedback = Column(Text, nullable=True) # Feedback from user about interviewer/experience
    interviewer_feedback = Column(Text, nullable=True) # Feedback from interviewer about user
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="scheduled_interviews_as_interviewee")
    interviewer = relationship("Interviewer", foreign_keys=[interviewer_id], back_populates="scheduled_interviews_as_interviewer")
    availability_slot = relationship("AvailabilitySlot", back_populates="scheduled_interview")


# --- Existing DSA and Core Models ---
class TestCase(Base):
    __tablename__ = "test_cases"
    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, nullable=True, index=True)
    question_hash = Column(String, unique=True, index=True, nullable=False)
    problem_statement = Column(Text, nullable=False)
    input_data = Column(Text, nullable=False)  # JSON string for structured input_config
    expected_output = Column(Text, nullable=False)  # Direct expected_stdout string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DSAEvaluation(Base):
    __tablename__ = "dsa_evaluations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    language = Column(String, nullable=False, default="python")
    user_code = Column(Text, nullable=False)
    passed_testcases = Column(String, nullable=False)
    score = Column(Integer, nullable=True) 
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="dsa_submissions")

class CoreEvaluation(Base):
    __tablename__ = "core_evaluations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    user_answer = Column(Text, nullable=False)
    correct_answer = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    difficulty = Column(String, nullable=True)
    topic = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="core_submissions")