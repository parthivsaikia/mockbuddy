from sqlalchemy.orm import Session
from typing import Optional, Any, List ,Dict
import json

from app.models.db_models import TestCase, DSAEvaluation, CoreEvaluation 

def get_test_case_by_hash(db: Session, question_hash: str) -> Optional[TestCase]:
    """Retrieves a test case by its question_hash."""
    return db.query(TestCase).filter(TestCase.question_hash == question_hash).first()

def create_test_case(
    db: Session,
    problem_statement: str,
    question_hash: str,
    input_data: Dict[str, Any], 
    expected_output: str,      
    company: Optional[str] = None
) -> TestCase:
    """
    Creates a new test case in the database.
    input_data (structured input_config) is stored as a JSON string.
    expected_output (direct stdout string) is stored as text.
    """
    db_test_case = TestCase(
        company=company,
        question_hash=question_hash,
        problem_statement=problem_statement,
        input_data=json.dumps(input_data), 
        expected_output=expected_output    
    )
    db.add(db_test_case)
    db.commit()
    db.refresh(db_test_case)
    return db_test_case

def save_dsa_evaluation(
    db: Session, 
    user_id: int, 
    question: str,       
    language: str, 
    user_code: str,
    passed_testcases: str,  
    score: Optional[int] = None, 
    feedback: Optional[str] = None
) -> DSAEvaluation:
    """Saves a DSA code submission evaluation result."""
    dsa_eval = DSAEvaluation(
        user_id=user_id, 
        question=question, 
        language=language, 
        user_code=user_code,
        passed_testcases=str(passed_testcases),
        score=score, 
        feedback=feedback
    )
    db.add(dsa_eval)
    db.commit()
    db.refresh(dsa_eval)
    return dsa_eval

def get_dsa_evaluations_by_user_id(
    db: Session, 
    user_id: int, 
    skip: int = 0, 
    limit: int = 10
) -> List[DSAEvaluation]:
    """Retrieves DSA evaluation history for a user with pagination."""
    return db.query(DSAEvaluation).filter(
        DSAEvaluation.user_id == user_id
    ).order_by(DSAEvaluation.created_at.desc()).offset(skip).limit(limit).all()




def save_core_evaluation(
    db: Session,
    user_id: int,
    subject: str,
    question: str,
    user_answer: str,
    correct_answer: Optional[str] = None,
    feedback: Optional[str] = None,
    score: Optional[int] = None,
    difficulty: Optional[str] = None,
    topic: Optional[str] = None
) -> CoreEvaluation:
    """Saves a Core subject evaluation result."""
    core_eval = CoreEvaluation(
        user_id=user_id,
        subject=subject,
        question=question,
        user_answer=user_answer,
        correct_answer=correct_answer,
        feedback=feedback,
        score=score,
        difficulty=difficulty,
        topic=topic
    )
    db.add(core_eval)
    db.commit()
    db.refresh(core_eval)
    return core_eval

def get_core_evaluations_by_user_id(
    db: Session, 
    user_id: int, 
    skip: int = 0, 
    limit: int = 10
) -> List[CoreEvaluation]:
    """Retrieves Core subject evaluation history for a user with pagination."""
    return db.query(CoreEvaluation).filter(
        CoreEvaluation.user_id == user_id
    ).order_by(CoreEvaluation.created_at.desc()).offset(skip).limit(limit).all()