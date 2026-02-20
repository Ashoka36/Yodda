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
