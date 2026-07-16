from fastapi import APIRouter, Response
import time
import psutil
from services.blackboard_service import get_blackboard
from core.state import orchestrator

router = APIRouter()
# TODO: Replace @router. with @router.

@router.get("/health")
async def health():
    return {"status": "ok", "engine": "MiroFish-MAS-Standard", "agents": 4}

@router.get("/api/v1/health/llm-stats")
async def llm_stats():
    from services.llm_client import get_llm_stats
    return get_llm_stats()

@router.get("/agents/status")
async def agents_status():
    return {
        "router": "ACTIVE",
        "empathy": orchestrator.empathetic_agent.get_status(),
        "medical": orchestrator.medical_agent.get_status(),
        "safety": orchestrator.safety_agent.get_status(),
        "arbitrator": arbitrator.get_current_priority_agent(),
    }

