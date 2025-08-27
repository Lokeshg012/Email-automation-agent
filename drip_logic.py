from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Contact, ContentInfo, SessionLocal
from mail_service import send_drip_email, send_initial_email
from openai import OpenAI
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DripCampaignManager:
    def __init__(self):
        self.drip_intervals = {
            1: 0,  # Send drip1 immediately
            2: 3,  # Send drip2 after 3 days
            3: 5   # Send drip3 after 5 days from drip2
        }
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def schedule_drip1(self, contact: Contact, db: Session):
        """Schedule drip1 immediately for existing contact"""
        try:
            # Ensure ContentInfo exists for this contact (don't create new if exists)
            if not contact.content_info:
                content_info = ContentInfo(contact_id=contact.id)
                db.add(content_info)
                db.flush()  # Get the ID without committing
                contact.content_info = content_info
            
            # Send drip1 immediately
            drip1_content = send_drip_email(contact, 1)
            
            if drip1_content:
                now = datetime.utcnow()
                contact.drip1_date = now
                contact.last_email_sent = now
                
                # Schedule drip2 for 3 days later
                contact.drip2_date = now + timedelta(days=self.drip_intervals[2])
                
                # Update content table with drip1 content
                content_info = db.query(ContentInfo).filter(ContentInfo.contact_id == contact.id).first()
                if content_info:
                    content_info.drip1_email_content = drip1_content
                
                db.commit()
                logger.info(f"Drip1 sent and drip2 scheduled for contact: {contact.email}")
                return True
            else:
                logger.error(f"Failed to send drip1 for contact: {contact.email}")
                return False
                
        except Exception as e:
            logger.error(f"Error scheduling drip1 for {contact.email}: {str(e)}")
            db.rollback()
            return False
    
    def process_pending_drips(self):
        """Process all pending drip campaigns"""
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            
            # Find contacts ready for drip2
            drip2_contacts = db.query(Contact).filter(
                Contact.status != "replied",
                Contact.drip1_date.isnot(None),
                Contact.drip2_date <= now,
                Contact.drip2_date.isnot(None)
            ).all()
            
            for contact in drip2_contacts:
                if self.send_drip2(contact, db):
                    logger.info(f"Drip2 sent to {contact.email}")
            
            # Find contacts ready for drip3
            drip3_contacts = db.query(Contact).filter(
                Contact.status != "replied",
                Contact.drip2_date.isnot(None),
                Contact.drip3_date <= now,
                Contact.drip3_date.isnot(None)
            ).all()
            
            for contact in drip3_contacts:
                if self.send_drip3(contact, db):
                    logger.info(f"Drip3 sent to {contact.email}")
                    
        except Exception as e:
            logger.error(f"Error processing pending drips: {str(e)}")
        finally:
            db.close()
    
    def send_drip2(self, contact: Contact, db: Session) -> bool:
        """Send drip2 email"""
        try:
            drip2_content = send_drip_email(contact, 2)
            
            if drip2_content:
                now = datetime.utcnow()
                contact.last_email_sent = now
                
                # Schedule drip3 for 5 days later
                contact.drip3_date = now + timedelta(days=self.drip_intervals[3])
                
                # Clear drip2_date to mark as sent
                contact.drip2_date = now
                
                # Update content table with drip2 content
                content_info = db.query(ContentInfo).filter(ContentInfo.contact_id == contact.id).first()
                if content_info:
                    content_info.drip2_email_content = drip2_content
                
                db.commit()
                return True
            else:
                logger.error(f"Failed to send drip2 for contact: {contact.email}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending drip2 for {contact.email}: {str(e)}")
            db.rollback()
            return False
    
    def send_drip3(self, contact: Contact, db: Session) -> bool:
        """Send drip3 email (final drip)"""
        try:
            drip3_content = send_drip_email(contact, 3)
            
            if drip3_content:
                now = datetime.utcnow()
                contact.last_email_sent = now
                
                # Mark drip3 as sent
                contact.drip3_date = now
                
                # Update content table with drip3 content
                content_info = db.query(ContentInfo).filter(ContentInfo.contact_id == contact.id).first()
                if content_info:
                    content_info.drip3_email_content = drip3_content
                
                db.commit()
                return True
            else:
                logger.error(f"Failed to send drip3 for contact: {contact.email}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending drip3 for {contact.email}: {str(e)}")
            db.rollback()
            return False
    
    def stop_drips_for_replied_contact(self, contact: Contact, db: Session):
        """Stop all future drips when contact replies"""
        try:
            # Clear future drip dates
            if contact.drip2_date and contact.drip2_date > datetime.utcnow():
                contact.drip2_date = None
            if contact.drip3_date and contact.drip3_date > datetime.utcnow():
                contact.drip3_date = None
                
            db.commit()
            logger.info(f"Stopped future drips for replied contact: {contact.email}")
            
        except Exception as e:
            logger.error(f"Error stopping drips for {contact.email}: {str(e)}")
            db.rollback()
    
    def get_drip_status(self, contact_id: int) -> dict:
        """Get drip campaign status for a contact"""
        db = SessionLocal()
        try:
            contact = db.query(Contact).filter(Contact.id == contact_id).first()
            if not contact:
                return {"error": "Contact not found"}
            
            now = datetime.utcnow()
            status = {
                "contact_id": contact.id,
                "email": contact.email,
                "status": contact.status,
                "drip1_sent": contact.drip1_date is not None,
                "drip1_date": contact.drip1_date,
                "drip2_scheduled": contact.drip2_date is not None,
                "drip2_date": contact.drip2_date,
                "drip2_ready": contact.drip2_date and contact.drip2_date <= now if contact.drip2_date else False,
                "drip3_scheduled": contact.drip3_date is not None,
                "drip3_date": contact.drip3_date,
                "drip3_ready": contact.drip3_date and contact.drip3_date <= now if contact.drip3_date else False,
                "last_email_sent": contact.last_email_sent,
                "reply_date": contact.reply_date
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting drip status for contact {contact_id}: {str(e)}")
            return {"error": str(e)}
        finally:
            db.close()

# Global drip campaign manager
drip_manager = DripCampaignManager()

def add_new_contact_and_start_drip(name: str, email: str, company_name: str, 
                                 company_url: str = None, industry: str = None) -> dict:
    """Add new contact, send initial email, and start drip campaign only if no reply"""
    db = SessionLocal()
    try:
        # Check if contact already exists
        existing_contact = db.query(Contact).filter(Contact.email == email).first()
        if existing_contact:
            # Work with existing contact - update their row
            contact = existing_contact
            # Update fields if provided
            if name:
                contact.name = name
            if company_name:
                contact.company_name = company_name
            if company_url:
                contact.company_url = company_url
            if industry:
                contact.industry = industry
        else:
            # Create new contact
            contact = Contact(
                name=name,
                email=email,
                company_name=company_name,
                company_url=company_url,
                industry=industry
            )
            db.add(contact)
        
        db.commit()
        
        # Industry is mandatory - generate if not provided
        if not contact.industry:
            if not contact.company_name or not contact.company_url:
                return {"error": "Company name and URL required to generate industry", "contact_id": contact.id}
            
            industry = generate_industry_for_contact(contact, db)
            if not industry:
                return {"error": "Failed to generate industry", "contact_id": contact.id}
            
            logger.info(f"Industry '{industry}' generated for {contact.email}")
        
        # Only proceed with emails after industry is confirmed
        if not contact.industry:
            return {"error": "Industry is required before sending emails", "contact_id": contact.id}
        
        # Send initial email after industry is filled
        initial_email_content = send_initial_email(contact)
        if not initial_email_content:
            return {"error": "Failed to send initial email", "contact_id": contact.id}
        
        # Update last_email_sent for initial email
        contact.last_email_sent = datetime.utcnow()
        db.commit()
        
        # Create ContentInfo record with initial email data
        content_info = ContentInfo(
            contact_id=contact.id,
            client_email=contact.email,
            initial_email_content=initial_email_content
        )
        db.add(content_info)
        db.commit()
        
        logger.info(f"Initial email sent to {contact.email}")
        logger.info(f"Content record created for contact {contact.id}")
        
        # Start drip campaign only after initial email
        success = drip_manager.schedule_drip1(contact, db)
        
        if success:
            return {
                "success": True,
                "contact_id": contact.id,
                "message": "Initial email sent and drip campaign scheduled",
                "email": contact.email
            }
        else:
            return {
                "error": "Initial email sent but failed to schedule drip campaign",
                "contact_id": contact.id
            }
            
    except Exception as e:
        logger.error(f"Error processing contact {email}: {str(e)}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()

def generate_industry_for_contact(contact: Contact, db: Session) -> str:
    """Generate industry using LLM for a contact"""
    try:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        prompt = f"""
        Give me only the industry type of this company:
        Name: {contact.company_name}
        URL: {contact.company_url}
        Reply with only the industry name (like 'Fintech', 'Marketing', 'Sports Tech').
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        
        industry = response.choices[0].message.content.strip()
        
        # Update contact with industry
        contact.industry = industry
        db.commit()
        
        logger.info(f"Generated industry '{industry}' for {contact.company_name}")
        return industry
        
    except Exception as e:
        logger.error(f"Error generating industry for {contact.company_name}: {str(e)}")
        return None

def process_contacts_without_industry():
    """Process contacts that don't have industry filled and send initial emails"""
    db = SessionLocal()
    try:
        # Fetch contacts without industry
        contacts = db.query(Contact).filter(
            Contact.industry.is_(None),
            Contact.company_name.isnot(None),
            Contact.company_url.isnot(None)
        ).all()
        
        processed_count = 0
        
        for contact in contacts:
            logger.info(f"Processing contact: {contact.name} ({contact.company_name})")
            
            # Generate industry
            industry = generate_industry_for_contact(contact, db)
            
            if industry:
                # Send initial email first
                initial_success = send_initial_email(contact)
                
                if initial_success:
                    logger.info(f"Initial email sent to {contact.name}")
                    
                    # Update last_email_sent for initial email
                    contact.last_email_sent = datetime.utcnow()
                    db.commit()
                    
                    # Start drip campaign after initial email
                    success = drip_manager.schedule_drip1(contact, db)
                    
                    if success:
                        processed_count += 1
                        logger.info(f"Started drip campaign for {contact.name}")
                    else:
                        logger.error(f"Failed to start drip campaign for {contact.name}")
                else:
                    logger.error(f"Failed to send initial email to {contact.name}")
            else:
                logger.error(f"Failed to generate industry for {contact.name}")
        
        return {
            "message": f"Processed {processed_count} contacts",
            "total_found": len(contacts),
            "processed": processed_count
        }
        
    except Exception as e:
        logger.error(f"Error processing contacts: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()

def trigger_drip_processing():
    """Manually trigger drip processing for testing"""
    drip_manager.process_pending_drips()
    return {"message": "Drip processing triggered"}
