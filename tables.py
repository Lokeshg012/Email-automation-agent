from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from contextlib import contextmanager
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

Base = declarative_base()

class UserAuth(Base):
    __tablename__ = "userAuth"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(150), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    status = Column(String(50), nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmailData(Base):
    __tablename__ = "EmailData"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cc = Column(Text)
    company_name = Column(String(255))
    referred = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

class Contact(Base):
    __tablename__ = "first"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    company_name = Column(String(255))
    company_url = Column(String(255))
    linkedin = Column(String(255))
    industry = Column(String(255))
    status = Column(String(50), nullable=True, default=None) 
    booking_status = Column(String(50), nullable=True, default=None)
    drip1_date = Column(DateTime)
    drip2_date = Column(DateTime)
    drip3_date = Column(DateTime)
    mail_sent_status = Column(String(50)) 
    first_mail_date = Column(DateTime)  
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    content_info = relationship("ContentInfo", back_populates="contact", cascade="all, delete-orphan")

class ContentInfo(Base):
    __tablename__ = "content"
    
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("first.id"), nullable=False)
    client_email = Column(String(255))
    email_type = Column(Text)
    subject = Column(Text)
    body = Column(Text(6000))
    thread_id = Column(String(255))
    message_id = Column(String(255), nullable=True)
    reference = Column(Text, nullable=True)
    in_reply_to = Column(String(255), nullable=True)
    sentiment = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  
    
    contact = relationship("Contact", back_populates="content_info")

# --- Database configuration and session management ---

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'ssl_ca': os.getenv('DB_SSL_CA')
}

# Initialize variables to handle potential import errors
engine = None
SessionLocal = None
DATABASE_AVAILABLE = False

try:
    if all([DB_CONFIG['host'], DB_CONFIG['user'], DB_CONFIG['password'], DB_CONFIG['database']]):
        DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        if DB_CONFIG['ssl_ca']:
            DATABASE_URL += f"?ssl_ca={DB_CONFIG['ssl_ca']}"
        
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=280)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        DATABASE_AVAILABLE = True
    else:
        logger.warning("Database configuration incomplete. Database features will be disabled.")
except Exception as e:
    logger.error(f"Database connection failed: {e}. Database features will be disabled.")

def get_db():
    if not DATABASE_AVAILABLE:
        raise Exception("Database not available")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_session():
    if not DATABASE_AVAILABLE:
        raise Exception("Database not available")
    
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()

def create_tables():
    if DATABASE_AVAILABLE and engine:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created successfully")
    else:
        logger.warning("Database not available, skipping table creation")
