import email
from email.utils import parsedate_to_datetime, parseaddr
from datetime import datetime, timezone, timedelta
import os
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import time
from dotenv import load_dotenv
import pytz
import smtplib
import imaplib
from sqlalchemy.orm import Session
from email.header import decode_header
from typing import List, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid, formatdate
import logging
from typing import List, Optional, Dict, Any
from tables import SessionLocal, Contact, ContentInfo, EmailData, get_db_session
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_body_from_message(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                return payload.decode(charset, errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or 'utf-8'
        return payload.decode(charset, errors="ignore")
    return ""

class MailService:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.assistant_id = os.getenv("ASSISTANT_ID")
        self.file_id = os.getenv("FILE_ID")
        self.default_thread_id = os.getenv("THREAD_ID")
        self.smtp_server = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.imap_server = os.getenv("IMAP_HOST", "imap.gmail.com")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.email_address = os.getenv("EMAIL_ADDRESS")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.timezone = pytz.timezone('Asia/Kolkata')  

        if not all([self.assistant_id, self.file_id, self.default_thread_id]):
            raise ValueError("ASSISTANT_ID, FILE_ID, or THREAD_ID not found in .env file. Please run setup_assistant.py first.")
        
    
    def _get_assistant_response(self, prompt: str, thread_id: Optional[str]) -> Optional[str]:
        active_thread_id = thread_id or self.default_thread_id
        if not all([self.assistant_id, self.file_id, active_thread_id]):
            logger.error("Assistant, File, or Thread ID not set.")
            return None

        try:
            self.openai_client.beta.threads.messages.create(
                thread_id=active_thread_id,
                role="user",
                content=prompt,
                attachments=[
                    {"file_id": self.file_id, "tools": [{"type": "file_search"}]}
                ]
            )
            
            run = self.openai_client.beta.threads.runs.create(
                thread_id=active_thread_id,
                assistant_id=self.assistant_id
            )
            while run.status not in ["completed", "failed"]:
                time.sleep(1)
                run = self.openai_client.beta.threads.runs.retrieve(
                    thread_id=active_thread_id,
                    run_id=run.id
                )

            if run.status == "completed":
                messages = self.openai_client.beta.threads.messages.list(
                    thread_id=active_thread_id
                )
                return messages.data[0].content[0].text.value
            else:
                logger.error(f"Assistant run failed with status: {run.status}")
                return None
        except Exception as e:
            logger.error(f"An error occurred while running the assistant: {e}")
            return None


    def get_or_create_thread_for_contact(self, contact: Contact, db_session: Session = None) -> str:
        # Helper function to check for existing thread
        def check_existing_thread(db):
            return db.query(ContentInfo).filter(
                ContentInfo.contact_id == contact.id,
                ContentInfo.thread_id.isnot(None)
            ).first()
        if db_session:
            existing_content = check_existing_thread(db_session)
        else:
            with get_db_session() as db:
                existing_content = check_existing_thread(db)
        
        if existing_content and existing_content.thread_id:
            logger.info(f"Using existing thread {existing_content.thread_id} for contact {contact.email}")
            return existing_content.thread_id
        try:
            thread = self.openai_client.beta.threads.create()
            new_thread_id = thread.id
            logger.info(f"Created OpenAI thread {new_thread_id} for contact {contact.email}")
        except Exception as e:
            logger.error(f"Error creating OpenAI thread for contact {contact.email}: {e}")
            return self.default_thread_id
        
        # Store thread in database
        try:
            if db_session:
                existing = check_existing_thread(db_session)
                if existing:
                    logger.info(f"Thread already exists for contact {contact.email}, using {existing.thread_id}")
                    return existing.thread_id
                
                new_content = ContentInfo(
                    contact_id=contact.id,
                    client_email=contact.email,
                    thread_id=new_thread_id,
                    email_type="thread_created",
                    subject="Thread Created",
                    body="Thread created for contact communication"
                )
                db_session.add(new_content)
                db_session.flush()  # Flush but don't commit - let caller handle commit
                logger.info(f"Stored thread {new_thread_id} in database for contact {contact.email}")
                return new_thread_id
            else:
                with get_db_session() as db:
                    existing = check_existing_thread(db)
                    if existing:
                        logger.info(f"Thread already exists for contact {contact.email}, using {existing.thread_id}")
                        return existing.thread_id
                    
                    new_content = ContentInfo(
                        contact_id=contact.id,
                        client_email=contact.email,
                        thread_id=new_thread_id,
                        email_type="thread_created",
                        subject="Thread Created",
                        body="Thread created for contact communication"
                    )
                    db.add(new_content)
                    db.commit()
                    logger.info(f"Stored thread {new_thread_id} in database for contact {contact.email}")
                    return new_thread_id
                
        except Exception as e:
            logger.error(f"Error storing thread in database for contact {contact.email}: {e}")
            # Return the OpenAI thread ID anyway since it was created successfully
            return new_thread_id

    def generate_initial_email_content(self, contact: Contact, db_session: Session = None) -> tuple[str, str]:
        thread_id = self.get_or_create_thread_for_contact(contact, db_session)
        prompt = f"""
Write a hyper-personalized, high-level strategic outreach email from the perspective of Ambika Sharma, owner and chief strategist at Pulp Strategy.
Your tone should be that of a confident expert—an insider who has spotted a profound, often overlooked, opportunity and is providing a valuable, unsolicited blueprint for success. The email is a strategic opening move, not a sales pitch.
 
Required Inputs
 
The final output will be based on the following specific data points:
Contact Name: {contact.name}
Company Name: {contact.company_name}
Company Industry: {contact.industry}
High-Stakes Business Goal: A specific, publicly stated goal, strategic move, or business challenge (e.g., "expanding market share," "improving customer LTV," "brand repositioning").
Relevant Pulp Strategy Service/Case Study: A specific service or case study result that directly addresses the business goal (e.g., "our unique approach to immersive brand activations," "data-driven loyalty programs").
 
Email Blueprint
 
> Subject Line: A single, intriguing observation, hyper-specific to the business goal. It must be under 7 words, professional, and contain no question marks.
> Opening Hook: Begin with "Hi {contact.name}," (line space). Starting should be polite and some formal greeting like "hope you are doing well". The next sentence must be a knockout—a precise strategic observation that proves a high-level understanding of their business. Avoid all generic pleasantries.
> Strategic Insight: The main body should diagnose the identified challenge and articulate a concise, high-impact solution. Connect the specified Pulp Strategy service or case study result directly to their business goal, positioning it as a catalyst for success. This must feel like a strategic blueprint.
> Closing: End with a low-pressure, intelligent question that invites a strategic dialogue, not a meeting. The question should be about the core idea you've presented and prompt them to think about their next strategic move.
 
Mandatory Rules & Constraints
 
1. The entire email must feel like a whispered secret, not a shouted advertisement. The language must be sharp and precise.
2. Don't add "subject line:" in subject line output for perfect parsing, just content of the subject line.
3. Add spaces in the email output wherever needed.
4. The final output must be a complete, fully-written, ready-to-send email.
5. Do not include any placeholders, square brackets, or source links in the final email.
6. Do not include internal instructions or labels (e.g., "Hook," "Strategic Insight") in the final output.
7. The email must end with the following signature: Best regards, Ambika Sharma Chief Strategist Pulp Strategy Communications Pvt. Ltd.
 
Final Output Format:
 
Provide your final, complete email in the following exact format:
Your Actual Subject Line|||Your Full Email Body Here, Including the Signature
"""
    
        try:
            content = self._get_assistant_response(prompt,thread_id)
            logger.debug(f"Raw AI response for {contact.email}: {content}")
        
            if not content:
                logger.error(f"No content received from AI for {contact.email}")
                return ("Failed to generate content", f"Hello {contact.name},\n\nI hope this email finds you well.\n\nBest regards,\nLokesh Garg")

            if '|||' in content:
                try:
                    subject, body = content.split('|||', 1)
                    subject = subject.strip()
                    body = body.strip()
                
                    if subject and body:
                        return (subject, body)
                    else:
                        logger.error(f"Empty subject or body after split for {contact.email}")
                except ValueError as e:
                    logger.error(f"Error splitting content for {contact.email}: {e}")
        
            lines = content.strip().split('\n')
            if len(lines) >= 2:
                subject = lines[0].strip()
                body = '\n'.join(lines[1:]).strip()
                return (subject, body)
    
            logger.warning(f"Using fallback parsing for {contact.email}")
            return ("Following up on your business goals", content.strip())
        
        except Exception as e:
            logger.error(f"Exception in generate_initial_email_content for {contact.email}: {str(e)}")
            return (
                f"Partnership opportunity for {contact.company_name}",
                f"Hi {contact.name},\n\nI hope this email finds you well.\n\nBest regards,\n\nLokesh Garg\nBusiness Development Partner\nPulp Strategy\n+91 45289157"
            )
    def generate_drip_content(self, contact: Contact, drip_number: int, db_session: Session = None) -> tuple[str, str]:
        thread_id = self.get_or_create_thread_for_contact(contact, db_session)
        prompt = f"""
Persona: You are Ambika Sharma, a sharp and insightful Chief Strategist at Pulp Strategy. Your tone is helpful and respectful, continuing a conversation from a previous, high-level strategic email. You do not "check in"; you provide tangible value.

Opening (The Hook): Start the email with greeting like Hi {contact.name},.
Assignment: Write a brief, value-driven follow-up email to {contact.name} at {contact.company_name}. This is Drip Email #{drip_number} in the sequence.

Source Materials:

The attached Pulp Strategy knowledge file. This file contains our award-winning case studies, unique intellectual properties (like Neurorank™), and our core services in brand activation, digital transformation, and full-funnel strategy.

Creative Brief for Drip Email #{drip_number}:

1. If this is Drip #1 (The Gentle Nudge): Your goal is to subtly resurface the original idea by introducing a powerful, industry-relevant metric. Find a strategic data point or a compelling statistic from the knowledge file that directly supports your initial suggestion. The body must be adding immediate, quantifiable context to the conversation.
2. If this is Drip #2 (The Proof Point): Your goal is to provide concrete, real-world proof. Find the most relevant, high-impact mini-case study or success story from the knowledge file, particularly one in the '{contact.industry}' sector or a similar challenge. Summarize the problem and the outcome concisely, highlighting the business impact. Use a new, simple subject line like "A quick example for {contact.company_name}."
3. If this is Drip #3 (The Graceful Exit): Your goal is to politely and professionally close the loop, acknowledging their focus and time. State that this will be your last note on this specific topic for now, but gracefully leave the door open for a future conversation on their terms. The subject should be simple and final, such as "Closing the loop."

Mandatory Rules:
1. Don't add question mark in subject line please and proper gaps in content wherever suitable.
2. Start the email with the greeting. The final output must be a complete, fully-written, ready-to-send email.
3. Don't add "subject line:" in subject line output for perfect parsing, just content of the subject line.
4. There must be absolutely NO placeholders or square brackets left in the text.
5. Do not use generic phrases like "Just following up" or "Checking in."
6. The email body must be very brief (2-4 sentences).
7. Do not add any special characters or symbols in the email.
8. Don't include any brackets or symbols in the email nor provide any source links.
9. The signature must be exactly as follows and included at the end of the body: Best regards, Ambika Sharma Chief Strategist Pulp Strategy Communications Pvt. Ltd.

Output Format:Provide your final, complete email output in this exact format, using "|||" as a separator. Do not include any other text before or after this structure. Do NOT include the word "Subject:" or any prefixes before the subject line.
    """
        content = self._get_assistant_response(prompt,thread_id)
        if not content:
            return "Failed to generate drip content", ""

        try:
            subject, body = content.split('|||', 1)
            return subject.strip(), body.strip()
        except IndexError:
            logger.error(f"Failed to parse ||| from AI response. Content: {content}")
            return "Following up", content

    def _store_cc_info(self, msg: email.message.Message, db: Session) -> None:
        cc_list = msg.get_all('Cc', [])
        if not cc_list:
            return

        from_email = parseaddr(msg.get('From', ''))[1]
        
        referrer = db.query(Contact).filter(Contact.email == from_email).first()
        referrer_company = referrer.company_name if referrer else None
        
        for cc in cc_list:
            cc_name, cc_email = parseaddr(cc)
            if cc_email:
                # Store in EmailData table
                cc_entry = EmailData(
                    cc=cc_email,
                    company_name=referrer_company,  # Use referrer's company name from Contact table
                    referred=from_email,  # Store who included this CC
                    created_at=datetime.now(self.timezone)
                )
                db.add(cc_entry)
                logger.info(f"Stored CC recipient: {cc_email} from company {referrer_company} referred by {from_email}")

    def _extract_main_reply(self, body_text: str) -> str:
        if body_text is None:
            return ""
        
        markers = [
            "On ",
            "-----Original Message-----",
            "From:",
            "---" 
        ]
        for marker in markers:
            if marker in body_text:
                body_text = body_text.split(marker)[0]
                break
        return body_text.strip()
     
    def _build_references_chain(self, original_msg: email.message.Message) -> tuple[str, str]:
        current_msg_id = original_msg.get('Message-ID', '').strip()
        previous_refs = original_msg.get('References', '').strip()
        
        references = []
        if previous_refs:
            references.extend([ref.strip() for ref in previous_refs.split() if ref.strip()])
        if current_msg_id and current_msg_id not in references:
            references.append(current_msg_id)
            
        return current_msg_id, ' '.join(references)

    def _create_threaded_body(self, new_reply_text: str, original_message: email.message.Message) -> str:
        original_sender = original_message.get("From")
        original_date = original_message.get("Date")
        original_body = self._extract_main_reply(get_body_from_message(original_message))
        quoted_header = f"\n\nOn {original_date}, {original_sender} wrote:\n"
        quoted_body = "> " + "\n> ".join(original_body.splitlines())
        return f"{new_reply_text}{quoted_header}{quoted_body}"
    
    def _create_threaded_html_body(self, new_html_content: str, original_message: email.message.Message) -> str:
        """
        Combines new HTML content with a formatted HTML quote of the original email.
        """
        original_sender = original_message.get("From")
        original_date = original_message.get("Date")
        original_body_text = self._extract_main_reply(get_body_from_message(original_message))
        

        original_body_html = original_body_text.replace('\n', '<br>')

        quote_header = f'''
<p style="color:#5e5e5e; margin-top:20px; margin-bottom:10px;">
    On {original_date}, {original_sender} wrote:
</p>
'''
        blockquote = f'''
<blockquote style="border-left:2px solid #cccccc; margin:0 0 20px 0; padding-left:15px;">
    {original_body_html}
</blockquote>
'''
        
        return f"<div>{new_html_content}</div>{quote_header}{blockquote}"

    def send_email(self, to_email: str, subject: str, content: str, 
               html_content: Optional[str] = None, 
               in_reply_to: Optional[str] = None, 
               references: Optional[str] = None, 
               max_retries: int = 3) -> Optional[str]: # Return the new Message-ID
    
        for attempt in range(max_retries):
            try:
                msg = MIMEMultipart('alternative')
                msg['From'] = f"AMBIKA SHARMA <{self.email_address}>"
                msg['To'] = to_email
                msg['Subject'] = subject
            
                new_message_id = make_msgid()
                msg['Message-ID'] = new_message_id
                msg['Date'] = formatdate(localtime=True)
            
                # Proper email threading headers
                if in_reply_to:
                    msg['In-Reply-To'] = in_reply_to.strip()
                    
                # Build References header for proper threading
                refs = []
                if references:
                    # Split existing references and clean them
                    refs.extend([r.strip() for r in references.split() if r.strip()])
                if in_reply_to and in_reply_to.strip() not in refs:
                    refs.append(in_reply_to.strip())
                    
                if refs:
                    msg['References'] = ' '.join(refs)
           
                msg.attach(MIMEText(content, 'plain'))
                if html_content:
                    msg.attach(MIMEText(html_content, 'html'))
            
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.starttls()
                    server.login(self.email_address, self.email_password)
                    server.send_message(msg)
            
                logger.info(f"Email sent successfully to {to_email}")
                return new_message_id 

            except Exception as e:
                logger.error(f"Failed to send email to {to_email} on attempt {attempt+1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1)) 
        return None

    def agent_3_reply_checking(self) -> List[email.message.Message]:
        emails_to_process = []
        with get_db_session() as db:
            try:
                contacts_with_emails = db.query(Contact).filter(Contact.mail_sent_status.isnot(None)).all()
                if not contacts_with_emails:
                    logger.info("No active contacts to check for replies.")
                    return []
                
                contact_emails = {c.email.lower().strip() for c in contacts_with_emails}
                processed_ids_query = db.query(ContentInfo.message_id).filter(ContentInfo.message_id.isnot(None)).all()
                processed_ids = {pid[0] for pid in processed_ids_query}

                since_date = (datetime.now(self.timezone) - timedelta(days=1)).strftime("%d-%b-%Y")
                
                with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as mail:
                    mail.login(self.email_address, self.email_password)
                    mail.select('INBOX')
                    
                    status, messages = mail.search(None, f'(SINCE "{since_date}")')
                    if status != 'OK' or not messages[0]:
                        logger.info(f"No new messages found since {since_date}.")
                        return []

                    for email_id in messages[0].split():
                        _, msg_data = mail.fetch(email_id, '(RFC822)')
                        email_message = email.message_from_bytes(msg_data[0][1])
                        
                        sender_email = parseaddr(email_message['From'])[1].lower().strip()
                        message_id = email_message.get('Message-ID')

                        if sender_email in contact_emails and message_id not in processed_ids:
                            emails_to_process.append(email_message)
                            logger.info(f"Found new reply from {sender_email} (ID: {message_id})")

            except Exception as e:
                logger.error(f"Error in agent_3_reply_checking: {str(e)}")
        
        return emails_to_process
    
    
    def analyze_reply_sentiment(self, reply_body: str) -> tuple[str, dict]:
        prompt = f"""
## ROLE & GOAL
You are an expert B2B communication analysis AI named 'The Classifier'. Your sole mission is to analyze an incoming email reply, classify its intent with extreme precision, and return a single, valid JSON object.

## CLASSIFICATION CRITERIA
Analyze the input email based on the following criteria in order of priority.

### 1. Stop Request Analysis
First, scan for explicit requests to stop communication.
- **Triggers:** Phrases like "unsubscribe," "remove me," "take me off your list," "don't email me again," etc.
- **Action:** If a stop request is found, set `stopContact` to `true`.

### 2. Query Analysis
Next, identify if the email contains a direct business query.
- **Definition:** A business query is a direct question asking for specific information about services, pricing, implementation, availability, case studies, or next steps.
- **Action:** If a query is found, set `hasQuery` to `true` and extract the exact question(s) into the `queries` field.

### 3. Sentiment & Intent Analysis
Finally, determine the sentiment based on the user's intent.

* **POSITIVE (High Intent / Buying Signal):** The user is signaling they want to move forward. Mark as POSITIVE if they:
    * Request a proposal, quote, or pricing details.
    * Ask for a meeting, call, or demo.
    * Discuss budget, timeline, or specific project needs.
    * Use strong positive language like "This is exactly what we're looking for," or "We are very interested in learning more."

* **NEUTRAL (Low Intent / Information Gathering):** The user is acknowledging the email or asking for general information without clear buying signals. Mark as NEUTRAL if they:
    * Provide a simple acknowledgment ("Thanks," "Got it," "Acknowledged").
    * Politely defer ("Not right now, but maybe in the future," "We'll keep you in mind").
    * Ask a general, non-committal question ("What other services do you offer?").

* **NEGATIVE (No Intent / Rejection):** The user is clearly not interested or is asking to stop contact. Mark as NEGATIVE if they:
    * Explicitly state "not interested," "not a good fit," or "we have a solution for this."
    * Make a `stopContact` request (this automatically makes the sentiment NEGATIVE).
    * Express frustration or annoyance.

## INPUT EMAIL FOR ANALYSIS:
---
{reply_body}
---

## REQUIRED OUTPUT FORMAT:
Your response MUST be a single, valid JSON object and nothing else. Adhere strictly to this structure:
{{
  "sentiment": "POSITIVE", "NEGATIVE", or "NEUTRAL",
  "reasoning": "A one-sentence justification for the sentiment choice, citing a key phrase from the email.",
  "hasQuery": true or false,
  "queries": "The specific question(s) asked, or 'none' if no query was found.",
  "stopContact": true or false
}}
"""
    
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2, 
                response_format={"type": "json_object"}  
            )
        
            analysis = json.loads(response.choices[0].message.content)
            sentiment = analysis.get('sentiment', 'NEUTRAL')

            return sentiment, {
                'has_query': analysis.get('hasQuery', False),
                'queries': analysis.get('queries') if analysis.get('queries') != 'none' else None,
                'stop_contact': analysis.get('stopContact', False)
            }
        except Exception as e:
            logger.error(f"Error analyzing sentiment and queries: {e}")
            return "NEUTRAL", {'has_query': False, 'queries': None, 'stop_contact': False}

    
    def update_reply_status_and_check_sentiment(self, email_messages: List[email.message.Message]):
        if not email_messages:
            return

        with get_db_session() as db:
            for msg in email_messages:
                sender_email = ""
                try:
                    # Store CC information first
                    self._store_cc_info(msg, db)
                    
                    # Continue with normal reply processing
                    sender_email = parseaddr(msg['From'])[1].lower().strip()
                    contact = db.query(Contact).filter(Contact.email == sender_email).first()
                    if not contact:
                        continue

                    clean_body = self._extract_main_reply(get_body_from_message(msg))
                    sentiment, analysis = self.analyze_reply_sentiment(clean_body)

                    db.add(ContentInfo(
                    contact_id=contact.id, client_email=contact.email, email_type="reply",
                    subject=msg.get("Subject",""), body=clean_body, message_id=msg.get("Message-ID"), sentiment=sentiment
                    ))
                    db.commit()
                    contact.status = "replied"
                    contact.mail_sent_status = 5
                    
                    if analysis.get('stop_contact'):
                        contact.status = "do_not_contact"
                        self.send_stop_contact_acknowledgment(db, contact, msg)
                        logger.info(f"Contact {sender_email} has requested to stop communication.")
                        continue

                    elif sentiment == "POSITIVE":
                        if analysis.get('has_query'):
                            personalized_response = self.generate_query_response(contact, analysis['queries'])
                            self.send_query_response_with_booking(db, contact, msg, personalized_response)
                        else:
                            self.send_meeting_booking_email(db, contact, msg)
                
                    elif sentiment == "NEGATIVE":
                        if analysis.get('has_query'):
                            negative_response = self.generate_negative_response_with_query(contact, clean_body, analysis['queries'])
                            self.send_negative_response_email(db, contact, msg, negative_response)
                        else:
                            self.send_acknowledgment_email(db, contact, msg)
                
                    else:  
                        if analysis.get('has_query'):
                            neutral_response = self.generate_neutral_response_with_query(contact, analysis['queries'])
                            self.send_neutral_response_email(db, contact, msg, neutral_response)
                        else:
                            self.send_neutral_acknowledgment_email(db, contact, msg)

                    logger.info(f"Reply from {sender_email} analyzed as {sentiment}. Response sent.")

                except Exception as e:
                    logger.error(f"Error processing reply from {sender_email}: {str(e)}")
                    db.rollback()
        
            db.commit()
                
    
    def generate_negative_response_with_query(self, contact: Contact, reply_body: str, queries: str) -> str:
        thread_id = self.get_or_create_thread_for_contact(contact)
        
        prompt = f"""
**Context:** A potential client, whose attention you've captured with an initial strategic outreach, has responded negatively. However, they have asked specific questions. Your goal is to provide a brief, professional, and value-driven reply that respectfully answers their queries, maintains a high-level advisory tone, and keeps the door open for a future, more relevant conversation.
 
**Client's Negative Response:**
{reply_body}
 
**Client Questions to Address:**
{queries}
 
**Response Instructions:**
 
1.  **Opening:**
    -   Acknowledge and thank them for their candor and the time they took to respond.
    -   Respect their current position without being defensive or trying to argue. Your tone should be that of a peer who understands and accepts their priorities.
 
2.  **Answer Their Questions:**
    -   Address each of their questions directly but concisely.
    -   Instead of simple answers, provide a high-level strategic perspective. Frame your response in a way that provides genuine value and demonstrates your deep understanding of the problem space, even without a commercial engagement.
    -   Showcase your expertise through your insights, not through a sales pitch.
 
3.  **The Unsolicited Insight (Optional but encouraged):**
    -   If a natural opportunity exists, provide one brief, relevant, and unsolicited insight related to their questions or industry. This should not be a sales point but rather a piece of knowledge that reinforces your status as a knowledgeable partner.
 
4.  **Closing:**
    -   Respect their decision and the timing of their business needs.
    -   Leave a strategic breadcrumb for the future. State that you'll be there as a resource if their needs evolve, but do so without a request for a meeting or a follow-up. The goal is to be remembered as a trusted advisor, not a persistent salesperson.
 
**Important Guidelines:**
-   Maintain a highly respectful, professional, and non-pushy tone throughout.
-   Do not try to overcome their stated objections.
-   The focus is on providing value for free, building trust for a future relationship.
-   Do not include any sales pitches, links, or requests for meetings.
-   Keep the response concise, ideally 1-2 paragraphs.
-   Do not add any special characters or symbols.
 
Write only the email body content. Do not include a subject line or a greeting. I will add those separately.
"""
        
        response = self._get_assistant_response(prompt, thread_id)
        if response:
            return response
        else:
            return f"""Thank you for your honest feedback and for taking the time to respond. I completely understand that our services may not be the right fit for {contact.company_name} at this time.

Regarding your questions: {queries} - I'd be happy to provide some insights that might be helpful for your business, regardless of whether we work together.

I appreciate your professionalism and wish you continued success with {contact.company_name}."""
        

    def generate_neutral_response_with_query(self, contact: Contact, queries: str) -> str:
        thread_id = self.get_or_create_thread_for_contact(contact)
        
        prompt = f"""
**Context:** A potential client has given a neutral response to our outreach but has asked specific questions. They haven't rejected us but haven't shown strong interest either. Your goal is to provide valuable answers and gently nurture the relationship.

**Client Questions:**
{queries}

**Response Instructions:**

1. **Opening:**
    - Thank them for their response
    - Acknowledge their questions
    - Show appreciation for their interest

2. **Answer Their Questions:**
    - Provide detailed, valuable answers
    - Show expertise and build credibility
    - Include relevant examples without naming clients
    - Focus on value and outcomes

3. **Soft Close:**
    - Don't push for immediate action
    - Invite further discussion if they find the information useful
    - Keep it low-pressure but professional

**Important Guidelines:**
- Maintain warm but professional tone
- Provide real value in answers
- Build trust through expertise
- No hard sales pitch
- Do not add any special character or symbols in mail
- Keep response informative but concise (3-4 paragraphs max)

Write only the email body content, no subject line needed. Don't include greeting, I will add it.
"""
        
        response = self._get_assistant_response(prompt, thread_id)
        if response:
            return response
        else:
            return f"""Thank you for taking the time to respond and for your questions about our services.

Regarding your questions: {queries} - I'd be happy to provide detailed insights that could be valuable for {contact.company_name}, whether or not we end up working together.

If you find this information useful or have any follow-up questions, feel free to reach out. I'm here to help."""

    def send_negative_response_email(self, db: Session, contact: Contact, original_msg: email.message.Message, ai_response: str):
        subject = original_msg.get("Subject", "")
        subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

        content = f"""Hi {contact.name},

{ai_response}

Best regards,
Ambika Sharma
Chief Strategist
Pulp Strategy Communications Pvt. Ltd."""
        full_body = self._create_threaded_body(content, original_msg)

        in_reply_to, references_chain = self._build_references_chain(original_msg)
        
        success = self.send_email(
            to_email=contact.email,
            subject=subject,
            content=full_body,
            in_reply_to=in_reply_to,
            references=references_chain
        )
        if success:
            with get_db_session() as db:
                response_content = ContentInfo(
                    contact_id=contact.id,
                    client_email=contact.email,
                    email_type="reply_response",
                    subject=subject,
                    body=content,
                    message_id=success,
                    reference=references_chain,
                    in_reply_to=original_msg.get("Message-ID")
                )
                db.add(response_content)
                db.commit()
    
    def send_neutral_response_email(self, db: Session, contact: Contact, original_msg: email.message.Message, ai_response: str):
        subject = original_msg.get("Subject", "")
        subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        
        content = f"""Hi {contact.name},

{ai_response}

Best regards,
Ambika Sharma
Chief Strategist
Pulp Strategy Communications Pvt. Ltd."""
        full_body = self._create_threaded_body(content, original_msg)
        
        previous_refs = original_msg.get('References', '').strip()
        current_msg_id = original_msg.get('Message-ID', '').strip()
    
        references = []
        if previous_refs:
            references.extend([ref.strip() for ref in previous_refs.split() if ref.strip()])
        if current_msg_id and current_msg_id not in references:
            references.append(current_msg_id)
            
        references_chain = ' '.join(references)

        success = self.send_email(
            to_email=contact.email,
            subject=subject,
            content=full_body,
            in_reply_to=current_msg_id,
            references=references_chain
        )
        if success:
            with get_db_session() as db:
                response_content = ContentInfo(
                    contact_id=contact.id,
                    client_email=contact.email,
                    email_type="reply_response",
                    subject=subject,
                    body=content,
                    message_id=success,
                    in_reply_to=original_msg.get("Message-ID"),
                    reference=references_chain
                )
                db.add(response_content)
                db.commit()

    def send_neutral_acknowledgment_email(self, db: Session, contact: Contact, original_msg: email.message.Message):
        subject = original_msg.get("Subject", "")
        subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        in_reply_to, references_chain = self._build_references_chain(original_msg)
        content = f"""Hi {contact.name},

Thank you for taking the time to respond to my message. I understand you may be evaluating various options or have other priorities at the moment.

If circumstances change or if you'd like to explore how we might help {contact.company_name} in the future, please don't hesitate to reach out.

Best regards,
Ambika Sharma
Chief Strategist
Pulp Strategy Communications Pvt. Ltd."""
        full_body = self._create_threaded_body(content, original_msg)
        success = self.send_email(to_email=contact.email, subject=subject, content=full_body, in_reply_to=in_reply_to, references=references_chain)
        if success:
            with get_db_session() as db:
                response_content = ContentInfo(
                    contact_id=contact.id,
                    client_email=contact.email,
                    email_type="reply_response",
                    subject=subject,
                    body=full_body,
                    message_id=success,
                    in_reply_to=in_reply_to,
                    reference=references_chain

            )
            db.add(response_content)
            db.commit()

    def generate_query_response(self, contact: Contact, queries: str) -> str:
        thread_id = self.get_or_create_thread_for_contact(contact)
        prompt = f"""
Don't start with greeting just give the main query answering body.
**Context:** A potential client has responded positively to our outreach and asked specific questions. Your goal is to provide detailed, value-focused answers that build trust and demonstrate expertise.

**Client Questions:**
{queries}

**Response Instructions:**

1. **Opening (First Paragraph):**
    - Express appreciation for their interest
    - Acknowledge their specific questions
    - Show that you understand their business needs

2. **Main Response (2-3 small Paragraphs):**
    - Answer each question thoroughly but concisely
    - Support answers with specific capabilities or methodologies
    - Mention relevant experience without naming clients
    - Focus on value and results
    - Use bullet points for clarity when listing features/benefits

3. **Value Proposition:**
    - Highlight Pulp Strategy's unique strengths
    - Emphasize our proven track record
    - Reference our expertise in their industry
    - Show understanding of their specific challenges

4. **Closing:**
    - Express enthusiasm about potential collaboration
    - Maintain professionalism with a warm tone
Don't add anything regarding booking a call or meeting in the mail
**Important Guidelines:**
- Keep responses business-focused and specific
- No pricing details
- No technical jargon unless in their questions
- Focus on benefits and outcomes
- Do not add any special character or symbols in mail (most important to remember).
- Make each answer value-focused
- Use clear, confident language
- Keep total response length to 2 paragraphs plus any bullet points

Write a reply for just these queries dont't send me the whole mail content. I will integrate this content in my mail body.
"""
        response = self._get_assistant_response(prompt,thread_id)
        if response:
            return response
        else:
            return f"""Thank you for your interest and questions about Pulp Strategy's services. I appreciate you taking the time to reach out.

While each client engagement is unique, I can share that we've helped companies in {contact.industry} achieve significant results through our strategic approach. I'd be happy to discuss your specific requirements and how we can tailor our solutions to {contact.company_name}'s needs.

I believe a brief conversation would be the most effective way to explore this opportunity further and provide detailed answers to your questions."""

    def send_query_response_with_booking(self, db: Session, contact: Contact, original_msg: email.message.Message, personalized_response: str):
        subject = original_msg.get("Subject", "")
        subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        booking_url = 'https://outlook.office.com/book/lol@pulpstrategy.com/s/_y6EIIzMKEWQlBg_0SarWQ2?ismsaljsauthenabled'
        button_html = f"""
        <div style="text-align: center; margin: 25px 0;">
            <a href="{booking_url}" target="_blank" style="display: inline-block; padding: 12px 24px; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; color: #ffffff; background-color: #007bff; text-decoration: none; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            Schedule a Quick Call
            </a>
        </div>
        """
        plain_text = f"""Hi {contact.name},

        {personalized_response}

I believe a quick call would be the best way to dive deeper into these points and discuss how we can specifically help {contact.company_name}. Please feel free to schedule a time that works best for you:

{booking_url}

Best regards,
Ambika Sharma
Chief Strategist
Pulp Strategy Communications Pvt. Ltd"""
        full_plain_text = self._create_threaded_body(plain_text, original_msg)
        in_reply_to, references_chain = self._build_references_chain(original_msg)
        references_chain = f"{original_msg.get('References', '')} {original_msg.get('Message-ID')}".strip()

        success = self.send_email(
            to_email=contact.email,
            subject=subject,
            content=full_plain_text,
            in_reply_to=in_reply_to,
            references=references_chain
        )
        if success:
            with get_db_session() as db:
                response_content = ContentInfo(
                    contact_id=contact.id,
                    client_email=contact.email,
                    email_type="reply_response",
                    subject=subject,
                    body=full_plain_text,
                    message_id=success,
                    reference=references_chain,
                    in_reply_to=in_reply_to
                )
                db.add(response_content)
                db.commit()


    def send_meeting_booking_email(self, db: Session, contact: Contact, original_msg: email.message.Message):
        subject = original_msg.get("Subject", "")
        subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        reply_body = self._extract_main_reply(get_body_from_message(original_msg))
        booking_url = 'https://outlook.office.com/book/lol@pulpstrategy.com/s/_y6EIIzMKEWQlBg_0SarWQ2?ismsaljsauthenabled'
        prompt = f"""
You are Ambika Sharma, owner and chief strategist at Pulp Strategy.
Your goal is to write a warm, personalized email to convert a prospect's positive interest into a meeting.
You are acting as a skilled communicator, NOT a file searcher.

**Context:**
- Their name: {contact.name}
- Their company: {contact.company_name}
- Their positive reply to our first email: "{reply_body}"

**Your Task:**
Read their reply carefully. Write a natural, human-sounding response that:
1.  Acknowledges their specific message (e.g., if they said "this is timely", mention that).
2.  Briefly and relevantly bridges their interest to the value Pulp Strategy provides.
3.  Naturally transitions to asking for a brief introductory call.
4.  Inserts the exact placeholder [MEETING_BUTTON] where the call-to-action should logically go.
5.  Do not add any special character or symbols in mail or any bold letters i.e. ** (most important to remember).

**Output Format:**
Provide your response as a single string in this exact format: Subject Line|||Email Body
"""
        ai_response = None
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3  
            )
            ai_response = response.choices[0].message.content
        
            try:
                new_subject, email_body = ai_response.split('|||', 1)
                if new_subject and new_subject.strip():
                    subject = new_subject.strip()
            except ValueError:
                email_body = ai_response
                logger.warning(f"Could not parse subject from AI response for {contact.email}")
            
            if not email_body.strip():
                logger.error(f"Empty email body from AI for {contact.email}")
                return
 
            plain_text_link = f"You can book a convenient time on my calendar here: {booking_url}"

            email_body = email_body.strip()

            plain_text_content = email_body.replace('[MEETING_BUTTON]', plain_text_link)
            full_plain_text_content = self._create_threaded_body(plain_text_content, original_msg)
            
            in_reply_to, references_chain = self._build_references_chain(original_msg)
            
            # Send the email
            success = self.send_email(
                to_email=contact.email,
                subject=subject,
                content=full_plain_text_content,
                in_reply_to=in_reply_to,
                references=references_chain
            )
            if success:
                with get_db_session() as db:
                    response_content = ContentInfo(
                        contact_id=contact.id,
                        client_email=contact.email,
                        email_type="reply_response",
                        subject=subject,
                        body=full_plain_text_content,
                        message_id=success,
                        in_reply_to=in_reply_to,
                        reference=references_chain
                    )
                    db.add(response_content)
                    db.commit()
                    logger.info(f"Successfully sent meeting booking email to {contact.email}")

        except Exception as e:
            logger.error(f"An unexpected error occurred while sending the booking email to {contact.email}: {e}")
    
    
    def send_acknowledgment_email(self, db: Session, contact: Contact, original_msg: email.message.Message):
        subject = original_msg.get("Subject", "")
        subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        content = f"""Hi {contact.name},

Thank you for taking the time to respond. I appreciate your feedback and understand that this might not be the right fit or timing for {contact.company_name}.

If circumstances change in the future or if you ever need digital marketing and strategy services, please don't hesitate to reach out.

Best regards,
Ambika Sharma
Chief Strategist
Pulp Strategy Communications Pvt. Ltd."""
        full_body = self._create_threaded_body(content, original_msg)
        in_reply_to, references_chain = self._build_references_chain(original_msg)
        success = self.send_email(to_email=contact.email, subject=subject, content=full_body, in_reply_to=in_reply_to, references=references_chain)
        if success:
            with get_db_session() as db:
                response_content = ContentInfo(
                    contact_id=contact.id,
                    client_email=contact.email,
                    email_type="reply_response",
                    subject=subject,
                    body=content,
                    message_id=success,
                    in_reply_to=original_msg.get("Message-ID"),
                    reference=references_chain
                )
                db.add(response_content)
                db.commit()
    
    def send_stop_contact_acknowledgment(self, db: Session, contact: Contact, original_msg: email.message.Message):        
        subject = original_msg.get("Subject", "")
        subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        in_reply_to, references_chain = self._build_references_chain(original_msg)

        content = f"""Hi {contact.name},
        
As requested, you have been removed from our mailing list and will not receive any further communication from us on this topic.

We appreciate you letting us know.

Best regards,
Ambika Sharma
Chief Strategist
Pulp Strategy Communications Pvt. Ltd."""
        full_body = self._create_threaded_body(content, original_msg)

        success = self.send_email(
            to_email=contact.email,
            subject=subject,
            content=full_body,
            in_reply_to=in_reply_to,
            references=references_chain
        )
            
        if success:
            with get_db_session() as db:
                response_content = ContentInfo(
                    contact_id=contact.id,
                    client_email=contact.email,
                    email_type="stop_contact_ack",
                    subject=subject,
                    body=content,
                    message_id=success, in_reply_to=in_reply_to, reference=references_chain
                )
                db.add(response_content)
                db.commit()
            logger.info(f"Sent stop contact acknowledgment to {contact.email}")
        else:
            logger.error(f"Failed to send stop contact acknowledgment to {contact.email}")

mail_service = MailService()

def send_initial_email(contact: Contact, db: Session) -> bool:
    try:
        subject, content = mail_service.generate_initial_email_content(contact, db)
        
        message_id = mail_service.send_email(contact.email, subject=subject, content=content)
        
        if message_id:
            db.add(ContentInfo(
                contact_id=contact.id, client_email=contact.email,
                email_type="initial", subject=subject, body=content,
                message_id=message_id
            ))
            db.flush()
            return True
        else:
            logger.error(f"Failed to send initial email to {contact.email}")
            return False
            
    except Exception as e:
        logger.error(f"Exception in send_initial_email for {contact.email}: {e}")
        return False

def send_drip_email(contact: Contact, drip_number: int, db: Session) -> bool:
    try:
        subject, content = mail_service.generate_drip_content(contact, drip_number, db)
        
        message_id = mail_service.send_email(
            to_email=contact.email, 
            subject=subject, 
            content=content
        )

        if message_id:
            db.add(ContentInfo(
                contact_id=contact.id,
                client_email=contact.email,
                email_type=f"drip_{drip_number}",
                subject=subject,
                body=content,
                message_id=message_id
            ))
            db.flush()
            return True
    except Exception as e:
        logger.error(f"Error in send_drip_email for {contact.email}: {e}")
    return False

def check_and_update_replies():
    new_email_messages = mail_service.agent_3_reply_checking()
    if new_email_messages:
        mail_service.update_reply_status_and_check_sentiment(new_email_messages)
    return len(new_email_messages)
     
