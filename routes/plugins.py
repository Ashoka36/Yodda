from fastapi import APIRouter, HTTPException, Depends
from agents.models import Plugin, PluginManage
from config.database import users_db
from routes.auth import verify_token
from routes.admin import validate_api

router = APIRouter()

@router.post("/plugins/add")
def add_plugin(plugin: Plugin, payload = Depends(verify_token)):
    for user in users_db.values():
        if user["email"] == payload["email"]:
            if not validate_api(plugin.endpoint, plugin.key):
                raise HTTPException(400, "Invalid API")
            user["plugins"].append(plugin.dict())
            return {"message": "Plugin added"}
    raise HTTPException(404, "User not found")

@router.post("/plugins/manage")
def manage_plugin(data: PluginManage, payload = Depends(verify_token)):
    if not payload.get("is_admin"):
        raise HTTPException(403, "Admin only")
    if data.user_email:
        for user in users_db.values():
            if user["email"] == data.user_email:
                if not validate_api(data.plugin.endpoint, data.plugin.key):
                    raise HTTPException(400, "Invalid API")
                user["plugins"].append(data.plugin.dict())
                return {"message": "Plugin added to user"}
    return {"message": "Global plugin managed"}

@router.delete("/plugins/delete")
def delete_plugin(index: int, payload = Depends(verify_token)):
    for user in users_db.values():
        if user["email"] == payload["email"]:
            if 0 <= index < len(user["plugins"]):
                del user["plugins"][index]
                return {"message": "Plugin deleted"}
            raise HTTPException(400, "Invalid index")
    raise HTTPException(404, "User not found")
