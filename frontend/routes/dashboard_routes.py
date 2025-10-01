from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import or_
from frontend.db import get_db_session
from tables import Contact, ContentInfo
from frontend.routes.auth_routes import login_required

from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)

dashboard_router = APIRouter()
TEMPLATES_DIR = str(Path(__file__).resolve().parents[1] / "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@dashboard_router.get("/dashboard", response_class=HTMLResponse, name="dashboard")
@login_required
async def dashboard(request: Request):
    """
    Dashboard endpoint to display statistics and analytics.
    It fetches all required data for the stat cards and charts.
    """
    
    context_data = {
        "request": request,
        # THE FIX IS HERE: Default to a string "Guest" instead of {}
        "user": request.session.get("user", "Guest"),
        "total_clients": 0,
        "initial_mail_sent": 0,
        "received_mail": 0,
        "positive_replies": 0,
        "meetings_booked": 0,
        "drip_mails_sent": 0,
        "do_not_contact_requests": 0,
    }

    db = None
    try:
        db = get_db_session()
        
        # Original cards
        context_data["total_clients"] = db.query(Contact).count()
        context_data["initial_mail_sent"] = db.query(Contact).filter(Contact.first_mail_date.isnot(None)).count()
        context_data["received_mail"] = db.query(Contact).filter(Contact.status == "replied").count()
        
        # New cards data
        context_data["positive_replies"] = db.query(ContentInfo).filter(ContentInfo.sentiment == "positive").count()
        context_data["meetings_booked"] = db.query(Contact).filter(Contact.booking_status == "clicked").count()
        context_data["drip_mails_sent"] = db.query(Contact).filter(
            or_(
                Contact.drip1_date.isnot(None),
                Contact.drip2_date.isnot(None),
                Contact.drip3_date.isnot(None)
            )
        ).count()
        context_data["do_not_contact_requests"] = db.query(Contact).filter(Contact.status == "do_not_contact").count()

    except Exception as e:
        logger.error(f"Database error in dashboard. Using default data: {e}")
    
    finally:
        if db:
            db.close()

    # Date Calculation
    kolkata_tz = pytz.timezone('Asia/Kolkata')
    kolkata_now = datetime.now(kolkata_tz)
    context_data["current_date"] = kolkata_now.strftime('%A, %B %d, %Y')

    # Render the template
    return templates.TemplateResponse("dashboard.html", context_data)