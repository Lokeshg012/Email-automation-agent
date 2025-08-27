"# Email Drip Campaign System

A complete automated email drip campaign system built with FastAPI, SQLAlchemy, and OpenAI for personalized email generation.

## Features

- **Automated Drip Campaigns**: 3-stage drip sequence (immediate, +3 days, +5 days)
- **Reply Detection**: Automatic IMAP monitoring and drip stopping
- **Personalized Content**: OpenAI-powered email generation
- **RESTful API**: Complete FastAPI backend with all CRUD operations
- **Background Scheduling**: APScheduler for automated processing
- **Database Integration**: SQLAlchemy with MySQL support
- **Meeting Booking**: Automatic calendar link sending on replies

## Database Schema

### first table
- `id` (int, pk)
- `name`, `email`, `company_name`, `company_url`, `industry`
- `status` (default "null", changes to "replied" if reply comes)
- `last_email_sent`, `drip1_date`, `drip2_date`, `drip3_date`, `reply_date`
- `created_at`, `updated_at`

### content table
- `id` (int, pk)
- `contact_id` (foreign key → first.id)
- `drip1_content`, `drip2_content`, `drip3_content`, `reply_content`
- `created_at`, `updated_at`

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables** (create `.env` file):
   ```env
   # Database
   DB_HOST=your-db-host
   DB_PORT=3306
   DB_USER=your-db-user
   DB_PASSWORD=your-db-password
   DB_NAME=your-db-name
   DB_SSL_CA=ca.pem

   # Email
   EMAIL_ADDRESS=your-email@gmail.com
   EMAIL_PASSWORD=your-app-password
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   IMAP_HOST=imap.gmail.com
   IMAP_PORT=993

   # OpenAI
   OPENAI_API_KEY=your-openai-key

   # Optional
   CALENDAR_LINK=https://calendly.com/your-link
   SENDER_NAME=Piyush Mishra
   SENDER_COMPANY=XYZ Company
   ```

3. **Run the Application**:
   ```bash
   python app.py
   ```

## API Endpoints

### Core Operations
- `POST /contacts` - Add new contact and start drip campaign
- `GET /contacts` - List all contacts (with filtering)
- `GET /contacts/{id}` - Get specific contact
- `DELETE /contacts/{id}` - Delete contact

### Campaign Management
- `GET /contacts/{id}/drip-status` - Get drip campaign status
- `POST /trigger-drips` - Manually trigger drip processing
- `POST /check-replies` - Manually check for replies
- `GET /stats` - Get campaign statistics

### Example Usage

**Add a new contact**:
```bash
curl -X POST "http://localhost:8000/contacts" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "company_name": "Example Corp",
    "company_url": "https://example.com",
    "industry": "Technology"
  }'
```

**Get campaign stats**:
```bash
curl "http://localhost:8000/stats"
```

## Workflow

1. **Add Contact**: Use POST /contacts to add a new contact
2. **Drip1 Sent**: Immediately sends personalized first email
3. **Drip2 Scheduled**: Automatically scheduled for 3 days later
4. **Drip3 Scheduled**: Automatically scheduled for 5 days after drip2
5. **Reply Detection**: System checks emails every 10 minutes
6. **Meeting Email**: Sends calendar booking link when reply detected
7. **Drip Stopping**: All future drips stopped when reply received

## Background Processing

- **Drip Processing**: Every 30 minutes
- **Reply Checking**: Every 10 minutes
- **Automatic Scheduling**: Handled by APScheduler

## File Structure

- `app.py` - FastAPI application and API endpoints
- `models.py` - SQLAlchemy database models
- `mail_service.py` - Email sending and reply checking
- `drip_logic.py` - Drip campaign management
- `config.py` - Configuration management
- `requirements.txt` - Python dependencies

## Notes

- Uses OpenAI GPT-4o-mini for personalized email generation
- Supports Gmail SMTP/IMAP (configure app passwords)
- MySQL database with SSL support
- Comprehensive error handling and logging
- Production-ready with proper scheduling

this is for testing
