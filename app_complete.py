"""
YODDA Premium v3.0 COMPLETE - With Real Grok AI Integration
"""
import os
import uuid
import bcrypt
import jwt
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="YODDA Premium v3.0 COMPLETE", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount builds folder for serving generated files
os.makedirs("builds", exist_ok=True)
app.mount("/builds", StaticFiles(directory="builds"), name="builds")

# ==================== CONFIG ====================
SECRET_KEY = os.getenv("SECRET_KEY", "yodda-premium-secret-key-change-in-production")
GROK_API_KEY = os.getenv("GROK_API_KEY")  # Your key from Render env
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
ADMIN_SETUP_DONE = False

# ==================== DATABASE (In-Memory) ====================
users_db = {}
licenses_db = {}
agents_db = {
    "mcp": {"name": "MCP Master", "state": "IDLE", "tasks": 0},
    "planner": {"name": "Planner", "state": "IDLE", "tasks": 0},
    "developer": {"name": "Developer", "state": "IDLE", "tasks": 0},
    "pw": {"name": "P&W Orchestrator", "state": "IDLE", "tasks": 0},
    "watchdog": {"name": "Watchdog", "state": "IDLE", "tasks": 0},
    "debugger": {"name": "Debugger", "state": "IDLE", "tasks": 0},
    "deployer": {"name": "Deployer", "state": "IDLE", "tasks": 0},
    "coordinator": {"name": "Swarm Coordinator", "state": "IDLE", "tasks": 0}
}

PRICING_TIERS = {
    "FREE": {"price": 0, "builds": 1, "description": "1 build total"},
    "BASIC": {"price": 15, "builds": 20, "description": "20 builds/day"},
    "PRO": {"price": 50, "builds": 100, "description": "100 builds/day"},
    "ENTERPRISE": {"price": 199, "builds": -1, "description": "Unlimited"},
    "PREMIUM": {"price": 199, "builds": -1, "description": "Lifetime Unlimited", "lifetime": True}
}

GAMMA_THEMES = [
    {"id": "dark-pro", "name": "Dark Professional"},
    {"id": "light-modern", "name": "Light Modern"},
    {"id": "blue-enterprise", "name": "Blue Enterprise"},
    {"id": "vibrant-creative", "name": "Vibrant Creative"},
    {"id": "minimal-zen", "name": "Minimal Zen"},
    {"id": "aurora", "name": "Aurora Borealis"}
]

# ==================== MODELS ====================
class AdminSetup(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class BuildRequest(BaseModel):
    query: str
    platform: str = "web"
    theme: str = "dark-pro"

class PaymentRequest(BaseModel):
    tier: str
    lifetime: bool = False

# ==================== AUTH HELPERS ====================
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

def verify_token(token: str = Header(None)):
    if not token:
        raise HTTPException(401, "No token provided")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except:
        raise HTTPException(401, "Invalid token")

# ==================== GROK AI HELPER ====================
def call_grok(prompt: str):
    if not GROK_API_KEY:
        raise HTTPException(500, "GROK_API_KEY not configured")
    headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "grok-beta",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    response = requests.post(GROK_API_URL, headers=headers, json=data)
    if response.status_code != 200:
        raise HTTPException(500, f"Grok API error: {response.text}")
    return response.json()["choices"][0]["message"]["content"]

# ==================== ROUTES ====================

@app.get("/")
def root():
    return {
        "message": "YODDA Premium v3.0 COMPLETE",
        "version": "3.0.0",
        "features": ["auth", "payments", "8_agents", "6_themes", "5_platforms"],
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "admin_setup": ADMIN_SETUP_DONE,
        "users": len(users_db),
        "timestamp": datetime.utcnow().isoformat()
    }

# ==================== ADMIN ====================

@app.post("/admin/setup")
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
        "created": datetime.utcnow().isoformat()
    }
    
    ADMIN_SETUP_DONE = True
    token = create_token(data.email, is_admin=True)
    
    return {
        "message": "Admin created successfully",
        "token": token,
        "user": {"email": data.email, "is_admin": True}
    }

# ==================== AUTH ====================

@app.post("/auth/register")
def register(data: UserRegister):
    # Check if user exists
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
        "created": datetime.utcnow().isoformat()
    }
    
    # Generate FREE license
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

@app.post("/auth/login")
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

@app.get("/auth/me")
def get_current_user(payload = Depends(verify_token)):
    for user in users_db.values():
        if user["email"] == payload["email"]:
            return {
                "email": user["email"],
                "tier": user.get("tier", "FREE"),
                "is_admin": user.get("is_admin", False),
                "builds_used": user.get("builds_used", 0)
            }
    raise HTTPException(404, "User not found")

# ==================== PAYMENTS ====================

@app.get("/payments/tiers")
def get_tiers():
    return {"tiers": PRICING_TIERS}

@app.post("/payments/subscribe")
def subscribe(data: PaymentRequest, payload = Depends(verify_token)):
    tier = data.tier.upper()
    if tier not in PRICING_TIERS:
        raise HTTPException(400, "Invalid tier")
    
    # Find user and update tier
    for user in users_db.values():
        if user["email"] == payload["email"]:
            user["tier"] = tier
            user["builds_used"] = 0
            
            # Generate new license
            license_key = f"YP-{tier}-{uuid.uuid4().hex[:8].upper()}"
            licenses_db[license_key] = {
                "user_id": payload["email"],
                "tier": tier,
                "status": "active",
                "lifetime": data.lifetime
            }
            
            return {
                "message": f"Subscribed to {tier}",
                "tier": tier,
                "license_key": license_key,
                "price": PRICING_TIERS[tier]["price"]
            }
    
    raise HTTPException(404, "User not found")

@app.get("/payments/history")
def payment_history(payload = Depends(verify_token)):
    # Return user's licenses
    user_licenses = []
    for key, lic in licenses_db.items():
        if lic["user_id"] == payload["email"]:
            user_licenses.append({"license_key": key, **lic})
    return {"licenses": user_licenses}

# ==================== AGENTS ====================

@app.get("/api/v1/swarm/agents")
def list_agents():
    agents = []
    for agent_id, data in agents_db.items():
        agents.append({
            "id": agent_id,
            "name": data["name"],
            "state": data["state"],
            "completed_tasks": data["tasks"]
        })
    return {"agents": agents}

@app.post("/api/v1/swarm/orchestrate")
def orchestrate(request: dict, payload = Depends(verify_token)):
    query = request.get("query", "")
    if not query:
        raise HTTPException(400, "No query provided")
    
    # Check user tier limits
    for user in users_db.values():
        if user["email"] == payload["email"]:
            tier = user.get("tier", "FREE")
            builds_used = user.get("builds_used", 0)
            max_builds = PRICING_TIERS[tier]["builds"]
            
            if max_builds != -1 and builds_used >= max_builds:
                raise HTTPException(403, f"Build limit reached for {tier} tier")
            
            # Increment builds
            user["builds_used"] = builds_used + 1
            
            # Route to agents and generate with Grok
            agents_used = []
            generated_content = ""
            
            if any(word in query.lower() for word in ["code", "create", "build", "generate", "landing page"]):
                agents_used.append("Developer")
                agents_db["developer"]["tasks"] += 1
                prompt = f"Generate full HTML code for: {query}. Make it professional and complete."
                generated_content = call_grok(prompt)
            
            if any(word in query.lower() for word in ["deploy", "production"]):
                agents_used.append("Deployer")
                agents_db["deployer"]["tasks"] += 1
                # For deploy, could add more logic later
            
            if any(word in query.lower() for word in ["presentation", "slides"]):
                agents_used.append("P&W Orchestrator")
                agents_db["pw"]["tasks"] += 1
                prompt = f"Generate HTML for a presentation on: {query}."
                generated_content = call_grok(prompt)
            
            if not agents_used:
                agents_used = ["MCP Master"]
                agents_db["mcp"]["tasks"] += 1
                prompt = f"Respond to: {query} with generated content."
                generated_content = call_grok(prompt)
            
            # Save generated content to file
            build_id = uuid.uuid4().hex[:8]
            build_dir = f"builds/{build_id}"
            os.makedirs(build_dir, exist_ok=True)
            file_path = f"{build_dir}/index.html"
            with open(file_path, "w") as f:
                f.write(generated_content)
            
            # Build URL (adjust base to your Render URL in production)
            base_url = request.get("base_url", "http://localhost:8000")  # Frontend can pass, or hardcode
            generated_url = f"{base_url}/builds/{build_id}/index.html"
            
            return {
                "status": "success",
                "query": query,
                "response": "Build complete! Your project is ready.",
                "generated_url": generated_url,
                "agents_used": agents_used,
                "builds_remaining": max_builds - user["builds_used"] if max_builds != -1 else "unlimited"
            }
    
    raise HTTPException(404, "User not found")

# ==================== THEMES ====================

@app.get("/api/v1/pw/themes")
def get_themes():
    return {"themes": GAMMA_THEMES}

# ==================== BUILD ====================

@app.post("/build")
def build_project(data: BuildRequest, payload = Depends(verify_token)):
    return {
        "status": "building",
        "query": data.query,
        "platform": data.platform,
        "theme": data.theme,
        "message": "Build started - use /orchestrate for real generation"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)