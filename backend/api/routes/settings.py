from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging

from infrastructure.repositories.sqlite_settings_repo import get_settings_repo
from config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class GroqKeyRequest(BaseModel):
    api_key: str


class GroqStatusResponse(BaseModel):
    configured: bool


@router.get("/groq-status", response_model=GroqStatusResponse)
async def get_groq_status():
    """Check if the Groq API key is configured (either in DB or env)."""
    repo = get_settings_repo()
    db_key = await repo.get_setting("groq_api_key")
    
    if db_key and db_key.strip():
        return GroqStatusResponse(configured=True)
    
    env_settings = get_settings()
    if env_settings.groq_api_key and env_settings.groq_api_key.strip():
        return GroqStatusResponse(configured=True)
        
    return GroqStatusResponse(configured=False)


@router.post("/groq-key")
async def save_groq_key(req: GroqKeyRequest):
    """Save the Groq API key to the database."""
    if not req.api_key or not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
        
    repo = get_settings_repo()
    try:
        await repo.set_setting("groq_api_key", req.api_key.strip(), category="llm")
        return {"status": "success", "message": "Groq API key saved successfully"}
    except Exception as e:
        logger.error(f"Failed to save Groq API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to save API key")
