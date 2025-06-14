import google.generativeai as genai
import json
import re
import os
import hashlib
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from typing import Tuple, Any, Optional, Dict
import logging

from app.db.crud_dsa import get_test_case_by_hash, create_test_case
from app.db.database import get_db
from app.models.db_models import TestCase # Import TestCase for type hinting

# Load environment variables and configure Gemini
load_dotenv(dotenv_path='mockbuddy.env')
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    logging.warning("GOOGLE_API_KEY not found in environment. Test case generation will fail if not found in DB.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

model = None
try:
    if GEMINI_API_KEY:
        model = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    logging.error(f"Failed to initialize Gemini model: {e}", exc_info=True)

logger = logging.getLogger(__name__)

# === Prompt Builder ===
def get_gemini_prompt(problem_description: str) -> str:
    return f"""
You are a helpful assistant tasked with generating a **simple valid test case** for a LeetCode-style problem.

---

📘 Problem:
{problem_description}

---

🧾 Your output **must follow this strict JSON format**:
{{
  "input": <valid input in LeetCode-style representing parameters, e.g., {{"nums": [1,2,3], "target": 4}} or just [1,2,3] if one array is the input>,
  "expected_output": <expected output for that input, e.g., [0,1] or 7>
}}

📌 Serialization Rules:
- Input should generally be a dictionary if there are multiple named parameters. If there's a single unnamed input (like just an array), it can be that direct value.
- Arrays: [1, 2, 3]
- Strings: "abc"
- Integers/Floats: 42, 3.14
- Linked Lists (represented as arrays for JSON): [1, 2, 3]
- Binary Trees (represented as arrays for JSON, level-order with nulls): [4, 2, 6, null, 3]
- Nested structures: use typical LeetCode JSON-like style.

---

⚠️ DO NOT include:
- Any explanations
- Comments
- Markdown (```json ... ```)
- Additional text

✅ Only output the raw JSON object with valid syntax.
✅ Keep the test case **simple and minimal** (1 valid base case).
Ensure the JSON is a single object with "input" and "expected_output" keys.
"""

# === Helper: Strip JSON from code block ===
def strip_code_block_and_parse_json(text: str) -> Dict[str, Any]:
    cleaned_text = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", text).strip()
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini response: '{cleaned_text}'. Error: {e}", exc_info=True)
        raise ValueError(f"Gemini returned invalid JSON. Raw response excerpt: {text[:200]}")


# === Main Generator ===
def generate_or_get_test_case(
    problem_statement: str,
    db: Session, 
    company: Optional[str] = None
) -> Tuple[Any, Any, str, str]:
    """
    Generates a new test case or retrieves an existing one from the database.
    Returns: (input_data, expected_output, message, question_hash)
    """
    question_hash = hashlib.sha256(problem_statement.encode('utf-8')).hexdigest()

    # 1. Try to fetch from DB
    db_test_case: Optional[TestCase] = get_test_case_by_hash(db, question_hash)
    if db_test_case:
        logger.info(f"Test case found in DB for hash: {question_hash}")
        
        # Explicitly acknowledge these are strings fetched from DB for Pylance
        input_data_str: str = db_test_case.input_data  # type: ignore
        expected_output_str: str = db_test_case.expected_output # type: ignore

        try:
            input_data = json.loads(input_data_str)
            expected_output = json.loads(expected_output_str)
            return input_data, expected_output, "Test case fetched from DB.", question_hash
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse stored JSON for test case {db_test_case.id} (hash: {question_hash}): {e}", exc_info=True)
            logger.debug(f"Problematic input_data_str from DB: {input_data_str}")
            logger.debug(f"Problematic expected_output_str from DB: {expected_output_str}")
            # Fall through to regenerate if parsing fails for a stored test case

    # 2. If not in DB or failed to parse, generate using Gemini
    logger.info(f"Generating new test case (hash: {question_hash}). Reason: Not found in DB or stored version was unparsable.")
    if not model:
        logger.error("Gemini model is not initialized. Cannot generate new test case.")
        raise RuntimeError("Test case generation service (Gemini) is unavailable and test case not found/parsable in DB.")

    prompt = get_gemini_prompt(problem_statement)
    try:
        response = model.generate_content(prompt) # type: ignore
        
        # Check for empty or invalid response structure from Gemini
        if not response.candidates or not hasattr(response.candidates[0], 'content') or not response.candidates[0].content.parts:
             logger.error(f"Gemini response empty or invalid structure for problem: {problem_statement}. Response: {response}")
             raise ValueError("Gemini returned an empty or invalid response structure.")
        
        response_text = response.candidates[0].content.parts[0].text
        if not response_text:
            logger.error(f"Gemini response part contained no text. Full response: {response}")
            raise ValueError("Gemini response part was empty.")

        testcase_json = strip_code_block_and_parse_json(response_text)

    except Exception as e: 
        logger.error(f"Error during Gemini test case generation or parsing: {str(e)}", exc_info=True)
        # Provide more context about the problem statement that failed.
        problem_preview = problem_statement[:100] + "..." if len(problem_statement) > 100 else problem_statement
        raise ValueError(f"Failed to generate/parse test case from Gemini for problem '{problem_preview}': {str(e)}")

    if not isinstance(testcase_json, dict) or "input" not in testcase_json or "expected_output" not in testcase_json:
        logger.error(f"Generated JSON is not in the expected format ('input'/'expected_output' keys missing): {testcase_json}")
        raise ValueError("Generated test case JSON does not contain 'input' and/or 'expected_output' keys.")

    input_data = testcase_json["input"]
    expected_output = testcase_json["expected_output"]

    # 3. Save the new test case to DB
    try:
        create_test_case(
            db=db,
            problem_statement=problem_statement,
            question_hash=question_hash,
            input_data=input_data, 
            expected_output=expected_output,
            company=company
        )
        logger.info(f"New test case generated and saved to DB for hash: {question_hash}")
        return input_data, expected_output, "Test case generated and saved to DB.", question_hash
    except Exception as e:
        logger.error(f"Failed to save newly generated test case to DB: {str(e)}", exc_info=True)
        return input_data, expected_output, f"Test case generated but failed to save to DB (will use unsaved): {str(e)}", question_hash

def generate_or_get_test_case_standalone(
    problem_statement: str,
    company: Optional[str] = None
) -> Tuple[Any, Any, str, str]:
    db: Optional[Session] = None
    try:
        db = get_db()
        return generate_or_get_test_case(problem_statement, db, company)
    finally:
        if db:
            db.close()