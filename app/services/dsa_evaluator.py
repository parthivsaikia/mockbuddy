from dotenv import load_dotenv
import google.generativeai as genai
import os

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=GEMINI_API_KEY) # type: ignore
model = genai.GenerativeModel("gemini-1.5-flash") # type: ignore


def evaluate_code(candidate_code: str, problem_statement: str, code_language: str) -> dict:
    """
    Uses LLM to evaluate code quality and performance.

    Returns a structured dict with key insights.
    """

    # === PROMPT BUILDING ===
    prompt = f"""
You are a senior software engineer and coding expert.
Evaluate the candidate's code written in **{code_language}**.

===============================
Problem Statement:
{problem_statement.strip()}

Language: {code_language}

Candidate's Code:
{candidate_code.strip()}
===============================

Please respond with:
1. Logical correctness
2. Time and space complexity
3. Missing edge cases or flaws
4. Code readability and structure
5. Suggestions for improvement
6. Score out of 10 and a short 1-line verdict

Respond in a structured one bullet-point format.
"""

    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # === Parse Response to JSON-like Dict ===
        lines = [line.strip("-• \n") for line in raw_text.splitlines() if line.strip()]
        result = {
            "logical_correctness": lines[0] if len(lines) > 0 else "",
            "complexity_analysis": lines[1] if len(lines) > 1 else "",
            "edge_cases": lines[2] if len(lines) > 2 else "",
            "readability": lines[3] if len(lines) > 3 else "",
            "suggestions": lines[4] if len(lines) > 4 else "",
            "score_and_verdict": lines[5] if len(lines) > 5 else "",
            "raw": raw_text,
            "error": None
        }
        return result

    except Exception as e:
        print(f"[Evaluator Error] {e}")
        return {
            "logical_correctness": None,
            "complexity_analysis": None,
            "edge_cases": None,
            "readability": None,
            "suggestions": None,
            "score_and_verdict": None,
            "raw": None,
            "error": "Evaluation failed due to a server error. Please try again later."
        }