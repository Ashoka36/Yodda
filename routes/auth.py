import uuid
import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from agents.models import UserRegister, UserLogin
from config.database import users_db, licenses_db
from config.settings import SECRET_KEY, security

router = APIRouter()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(email: str, is_admin: bool = False) -> str:
    payload = {
        "email": email,
        "is_admin": is_admin,
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if not token:
        raise HTTPException(401, "No token provided")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except:
        raise HTTPException(401, "Invalid token")

@router.post("/auth/register")
def register(data: UserRegister):
    for user in users_db.values():
        if user["email"] == data.email:
            raise HTTPException(400, "User already exists")
    
    user_id = str(uuid.uuid4())
    users_db[user_id] = {
        "email": data.email,
        "password": hash_password(data.password),
        "is_admin": False,
        "tier": "FREE",
        "builds_used": 0,
        "created": datetime.utcnow().isoformat(),
        "plugins": []
    }
    
    license_key = f"YP-FREE-{uuid.uuid4().hex[:8].upper()}"
    licenses_db[license_key] = {
        "user_id": user_id,
        "tier": "FREE",
        "status": "active"
    }
    
    token = create_token(data.email)
    
    return {
        "message": "Registration successful",
        "token": token,
        "license_key": license_key,
        "tier": "FREE"
    }

@router.post("/auth/login")
def login(data: UserLogin):
    for user in users_db.values():
        if user["email"] == data.email:
            if verify_password(data.password, user["password"]):
                token = create_token(data.email, user.get("is_admin", False))
                return {
                    "message": "Login successful",
                    "token": token,
                    "user": {
                        "email": user["email"],
                        "is_admin": user.get("is_admin", False),
                        "tier": user.get("tier", "FREE")
                    }
                }
            raise HTTPException(401, "Invalid password")
    raise HTTPException(404, "User not found")

@router.get("/auth/me")
def get_current_user(payload = Depends(verify_token)):
    for user in users_db.values():
        if user["email"] == payload["email"]:
            return {
                "email": user["email"],
                "tier": user.get("tier", "FREE"),
                "is_admin": user.get("is_admin", False),
                "builds_used": user.get("builds_used", 0),
                "plugins": user.get("plugins", [])
            }
    raise HTTPException(404, "User not found")
