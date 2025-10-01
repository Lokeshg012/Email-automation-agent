from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List
import logging
import pytz
from datetime import datetime
import mail_service
import drip_logic
# ✨ CORRECTED IMPORTS: All imports are at the top level for clarity and safety.
from tables import Contact, get_db, get_db_session, ContentInfo
from mail_service import send_initial_email # Import the correct function
from drip_logic import DripCampaignManager

email_router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMPLATES_DIR = str(Path(__file__).resolve().parents[1] / "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

class SendInitialEmailsRequest(BaseModel):
    contact_ids: List[int]

def process_selected_initial_emails(contact_ids: List[int]):
    with get_db_session() as db:
        for contact_id in contact_ids:
            try:
                # Lock the row for update
                contact = db.query(Contact).filter(
                    Contact.id == contact_id,
                    Contact.mail_sent_status.is_(None)
                ).with_for_update().first()
                
                if not contact:
                    continue
                
                # Generate industry if needed
                if not contact.industry:
                    drip_manager = DripCampaignManager()
                    industry = drip_manager.generate_industry_for_contact(contact)
                    if industry:
                        contact.industry = industry
                        db.flush()  # Flush the industry update
                    else:
                        logger.warning(f"Skipping {contact.email}, failed to generate industry.")
                        db.rollback()
                        continue
                
                # Use the existing send_initial_email function
                if send_initial_email(contact, db):
                    # Update contact
                    contact.mail_sent_status = "1"
                    contact.first_mail_date = datetime.now(pytz.timezone('Asia/Kolkata'))
                    db.commit()  # Commit per contact
                    logger.info(f"Successfully sent initial email to {contact.email}")
                else:
                    logger.error(f"Failed to send email to {contact.email}")
                    db.rollback()
                    
            except Exception as e:
                logger.error(f"Error processing contact {contact_id}: {e}")
                db.rollback()

@email_router.get("/email", response_class=HTMLResponse)
async def email_page(request: Request, db: Session = Depends(get_db)):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)
    try:
        contacts_data = db.query(Contact).all()
        industries_query = db.query(func.distinct(Contact.industry).label('industry')).filter(Contact.industry.isnot(None)).order_by('industry').all()
        industries = [i.industry for i in industries_query if i.industry]
        return templates.TemplateResponse(
            "email.html", 
            {"request": request, "user": request.session["user"], "contacts": contacts_data, "industries": industries}
        )
    except Exception as e:
        logger.error(f"Error in email route: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@email_router.post("/api/contacts/send-initial")
async def api_send_initial_emails(
    request_data: SendInitialEmailsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """API endpoint to process initial emails for selected contacts."""
    try:
        # Find which of the requested contacts are actually eligible
        eligible_contacts = db.query(Contact).filter(
            Contact.id.in_(request_data.contact_ids),
            Contact.mail_sent_status.is_(None)
        ).all()
        
        if not eligible_contacts:
            return {"status": "success", "message": "All selected contacts have already been processed.", "processed_count": 0}
        
        eligible_contact_ids = [contact.id for contact in eligible_contacts]
    
        background_tasks.add_task(process_selected_initial_emails, eligible_contact_ids)
        
        return {
            "status": "processing",
            "message": f"Initial emails for {len(eligible_contact_ids)} contacts are being processed in the background.",
            "total_contacts": len(eligible_contact_ids)
        }
    except Exception as e:
        logger.error(f"Error in send_initial_emails API: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
