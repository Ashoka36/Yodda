import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routes import auth, admin, payments, plugins, swarm, themes
from datetime import datetime
from config.database import users_db
from config.settings import NVIDIA_API_KEY, ADMIN_SETUP_DONE

app = FastAPI(title="YODDA Premium v3.0 COMPLETE", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

os.makedirs("builds", exist_ok=True)
app.mount("/builds", StaticFiles(directory="builds"), name="builds")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(payments.router)
app.include_router(plugins.router)
app.include_router(swarm.router)
app.include_router(themes.router)

@app.get("/")
def root():
    return {
        "message": "YODDA Premium v3.0 COMPLETE",
        "version": "3.0.0",
        "features": ["auth", "payments", "8_agents", "6_themes", "platforms", "plugins", "admin", "debug", "deployment"],
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "admin_setup": ADMIN_SETUP_DONE,
        "users": len(users_db),
        "timestamp": datetime.utcnow().isoformat(),
        "nvidia_ready": bool(NVIDIA_API_KEY and NVIDIA_API_KEY.startswith("nvapi-")),
    }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
