import os
import sys
import secrets
import hashlib
import uuid
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import uvicorn

from auth import get_password_hash, verify_password

sys.path.append(".")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

class Config:
    JWT_SECRET = "a_very_strong_and_long_secret_for_jwt_that_is_at_least_32_bytes"
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24
    DB_FILE = "yodda.db"
    GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

API_PROVIDER_CONFIG = {
    "groq": {"endpoint": "https://api.groq.com/openai/v1/chat/completions", "model": "llama3-8b-8192"},
    "nvidia": {"endpoint": "https://integrate.api.nvidia.com/v1/chat/completions", "model": "meta/llama3-8b-instruct"},
    "huggingface": {"endpoint": "https://router.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2", "model": "mistralai/Mistral-7B-Instruct-v0.2"},
    "google_gemini": {"endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent", "model": "gemini-1.5-pro-latest"},
    "google_ai_studio": {"endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent", "model": "gemini-1.5-flash-latest"}
}

class UserRegister(BaseModel):
    name: str
    email: str
    password: str = Field(..., min_length=8)
class UserLogin(BaseModel): email: str; password: str
class OrchestrateRequest(BaseModel): query: str; platform: str; theme: str
class PluginRequest(BaseModel): provider: str; key: str; type: str
class AdminPluginRequest(PluginRequest): user_email: str = None
class ValidateRequest(BaseModel): provider: str; key: str

def load_db():
    if not os.path.exists(Config.DB_FILE): return {"users": {}}
    try:
        with open(Config.DB_FILE, "r") as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {"users": {}}

def save_db(db):
    with open(Config.DB_FILE, "w") as f: json.dump(db, f, indent=4)


def init_sqlite_db():
    """
    Ensure SQLite test.db exists with a users table and a default admin user.
    This runs on startup so a fresh server can work without manual seeding.
    """
    import sqlite3

    db_path = "test.db"
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        if count == 0:
            admin_email = "admin@test.com"
            admin_password_hash = get_password_hash("password123")
            cur.execute(
                "INSERT INTO users (email, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
                (admin_email, admin_password_hash, 1, datetime.utcnow().isoformat()),
            )
        conn.commit()
    finally:
        conn.close()

DataStore = load_db()
app = FastAPI(title="YODDA", description="YODDA Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """
    Initialize the SQLite database with a default admin user if needed.
    """
    init_sqlite_db()

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def create_jwt_token(user_email: str) -> str:
    payload = {"sub": user_email, "iat": datetime.utcnow(), "exp": datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRATION_HOURS)}
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    # ... (rest of the function is unchanged)
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
        email = payload.get("sub")
        if not email: raise HTTPException(status_code=401, detail="Invalid token")
        user = DataStore["users"].get(email)
        if not user: raise HTTPException(status_code=401, detail="User not found")
        user['email'] = email
        return user
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_current_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("is_admin"): raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

@router.post("/auth/register")
def register(user: UserRegister):
    if user.email in DataStore["users"]: raise HTTPException(status_code=400, detail="Email already registered")
    password_hash = get_password_hash(user.password)
    DataStore["users"][user.email] = {
        "name": user.name,
        "password_hash": password_hash,
        "created_at": datetime.utcnow().isoformat(),
        "is_admin": not DataStore["users"],
        "tier": "PREMIUM" if not DataStore["users"] else "FREE",
        "plugins": [],
    }
    save_db(DataStore)
    return {"token": create_jwt_token(user.email)}

@router.post("/auth/login")
def login(credentials: UserLogin):
    user = DataStore["users"].get(credentials.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored_hash: Optional[str] = user.get("password_hash")
    if not stored_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Prefer bcrypt hashes; fall back to legacy SHA256 comparison if needed.
    if stored_hash.startswith("$2") and "$" in stored_hash:
        if not verify_password(credentials.password, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        legacy_hash = hashlib.sha256(credentials.password.encode()).hexdigest()
        if legacy_hash != stored_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"token": create_jwt_token(credentials.email)}

@router.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)): return current_user

@api_router.post("/swarm/orchestrate")
def orchestrate(req: OrchestrateRequest, current_user: dict = Depends(get_current_user)):
    logging.info("Orchestration started.")
    text_plugin = next((p for p in current_user.get("plugins", []) if p.get('type') == 'text'), None)
    
    if not text_plugin and Config.GOOGLE_GEMINI_API_KEY:
        logging.info("Using fallback Google Gemini API key from environment.")
        text_plugin = {"provider": "google_gemini", "key": Config.GOOGLE_GEMINI_API_KEY}

    if not text_plugin: 
        logging.error("No API key configured or found in environment.")
        raise HTTPException(status_code=400, detail="No API key configured or found in environment.")
    
    provider = text_plugin['provider']
    logging.info(f"Using provider: {provider}")
    config = API_PROVIDER_CONFIG.get(provider)
    if not config: 
        logging.error(f"Provider '{provider}' not configured.")
        raise HTTPException(status_code=500, detail=f"Provider '{provider}' not configured.")
    
    headers = {"Content-Type": "application/json"}
    prompt = f"Generate a complete, single-file HTML document for a '{req.platform}' application. Request: '{req.query}'. Theme: '{req.theme}'. The file must be self-contained with all CSS and JavaScript. Respond with only the raw HTML code, no markdown."
    endpoint = config['endpoint']

    if provider in ["google_gemini", "google_ai_studio"]:
        endpoint = f"{endpoint}?key={text_plugin['key']}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
    else:
        headers["Authorization"] = f"Bearer {text_plugin['key']}"
        payload = {"model": config['model'], "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}

    try:
        logging.info(f"Making API call to {endpoint}")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        api_response = response.json()
        logging.info(f"Raw API response received: {json.dumps(api_response, indent=2)}")

        generated_code = None
        if provider in ["google_gemini", "google_ai_studio"]:
            generated_code = api_response.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        else:
            generated_code = api_response.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if not generated_code:
            logging.error("Failed to extract generated_code from API response.")
            raise HTTPException(status_code=500, detail="Failed to parse generated code from API response.")

        logging.info("Successfully extracted generated code.")
        return {"status": "BUILD_COMPLETED", "generated_code": generated_code.strip("```html").strip("```").strip()}

    except requests.exceptions.RequestException as e: 
        logging.error(f"API call failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API call failed: {str(e)}")
    except (KeyError, IndexError, Exception) as e: 
        logging.error(f"Failed to parse API response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to parse API response: {str(e)}")

@api_router.post("/admin/plugins")
def manage_plugin(req: AdminPluginRequest, admin_user: dict = Depends(get_current_admin_user)):
    user_email = req.user_email or admin_user['email']
    if user_email not in DataStore["users"]: raise HTTPException(status_code=404, detail=f"User '{user_email}' not found")
    DataStore["users"][user_email]["plugins"] = [p for p in DataStore["users"][user_email]["plugins"] if p.get('type') != req.type]
    DataStore["users"][user_email]["plugins"].append(req.dict(exclude={'user_email'}))
    save_db(DataStore)
    return {"message": f"API key for '{req.provider}' saved."}

@api_router.post("/admin/validate_key")
def validate_key(req: ValidateRequest, admin_user: dict = Depends(get_current_admin_user)):
    config = API_PROVIDER_CONFIG.get(req.provider)
    if not config: raise HTTPException(status_code=400, detail="Invalid provider.")
    
    headers = {"Content-Type": "application/json"}
    endpoint = config['endpoint']

    if req.provider in ["google_gemini", "google_ai_studio"]:
        endpoint = f"{endpoint}?key={req.key}"
        payload = {"contents": [{"parts": [{"text": "Test"}]}]}
    else:
        headers["Authorization"] = f"Bearer {req.key}"
        payload = {"model": config['model'], "messages": [{"role": "user", "content": "Test"}], "max_tokens": 5}
    
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return {"message": "API key is valid."}
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Validation API call failed: {str(e)}")

app.include_router(router)
app.include_router(api_router)
if __name__ == "__main__":
    uvicorn.run(app, host="159.65.144.25", port=5000)
