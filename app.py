from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import logging

from models import Contact, ContentInfo, get_db, create_tables
from drip_logic import add_new_contact_and_start_drip, trigger_drip_processing, drip_manager, process_contacts_without_industry
from mail_service import check_and_update_replies
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Email Drip Campaign API", version="1.0.0")

# Pydantic models for API
class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    company_name: str
    company_url: Optional[str] = None
    industry: Optional[str] = None

class ContactResponse(BaseModel):
    id: int
    name: str
    email: str
    company_name: str
    company_url: Optional[str]
    industry: Optional[str]
    status: str
    last_email_sent: Optional[datetime]
    drip1_date: Optional[datetime]
    drip2_date: Optional[datetime]
    drip3_date: Optional[datetime]
    reply_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ContentInfoCreate(BaseModel):
    contact_id: int
    client_email: Optional[str] = None
    initial_email_content: Optional[str] = None
    drip1_email_content: Optional[str] = None
    drip2_email_content: Optional[str] = None
    drip3_email_content: Optional[str] = None
    reply_email_content: Optional[str] = None

# Initialize scheduler
scheduler = BackgroundScheduler()

def scheduled_drip_processing():
    """Background task to process drips"""
    try:
        logger.info("Running scheduled drip processing...")
        drip_manager.process_pending_drips()
        check_and_update_replies()
        logger.info("Scheduled drip processing completed")
    except Exception as e:
        logger.error(f"Error in scheduled drip processing: {str(e)}")

def scheduled_reply_checking():
    """Background task to check for replies"""
    try:
        logger.info("Checking for email replies...")
        reply_count = check_and_update_replies()
        logger.info(f"Reply checking completed. Found {reply_count} new replies.")
    except Exception as e:
        logger.error(f"Error checking replies: {str(e)}")

# Schedule tasks
scheduler.add_job(
    func=scheduled_drip_processing,
    trigger=IntervalTrigger(days=1),  # Run daily for drip status checking and sending
    id='drip_processing',
    name='Process pending drip campaigns daily',
    replace_existing=True
)

scheduler.add_job(
    func=scheduled_reply_checking,
    trigger=IntervalTrigger(minutes=30),  # Check replies every 30 minutes
    id='reply_checking',
    name='Check for email replies and send meeting emails',
    replace_existing=True
)

@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler"""
    try:
        create_tables()
        scheduler.start()
        logger.info("Application started successfully")
        logger.info("Scheduler started - drip processing daily, reply checking every 30 minutes")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        scheduler.shutdown()
        logger.info("Application shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Email Drip Campaign API is running", "status": "healthy"}

@app.post("/contacts", response_model=dict)
async def add_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    """Add new contact and start drip campaign"""
    try:
        result = add_new_contact_and_start_drip(
            name=contact.name,
            email=contact.email,
            company_name=contact.company_name,
            company_url=contact.company_url,
            industry=contact.industry
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error adding contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/contacts", response_model=List[ContactResponse])
async def get_contacts(
    skip: int = 0, 
    limit: int = 100, 
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all contacts with optional filtering"""
    try:
        query = db.query(Contact)
        
        if status:
            query = query.filter(Contact.status == status)
        
        contacts = query.offset(skip).limit(limit).all()
        return contacts
        
    except Exception as e:
        logger.error(f"Error fetching contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(contact_id: int, db: Session = Depends(get_db)):
    """Get specific contact by ID"""
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        return contact
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching contact {contact_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/contacts/{contact_id}/drip-status")
async def get_drip_status(contact_id: int):
    """Get drip campaign status for a contact"""
    try:
        status = drip_manager.get_drip_status(contact_id)
        
        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting drip status for contact {contact_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trigger-drips")
async def trigger_drips():
    """Manually trigger drip processing for testing"""
    try:
        result = trigger_drip_processing()
        return result
        
    except Exception as e:
        logger.error(f"Error triggering drips: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/check-replies")
async def check_replies():
    """Manually trigger reply checking"""
    try:
        reply_count = check_and_update_replies()
        return {"message": f"Reply check completed. Found {reply_count} new replies."}
        
    except Exception as e:
        logger.error(f"Error checking replies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-contacts")
async def process_contacts():
    """Process contacts without industry - generate industry and send initial emails"""
    try:
        result = process_contacts_without_industry()
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get campaign statistics"""
    try:
        total_contacts = db.query(Contact).count()
        replied_contacts = db.query(Contact).filter(Contact.status == "replied").count()
        pending_contacts = db.query(Contact).filter(Contact.status != "replied").count()
        
        # Count drips sent
        drip1_sent = db.query(Contact).filter(Contact.drip1_date.isnot(None)).count()
        drip2_sent = db.query(Contact).filter(Contact.drip2_date.isnot(None)).count()
        drip3_sent = db.query(Contact).filter(Contact.drip3_date.isnot(None)).count()
        
        return {
            "total_contacts": total_contacts,
            "replied_contacts": replied_contacts,
            "pending_contacts": pending_contacts,
            "reply_rate": round((replied_contacts / total_contacts * 100), 2) if total_contacts > 0 else 0,
            "drips_sent": {
                "drip1": drip1_sent,
                "drip2": drip2_sent,
                "drip3": drip3_sent
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    """Delete a contact and their content info"""
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        # Delete content info if exists
        if contact.content_info:
            db.delete(contact.content_info)
        
        # Delete contact
        db.delete(contact)
        db.commit()
        
        return {"message": f"Contact {contact_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact {contact_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)