import pandas as pd
import os
from app.utils.logger import get_logger

logger = get_logger(__name__)

def load_questions_for_company(company_name: str):
    file_path = os.path.join("app", "data", "dsa_dataset", f"{company_name.lower()}.csv")
    
    if not os.path.exists(file_path):
        logger.error(f"CSV not found for {company_name}")
        raise FileNotFoundError(f"No dataset found for company: {company_name}")
    
    logger.info(f"Loaded DSA questions from {file_path}")
    return pd.read_csv(file_path)

def get_available_companies():
    folder_path = os.path.join("app", "data", "dsa_dataset")
    if not os.path.exists(folder_path):
        logger.warning("DSA dataset folder is missing")
        return []
    
    files = os.listdir(folder_path)
    companies = [f.replace(".csv", "") for f in files if f.endswith(".csv")]
    logger.info(f"Available companies: {companies}")
    return companies
