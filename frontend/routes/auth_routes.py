from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from tables import UserAuth, get_db 
from functools import wraps


TEMPLATES_DIR = str(Path(__file__).resolve().parents[1] / "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

auth_router = APIRouter()

# Login required decorator
def login_required(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if "user" not in request.session:
            return RedirectResponse(url="/", status_code=302)
        return await func(request, *args, **kwargs)
    return wrapper

# --- Login Routes ---

@auth_router.get("/", response_class=HTMLResponse)
async def login_get(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request})

@auth_router.post("/", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # WARNING: This checks for a plain text password in the database.
    user = db.query(UserAuth).filter(
        UserAuth.user_name == username,
        UserAuth.password == password  # Direct comparison
    ).first()

    if user:
        request.session["user"] = user.user_name
        request.session["user_id"] = user.id
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "error": "Invalid username or password"}
    )

# --- Registration Routes ---

@auth_router.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@auth_router.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match"}
        )

    existing_user = db.query(UserAuth).filter(UserAuth.user_name == username).first()
    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username already exists"}
        )
    
    # Create new user, saving the plain text password
    new_user = UserAuth(
        user_name=username,
        password=password,  # WARNING: Storing plain text password
        status="active"
    )
    
    db.add(new_user)
    db.commit()
    
    # Log the new user in immediately
    request.session["user"] = new_user.user_name
    request.session["user_id"] = new_user.id
    return RedirectResponse(url="/dashboard", status_code=302)


# --- Logout Route ---

@auth_router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)