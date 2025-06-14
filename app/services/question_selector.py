import os
import random
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
import logging
from typing import List, Dict, Optional
import math

# Set up logging
logger = logging.getLogger(__name__)

# Load the .env file and configure Gemini
load_dotenv(dotenv_path='mockbuddy.env')
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Path to dataset folder
DATASET_PATH = "data/dsa_dataset"

def generate_prompt(company_name: str, existing_questions_info: List[Dict]) -> str:
    if not existing_questions_info:
        return f"Generate a DSA coding interview question suitable for {company_name}."

    difficulties = [q.get('difficulty_level', '').lower() for q in existing_questions_info if q.get('difficulty_level')]
    topics = [q.get('topic_tagged_text', '').lower() for q in existing_questions_info if q.get('topic_tagged_text')]

    unique_difficulties = list(set(filter(None, difficulties)))
    unique_topics = list(set(filter(None, topics)))

    prompt = (
        f"Generate a DSA coding interview question suitable for {company_name}. "
    )

    if unique_difficulties:
        prompt += (
            f"The previously asked questions have difficulty levels: {', '.join(unique_difficulties)}. "
            f"Please provide a new question at the same or slightly higher difficulty level. "
        )

    if unique_topics:
        prompt += (
            f"Try to cover a different topic than the existing ones, which include: {', '.join(unique_topics)}. "
        )

    prompt += "Format the question clearly for an interview setting."

    return prompt

def generate_questions_via_gemini(company: str, count: int, existing_questions_info: Optional[List[Dict]] = None) -> List[str]:
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        generated_questions = []

        for i in range(count):
            try:
                prompt = generate_prompt(company, existing_questions_info or [])
                response = model.generate_content(prompt)
                if response.text:
                    generated_questions.append(response.text.strip())
                else:
                    logger.warning(f"Empty response from Gemini for question {i+1}")
                    generated_questions.append(f"Generated DSA question for {company} - Question {i+1}")
            except Exception as e:
                logger.error(f"Error generating question {i+1}: {str(e)}")
                generated_questions.append(f"Generated DSA question for {company} - Question {i+1}")

        return generated_questions
    except Exception as e:
        logger.error(f"Error in generate_questions_via_gemini: {str(e)}")
        # Fallback to simple generated questions
        return [f"Generated DSA question for {company} - Question {i+1}" for i in range(count)]

def load_company_dataset(company_name: str) -> Optional[pd.DataFrame]:
    try:
        if not os.path.exists(DATASET_PATH):
            logger.warning(f"Dataset path {DATASET_PATH} does not exist")
            return None

        for filename in os.listdir(DATASET_PATH):
            if filename.lower() == f"{company_name.lower()}.csv":
                filepath = os.path.join(DATASET_PATH, filename)
                df = pd.read_csv(filepath)
                logger.info(f"Loaded dataset for {company_name} with {len(df)} records")
                return df

        logger.info(f"No dataset file found for company: {company_name}")
        return None
    except Exception as e:
        logger.error(f"Error loading dataset for {company_name}: {str(e)}")
        return None

def clean_question_dict(q: Dict) -> Dict:
    """
    Replace NaN or None in question dict values with safe defaults (empty string).
    """
    cleaned = {}
    for k, v in q.items():
        if v is None:
            cleaned[k] = ""
        elif isinstance(v, float) and math.isnan(v):
            cleaned[k] = ""
        else:
            cleaned[k] = v
    return cleaned

def get_dsa_questions(company: str, total_required: int = 3) -> List[Dict]:
    try:
        df = load_company_dataset(company)
        required_columns = ['problem_id', 'question_title', 'question_text', 'topic_tagged_text', 'difficulty_level', 'hints']

        if df is None:
            logger.info(f"No dataset found for {company}. Generating all questions via Gemini.")
            generated_texts = generate_questions_via_gemini(company, total_required)

            questions = []
            for i, question_text in enumerate(generated_texts):
                question = {
                    'problem_id': f'gen_{i+1}',
                    'question_title': question_text,
                    'question_text': '',
                    'topic_tagged_text': '',
                    'difficulty_level': '',
                    'hints': ''
                }
                questions.append(clean_question_dict(question))

            return questions

        # Rename columns to consistent names
        column_mapping = {
            'problem id': 'problem_id',
            'question title': 'question_title',
            'question text': 'question_text',
            'topic tagged text': 'topic_tagged_text',
            'difficulty level': 'difficulty_level',
            'hints': 'hints'
        }
        df = df.rename(columns=column_mapping)

        existing_columns = [col for col in required_columns if col in df.columns]
        df = df[existing_columns]

        for col in required_columns:
            if col not in df.columns:
                df[col] = ''

        # Drop rows with missing or empty question_title
        df = df.dropna(subset=['question_title'])
        df = df[df['question_title'].str.strip() != '']

        if len(df) >= total_required:
            sampled_df = df.sample(n=total_required, random_state=42)
            questions = [clean_question_dict(q) for q in sampled_df.to_dict(orient="records")]
            logger.info(f"Selected {total_required} questions from dataset for {company}")
            return questions

        existing_count = len(df)
        needed = total_required - existing_count
        logger.info(f"Found only {existing_count} existing questions for {company}, generating {needed} more.")

        existing_questions_info = df.to_dict(orient="records") if not df.empty else []

        generated_texts = generate_questions_via_gemini(company, needed, existing_questions_info)

        generated_questions = []
        for i, question_text in enumerate(generated_texts):
            question = {
                'problem_id': f'gen_{existing_count + i + 1}',
                'question_title': question_text,
                'question_text': '',
                'topic_tagged_text': '',
                'difficulty_level': '',
                'hints': ''
            }
            generated_questions.append(clean_question_dict(question))

        all_questions = [clean_question_dict(q) for q in df.to_dict(orient="records")] + generated_questions
        logger.info(f"Combined {existing_count} existing + {needed} generated questions for {company}")

        return all_questions

    except Exception as e:
        logger.error(f"Error in get_dsa_questions for {company}: {str(e)}")
        try:
            generated_texts = generate_questions_via_gemini(company, total_required)
            fallback_questions = []
            for i, question_text in enumerate(generated_texts):
                question = {
                    'problem_id': f'fallback_{i+1}',
                    'question_title': question_text,
                    'question_text': '',
                    'topic_tagged_text': '',
                    'difficulty_level': '',
                    'hints': ''
                }
                fallback_questions.append(clean_question_dict(question))
            return fallback_questions
        except Exception as fallback_error:
            logger.error(f"Fallback question generation also failed: {str(fallback_error)}")
            return []
