from sqlalchemy.orm import Session
from tables import SessionLocal, Contact, ContentInfo, DATABASE_AVAILABLE

def get_db_session():
    """Get a database session for frontend operations"""
    if not DATABASE_AVAILABLE or not SessionLocal:
        raise Exception("Database not available")
    return SessionLocal()

def get_db_connection():
    """Legacy function for backward compatibility - returns SQLAlchemy session"""
    return get_db_session()

