# config.py - Centralized configuration management
from dotenv import load_dotenv
import os

load_dotenv()

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'ssl_ca': os.getenv('DB_SSL_CA') 
}

# Email Configuration
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
IMAP_HOST = os.getenv('IMAP_HOST')
IMAP_PORT = int(os.getenv('IMAP_PORT', 993))
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Drip Campaign Settings
DRIP_INTERVALS = {
    1: 0,  # Send drip1 immediately
    2: 3,  # Send drip2 after 3 days
    3: 5   # Send drip3 after 5 days from drip2
}

# Scheduler Settings
DRIP_PROCESSING_INTERVAL_MINUTES = 30  # Process drips every 30 minutes
REPLY_CHECK_INTERVAL_MINUTES = 10      # Check replies every 10 minutes

# Meeting booking link
CALENDAR_LINK = os.getenv('CALENDAR_LINK', 'https://calendly.com/your-calendar-link')

# Sender Information
SENDER_NAME = os.getenv('SENDER_NAME', 'Piyush Mishra')
SENDER_COMPANY = os.getenv('SENDER_COMPANY', 'XYZ Company')
SENDER_ROLE = os.getenv('SENDER_ROLE', 'Business Development Partner for Pulp Strategy')

# Validation
def validate_config():
    """Validate required configuration"""
    required_vars = [
        'DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME',
        'EMAIL_ADDRESS', 'EMAIL_PASSWORD', 'OPENAI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    return True
