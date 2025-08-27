from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Contact(Base):
    __tablename__ = "first"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    company_name = Column(String(255))
    company_url = Column(String(255))
    industry = Column(String(255))
    status = Column(String(50), default="null")  # null, replied
    last_email_sent = Column(DateTime)
    drip1_date = Column(DateTime)
    drip2_date = Column(DateTime)
    drip3_date = Column(DateTime)
    reply_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    content_info = relationship("ContentInfo", back_populates="contact", uselist=False)

class ContentInfo(Base):
    __tablename__ = "content"
    
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("first.id"), nullable=False)
    client_email = Column(String(255))
    initial_email_content = Column(Text)
    drip1_email_content = Column(Text)
    drip2_email_content = Column(Text)
    drip3_email_content = Column(Text)
    reply_email_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    contact = relationship("Contact", back_populates="content_info")

# Database configuration from your existing setup
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'ssl_ca': os.getenv('DB_SSL_CA')
}

# Build DATABASE_URL from config
DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
if DB_CONFIG['ssl_ca']:
    DATABASE_URL += f"?ssl_ca={DB_CONFIG['ssl_ca']}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
