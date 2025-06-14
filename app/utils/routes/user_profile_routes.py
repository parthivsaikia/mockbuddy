from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional 
from datetime import datetime, timezone

from app.db import database, crud_user, crud_dsa, crud_scheduling
from app.models import request_models as rm 
from app.models import response_models as resp_m
from app.models.db_models import User, DSAEvaluation, CoreEvaluation, ScheduledInterview, InterviewStatus 
from app.services.auth_services import get_current_active_user
from app.config import settings 
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["User Profile & History"])

@router.get("/me", response_model=resp_m.UserResponse)
async def read_current_user_profile_route(
    current_user: User = Depends(get_current_active_user) 
):
    return resp_m.UserResponse.model_validate(current_user)

@router.put("/me", response_model=resp_m.UserResponse)
async def update_current_user_profile_route(
    user_update_in: rm.UserProfileUpdate,
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_active_user)
):
    
    updated_user_db = crud_user.update_user_profile(
        db, user_id=current_user.id, user_update_in=user_update_in # type: ignore
    )
    if not updated_user_db: 
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found during update process.")
    return resp_m.UserResponse.model_validate(updated_user_db)

@router.get("/me/dsa-submissions", response_model=List[resp_m.DSASubmissionResponse]) 
async def get_my_dsa_submissions_history_route(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_active_user)
):
    submissions_db: List[DSAEvaluation] = crud_dsa.get_dsa_evaluations_by_user_id( # type: ignore [assignment] 
        db, user_id=current_user.id, skip=skip, limit=limit # type: ignore
    )
    
    response_submissions: List[resp_m.DSASubmissionResponse] = []
    for sub_db in submissions_db:
       
        passed_status_str = "Passed" if sub_db.passed_testcases.lower() == "true" else "Failed"


        response_submissions.append(
            resp_m.DSASubmissionResponse( 
                id=sub_db.id, # type: ignore
                question=sub_db.question,  # type: ignore
                language=sub_db.language, # type: ignore
                difficulty=None, # 
                topic=None,      
                passed_testcases=passed_status_str, 
                total_testcases=1, 
                score=sub_db.score, # type: ignore
                created_at=sub_db.created_at # type: ignore
            )
        )
    return response_submissions

# @router.get("/me/core-submissions", response_model=List[resp_m.CoreSubmissionResponse])
# async def get_my_core_submissions_history_route(
#     skip: int = Query(0, ge=0),
#     limit: int = Query(10, ge=1, le=100),
#     db: Session = Depends(database.get_db),
#     current_user: User = Depends(get_current_active_user)
# ):
#     submissions_db: List[CoreEvaluation] = crud_dsa.get_core_evaluations_by_user_id( # type: ignore [assignment]
#         db, user_id=current_user.id, skip=skip, limit=limit
#     )
#     # CoreSubmissionResponse fields should map well from CoreEvaluation if names align
#     # and CoreSubmissionResponse has `model_config = ConfigDict(from_attributes=True)`
#     return [resp_m.CoreSubmissionResponse.model_validate(sub) for sub in submissions_db]

@router.get("/me/scheduled-interviews", response_model=List[resp_m.ScheduledInterviewResponse])
async def user_get_own_scheduled_interviews_route(
    upcoming_only: bool = Query(False, description="Set to true to only fetch upcoming interviews."),
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_active_user)
):
    interviews_db: List[ScheduledInterview] = crud_scheduling.get_scheduled_interviews_for_user( # type: ignore [assignment]
        db, user_id=current_user.id, upcoming_only=upcoming_only # type: ignore
    )
    
    response_list: List[resp_m.ScheduledInterviewResponse] = []
    # Prepare user profile once if it's the same for all list items
    user_public_profile = resp_m.UserPublicProfile.model_validate(current_user)
    
    for interview_db_item in interviews_db: # Renamed to avoid conflict with interview_db module
        interviewer_public_profile = None
        # `interview_db_item.interviewer` is the Interviewer ORM instance if relationship is loaded
        if interview_db_item.interviewer: 
            interviewer_public_profile = resp_m.InterviewerPublicProfile.model_validate(interview_db_item.interviewer)
        
        response_list.append(resp_m.ScheduledInterviewResponse(
            id=interview_db_item.id, # type: ignore
            interview_datetime_utc=interview_db_item.interview_datetime_utc, # type: ignore
            duration_minutes=interview_db_item.duration_minutes, # type: ignore
            status=interview_db_item.status.value, # Get string value from Enum
            meeting_link=interview_db_item.meeting_link, # type: ignore
            user=user_public_profile, 
            interviewer=interviewer_public_profile,
            created_at=interview_db_item.created_at, # type: ignore
            updated_at=interview_db_item.updated_at # type: ignore
        ))
    return response_list