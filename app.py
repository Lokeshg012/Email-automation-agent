from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Annotated, TypedDict
from datetime import datetime
import logging
import uvicorn
import os
from pathlib import Path
import atexit
from contextlib import asynccontextmanager

from frontend.routes.auth_routes import auth_router
from frontend.routes.client_routes import client_router
from frontend.routes.email_routes import email_router
from frontend.routes.dashboard_routes import dashboard_router

# Login dependency for protected routes
async def verify_session(request: Request):
    if not request.session.get("user"):
        raise HTTPException(status_code=303, detail="Not authenticated")
    return request.session.get("user")

# Try to import database modules, but don't fail if they're not available
try:
    from tables import Contact, ContentInfo, get_db, create_tables
    from drip_logic import add_new_contact_and_start_drip, trigger_drip_processing, drip_manager
    from mail_service import check_and_update_replies
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.executors.pool import ThreadPoolExecutor
    from apscheduler.jobstores.memory import MemoryJobStore
    import pytz
    DATABASE_AVAILABLE = True
except ImportError as e:
    print(f"Database modules not available: {e}")
    print("Running in frontend-only mode. Database features will be disabled.")
    DATABASE_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure APScheduler logging to reduce verbosity
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        if DATABASE_AVAILABLE:
            create_tables()
            if scheduler and not scheduler.running:
                scheduler.start()
                logger.info("Scheduler started - Agent 1 (daily at 9 AM), Agent 2 (daily at 10 AM), Agent 3 (every 30 min)")
        else:
            logger.info("Running in frontend-only mode")
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
    
    yield  # Application runs here
    
    try:
        shutdown_scheduler()
        logger.info("Application shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

app = FastAPI(title="Email Drip Campaign API", version="1.0.0", lifespan=lifespan)

# Add session middleware for frontend
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-super-secret-key"),
    session_cookie="session_token",
    max_age=7 * 24 * 60 * 60,  # 1 week in seconds
    same_site="lax",
    https_only=False  # Set to True in production with HTTPS
)

# Setup templates for frontend
TEMPLATES_DIR = str(Path(__file__).resolve().parent / "frontend" / "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Setup uploads folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), "frontend", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    company_url: Optional[str] = None
    linkedin: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None
    booking_status: Optional[str] = None
    drip1_date: Optional[datetime] = None
    drip2_date: Optional[datetime] = None
    drip3_date: Optional[datetime] = None
    reply_date: Optional[datetime] = None
    mail_sent_status: Optional[int] = None
    first_mail_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ContentInfoCreate(BaseModel):
    contact_id: int
    client_email: Optional[str] = None
    initial_email_content: Optional[str] = None
    email_type: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None

# Initialize scheduler with proper configuration
scheduler = None
if DATABASE_AVAILABLE:
    # Configure job stores and executors
    jobstores = {
        'default': MemoryJobStore()
    }
    
    executors = {
        'default': ThreadPoolExecutor(max_workers=3)
    }
    
    job_defaults = {
        'coalesce': False,
        'max_instances': 1,
        'misfire_grace_time': 30
    }
    
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=pytz.timezone('Asia/Kolkata')
    )

def scheduled_drip_processing():
    """Background task to process drips - runs daily"""
    if not DATABASE_AVAILABLE:
        return
    try:
        logger.info("Running daily drip processing...")
        drip_manager.process_drips()
        logger.info("Daily drip processing completed")
    except Exception as e:
        logger.error(f"Error in drip processing: {str(e)}")

def scheduled_reply_checking():
    """Background task to check for replies - runs every 30 minutes"""
    if not DATABASE_AVAILABLE:
        return
    try:
        logger.info("Checking for email replies...")
        reply_count = check_and_update_replies()
        logger.info(f"Reply check completed. Found {reply_count} new replies.")
    except Exception as e:
        logger.error(f"Error checking replies: {str(e)}")

def scheduled_initial_emails():
    """Background task to send initial emails - runs daily"""
    if not DATABASE_AVAILABLE:
        return
    try:
        logger.info("Processing initial emails...")
        drip_manager.process_initial_emails()
        logger.info("Initial email processing completed")
    except Exception as e:
        logger.error(f"Error processing initial emails: {str(e)}")

# Add jobs to scheduler only if database is available
if DATABASE_AVAILABLE and scheduler:
    try:
        # scheduler.add_job(
        #     func=scheduled_initial_emails,
        #     trigger=CronTrigger(hour=9, minute=0, timezone=pytz.timezone('Asia/Kolkata')),
        #     id='initial_emails_job',
        #     name='Daily Initial Emails',
        #     replace_existing=True
        # )

        scheduler.add_job(
            func=scheduled_drip_processing,
            trigger=CronTrigger(hour=10, minute=0, timezone=pytz.timezone('Asia/Kolkata')),
            id='drip_processing_job',
            name='Daily Drip Processing',
            replace_existing=True
        )

        scheduler.add_job(
            func=scheduled_reply_checking,
            trigger=IntervalTrigger(minutes=30, timezone=pytz.timezone('Asia/Kolkata')),
            id='reply_checking_job',
            name='Reply Checking',
            replace_existing=True
        )
        
        logger.info("Scheduler jobs configured successfully")
    except Exception as e:
        logger.error(f"Error configuring scheduler jobs: {str(e)}")

def shutdown_scheduler():
    """Gracefully shutdown the scheduler"""
    global scheduler
    if scheduler and scheduler.running:
        try:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown(wait=True)
            logger.info("Scheduler shutdown completed")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {str(e)}")

# Register shutdown handler
atexit.register(shutdown_scheduler)

@app.get("/api/status")
async def api_status():
    """API status endpoint"""
    scheduler_status = "not available"
    if DATABASE_AVAILABLE and scheduler:
        scheduler_status = "running" if scheduler.running else "stopped"
    
    if DATABASE_AVAILABLE:
        return {
            "message": "Email Drip Campaign API is running", 
            "status": "healthy", 
            "mode": "full",
            "scheduler_status": scheduler_status
        }
    else:
        return {
            "message": "Frontend-only mode", 
            "status": "limited", 
            "mode": "frontend-only",
            "scheduler_status": scheduler_status
        }

@app.post("/contacts", response_model=dict)
async def add_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    """Add new contact and start drip campaign"""
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
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
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
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
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    return contact

@app.get("/contacts/{contact_id}/drip-status")
async def get_drip_status(contact_id: int):
    """Get drip campaign status for a contact"""
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
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
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        result = trigger_drip_processing()
        return result
        
    except Exception as e:
        logger.error(f"Error triggering drips: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/check-replies")
async def check_replies():
    """Manually trigger reply checking"""
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        reply_count = check_and_update_replies()
        return {"message": f"Reply check completed. Found {reply_count} new replies."}
        
    except Exception as e:
        logger.error(f"Error checking replies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get campaign statistics"""
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
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
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        # Delete related content info records
        db.query(ContentInfo).filter(ContentInfo.contact_id == contact_id).delete()
        
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

@app.get("/track/booking/{contact_id}")
def track_booking_click(contact_id: int, db: Session = Depends(get_db)):
    """
    Handles tracking the click on a booking link.
    This endpoint logs the click in the database and redirects the user.
    """
    REAL_BOOKING_URL = os.getenv(
        "BOOKING_URL", 
        "https://outlook.office.com/book/lol@pulpstrategy.com/s/_y6EIIzMKEWQlBg_0SarWQ2?ismsaljsauthenabled"
    )

    if DATABASE_AVAILABLE:
        try:
            contact = db.query(Contact).filter(Contact.id == contact_id).first()
            
            if contact:
                contact.booking_status = "clicked"
                db.commit()
                logger.info(f"Booking link clicked for contact ID: {contact_id}, Email: {contact.email}")
            else:
                logger.warning(f"Contact ID {contact_id} not found for click tracking.")
                
        except Exception as e:
            logger.error(f"Error during click tracking for contact ID {contact_id}: {str(e)}")
            if db:
                db.rollback()

    # Always redirect to the real booking page, even if tracking fails
    return RedirectResponse(url=REAL_BOOKING_URL)

@app.get("/scheduler/jobs")
async def get_scheduler_jobs():
    """Get current scheduler job status"""
    if not DATABASE_AVAILABLE or not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not available")
    
    try:
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        return {"jobs": jobs, "scheduler_running": scheduler.running}
    except Exception as e:
        logger.error(f"Error getting scheduler jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Include Frontend Routes (always available)
app.include_router(auth_router)
app.include_router(client_router)
app.include_router(email_router)
app.include_router(dashboard_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)