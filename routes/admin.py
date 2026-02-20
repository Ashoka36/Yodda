import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from agents.models import AdminSetup, AdminPluginRequest, ValidateRequest
from config.database import users_db
from config.settings import ADMIN_SETUP_DONE
from routes.auth import create_token, verify_token, hash_password
from config.settings import NVIDIA_API_URL

router = APIRouter()

def validate_api(endpoint: str, key: str) -> bool:
    return bool(key and key.startswith("nvapi-"))

@router.post("/admin/setup")
def setup_admin(data: AdminSetup):
    global ADMIN_SETUP_DONE
    if ADMIN_SETUP_DONE:
        raise HTTPException(400, "Admin already exists")
    
    admin_id = str(uuid.uuid4())
    users_db[admin_id] = {
        "email": data.email,
        "password": hash_password(data.password),
        "is_admin": True,
        "tier": "ENTERPRISE",
        "builds_used": 0,
        "created": datetime.utcnow().isoformat(),
        "plugins": []
    }
    
    ADMIN_SETUP_DONE = True
    token = create_token(data.email, is_admin=True)
    
    return {
        "message": "Admin created successfully",
        "token": token,
        "user": {"email": data.email, "is_admin": True}
    }

@router.post("/api/v1/admin/plugins")
def admin_manage_plugins(req: AdminPluginRequest, payload=Depends(verify_token)):
    if not payload.get("is_admin"):
        raise HTTPException(403, "Admin only")

    target_email = req.user_email or payload.get("email")
    if not target_email:
        raise HTTPException(400, "Missing target user email")

    target_user = None
    for u in users_db.values():
        if u["email"] == target_email:
            target_user = u
            break
    if not target_user:
        raise HTTPException(404, f"User '{target_email}' not found")

    plugin_entry = {"provider": req.provider, "key": req.key, "type": req.type}
    target_user["plugins"] = [p for p in target_user.get("plugins", []) if p.get("type") != req.type]
    target_user["plugins"].append(plugin_entry)
    return {"message": f"API key for '{req.provider}' saved."}

@router.post("/api/v1/admin/validate_key")
def admin_validate_key(req: ValidateRequest, payload=Depends(verify_token)):
    if not payload.get("is_admin"):
        raise HTTPException(403, "Admin only")

    if not req.key:
        raise HTTPException(400, "Missing API key")

    if req.provider.lower() == "nvidia":
        if not validate_api(NVIDIA_API_URL, req.key):
            raise HTTPException(400, "API key is invalid.")

    return {"message": "API key is valid."}
