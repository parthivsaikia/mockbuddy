# app/routes/core_subject_routes.py

from fastapi import APIRouter
from app.models.request_models import CoreEvaluationRequest
from app.models.response_models import CoreEvaluationResponse
from app.utils.filler_utils import extract_filler_words
from app.services.core_coresub import run_core_evaluation

# from app.services.core_coresubquestion import get_core_subject_questions

router = APIRouter()

@router.post("/evaluate", response_model=CoreEvaluationResponse)
async def evaluate_core_subject(request: CoreEvaluationRequest):
    filler_count = extract_filler_words(request.transcription)

    score, feedback, followup = run_core_evaluation(
        question=request.question,
        transcription=request.transcription,
        filler_count=filler_count
    )

    return CoreEvaluationResponse(score=score, feedback=feedback, followup=followup)
