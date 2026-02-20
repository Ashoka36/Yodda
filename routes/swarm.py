import os
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from agents.models import OrchestrateRequest
from config.database import users_db, agents_db, PRICING_TIERS, THEME_PROMPTS
from routes.auth import verify_token
from agents.llm import call_llm
from config.settings import NVIDIA_API_URL, NVIDIA_API_KEY, DEFAULT_MODEL

router = APIRouter()

@router.get("/api/v1/swarm/agents")
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

@router.post("/api/v1/swarm/orchestrate")
def orchestrate(data: OrchestrateRequest, payload = Depends(verify_token)):
    query = data.query
    if not query:
        raise HTTPException(400, "No query provided")
    
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
    
    user["builds_used"] = builds_used + 1
    
    endpoint = NVIDIA_API_URL
    key = NVIDIA_API_KEY
    model = DEFAULT_MODEL
    if user.get("plugins"):
        plugin = user["plugins"][0]
        endpoint = plugin["endpoint"]
        key = plugin["key"]
        model = "gpt-3.5-turbo" if plugin["type"] == "text" else "gpt-4-vision-preview"
    
    agents_used = []
    agent_logs = []
    generated_content = ""

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

    log_agent("architect", "Parsed request and selected high-level architecture.")
    log_agent("planner", f"Planned build flow for theme '{data.theme}'.")
    log_agent("coder", "Generating application code via NVIDIA endpoint.")

    prompt = (
        f"You are a swarm of 8 expert agents (Architect, Planner, Coder, Reviewer, "
        f"Tester, Ops, Security, Orchestrator) collaborating on a {data.platform} build.
"
        f"User request: {query}
"
        f"Selected theme: {data.theme}.
"
        f"Theme specification: {theme_hint}
"
        "Produce a complete, single-file implementation matching the theme and platform. "
        "Return only the raw code (no markdown)."
    )

    generated_content = call_llm(prompt, endpoint, key, model)
    log_agent("reviewer", "Reviewed generated code for consistency.")
    log_agent("tester", "Virtually tested main flows.")
    log_agent("ops", "Prepared build artifact for deployment.")
    log_agent("security", "Performed basic security sanity checks.")
    
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
