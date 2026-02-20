import uuid
from fastapi import APIRouter, HTTPException, Depends
from agents.models import PaymentRequest, PaymentProcess
from config.database import users_db, licenses_db, PRICING_TIERS
from routes.auth import verify_token

router = APIRouter()

@router.get("/payments/tiers")
def get_tiers():
    return {"tiers": PRICING_TIERS}

@router.post("/payments/subscribe")
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

@router.post("/payments/process")
def process_payment(data: PaymentProcess, payload = Depends(verify_token)):
    if not data.card_number or not data.expiry or not data.cvv:
        raise HTTPException(400, "Invalid card info")
    return subscribe(PaymentRequest(tier=data.tier, lifetime=False), payload)

@router.get("/payments/history")
def payment_history(payload = Depends(verify_token)):
    user_licenses = []
    for key, lic in licenses_db.items():
        if lic["user_id"] == payload["email"]:
            user_licenses.append({"license_key": key, **lic})
    return {"licenses": user_licenses}
