from fastapi import APIRouter
from config.database import GAMMA_THEMES

router = APIRouter()

@router.get("/api/v1/pw/themes")
def get_themes():
    return {"themes": GAMMA_THEMES}
