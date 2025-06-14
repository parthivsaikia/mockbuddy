# app/routes/interviewer_profile_routes.py
from fastapi import APIRouter, Depends, HTTPException, status,Query
from sqlalchemy.orm import Session
from typing import List

from app.db import database, crud_interviewer
from app.models import request_models as rm 
from app.models import response_models as resp_m
from app.models.db_models import Interviewer
from app.services.auth_service_interviewer import AuthServiceInterviewer,get_current_active_interviewer,get_current_interviewer


router = APIRouter(tags=["Interviewer Profiles"]) 

@router.get("/me", response_model=resp_m.InterviewerResponse)
async def read_interviewer_me_profile_route(
    current_interviewer: Interviewer = Depends(get_current_active_interviewer)
):
    return resp_m.InterviewerResponse.model_validate(current_interviewer)

@router.put("/me", response_model=resp_m.InterviewerResponse)
async def update_interviewer_me_profile_route(
    profile_update_in: rm.InterviewerUpdate, 
    db: Session = Depends(database.get_db),
    current_interviewer: Interviewer = Depends(get_current_active_interviewer)
):
    updated_interviewer_db = crud_interviewer.update_interviewer_profile(
        db, interviewer_id=current_interviewer.id, profile_data_in=profile_update_in # type: ignore
    )
    if not updated_interviewer_db:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interviewer not found during update.")
    return resp_m.InterviewerResponse.model_validate(updated_interviewer_db)

@router.get("/", response_model=List[resp_m.InterviewerPublicProfile])
def list_public_interviewers_route(
    skip: int = Query(0, ge=0), 
    limit: int = Query(20, ge=1, le=100), 
    db: Session = Depends(database.get_db)
):
    interviewers_db = crud_interviewer.get_active_verified_interviewers(db, skip=skip, limit=limit)
    return [resp_m.InterviewerPublicProfile.model_validate(interviewer) for interviewer in interviewers_db]


@router.get("/{interviewer_id}/profile", response_model=resp_m.InterviewerPublicProfile)
def get_public_interviewer_profile_route(
    interviewer_id: int, 
    db: Session = Depends(database.get_db)
):
    interviewer_db_obj = crud_interviewer.get_interviewer_by_id(db, interviewer_id)
    if not interviewer_db_obj or not interviewer_db_obj.is_active or not interviewer_db_obj.is_verified: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interviewer not found or not currently available."
        )
    return resp_m.InterviewerPublicProfile.model_validate(interviewer_db_obj)