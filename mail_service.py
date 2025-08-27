import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime, parseaddr
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
from typing import List, Optional
from models import SessionLocal, Contact
from openai import OpenAI

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.imap_server = os.getenv("IMAP_HOST", "imap.gmail.com")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.email_address = os.getenv("EMAIL_ADDRESS")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if not self.email_address or not self.email_password:
            raise ValueError("EMAIL_ADDRESS and EMAIL_PASSWORD must be set in environment variables")
    
    def generate_initial_email_content(self, contact: Contact) -> tuple[str, str]:
        """Generate initial personalized email content after industry generation"""
        prompt = f"""
You are writing a professional cold outreach email.

Sender details:
- Name: Piyush Mishra
- Company: XYZ Company
- Role: Business Development Partner for Pulp Strategy (a digital marketing and strategy agency).

Recipient details:
- Name: {contact.name}
- Company: {contact.company_name}
- Website: {contact.company_url}
- Industry: {contact.industry}

Instructions:
- This is the **Initial Cold Outreach** email.
- Write the email as if it's coming from Piyush Mishra (XYZ Company) on behalf of Pulp Strategy.
- Make it highly personalized by referencing their company, website, and industry.
- Highlight how **Pulp Strategy** can specifically add value in their industry context.
- Keep the tone professional, friendly, and non-generic.
- Structure: **Subject line + Email body**.
- End with a polite call-to-action for a quick call/meeting.
- Make this feel like a genuine first outreach, not a follow-up.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()
            
            # Split subject and body
            lines = content.split("\n", 1)
            subject = lines[0].replace("Subject:", "").strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            
            return subject, body
            
        except Exception as e:
            logger.error(f"Error generating initial email content: {str(e)}")
            # Fallback content
            subject = f"Partnership opportunity with {contact.company_name}"
            body = f"Hi {contact.name},\n\nI hope this email finds you well. I'm reaching out regarding potential collaboration opportunities with {contact.company_name} in the {contact.industry} industry.\n\nBest regards,\nPiyush Mishra"
            return subject, body

    def generate_drip_content(self, contact: Contact, drip_number: int) -> tuple[str, str]:
        """Generate personalized drip email content using OpenAI"""
        if drip_number == 1:
            prompt = f"""
You are writing a follow-up email.

Sender details:
- Name: Piyush Mishra
- Company: XYZ Company
- Role: Business Development Partner for Pulp Strategy (a digital marketing and strategy agency).

Recipient details:
- Name: {contact.name}
- Company: {contact.company_name}
- Website: {contact.company_url}
- Industry: {contact.industry}

Instructions:
- This is **Drip 1: First Follow-up** (after the initial outreach email).
- Write the email as if it's coming from Piyush Mishra (XYZ Company) on behalf of Pulp Strategy.
- Reference that you reached out previously and are following up.
- Provide additional value proposition specific to their industry.
- Keep the tone professional, friendly, and not pushy.
- Structure: **Subject line + Email body**.
- End with a polite call-to-action for a quick call/meeting.
"""
        else:
            prompt = f"""
You are writing a follow-up cold email.

Sender details:
- Name: Piyush Mishra
- Company: XYZ Company
- Role: Business Development Partner for Pulp Strategy (a digital marketing and strategy agency).

Recipient details:
- Name: {contact.name}
- Company: {contact.company_name}
- Website: {contact.company_url}
- Industry: {contact.industry}

Instructions:
- This is **Drip {drip_number} follow-up** (after no reply to earlier emails).
- Keep the tone polite, professional, and not pushy.
- Ensure it feels different from previous emails.
- Adjust the approach depending on the drip:
  - **Drip 2** → Share an insight, case study, or industry-specific value.
  - **Drip 3** → Light final nudge with "happy to connect later if now isn't a good time".
- Structure: **Subject line + Email body**.
- End with a polite call-to-action for a quick call/meeting.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()
            
            # Split subject and body
            lines = content.split("\n", 1)
            subject = lines[0].replace("Subject:", "").strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            
            return subject, body
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            # Fallback content
            subject = f"Partnership opportunity with {contact.company_name}"
            body = f"Hi {contact.name},\n\nI hope this email finds you well. I'm reaching out regarding potential collaboration opportunities with {contact.company_name}.\n\nBest regards,\nPiyush Mishra"
            return subject, body
    
    def send_email(self, to_email: str, subject: str, content: str, contact_name: str = "") -> bool:
        """Send email using SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Personalize content if contact name is provided
            if contact_name:
                content = content.replace("{name}", contact_name)
            
            msg.attach(MIMEText(content, 'plain'))
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def check_replies(self) -> List[str]:
        """Check for replies from client emails (works for initial + drip emails)"""
        replied_emails = []
        
        # Get list of client emails we've sent ANY emails to (initial or drip)
        db = SessionLocal()
        try:
            # Get contacts where we've sent initial email OR any drip emails
            contacts_with_emails = db.query(Contact.email).filter(
                (Contact.last_email_sent.isnot(None)) |
                (Contact.drip1_date.isnot(None)) |
                (Contact.drip2_date.isnot(None)) |
                (Contact.drip3_date.isnot(None))
            ).all()
            
            client_emails = set(email[0].lower().strip() for email in contacts_with_emails)
            
            if not client_emails:
                logger.info("No emails sent yet, skipping reply check")
                return replied_emails
            
            logger.info(f"Checking replies from {len(client_emails)} client emails")
            
            # Connect to IMAP server with timeout
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as mail:
                mail.login(self.email_address, self.email_password)
                mail.select('INBOX')
                
                # Search for recent unread emails (last 7 days) to speed up
                import datetime
                since_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%d-%b-%Y')
                status, messages = mail.search(None, f'UNSEEN SINCE {since_date}')
                
                if status == 'OK' and messages[0]:
                    email_ids = messages[0].split()
                    logger.info(f"Found {len(email_ids)} unread emails to check")
                    
                    for email_id in email_ids:
                        # Fetch only headers first for speed
                        status, msg_data = mail.fetch(email_id, '(BODY[HEADER.FIELDS (FROM SUBJECT)])')
                        
                        if status == 'OK':
                            header_data = msg_data[0][1].decode('utf-8')
                            
                            # Extract sender from header
                            for line in header_data.split('\n'):
                                if line.lower().startswith('from:'):
                                    sender = line[5:].strip()
                                    sender_email = parseaddr(sender)[1].lower().strip()
                                    
                                    # Only process if sender is one of our clients
                                    if sender_email in client_emails:
                                        replied_emails.append(sender_email)
                                        logger.info(f"Client reply detected from: {sender_email}")
                                        
                                        # Mark as read
                                        mail.store(email_id, '+FLAGS', '\\Seen')
                                    break
            
        except Exception as e:
            logger.error(f"Error checking replies: {str(e)}")
        finally:
            db.close()
        
        return replied_emails
    
    def update_reply_status(self, replied_emails: List[str]):
        """Update database when replies are detected"""
        if not replied_emails:
            return
        
        db = SessionLocal()
        try:
            for email in replied_emails:
                # Update contact status to 'replied'
                contact = db.query(Contact).filter(Contact.email == email).first()
                if contact:
                    contact.status = "replied"
                    contact.reply_date = datetime.utcnow()
                    
                    # Get the actual reply content and store it
                    reply_content = self.get_reply_content(email)
                    if reply_content:
                        content_info = db.query(ContentInfo).filter(ContentInfo.contact_id == contact.id).first()
                        if content_info:
                            content_info.reply_email_content = reply_content
                    
                    # Send meeting booking email
                    self.send_meeting_email(contact)
                    
                    logger.info(f"Updated reply status for {email}")
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating reply status: {str(e)}")
            db.rollback()
        finally:
            db.close()
    
    def get_reply_content(self, sender_email: str) -> str:
        """Get the actual reply content from the latest email from sender"""
        try:
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as mail:
                mail.login(self.email_address, self.email_password)
                mail.select('INBOX')
                
                # Search for emails from this specific sender
                status, messages = mail.search(None, f'FROM "{sender_email}"')
                
                if status == 'OK' and messages[0]:
                    email_ids = messages[0].split()
                    # Get the latest email (last in list)
                    latest_email_id = email_ids[-1]
                    
                    # Fetch the email content
                    status, msg_data = mail.fetch(latest_email_id, '(RFC822)')
                    
                    if status == 'OK':
                        email_body = msg_data[0][1]
                        email_message = email.message_from_bytes(email_body)
                        
                        # Extract text content
                        if email_message.is_multipart():
                            for part in email_message.walk():
                                if part.get_content_type() == "text/plain":
                                    return part.get_payload(decode=True).decode('utf-8')
                        else:
                            return email_message.get_payload(decode=True).decode('utf-8')
                            
        except Exception as e:
            logger.error(f"Error getting reply content from {sender_email}: {str(e)}")
            
        return f"Reply received from {sender_email}"
    
    def send_meeting_booking_email(self, contact: Contact):
        """Send meeting booking email when someone replies"""
        meeting_subject = f"Great to hear from you, {contact.name}! Let's schedule a meeting"
        meeting_content = f"""Hi {contact.name},

Thank you for your reply! I'm excited to connect with you and discuss how we can help {contact.company_name}.

I'd love to schedule a brief 15-30 minute call to understand your needs better. Please feel free to book a convenient time slot using the link below:

📅 Book a Meeting: https://calendly.com/your-calendar-link

Alternatively, you can reply to this email with your preferred time slots, and I'll send you a calendar invite.

Looking forward to our conversation!

Best regards,
Piyush Mishra
XYZ Company
Business Development Partner - Pulp Strategy"""
        
        self.send_email(contact.email, meeting_subject, meeting_content, contact.name)

# Global mail service instance
mail_service = MailService()

def send_initial_email(contact: Contact) -> str:
    """Send initial email to a contact after industry generation"""
    subject, content = mail_service.generate_initial_email_content(contact)
    success = mail_service.send_email(contact.email, subject, content, contact.name)
    
    if success:
        # Return the email content for storage in content table
        return f"Subject: {subject}\n\n{content}"
    else:
        return None

def send_drip_email(contact: Contact, drip_number: int) -> str:
    """Send a drip email to a contact and return content for storage"""
    subject, content = mail_service.generate_drip_content(contact, drip_number)
    success = mail_service.send_email(contact.email, subject, content, contact.name)
    
    if success:
        # Return the email content for storage in content table
        return f"Subject: {subject}\n\n{content}"
    else:
        return None

def check_and_update_replies():
    """Check for replies and update database"""
    replied_emails = mail_service.check_replies()
    mail_service.update_reply_status(replied_emails)
    return len(replied_emails)
