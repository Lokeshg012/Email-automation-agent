from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os, csv
from pathlib import Path
import re
from datetime import datetime

from frontend.db import get_db_session
from tables import Contact, ContentInfo
from sqlalchemy.orm import Session, joinedload

client_router = APIRouter()
TEMPLATES_DIR = str(Path(__file__).resolve().parents[1] / "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

UPLOAD_FOLDER = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

_FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")

def _secure_filename(filename: str) -> str:
    name = os.path.basename(filename)
    name = name.replace(" ", "_")
    return _FILENAME_SAFE_PATTERN.sub("", name)

# ------------------ Client Management ------------------
@client_router.get("/client-management", response_class=HTMLResponse)
async def client_management(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)

    try:
        db = get_db_session()
        try:
            clients = db.query(Contact).all()
        finally:
            db.close()
    except Exception as e:
        print(f"Database not available: {e}")
        clients = []  # Empty list when database is not available

    return templates.TemplateResponse(
        "client_management.html", {"request": request, "clients": clients}
    )

@client_router.get("/client/{client_id}/emails", response_class=HTMLResponse)
async def client_email_history(request: Request, client_id: int):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)

    try:
        db = get_db_session()
        try:
            # Get client details
            client = db.query(Contact).filter(Contact.id == client_id).first()
            if not client:
                request.session["flash"] = "Client not found"
                return RedirectResponse(url="/client-management", status_code=302)

            # Get all email content for this client, excluding thread-related emails
            emails = db.query(ContentInfo).filter(
                ContentInfo.contact_id == client_id,
                ~ContentInfo.email_type.in_(['thread_created', 'thread_replied'])  # Exclude thread-related emails
            ).order_by(
                ContentInfo.sent_at.desc() if hasattr(ContentInfo, 'sent_at') else ContentInfo.id.desc()
            ).all()

            # If no emails found, try to create placeholder entries based on client's email status
            if not emails:
                emails = []
                if hasattr(client, 'first_mail_date') and client.first_mail_date:
                    emails.append({
                        'email_type': 'initial_sent',
                        'subject': 'Initial Outreach',
                        'sent_at': client.first_mail_date,
                        'body': 'Email content not available in the database.'
                    })
                # Add similar placeholders for other email types if needed

            return templates.TemplateResponse(
                "email_history.html",
                {
                    "request": request,
                    "client": client,
                    "emails": emails
                }
            )
        finally:
            db.close()
    except Exception as e:
        print(f"Error fetching email history: {e}")
        request.session["flash"] = f"Error loading email history: {str(e)}"
        return RedirectResponse(url=f"/client/{client_id}", status_code=302)

# ------------------ Add Client ------------------
@client_router.get("/client/add", response_class=HTMLResponse)
async def add_client_get(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("add_client.html", {"request": request})


@client_router.post("/client/add")
async def add_client_post(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    company_name: str = Form(...),
    company_url: str = Form(...),
    linkedin: str = Form(...),
):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)

    db = get_db_session()
    try:
        # Check if contact already exists
        existing_contact = db.query(Contact).filter(Contact.email == email).first()
        if existing_contact:
            request.session["flash"] = f"Contact with email {email} already exists"
            return RedirectResponse(url="/client-management", status_code=302)
        
        # Create new contact
        contact = Contact(
            name=name,
            email=email,
            company_name=company_name,
            company_url=company_url,
            linkedin=linkedin
        )
        db.add(contact)
        db.commit()
        
        request.session["flash"] = f"Client {name} added successfully"
        return RedirectResponse(url="/client-management", status_code=302)
    except Exception as e:
        db.rollback()
        request.session["flash"] = f"Error adding client: {str(e)}"
        return RedirectResponse(url="/client-management", status_code=302)
    finally:
        db.close()

@client_router.get("/client/{client_id}", response_class=HTMLResponse)
async def client_details(request: Request, client_id: int):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)

    try:
        db = get_db_session()
        try:
            client = db.query(Contact).filter(Contact.id == client_id).first()
            if not client:
                request.session["flash"] = "Client not found"
                return RedirectResponse(url="/client-management", status_code=302)
        finally:
            db.close()
    except Exception as e:
        print(f"Database not available: {e}")
        request.session["flash"] = "Database not available"
        return RedirectResponse(url="/client-management", status_code=302)

    return templates.TemplateResponse(
        "client_details.html", {"request": request, "client": client}
    )
# ------------------ Upload CSV ------------------
@client_router.post("/upload-csv")
async def upload_csv(request: Request, file: UploadFile = File(...)):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)

    if not file.filename.endswith(".csv"):
        request.session["flash"] = "Invalid file type. Please upload a .csv file"
        return RedirectResponse(url="/client-management", status_code=302)

    filename = _secure_filename(file.filename)
    filepath = UPLOAD_FOLDER / filename

    with open(filepath, "wb") as f:
        f.write(await file.read())

    db = get_db_session()
    try:
        with open(filepath, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            added_count = 0
            skipped_count = 0
            
            for row in reader:
                try:
                    # Check if contact already exists
                    existing_contact = db.query(Contact).filter(Contact.email == row.get("email")).first()
                    if existing_contact:
                        skipped_count += 1
                        continue
                    
                    # Create new contact
                    contact = Contact(
                        name=row.get("name"),
                        email=row.get("email"),
                        company_name=row.get("company_name"),
                        company_url=row.get("company_url"),
                        linkedin=row.get("linkedin")
                    )
                    db.add(contact)
                    added_count += 1
                except Exception as e:
                    skipped_count += 1
                    continue
            
            db.commit()
            request.session["flash"] = f"CSV uploaded successfully! Added {added_count} contacts, skipped {skipped_count} duplicates."
            
    except Exception as e:
        db.rollback()
        request.session["flash"] = f"Error processing CSV: {str(e)}"
    finally:
        db.close()

    return RedirectResponse(url="/client-management", status_code=302)

# ------------------ Client Table Partial ------------------
@client_router.get("/client-table", response_class=HTMLResponse)
async def client_table_partial(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)

    db = get_db_session()
    try:
        clients = db.query(Contact).all()
        return templates.TemplateResponse(
            "partials/client_table.html", {"request": request, "clients": clients}
        )
    finally:
        db.close()
