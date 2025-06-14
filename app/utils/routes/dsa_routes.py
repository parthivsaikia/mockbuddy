from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
import json
import logging
import os 

from app.models.request_models import DSARequest, ProblemStatementRequest, EvaluationRequest
from app.models.response_models import DSAResponse, TestCaseResponse, EvaluationResponse, GeneratedTestCaseData, DSAQuestion # Added DSAQuestion import
from app.services.question_selector import get_dsa_questions
from app.services.testcase_generator import generate_or_get_test_case 
from app.services.dsa_evaluator import evaluate_code
from app.services.piston_executor import execute_on_piston
from app.db.database import get_db
from app.db.crud_dsa import save_dsa_evaluation
from app.utils.testcase_utils import load_test_case 

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["DSA"])

@router.post("/dsa/questions", response_model=DSAResponse)
def get_dsa_questions_route(request: DSARequest):
    try:
        company = request.company
        total_required = request.total_required

        questions_data: list[dict] = get_dsa_questions(company, total_required)
        
        parsed_questions: list[DSAQuestion] = []
        for q_data in questions_data:
            try:
                parsed_questions.append(DSAQuestion(**q_data))
            except Exception as e:
                logger.error(f"Error parsing question data into DSAQuestion model: {q_data}, error: {e}", exc_info=True)
                continue 
        
        if not parsed_questions and questions_data: 
            raise HTTPException(status_code=500, detail="Failed to parse any question data from the service.")

        return DSAResponse(questions=parsed_questions)
    except HTTPException as e: 
        raise e
    except Exception as e:
        logger.error(f"Error getting DSA questions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get questions: {str(e)}")

@router.post("/generate-testcase", response_model=TestCaseResponse)
def generate_testcase_endpoint(
    request: ProblemStatementRequest, 
    db: Session = Depends(get_db)
):
    try:
        input_data, expected_output, message, q_hash = generate_or_get_test_case(
            problem_statement=request.problem_description,
            db=db,
            company=request.company
        )
        return TestCaseResponse(
            question_hash=q_hash,
            testcase=GeneratedTestCaseData(input_data=input_data, expected_output=expected_output),
            message=message,
            company=request.company
        )
    except ValueError as e:
        logger.error(f"Validation error in testcase generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e: 
        logger.error(f"Runtime error in testcase generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=503, detail=str(e)) 
    except Exception as e:
        logger.error(f"Error generating testcase: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.post("/submit", response_model=EvaluationResponse)
def evaluate_submission(req: EvaluationRequest, db: Session = Depends(get_db)):
    try:
        input_data, expected_output, tc_message, _ = generate_or_get_test_case(
            problem_statement=req.problem_statement,
            db=db,
            company=None 
        )
        logger.info(f"Test case status for submission: {tc_message}")
        
        piston_result = execute_on_piston(
            code=req.candidate_code,
            language=req.language,
            version=req.version,
            input_dict=input_data, 
            expected_output=expected_output
        )

        response_data = {
            "compile_error": piston_result.get("compile_error"),
            "runtime_error": piston_result.get("runtime_error"),
            "execution_stdout": piston_result.get("stdout"),
            "execution_stderr": piston_result.get("stderr"),
            "passed_testcase": piston_result.get("passed", False),
            "logical_correctness": None,
            "complexity_analysis": None,
            "edge_cases": None,
            "readability": None,
            "suggestions": None,
            "score_and_verdict": None,
            "raw": None,
            "error": None
        }
        
        if response_data["passed_testcase"]:
            logger.info("Test case passed, proceeding to LLM evaluation.")
            try:
                llm_eval = evaluate_code(
                    candidate_code=req.candidate_code,
                    problem_statement=req.problem_statement,
                    code_language=req.language
                )
                response_data.update({
                    "logical_correctness": llm_eval.get("logical_correctness"),
                    "complexity_analysis": llm_eval.get("complexity_analysis"),
                    "edge_cases": llm_eval.get("edge_cases"),
                    "readability": llm_eval.get("readability"),
                    "suggestions": llm_eval.get("suggestions"),
                    "score_and_verdict": llm_eval.get("score_and_verdict"),
                    "raw": llm_eval.get("raw"),
                    "error": llm_eval.get("error") 
                })
            except Exception as e:
                logger.error(f"LLM evaluation failed: {str(e)}", exc_info=True)
                response_data["error"] = f"LLM evaluation failed: {str(e)}"
        else:
            logger.info("Test case failed or error in execution, skipping LLM evaluation.")

        evaluation_response = EvaluationResponse(**response_data)

        feedback_parts = []
        if evaluation_response.passed_testcase:
            if evaluation_response.logical_correctness: feedback_parts.append(f"Logical Correctness: {evaluation_response.logical_correctness}")
            if evaluation_response.complexity_analysis: feedback_parts.append(f"Complexity Analysis: {evaluation_response.complexity_analysis}")
            if evaluation_response.edge_cases: feedback_parts.append(f"Edge Cases: {evaluation_response.edge_cases}")
            if evaluation_response.readability: feedback_parts.append(f"Readability: {evaluation_response.readability}")
            if evaluation_response.suggestions: feedback_parts.append(f"Suggestions: {evaluation_response.suggestions}")
        
        if evaluation_response.execution_stdout: feedback_parts.append(f"Execution Stdout: {evaluation_response.execution_stdout}")
        if evaluation_response.execution_stderr: feedback_parts.append(f"Execution Stderr: {evaluation_response.execution_stderr}")
        if evaluation_response.compile_error: feedback_parts.append(f"Compile Error: {evaluation_response.compile_error}")
        if evaluation_response.runtime_error: feedback_parts.append(f"Runtime Error: {evaluation_response.runtime_error}")
        if evaluation_response.error: feedback_parts.append(f"Evaluation Error: {evaluation_response.error}")

        final_feedback = "\n".join(feedback_parts) if feedback_parts else "No detailed feedback available."
        
        score = None
        if evaluation_response.score_and_verdict and "/" in evaluation_response.score_and_verdict:
            try:
                score_str = evaluation_response.score_and_verdict.split("/")[0].strip()
                score = int(score_str)
            except ValueError:
                logger.warning(f"Could not parse score from: {evaluation_response.score_and_verdict}")

        save_dsa_evaluation(
            db=db,
            user_id=req.user_id,
            question=req.problem_statement,
            language=req.language,
            user_code=req.candidate_code,
            passed_testcases=str(evaluation_response.passed_testcase),
            score=score,
            feedback=final_feedback
        )

        return evaluation_response

    except ValueError as e:
        logger.error(f"Validation or input error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e: 
        logger.error(f"Runtime error during submission process: {str(e)}", exc_info=True)
        raise HTTPException(status_code=503, detail=str(e)) 
    except Exception as e:
        logger.error(f"Unexpected error in evaluation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")