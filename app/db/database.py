# app/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession
import logging

from app.config import settings # Import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL # Use from settings

# Add connect_args for SQLite if DATABASE_URL points to SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False


try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info(f"Database engine created for URL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}") # Avoid logging password
except Exception as e:
    logger.error(f"Failed to create database engine: {e}", exc_info=True)
    raise RuntimeError(f"Database configuration error: {e}")


def get_db() -> SQLAlchemySession: # type: ignore
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# For use in non-FastAPI contexts (e.g. scripts, standalone services)
def get_db_session_for_scripts() -> SQLAlchemySession:
    db = SessionLocal()
    return db # Caller is responsible for db.close()


def create_db_tables(): # Renamed for clarity
    try:
        logger.info("Attempting to create database tables if they don't exist...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        raise