# app/db/crud_scheduling.py
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, date, timezone

from app.models.db_models import AvailabilitySlot, ScheduledInterview, InterviewStatus
from app.models.request_models import AvailabilitySlotCreate 

def create_availability_slot(db: Session, interviewer_id: int, slot_in: AvailabilitySlotCreate) -> AvailabilitySlot:
    slot_date = slot_in.slot_date
    slot_date_at_midnight_utc = datetime.combine(slot_date, datetime.min.time(), tzinfo=timezone.utc)

    start_dt = datetime.combine(slot_date, slot_in.start_time)
    if start_dt.tzinfo is None:
        start_time_utc = start_dt.replace(tzinfo=timezone.utc)
    else:
        start_time_utc = start_dt.astimezone(timezone.utc)

    end_dt = datetime.combine(slot_date, slot_in.end_time)
    if end_dt.tzinfo is None:
        end_time_utc = end_dt.replace(tzinfo=timezone.utc)
    else:
        end_time_utc = end_dt.astimezone(timezone.utc) 

    db_slot = AvailabilitySlot(
        interviewer_id=interviewer_id,
        slot_date_utc=slot_date_at_midnight_utc,
        start_time_utc=start_time_utc,
        end_time_utc=end_time_utc,
        is_booked=False
    )
    db.add(db_slot)
    db.commit()
    db.refresh(db_slot)
    return db_slot

def get_availability_slots_for_interviewer(
    db: Session, 
    interviewer_id: int, 
    query_start_date: date,
    query_end_date: date,
    only_unbooked: bool = True 
) -> List[AvailabilitySlot]:
   
    query_start_dt_utc = datetime.combine(query_start_date, datetime.min.time(), tzinfo=timezone.utc)
    query_end_dt_utc = datetime.combine(query_end_date, datetime.min.time(), tzinfo=timezone.utc)

    filters = [
        AvailabilitySlot.interviewer_id == interviewer_id,
        AvailabilitySlot.slot_date_utc >= query_start_dt_utc,
        AvailabilitySlot.slot_date_utc <= query_end_dt_utc, 
        AvailabilitySlot.start_time_utc > datetime.now(timezone.utc).time() 
            if query_start_date == datetime.now(timezone.utc).date() else True, # type: ignore
    ]
    if only_unbooked:
        filters.append(AvailabilitySlot.is_booked == False)
    
    return db.query(AvailabilitySlot).filter(*filters).order_by(
        AvailabilitySlot.slot_date_utc, AvailabilitySlot.start_time_utc
    ).all()

def get_availability_slot_by_id(db: Session, slot_id: int, for_update: bool = False) -> Optional[AvailabilitySlot]:
    query = db.query(AvailabilitySlot)
    if for_update:
        query = query.with_for_update() 
    return query.filter(AvailabilitySlot.id == slot_id).first()

def update_slot_booked_status(db: Session, slot_id: int, is_booked: bool) -> Optional[AvailabilitySlot]:
    """Atomically updates the booked status of a slot, typically used with for_update."""
    db_slot = get_availability_slot_by_id(db, slot_id, for_update=True) 
    if db_slot:
    
        if db_slot.is_booked == is_booked:  # type: ignore
           
            pass 
        
        db_slot.is_booked = is_booked # type: ignore
        db_slot.updated_at = datetime.now(timezone.utc) # type: ignore
        # db.commit() # Caller should commit as part of a larger transaction
        return db_slot
    return None


def create_scheduled_interview(
    db: Session,
    user_id: int,
    interviewer_id: int,
    slot: AvailabilitySlot
) -> ScheduledInterview:
    
    interview_datetime_utc = datetime.combine(
        slot.slot_date_utc.date(), 
        slot.start_time_utc,      # type: ignore
    )
    # Ensure tzinfo is set if combining naive date with aware time, or vice-versa
    if interview_datetime_utc.tzinfo is None and slot.start_time_utc.tzinfo is not None:
        interview_datetime_utc = interview_datetime_utc.replace(tzinfo=slot.start_time_utc.tzinfo)
    elif interview_datetime_utc.tzinfo is None: # Default to UTC if still naive
        interview_datetime_utc = interview_datetime_utc.replace(tzinfo=timezone.utc)


    # Calculate duration based on slot times
    # Create dummy date objects to correctly subtract time objects
    dummy_date = date(2000, 1, 1) 
    start_for_calc = datetime.combine(dummy_date, slot.start_time_utc.replace(tzinfo=None) if slot.start_time_utc.tzinfo else slot.start_time_utc) # type: ignore
    end_for_calc = datetime.combine(dummy_date, slot.end_time_utc.replace(tzinfo=None) if slot.end_time_utc.tzinfo else slot.end_time_utc) # type: ignore
    
    duration_minutes = int((end_for_calc - start_for_calc).total_seconds() / 60)
    if duration_minutes <= 0:
        duration_minutes = 60 # Default duration if calculation is odd or times are same

    db_interview = ScheduledInterview(
        user_id=user_id,
        interviewer_id=interviewer_id,
        availability_slot_id=slot.id,
        interview_datetime_utc=interview_datetime_utc,
        duration_minutes=duration_minutes,
        status=InterviewStatus.PENDING_CONFIRMATION # Default status
    )
    # The slot's is_booked status should have been set to True before calling this
    # This function commits both the new interview and the slot update (if any pending).
    db.add(db_interview)
    db.commit() 
    db.refresh(db_interview)
    db.refresh(slot) # Refresh the slot too, as its scheduled_interview relationship might change
    return db_interview

def get_scheduled_interviews_for_user(db: Session, user_id: int, upcoming_only: bool = False) -> List[ScheduledInterview]:
    query = db.query(ScheduledInterview).filter(ScheduledInterview.user_id == user_id)
    if upcoming_only:
        query = query.filter(ScheduledInterview.interview_datetime_utc >= datetime.now(timezone.utc))
    return query.order_by(ScheduledInterview.interview_datetime_utc.asc()).all()

def get_scheduled_interviews_for_interviewer(db: Session, interviewer_id: int, upcoming_only: bool = False) -> List[ScheduledInterview]:
    query = db.query(ScheduledInterview).filter(ScheduledInterview.interviewer_id == interviewer_id)
    if upcoming_only:
        query = query.filter(ScheduledInterview.interview_datetime_utc >= datetime.now(timezone.utc))
    return query.order_by(ScheduledInterview.interview_datetime_utc.asc()).all()

def get_scheduled_interview_by_id(db: Session, interview_id: int) -> Optional[ScheduledInterview]:
    return db.query(ScheduledInterview).filter(ScheduledInterview.id == interview_id).first()

def update_scheduled_interview(
    db: Session, 
    interview_id: int, 
    status: Optional[InterviewStatus] = None, 
    meeting_link: Optional[str] = None, # Allow empty string to clear
    user_feedback: Optional[str] = None,
    interviewer_feedback: Optional[str] = None,
) -> Optional[ScheduledInterview]:
    db_interview = get_scheduled_interview_by_id(db, interview_id)
    if not db_interview:
        return None
    
    updated = False
    if status is not None and db_interview.status != status: # type: ignore
        db_interview.status = status # type: ignore
        updated = True
    if meeting_link is not None and db_interview.meeting_link != meeting_link: # type: ignore
        db_interview.meeting_link = meeting_link # type: ignore
        updated = True
    if user_feedback is not None and db_interview.user_feedback != user_feedback: # type: ignore
        db_interview.user_feedback = user_feedback # type: ignore
        updated = True
    if interviewer_feedback is not None and db_interview.interviewer_feedback != interviewer_feedback: # type: ignore
        db_interview.interviewer_feedback = interviewer_feedback # type: ignore
        updated = True
        
    if updated:
        db_interview.updated_at = datetime.now(timezone.utc) # type: ignore # Rely on onupdate in model
        db.commit()
        db.refresh(db_interview)
    return db_interview