import os
import google.generativeai as genai
from app.utils.filler_utils import extract_filler_words
import re

genai.configure(api_key=os.getenv("GOOGLE_API_KEY")) # type: ignore
model = genai.GenerativeModel("gemini-1.5-flash") # type: ignore




def parse_evaluation_response(response_text):
    """Extract score, feedback, and follow-up from LLM response"""
    score_match = re.search(r"Score:\s*(\d+(\.\d+)?)", response_text, re.IGNORECASE)
    feedback_match = re.search(r"Feedback:\s*(.+?)(?=Follow-up Question:|$)", response_text, re.IGNORECASE | re.DOTALL)
    followup_match = re.search(r"Follow-up Question:\s*(.+)", response_text, re.IGNORECASE | re.DOTALL)

    score = float(score_match.group(1)) if score_match else None
    feedback = feedback_match.group(1).strip() if feedback_match else ""
    followup = followup_match.group(1).strip() if followup_match else ""

    return score, feedback, followup

def run_core_evaluation(question: str, transcription: str, filler_count: int):
    prompt = f"""
You are a senior technical interviewer evaluating a spoken answer in a core computer science mock interview. The subject could be DBMS, Operating Systems, Computer Networks, or Object-Oriented Programming.

Your task:
1. Evaluate the candidate’s spoken answer for:
   - Technical correctness and depth
   - Clarity and structure
   - Use of accurate terminology
   - Overall delivery (including filler words)

2. Then return your evaluation in **this exact format**:

Score: <a number from 1 to 10>  
Feedback: <brief, natural spoken feedback covering both content and delivery>  
Follow-up Question: <a question that tests deeper understanding on the same topic>

Speak as if you're talking directly to the candidate — friendly but professional.

---

Here’s the evaluation input:

Question: {question}  
Answer: {transcription}  
Filler Word Count: {filler_count}
"""

    # Call LLM to evaluate
    response = model.generate_content(prompt)
    evaluation = response.text.strip()

    try:
        score, feedback, followup = [x.strip() for x in evaluation.split("|")]
        score = float(score)
    except Exception as e:
        print("Error parsing evaluation:", e)
        score, feedback, followup = None, evaluation, ""

    return score, feedback, followup
