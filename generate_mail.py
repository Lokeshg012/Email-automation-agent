# generate_mail.py
import mysql.connector
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# ---------- CONFIG ----------
db_config = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),  # <- correct variable
    'database': os.getenv('DB_NAME'),
    'ssl_ca': os.getenv('DB_SSL_CA')
}

# OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# ---------- FUNCTIONS ----------
def generate_mail(contact):
    """Generate initial cold outreach mail."""
    prompt = f"""
You are writing a professional cold outreach email.  

Sender details:  
- Name: Piyush Mishra  
- Company: XYZ Company  
- Role: Business Development Partner for Pulp Strategy (a digital marketing and strategy agency).  

Recipient details:  
- Name: {contact['name']}  
- Company: {contact['company_name']}  
- Website: {contact['company_url']}  
- Industry: {contact['industry']}  

Instructions:  
- This is **Day 1: Initial Outreach**.  
- Write the email as if it’s coming from Piyush Mishra (XYZ Company) on behalf of Pulp Strategy.  
- Make it personalized by referencing their company and industry.  
- Highlight how **Pulp Strategy** can add value in their industry context.  
- Keep the tone professional, friendly, and non-generic.  
- Structure: **Subject line + Email body**.  
- End with a polite call-to-action for a quick call/meeting.  
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    mail_content = response.choices[0].message.content.strip()

    # Split subject and body
    lines = mail_content.split("\n", 1)
    subject = lines[0].replace("Subject:", "").strip()
    body = lines[1].strip() if len(lines) > 1 else ""

    return subject, body

def generate_followup_mail(contact, day):
    """Generate follow-up email for given day (Day 2, Day 3, etc)."""
    prompt = f"""
You are writing a follow-up cold email.  

Sender details:  
- Name: Piyush Mishra  
- Company: XYZ Company  
- Role: Business Development Partner for Pulp Strategy (a digital marketing and strategy agency).  

Recipient details:  
- Name: {contact['name']}  
- Company: {contact['company_name']}  
- Website: {contact['company_url']}  
- Industry: {contact['industry']}  

Instructions:  
- This is **Day {day} follow-up** (after no reply to earlier emails).  
- Keep the tone polite, professional, and not pushy.  
- Ensure it feels different from previous emails.  
- Adjust the approach depending on the day:  
  - **Day 2** → Friendly reminder.  
  - **Day 3** → Share an insight, case study, or value proposition.  
  - **Day 4** → Light final nudge with “happy to connect later if now isn’t a good time”.  
- Structure: **Subject line + Email body**.  
- End with a polite call-to-action for a quick call/meeting.  
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    mail_content = response.choices[0].message.content.strip()

    # Split subject and body
    lines = mail_content.split("\n", 1)
    subject = lines[0].replace("Subject:", "").strip()
    body = lines[1].strip() if len(lines) > 1 else ""

    return subject, body

def fetch_first_contact():
    """Fetch the first contact with industry filled."""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, name, email, company_name, company_url, industry FROM contacts WHERE industry IS NOT NULL LIMIT 1;")
    row = cursor.fetchone()

    cursor.close()
    conn.close()
    return row

# ---------- MAIN ----------
if __name__ == "__main__":
    contact = fetch_first_contact()
    if contact:
        print(f" Generating initial mail for: {contact['name']} ({contact['company_name']})")
        mail_content = generate_mail(contact)
        print("\n------ DAY 1 MAIL ------\n")
        print(mail_content)

        # # Generate follow-ups
        # for day in range(2, 5):
        #     print(f"\n------ DAY {day} FOLLOW-UP ------\n")
        #     followup_content = generate_followup_mail(contact, day)
        #     print(followup_content)

    else:
        print(" No contact with industry found.")
