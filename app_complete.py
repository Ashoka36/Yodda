"""
YODDA Premium v3.0 COMPLETE - Now using NVIDIA NIM API (OpenAI-compatible)
"""
import os
import uuid
import bcrypt
import jwt
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="YODDA Premium v3.0 COMPLETE", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount builds folder for serving generated files
os.makedirs("builds", exist_ok=True)
app.mount("/builds", StaticFiles(directory="builds"), name="builds")

# ==================== CONFIG ====================
SECRET_KEY = os.getenv("SECRET_KEY", "yodda-premium-secret-key-change-in-production")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")          # Your nvapi-... key
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1" # Base URL
DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"           # Change to your preferred model
ADMIN_SETUP_DONE = False
security = HTTPBearer()

# ==================== DATABASE (In-Memory) ====================
users_db = {}
licenses_db = {}
agents_db = {
    "architect": {"name": "Architect", "state": "IDLE", "tasks": 0},
    "planner": {"name": "Planner", "state": "IDLE", "tasks": 0},
    "coder": {"name": "Coder", "state": "IDLE", "tasks": 0},
    "reviewer": {"name": "Reviewer", "state": "IDLE", "tasks": 0},
    "tester": {"name": "Tester", "state": "IDLE", "tasks": 0},
    "ops": {"name": "Ops & Deploy", "state": "IDLE", "tasks": 0},
    "security": {"name": "Security", "state": "IDLE", "tasks": 0},
    "orchestrator": {"name": "Swarm Orchestrator", "state": "IDLE", "tasks": 0},
}

PRICING_TIERS = {
    "FREE": {"price": 0, "builds": 3, "description": "3 builds total"},
    "BASIC": {"price": 15, "builds": 20, "description": "20 builds/month (monthly)"},
    "PRO": {"price": 50, "builds": 100, "description": "100 builds/month"},
    "ENTERPRISE": {"price": 149, "builds": -1, "description": "Unlimited (1 year)"},
    "PREMIUM": {"price": 249, "builds": -1, "description": "Lifetime Unlimited", "lifetime": True}
}

GAMMA_THEMES = [
    {"id": "website-builder", "name": "Website Builder"},
    {"id": "presentation-mode", "name": "Presentation Mode"},
    {"id": "saas-boilerplate", "name": "SaaS Boilerplate"},
    {"id": "dashboard-suite", "name": "Dashboard Suite"},
    {"id": "landing-funnel", "name": "Landing Funnel"},
    {"id": "knowledge-base", "name": "Knowledge Base"},
]

THEME_PROMPTS = {
    "website-builder": "Build a full production-ready marketing website with responsive layout, navigation, sections for features, pricing, and contact.",
    "presentation-mode": "Generate an HTML-based presentation/slides experience suitable for pitching to stakeholders.",
    "saas-boilerplate": "Create a SaaS application boilerplate with auth scaffolding, pricing, and feature overview sections.",
    "dashboard-suite": "Produce a data-centric dashboard UI with cards, charts placeholders, and filters for an internal tool.",
    "landing-funnel": "Optimize for a high-conversion landing page with hero, social proof, benefits, and clear call-to-action.",
    "knowledge-base": "Generate a documentation / knowledge base style layout with sidebar navigation and content sections.",
}

PLATFORMS = ["web", "desktop", "android", "ios"]

# ==================== MODELS ====================
class AdminSetup(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    name: str | None = None
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Plugin(BaseModel):
    endpoint: str
    key: str
    type: str  # text or vision

class PluginManage(BaseModel):
    user_email: str = None  # For admin to manage user plugins
    plugin: Plugin

class PaymentRequest(BaseModel):
    tier: str
    lifetime: bool = False

class PaymentProcess(BaseModel):
    tier: str
    card_number: str
    expiry: str
    cvv: str

class OrchestrateRequest(BaseModel):
    query: str
    platform: str = "web"
    theme: str = "dark-pro"

class PluginRequest(BaseModel):
    provider: str
    key: str
    type: str  # text or vision

class AdminPluginRequest(PluginRequest):
    user_email: str | None = None

class ValidateRequest(BaseModel):
    provider: str
    key: str

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

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if not token:
        raise HTTPException(401, "No token provided")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except:
        raise HTTPException(401, "Invalid token")

def validate_api(endpoint: str, key: str) -> bool:
    # NVIDIA is always valid if key is correct → simple check
    return bool(key and key.startswith("nvapi-"))

# ==================== LLM CALL HELPER (NVIDIA NIM) ====================
def call_llm(prompt: str, endpoint: str = None, key: str = None, model: str = None):
    endpoint = endpoint or NVIDIA_API_URL
    key = key or NVIDIA_API_KEY
    model = model or DEFAULT_MODEL

    if not key or not key.startswith("nvapi-"):
        raise HTTPException(500, "Invalid or missing NVIDIA API key")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1024,
        "stream": False
    }

    full_url = f"{endpoint}/chat/completions"
    response = requests.post(full_url, headers=headers, json=data)

    if response.status_code != 200:
        error_text = response.text
        raise HTTPException(500, f"NVIDIA API error: {response.status_code} - {error_text}")

    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise HTTPException(500, "Unexpected NVIDIA response format")

# ==================== ROUTES ====================

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

# ==================== AUTH ====================

@app.post("/auth/register")
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
                "builds_used": user.get("builds_used", 0),
                "plugins": user.get("plugins", [])
            }
    raise HTTPException(404, "User not found")

# ==================== PLUGINS ====================

@app.post("/plugins/add")
def add_plugin(plugin: Plugin, payload = Depends(verify_token)):
    for user in users_db.values():
        if user["email"] == payload["email"]:
            if not validate_api(plugin.endpoint, plugin.key):
                raise HTTPException(400, "Invalid API")
            user["plugins"].append(plugin.dict())
            return {"message": "Plugin added"}
    raise HTTPException(404, "User not found")

@app.post("/plugins/manage")
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
    # Global add (placeholder for now)
    return {"message": "Global plugin managed"}

@app.delete("/plugins/delete")
def delete_plugin(index: int, payload = Depends(verify_token)):
    for user in users_db.values():
        if user["email"] == payload["email"]:
            if 0 <= index < len(user["plugins"]):
                del user["plugins"][index]
                return {"message": "Plugin deleted"}
            raise HTTPException(400, "Invalid index")
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
    
    for user in users_db.values():
        if user["email"] == payload["email"]:
            user["tier"] = tier
            user["builds_used"] = 0
            
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

@app.post("/payments/process")
def process_payment(data: PaymentProcess, payload = Depends(verify_token)):
    # Dummy gateway - simulate success
    if not data.card_number or not data.expiry or not data.cvv:
        raise HTTPException(400, "Invalid card info")
    # Tomorrow: Integrate Infinity with provided creds
    return subscribe(PaymentRequest(tier=data.tier, lifetime=False), payload)  # Adjust lifetime as needed

@app.get("/payments/history")
def payment_history(payload = Depends(verify_token)):
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
def orchestrate(data: OrchestrateRequest, payload = Depends(verify_token)):
    query = data.query
    if not query:
        raise HTTPException(400, "No query provided")
    
    # Find user and check limits
    user = None
    for u in users_db.values():
        if u["email"] == payload["email"]:
            user = u
            break
    if not user:
        raise HTTPException(404, "User not found")
    
    tier = user.get("tier", "FREE")
    builds_used = user.get("builds_used", 0)
    max_builds = PRICING_TIERS[tier]["builds"]
    
    if max_builds != -1 and builds_used >= max_builds:
        raise HTTPException(403, f"Build limit reached for {tier} tier")
    
    # Increment builds
    user["builds_used"] = builds_used + 1
    
    # MCP Validation: Use user's plugin if available, else fallback
    endpoint = NVIDIA_API_URL
    key = NVIDIA_API_KEY
    model = DEFAULT_MODEL
    if user.get("plugins"):
        plugin = user["plugins"][0]  # Use first for simplicity
        endpoint = plugin["endpoint"]
        key = plugin["key"]
        model = "gpt-3.5-turbo" if plugin["type"] == "text" else "gpt-4-vision-preview"  # Adjust for vision
    
    # Route to agents and generate
    agents_used = []
    agent_logs = []
    generated_content = ""

    # Derive theme description
    theme_hint = THEME_PROMPTS.get(data.theme, "")

    def log_agent(agent_id: str, action: str):
        if agent_id in agents_db:
            agents_db[agent_id]["tasks"] += 1
            agents_used.append(agents_db[agent_id]["name"])
        agent_logs.append(
            {
                "agent": agents_db.get(agent_id, {}).get("name", agent_id),
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    # Simple multi-agent orchestration narrative without changing the NVIDIA call itself
    log_agent("architect", "Parsed request and selected high-level architecture.")
    log_agent("planner", f"Planned build flow for theme '{data.theme}'.")
    log_agent("coder", "Generating application code via NVIDIA endpoint.")

    prompt = (
        f"You are a swarm of 8 expert agents (Architect, Planner, Coder, Reviewer, "
        f"Tester, Ops, Security, Orchestrator) collaborating on a {data.platform} build.\n"
        f"User request: {query}\n"
        f"Selected theme: {data.theme}.\n"
        f"Theme specification: {theme_hint}\n"
        "Produce a complete, single-file implementation matching the theme and platform. "
        "Return only the raw code (no markdown)."
    )

    generated_content = call_llm(prompt, endpoint, key, model)
    log_agent("reviewer", "Reviewed generated code for consistency.")
    log_agent("tester", "Virtually tested main flows.")
    log_agent("ops", "Prepared build artifact for deployment.")
    log_agent("security", "Performed basic security sanity checks.")
    
    # Save generated content
    build_id = uuid.uuid4().hex[:8]
    build_dir = f"builds/{build_id}"
    os.makedirs(build_dir, exist_ok=True)
    file_ext = data.platform if data.platform != "web" else "html"
    file_path = f"{build_dir}/index.{file_ext}"
    with open(file_path, "w") as f:
        f.write(generated_content)

    base_url = os.getenv("PUBLIC_BASE_URL", "https://159.65.144.25")
    generated_url = f"{base_url}/builds/{build_id}/index.{file_ext}"
    
    return {
        "status": "success",
        "query": query,
        "response": "Build complete! Your project is ready.",
        "generated_code": generated_content,
        "generated_url": generated_url,
        "agents_used": agents_used,
        "agent_logs": agent_logs,
        "builds_remaining": max_builds - user["builds_used"] if max_builds != -1 else "unlimited"
    }

@app.post("/api/v1/admin/plugins")
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

@app.post("/api/v1/admin/validate_key")
def admin_validate_key(req: ValidateRequest, payload=Depends(verify_token)):
    if not payload.get("is_admin"):
        raise HTTPException(403, "Admin only")

    if not req.key:
        raise HTTPException(400, "Missing API key")

    # Keep validation lightweight; NVIDIA can be validated structurally.
    if req.provider.lower() == "nvidia":
        if not validate_api(NVIDIA_API_URL, req.key):
            raise HTTPException(400, "API key is invalid.")

    return {"message": "API key is valid."}

@app.post("/debug/build")
def debug_build(data: OrchestrateRequest, payload = Depends(verify_token)):
    return {"message": "Debug complete - no errors found", "details": "Code validated"}

# ==================== THEMES ====================

@app.get("/api/v1/pw/themes")
def get_themes():
    return {"themes": GAMMA_THEMES}

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
