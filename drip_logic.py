from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from tables import Contact, ContentInfo, SessionLocal
from sqlalchemy import and_,or_
from mail_service import send_drip_email, send_initial_email
from zoneinfo import ZoneInfo
from openai import OpenAI
import os
from datetime import timezone
from dotenv import load_dotenv
import logging
from tables import get_db_session

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DripCampaignManager:
    def __init__(self):
        self.drip_intervals = {
            1: 7, 
            2: 14,
            3: 30  
        }
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def generate_industry_for_contact(self, contact: Contact) -> str:
        try:
            prompt = f"""
You are an expert business analyst. Analyze this company's information and determine their primary industry category.

Company Details:
Company Name: {contact.company_name}
Website: {contact.company_url}

Instructions:
1. Analyze the company name and website URL for industry indicators
2. Select the MOST SPECIFIC category that applies
3. Return ONLY the industry name from this list:

Primary Industries:
- Technology & Software
- Digital Marketing & Advertising
- E-commerce & Online Retail
- Healthcare & Medical
- Financial Services
- Education & EdTech
- Manufacturing & Industrial
- Real Estate & Property
- Media & Entertainment
- Business Services
- Retail & Consumer Goods
- Travel & Hospitality
- Energy & Utilities
- Telecommunications
- Automotive & Transportation
- Food & Beverage
- Fashion & Apparel
- Insurance
- Legal Services
- IT Services
- Construction
- Pharmaceuticals
- Others (ONLY if no other category fits)

Respond with ONLY the industry name, no explanations or additional text.
Example responses:
"Digital Marketing & Advertising"
"Technology & Software"
"Financial Services"
"""
            for temp in [0.1, 0.3, 0.5]:
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temp
                    )
                    
                    industry = response.choices[0].message.content.strip().replace('"', '')
                    if industry and 3 <= len(industry) <= 50:
                        return industry
                    
                except Exception as inner_e:
                    logger.warning(f"Attempt {temp} failed for {contact.email}: {str(inner_e)}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating industry for {contact.email}: {str(e)}")
            return None
    

    def process_initial_emails(self):
        with get_db_session() as db:
            contacts = db.query(Contact).filter(Contact.mail_sent_status.is_(None)).all()
            logger.info(f"Found {len(contacts)} new contacts to process for initial emails.")

            for contact in contacts:
                try:
                    # Generate industry if it's missing
                    if not contact.industry:
                        if not (contact.company_name and contact.company_url):
                            logger.warning(f"Skipping {contact.email}: Missing company details to generate industry.")
                            continue
                        
                        industry = self.generate_industry_for_contact(contact)
                        if industry:
                            contact.industry = industry
                            logger.info(f"Generated industry '{industry}' for {contact.email}")
                        else:
                            logger.error(f"Failed to generate industry for {contact.email}, skipping.")
                            continue
                    
                    if send_initial_email(contact, db):
                        contact.mail_sent_status = 1
                        contact.first_mail_date = datetime.now(ZoneInfo("Asia/Kolkata"))
                        db.commit()
                        logger.info(f"Successfully processed and sent initial email to {contact.email}")
                    else:
                        logger.error(f"send_initial_email function failed for {contact.email}, rolling back.")
                        db.rollback()

                except Exception as e:
                    logger.error(f"A critical error occurred while processing contact {contact.email}: {str(e)}")
                    db.rollback()

    def process_drips(self):
        with get_db_session() as db:
            now = datetime.now(ZoneInfo("Asia/Kolkata"))
            contacts = db.query(Contact).filter(
                or_(Contact.status.is_(None), Contact.status != "do_not_contact"),
                Contact.mail_sent_status.in_([1, 2, 3])
            ).all()
            logger.info(f"Found {len(contacts)} contacts eligible for drip processing.")

            for contact in contacts:
                try:
                    drip_to_send = 0
                    if contact.mail_sent_status == 1 and (now - contact.first_mail_date).days >= self.drip_intervals[1]:
                        drip_to_send = 1
                    elif contact.mail_sent_status == 2 and (now - contact.drip1_date).days >= self.drip_intervals[2]:
                        drip_to_send = 2
                    elif contact.mail_sent_status == 3 and (now - contact.drip2_date).days >= self.drip_intervals[3]:
                        drip_to_send = 3

                    if drip_to_send > 0:
                        logger.info(f"Attempting to send Drip {drip_to_send} to {contact.email}")
                        if send_drip_email(contact, drip_to_send, db):
                            if drip_to_send == 1:
                                contact.drip1_date = now
                                contact.mail_sent_status = 2
                            elif drip_to_send == 2:
                                contact.drip2_date = now
                                contact.mail_sent_status = 3
                            elif drip_to_send == 3:
                                contact.drip3_date = now
                                contact.mail_sent_status = 4
                            
                            db.commit()
                            logger.info(f"Successfully sent Drip {drip_to_send} to {contact.email}")
                        else:
                            logger.error(f"send_drip_email function failed for Drip {drip_to_send} to {contact.email}")

                except Exception as e:
                    logger.error(f"A critical error occurred processing drips for {contact.email}: {str(e)}")
                    db.rollback()

drip_manager = DripCampaignManager()

def add_new_contact_and_start_drip(name: str, email: str, company_name: str, 
                                 company_url: str = None, industry: str = None) -> dict:
    with get_db_session() as db:
        existing_contact = db.query(Contact).filter(Contact.email == email).first()
        if existing_contact:
            return {"error": "Contact already exists", "contact_id": existing_contact.id}
        
        contact = Contact(
            name=name,
            email=email,
            company_name=company_name,
            company_url=company_url,
            industry=industry,
        )
        db.add(contact)
        db.commit()
        
        logger.info(f"Contact {contact.email} added to database - Agent 1 will send initial email")
        
        return {
            "success": True,
            "contact_id": contact.id,
            "message": "Contact added successfully - Agent 1 will process initial email",
            "email": contact.email
        }
            
    
    db.close()

def trigger_drip_processing():
    drip_manager.process_drips()
    return {"message": "Drip processing triggered"}
