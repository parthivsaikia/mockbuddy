# app/routes/scheduling_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timezone, timedelta # Added timedelta

from app.db import database, crud_scheduling, crud_interviewer, crud_user
from app.models import request_models as rm
from app.models import response_models as resp_m
from app.models.db_models import Interviewer, User, AvailabilitySlot, ScheduledInterview, InterviewStatus 
from app.services.auth_services import get_current_active_user
from app.services.auth_service_interviewer import get_current_active_interviewer
import logging

logger = logging.getLogger(__name__)
router = APIRouter() 

@router.post("/interviewers/me/availability", response_model=resp_m.AvailabilitySlotResponse, status_code=status.HTTP_201_CREATED)
async def interviewer_add_availability_slot_route(
    slot_in: rm.AvailabilitySlotCreate,
    db: Session = Depends(database.get_db),
    current_interviewer: Interviewer = Depends(get_current_active_interviewer)
):
    if slot_in.end_time <= slot_in.start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slot end time must be after start time.")
    
    today_utc_date = datetime.now(timezone.utc).date()
    if slot_in.slot_date < today_utc_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot add availability for past dates.")

    existing_slots_on_date = crud_scheduling.get_availability_slots_for_interviewer(
        db, current_interviewer.id, slot_in.slot_date, slot_in.slot_date, only_unbooked=False # type: ignore
    )
    for es in existing_slots_on_date:
        if max(slot_in.start_time, es.start_time_utc.replace(tzinfo=None)) < \
           min(slot_in.end_time, es.end_time_utc.replace(tzinfo=None)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Slot overlaps with existing slot ID {es.id} from {es.start_time_utc.strftime('%H:%M')} to {es.end_time_utc.strftime('%H:%M')} UTC.")

    new_slot_db = crud_scheduling.create_availability_slot(db, interviewer_id=current_interviewer.id, slot_in=slot_in) # type: ignore
    
    return resp_m.AvailabilitySlotResponse(
        id=new_slot_db.id, # type: ignore
        interviewer_id=new_slot_db.interviewer_id, # type: ignore
        slot_date_utc=new_slot_db.slot_date_utc.date(), # Send only date part
        start_time_utc=new_slot_db.start_time_utc, # type: ignore
        end_time_utc=new_slot_db.end_time_utc, # type: ignore
        is_booked=new_slot_db.is_booked, # type: ignore
        interviewer=resp_m.InterviewerPublicProfile.model_validate(current_interviewer)
    )

@router.get("/interviewers/me/availability", response_model=List[resp_m.AvailabilitySlotResponse])
async def interviewer_get_own_availability_route(
    start_date: date = Query(..., description="Start date for querying availability (YYYY-MM-DD)"), 
    end_date: date = Query(..., description="End date for querying availability (YYYY-MM-DD)"),
    db: Session = Depends(database.get_db),
    current_interviewer: Interviewer = Depends(get_current_active_interviewer)
):
    if end_date < start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date cannot be before start date.")
    
    slots_db = crud_scheduling.get_availability_slots_for_interviewer(
        db, interviewer_id=current_interviewer.id, query_start_date=start_date, query_end_date=end_date, only_unbooked=False # type: ignore
    )
    response_slots = []
    interviewer_profile = resp_m.InterviewerPublicProfile.model_validate(current_interviewer)
    for slot_db in slots_db:
        response_slots.append(resp_m.AvailabilitySlotResponse(
            id=slot_db.id, interviewer_id=slot_db.interviewer_id, # type: ignore
            slot_date_utc=slot_db.slot_date_utc.date(),
            start_time_utc=slot_db.start_time_utc, end_time_utc=slot_db.end_time_utc, # type: ignore
            is_booked=slot_db.is_booked, interviewer=interviewer_profile # type: ignore
        ))
    return response_slots

@router.delete("/interviewers/me/availability/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def interviewer_delete_availability_slot_route(
    slot_id: int,
    db: Session = Depends(database.get_db),
    current_interviewer: Interviewer = Depends(get_current_active_interviewer)
):
    slot = crud_scheduling.get_availability_slot_by_id(db, slot_id)
    if not slot or slot.interviewer_id != current_interviewer.id: # type: ignore
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found or not owned by interviewer.")
    if slot.is_booked: # type: ignore
        # More robust: check if an active ScheduledInterview references this slot.
        # scheduled_interview = db.query(ScheduledInterview).filter(ScheduledInterview.availability_slot_id == slot_id, ScheduledInterview.status.notin_([InterviewStatus.COMPLETED, InterviewStatus.CANCELLED_BY_USER, InterviewStatus.CANCELLED_BY_INTERVIEWER])).first()
        # if scheduled_interview:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete a booked slot that may have an active interview. Cancel the interview first.")
    
    db.delete(slot)
    db.commit()
    return # No content response

# --- USER: Viewing Interviewer Availability & Booking ---
@router.get("/interviewers/{interviewer_id}/availability", response_model=List[resp_m.AvailabilitySlotResponse])
def user_get_interviewer_availability_route(
    interviewer_id: int, 
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"), 
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(database.get_db)
):
    interviewer_db = crud_interviewer.get_interviewer_by_id(db, interviewer_id)
    if not interviewer_db or not interviewer_db.is_active or not interviewer_db.is_verified: # type: ignore
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interviewer not found or not available.")
    if end_date < start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date cannot be before start date.")
        
    slots_db = crud_scheduling.get_availability_slots_for_interviewer(
        db, interviewer_id=interviewer_id, query_start_date=start_date, query_end_date=end_date, only_unbooked=True
    )
    response_slots = []
    interviewer_profile = resp_m.InterviewerPublicProfile.model_validate(interviewer_db)
    for slot_db in slots_db:
        response_slots.append(resp_m.AvailabilitySlotResponse(
            id=slot_db.id, interviewer_id=slot_db.interviewer_id, # type: ignore
            slot_date_utc=slot_db.slot_date_utc.date(),
            start_time_utc=slot_db.start_time_utc, end_time_utc=slot_db.end_time_utc, # type: ignore
            is_booked=slot_db.is_booked, interviewer=interviewer_profile # type: ignore
        ))
    return response_slots

@router.post("/slots/{slot_id}/book", response_model=resp_m.ScheduledInterviewResponse, status_code=status.HTTP_201_CREATED)
async def user_book_interview_slot_route(
    slot_id: int,
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Begin a transaction if your DB session doesn't autocommit per request properly for this.
        # With FastAPI's Depends(get_db), each request usually gets its own session, committed at end or rolled back on error.
        # The for_update=True is key for locking.
        slot_to_book = crud_scheduling.get_availability_slot_by_id(db, slot_id, for_update=True)
            
        if not slot_to_book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability slot not found.")
        if slot_to_book.is_booked: # type: ignore
            # This means another transaction committed the booking after we started ours but before we locked.
            # Or, the lock wasn't effective / another process booked it.
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is already booked.")

        interviewer_db = crud_interviewer.get_interviewer_by_id(db, slot_to_book.interviewer_id) # type: ignore
        if not interviewer_db or not interviewer_db.is_active or not interviewer_db.is_verified: # type: ignore
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interviewer for this slot is not available.")

        # Mark slot as booked. The commit will happen in create_scheduled_interview or at end of request.
        updated_slot = crud_scheduling.update_slot_booked_status(db, slot_id=slot_to_book.id, is_booked=True) # type: ignore
        if not updated_slot : # Should not happen if previous checks passed
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to secure booking on slot.")


        scheduled_interview_db = crud_scheduling.create_scheduled_interview(
            db=db, user_id=current_user.id, interviewer_id=interviewer_db.id, slot=updated_slot # type: ignore
        ) # This function commits changes.
        
    except HTTPException:
        # db.rollback() # If using manual transaction begin/commit
        raise
    except Exception as e:
        # db.rollback() # If using manual transaction begin/commit
        logger.error(f"Booking transaction failed for slot {slot_id} by user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not finalize interview schedule due to a server error.")
    
    return resp_m.ScheduledInterviewResponse(
        id=scheduled_interview_db.id, # type: ignore
        interview_datetime_utc=scheduled_interview_db.interview_datetime_utc, # type: ignore
        duration_minutes=scheduled_interview_db.duration_minutes, # type: ignore
        status=scheduled_interview_db.status.value,
        meeting_link=scheduled_interview_db.meeting_link, # type: ignore
        user=resp_m.UserPublicProfile.model_validate(current_user),
        interviewer=resp_m.InterviewerPublicProfile.model_validate(interviewer_db),
        created_at=scheduled_interview_db.created_at, # type: ignore
        updated_at=scheduled_interview_db.updated_at # type: ignore
    )

# --- USER & INTERVIEWER: Managing/Viewing their own Scheduled Interviews ---
@router.get("/me/interviews/as-user", response_model=List[resp_m.ScheduledInterviewResponse])
async def user_get_own_scheduled_interviews_route(
    upcoming_only: bool = Query(False, description="Set to true to only fetch upcoming interviews."),
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_active_user)
):
    interviews_db = crud_scheduling.get_scheduled_interviews_for_user(
        db, user_id=current_user.id, upcoming_only=upcoming_only # type: ignore
    )
    response_list = []
    user_public_profile = resp_m.UserPublicProfile.model_validate(current_user)
    for interview_db_item in interviews_db:
        interviewer_public_profile = None
        if interview_db_item.interviewer:
            interviewer_public_profile = resp_m.InterviewerPublicProfile.model_validate(interview_db_item.interviewer)
        response_list.append(resp_m.ScheduledInterviewResponse(
            id=interview_db_item.id, interview_datetime_utc=interview_db_item.interview_datetime_utc, # type: ignore
            duration_minutes=interview_db_item.duration_minutes, status=interview_db_item.status.value, # type: ignore
            meeting_link=interview_db_item.meeting_link, user=user_public_profile, interviewer=interviewer_public_profile, # type: ignore
            created_at=interview_db_item.created_at, updated_at=interview_db_item.updated_at # type: ignore
        ))
    return response_list

@router.get("/me/interviews/as-interviewer", response_model=List[resp_m.ScheduledInterviewResponse])
async def interviewer_get_own_scheduled_interviews_route(
    upcoming_only: bool = Query(False, description="Set to true to only fetch upcoming interviews."),
    db: Session = Depends(database.get_db),
    current_interviewer: Interviewer = Depends(get_current_active_interviewer)
):
    interviews_db = crud_scheduling.get_scheduled_interviews_for_interviewer(
        db, interviewer_id=current_interviewer.id, upcoming_only=upcoming_only # type: ignore
    )
    response_list = []
    interviewer_public_profile = resp_m.InterviewerPublicProfile.model_validate(current_interviewer)
    for interview_db_item in interviews_db:
        user_public_profile = None
        if interview_db_item.user:
            user_public_profile = resp_m.UserPublicProfile.model_validate(interview_db_item.user)
        response_list.append(resp_m.ScheduledInterviewResponse(
            id=interview_db_item.id, interview_datetime_utc=interview_db_item.interview_datetime_utc, # type: ignore
            duration_minutes=interview_db_item.duration_minutes, status=interview_db_item.status.value, # type: ignore
            meeting_link=interview_db_item.meeting_link, user=user_public_profile, interviewer=interviewer_public_profile, # type: ignore
            created_at=interview_db_item.created_at, updated_at=interview_db_item.updated_at # type: ignore
        ))
    return response_list

@router.patch("/interviews/{interview_id}/confirm", response_model=resp_m.ScheduledInterviewResponse)
async def interviewer_confirm_interview_route(
    interview_id: int,
    confirm_data: rm.InterviewActionRequest,
    db: Session = Depends(database.get_db),
    current_interviewer: Interviewer = Depends(get_current_active_interviewer)
):
    interview_db = crud_scheduling.get_scheduled_interview_by_id(db, interview_id)
    if not interview_db or interview_db.interviewer_id != current_interviewer.id: # type: ignore
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found or not assigned to this interviewer.")
    if interview_db.status != InterviewStatus.PENDING_CONFIRMATION: # type: ignore
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Interview cannot be confirmed. Current status: {interview_db.status.value}")

    updated_interview_db = crud_scheduling.update_scheduled_interview(
        db, interview_id=interview_id, status=InterviewStatus.CONFIRMED, 
        meeting_link=str(confirm_data.meeting_link) if confirm_data.meeting_link else interview_db.meeting_link # type: ignore
    )
    if not updated_interview_db: 
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to confirm interview.")
    
    user_profile = resp_m.UserPublicProfile.model_validate(updated_interview_db.user) if updated_interview_db.user else None
    return resp_m.ScheduledInterviewResponse(
        id=updated_interview_db.id, interview_datetime_utc=updated_interview_db.interview_datetime_utc, # type: ignore
        duration_minutes=updated_interview_db.duration_minutes, status=updated_interview_db.status.value, # type: ignore
        meeting_link=updated_interview_db.meeting_link, user=user_profile,  # type: ignore
        interviewer=resp_m.InterviewerPublicProfile.model_validate(current_interviewer),
        created_at=updated_interview_db.created_at, updated_at=updated_interview_db.updated_at # type: ignore
    )

# --- USER: Actions on a specific interview ---
@router.patch("/interviews/{interview_id}/cancel", response_model=resp_m.ScheduledInterviewResponse)
async def user_cancel_interview_route(
    interview_id: int,
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_active_user)
):
    interview_db = crud_scheduling.get_scheduled_interview_by_id(db, interview_id)
    if not interview_db or interview_db.user_id != current_user.id: # type: ignore
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found or you are not authorized.")
    
    # Add business logic for cancellation window (e.g., cannot cancel X hours before)
    # cancellation_deadline = interview_db.interview_datetime_utc - timedelta(hours=getattr(settings, 'USER_CANCELLATION_WINDOW_HOURS', 24))
    # if datetime.now(timezone.utc) > cancellation_deadline:
    #    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot cancel interview: it is too close to the start time or has passed.")

    if interview_db.status not in [InterviewStatus.PENDING_CONFIRMATION, InterviewStatus.CONFIRMED]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Interview cannot be cancelled. Current status: {interview_db.status.value}")

    try:
        with db.begin_nested(): # Ensures atomicity for updating interview and slot
            updated_interview_db = crud_scheduling.update_scheduled_interview(db, interview_id, status=InterviewStatus.CANCELLED_BY_USER)
            if not updated_interview_db: 
                raise Exception("Failed to update interview status during cancellation.") # Will be caught by outer try-except

            if updated_interview_db.availability_slot_id: # type: ignore
                slot_unbooked = crud_scheduling.update_slot_booked_status(db, slot_id=updated_interview_db.availability_slot_id, is_booked=False) # type: ignore
                if not slot_unbooked:
                    logger.warning(f"Could not unbook slot {updated_interview_db.availability_slot_id} for cancelled interview {interview_id}")
                    # This might warrant a rollback if unbooking is critical.
                    raise Exception("Failed to unbook slot during interview cancellation.")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to cancel interview {interview_id} and unbook slot: {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to process interview cancellation.")

    db.refresh(updated_interview_db) # Refresh after commit
    
    interviewer_profile = resp_m.InterviewerPublicProfile.model_validate(updated_interview_db.interviewer) if updated_interview_db.interviewer else None
    return resp_m.ScheduledInterviewResponse(
        id=updated_interview_db.id, interview_datetime_utc=updated_interview_db.interview_datetime_utc, # type: ignore
        duration_minutes=updated_interview_db.duration_minutes, status=updated_interview_db.status.value, # type: ignore
        meeting_link=updated_interview_db.meeting_link,  # type: ignore
        user=resp_m.UserPublicProfile.model_validate(current_user), 
        interviewer=interviewer_profile,
        created_at=updated_interview_db.created_at, updated_at=updated_interview_db.updated_at # type: ignore
    )

