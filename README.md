# 🔥 PULP EMAIL AGENT 🔥
## *The AI That Never Sleeps (So You Can)*

Welcome to the **PULP EMAIL AGENT** – an absolutely *unhinged* AI-powered email automation beast that does what 10 sales reps can't: work 24/7 without coffee breaks, sick days, or existential crises.

This isn't your grandma's email client. This is a **fully autonomous, sentiment-analyzing, drip-campaign-running, OpenAI-powered** monster that turns cold leads into warm conversations while you sleep, eat, or question your life choices.

---

## 🎯 What Does This Thing Actually Do?

### **Agent 1: The Initiator** 🚀
- Wakes up every day at **9 AM** like it has a job interview
- Crafts **hyper-personalized** initial emails using OpenAI's GPT-4
- Sends them out with the confidence of someone who knows they're about to close deals
- Tracks everything in a MySQL database because data is power

### **Agent 2: The Persistent One** 🔄
- Runs daily at **10 AM** (very punctual)
- Sends follow-up drip emails (3 drips max because we're not *that* annoying)
- Uses AI to craft value-driven, non-pushy follow-ups
- Each email sounds like it was written by a human who actually cares

### **Agent 3: The Mind Reader** 🧠
- Checks for replies **every 30 minutes** like an obsessed stalker (but legal)
- Analyzes sentiment: POSITIVE, NEGATIVE, or NEUTRAL
- Detects queries and responds intelligently
- Automatically books meetings when prospects show interest
- Respects "stop contact" requests (we're not monsters)

---

## 🛠️ The Tech Stack (AKA The Arsenal)

| Technology | Why We Use It |
|------------|---------------|
| **FastAPI** | Because we're not peasants who use Flask |
| **OpenAI GPT-4o** | The brain behind the operation |
| **SQLAlchemy + MySQL** | Data persistence for days |
| **APScheduler** | The clockwork that makes magic happen on time |
| **IMAP/SMTP** | Good ol' email protocols (Gmail compatible) |
| **Jinja2** | Pretty HTML emails that don't look like spam |
| **Python 3.10+** | The language of gods |

---

## 📦 Installation (The "I'm Ready to Rumble" Guide)

### Prerequisites
- Python 3.10+ (anything older and you're living in the past)
- MySQL database (install it, love it, cherish it)
- Gmail account with App Password enabled
- OpenAI API key (costs money, but genius ain't free)

### Step 1: Clone This Bad Boy
```bash
git clone <your-repo-url>
cd pulp-intern
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Your `.env` File
Create a `.env` file and fill it with your secrets:

```env
# Database Configuration
DB_HOST=localhost
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_NAME=email_drip_campaign

# Email Configuration
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_PASSWORD=your_app_password_here
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
IMAP_HOST=imap.gmail.com
IMAP_PORT=993

# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here
ASSISTANT_ID=asst_your_assistant_id
FILE_ID=file-your_file_id
THREAD_ID=thread_your_thread_id

# Session Secret
SECRET_KEY=some-random-secret-key-change-this
```

### Step 4: Setup OpenAI Assistant
Run the setup script to create your AI assistant:
```bash
python setup_assistant.py
```

### Step 5: Launch The Beast
```bash
python app.py
```

Or if you're fancy:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🎮 How To Use This Thing

### Via Web Interface (Recommended for Humans)
1. Open your browser to `http://localhost:8000`
2. Log in (default credentials are probably in the code somewhere 👀)
3. Upload contacts via CSV
4. Watch the magic happen in real-time on the dashboard

### Via API (For Developers Who Like JSON)

#### Add a Contact
```bash
POST /api/contacts
{
  "name": "Elon Musk",
  "email": "elon@spacex.com",
  "company_name": "SpaceX",
  "company_url": "https://spacex.com",
  "industry": "Aerospace"
}
```

#### Get All Contacts
```bash
GET /api/contacts
```

#### Upload Bulk Contacts (CSV)
```bash
POST /contacts/upload
# Upload a CSV file with columns: name, email, company_name, company_url, industry
```

---

## 📊 The Database Schema (For Nerds)

### **Contact Table** (`first`)
- Stores all your precious leads
- Tracks email status, sentiment, drip stage
- Knows who replied, who ignored you, and who told you to buzz off

### **ContentInfo Table** (`content`)
- Every email sent/received is logged here
- Message IDs for proper email threading
- Sentiment analysis results
- Foreign key to Contact table

### **EmailData Table**
- Stores CC recipients when people forward your emails
- Tracks referrals (free leads, baby!)

---

## 🤖 The AI Prompts (The Secret Sauce)

This thing uses **carefully crafted prompts** that make GPT-4 write like Ambika Sharma, the Chief Strategist at Pulp Strategy.

### Email Characteristics:
- ✅ **Hyper-personalized** (mentions company, industry, goals)
- ✅ **Value-driven** (not salesy, but strategic)
- ✅ **Professional yet conversational**
- ✅ **Short and punchy** (no one reads War & Peace emails)
- ✅ **Proper email threading** (replies actually show up in the right thread)

---

## 🚨 Important Notes (READ THIS OR SUFFER)

### Gmail App Passwords
You **MUST** use an App Password for Gmail. Here's how:
1. Enable 2FA on your Google account
2. Go to Security → App Passwords
3. Generate one for "Mail"
4. Use that in your `.env` file

### OpenAI Costs
This uses GPT-4o, which costs money. Monitor your usage or you'll wake up to a $500 bill. Don't say I didn't warn you.

### Rate Limits
Gmail has sending limits:
- Free Gmail: ~500 emails/day
- Google Workspace: ~2000 emails/day

Don't be stupid. Respect the limits.

### Database Tables
The tables are named `first` and `content` because reasons. Don't question it. Just accept it.

---

## 📅 Scheduler Jobs (The Automation)

| Job | Schedule | What It Does |
|-----|----------|--------------|
| **Agent 1** | Daily @ 9:00 AM IST | Sends initial emails to new contacts |
| **Agent 2** | Daily @ 10:00 AM IST | Sends drip follow-ups (Days 2, 5, 8) |
| **Agent 3** | Every 30 minutes | Checks for replies, analyzes sentiment, responds |

---

## 🐛 Troubleshooting (When Stuff Breaks)

### "Tables not found" Error
Run this to create tables:
```python
from tables import create_tables
create_tables()
```

### Emails Not Sending
- Check your Gmail App Password
- Make sure SMTP settings are correct
- Check if Gmail is blocking "less secure apps"

### OpenAI Errors
- Check your API key
- Make sure you have credits
- Verify ASSISTANT_ID, FILE_ID, THREAD_ID in `.env`

### Scheduler Not Running
- Check logs for errors
- Make sure timezone is set to `Asia/Kolkata` or your preferred timezone

---

## 🎨 File Structure

```
pulp-intern/
├── app.py                  # Main FastAPI app
├── mail_service.py         # The email engine (56KB of pure chaos)
├── drip_logic.py           # Drip campaign logic
├── tables.py               # SQLAlchemy models
├── assistant.py            # OpenAI assistant setup
├── pulp_file.py            # File handling utilities
├── requirements.txt        # Dependencies
├── .env                    # Your secrets (DON'T COMMIT THIS)
├── .gitignore              # Keeps your secrets safe
├── frontend/               # Web UI
│   ├── templates/          # Jinja2 HTML templates
│   ├── routes/             # FastAPI routes
│   └── uploads/            # CSV uploads go here
└── env/                    # Virtual environment (ignored by git)
```

---

## 🔐 Security Notes

- **NEVER** commit your `.env` file
- Use environment variables in production
- Change the `SECRET_KEY` to something secure
- Don't expose your OpenAI API key
- Use HTTPS in production

---

## 🚀 Deployment (Going Live)

### Option 1: Traditional Server
```bash
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Option 2: Docker (For the Cool Kids)
```dockerfile
# Create a Dockerfile if you want
# I didn't include one because I'm lazy
```

### Option 3: Cloud (AWS, GCP, Azure)
Deploy it wherever. It's just Python. It runs anywhere.

---

## 📝 License

Do whatever you want with this. Just don't sue me if it sends an email to the wrong person and costs you a client.

---

## 🤝 Contributing

Found a bug? Fix it and send a PR. Want to add a feature? Go wild. This is open source, baby.

---

## 📞 Support

If this breaks, Google it. If Google doesn't help, pray to the Stack Overflow gods. If that fails, check the logs. There's a reason we have logging.

---

## 🎯 Final Words

This project is the result of:
- ☕ Too much coffee
- 🌙 Too many late nights
- 🤖 Too much faith in AI
- 😤 Too little patience for manual emailing

If it helps you close deals, great. If it doesn't, well, at least you learned something about FastAPI and email automation.

Now go forth and automate! 🚀

---

### Made with 💀 by someone who's tired of sending emails manually

**P.S.** Don't forget to star this repo if it saves your sanity. Or don't. I'm not your boss.
