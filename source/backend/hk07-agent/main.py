"""
HK-07 Multi-Agent Engine — FastAPI Entry Point

Architecture:
    Node-Router Multi-Agent graph flow using:
    - Supervisor/Router (router_agent.py)
    - Safety/Hardware Agent (safety_agent.py)
    - Medical Agent (medical_agent.py)
    - Empathetic Agent (empathetic_agent.py)
    Unified and coordinated by AgentOrchestrator.
"""

import asyncio
import logging
import os
import sys
import warnings
from contextlib import asynccontextmanager

# Suppress unavoidable third-party Pydantic model namespace warnings
warnings.filterwarnings("ignore", message='Field "model_name" has conflict with protected namespace "model_"')

from dotenv import load_dotenv
# Load environment variables
load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.agent_orchestrator import AgentOrchestrator
from arbitrator.arbitrator import Arbitrator
from memory.lance_memory import LanceMemory
from services.agent_log_client import start_log_client, stop_log_client
from services.blackboard_service import get_blackboard



# ─── Logging Configuration ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            "logs/hk07-agent.log", maxBytes=1_000_000, backupCount=2
        ) if os.path.exists("logs") else logging.NullHandler()
    ]
)
log = logging.getLogger("hk07.main")

# ─── Feature Flags ────────────────────────────────────────────────────────────
# Set USE_ORCHESTRATOR_V2=true in .env to enable parallel tool-calling router
USE_ORCHESTRATOR_V2 = os.getenv("USE_ORCHESTRATOR_V2", "true").lower() == "true"

if USE_ORCHESTRATOR_V2:
    from agents.agent_orchestrator_v2 import AgentOrchestratorV2
    log.info("[ENGINE] Feature flag USE_ORCHESTRATOR_V2=true — Cognitive Tool-Calling Router ACTIVE")

# ─── Global Orchestrator & Memory Setup ─────────────────────────────────────
memory = LanceMemory()
arbitrator = Arbitrator()
orchestrator = AgentOrchestrator(memory=memory, arbitrator=arbitrator)

# Orchestrator V2 (parallel tool-calling) — instantiated only when flag is on
orchestrator_v2 = AgentOrchestratorV2(memory=memory, arbitrator=arbitrator) if USE_ORCHESTRATOR_V2 else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown sequence for the agent engine"""
    log.info("+--------------------------------------------------+")
    log.info("|  HK-07 MULTI-AGENT ENGINE - STARTING             |")
    log.info("|  Architecture: Supervisor Node-Router Graph      |")
    log.info("|  MAS-STANDARD: ROUTER -> SAFETY/MED/EMP          |")
    log.info("+--------------------------------------------------+")

    # Initialize LanceDB memory
    await memory.initialize()
    
    # Start agent log client for REST logging
    await start_log_client()

    # Launch background loops for all agents + memory compaction
    agent_tasks = [
        asyncio.create_task(orchestrator.empathetic_agent.run_loop(), name="empathy-agent"),
        asyncio.create_task(orchestrator.medical_agent.run_loop(), name="medical-agent"),
        asyncio.create_task(orchestrator.safety_agent.run_loop(), name="safety-agent"),
        asyncio.create_task(memory.run_compaction_loop(), name="memory-compaction"),
    ]
    log.info("[ENGINE] All 3 agent tasks + memory compaction launched on event loop")

    yield  # App is running — serve API requests

    # Graceful shutdown: cancel agent loops
    log.info("[SHUTDOWN] Cancelling agent tasks...")
    for task in agent_tasks:
        task.cancel()
    await asyncio.gather(*agent_tasks, return_exceptions=True)

    # Volatile data wipe (security protocol — RAM data cleared on shutdown)
    log.info("[VOLATILE_WIPE] Clearing in-RAM conversation context...")
    orchestrator.empathetic_agent.clear_volatile_context()
    orchestrator.medical_agent.clear_volatile_context()
    orchestrator.safety_agent.clear_volatile_context()
    
    # Close client sessions
    await orchestrator.close()
    
    # Flush logs
    await stop_log_client()
    log.info("[SHUTDOWN] Engine stopped cleanly.")


# ─── FastAPI Application ─────────────────────────────────────────────────────
app = FastAPI(
    title="HK-07 Multi-Agent Engine",
    description="MiroFish Node-Router Multi-Agent AI system for HK-07 Robot",
    version="1.0.0-RC1",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8888"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health & Status Endpoints ───────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "engine": "MiroFish-MAS-Standard", "agents": 4}


@app.get("/agents/status")
async def agents_status():
    return {
        "router": "ACTIVE",
        "empathy": orchestrator.empathetic_agent.get_status(),
        "medical": orchestrator.medical_agent.get_status(),
        "safety": orchestrator.safety_agent.get_status(),
        "arbitrator": arbitrator.get_current_priority_agent(),
    }


@app.post("/api/v1/memory/sync_profile")
async def sync_profile(body: dict):
    """Sync medical profile baseline into LanceDB vector memory"""
    await memory.sync_medical_baseline(body)
    return {"status": "success", "message": "Medical baseline memory synced"}


@app.post("/agents/empathetic/interact")
async def empathetic_interact(body: dict):
    """Unified interaction endpoint utilizing Supervisor Router and Agent Orchestrator"""
    message = body.get("message", "")
    if not message:
        return {"error": "message field is required"}
    
    # Retrieve current cached vitals to pass for medical/routing context
    latest_vitals = orchestrator.medical_agent.latest_vitals
    
    # Run orchestrator routing and state processing based on V2 feature flag
    if USE_ORCHESTRATOR_V2 and orchestrator_v2 is not None:
        state = await orchestrator_v2.route_and_execute(message, latest_vitals)
    else:
        state = await orchestrator.route_and_execute(message, latest_vitals)
    
    return {
        "agent": state.get("current_agent", "EMPATHETIC_CHAT"),
        "response": state.get("output", ""),
        "alert_level": state.get("alert_level", "NORMAL"),
        "action": state.get("action", "COMPANION_CHAT")
    }


# ─── Orchestrator V2 Endpoint ─────────────────────────────────────────────────
@app.post("/api/v1/agents/v2/orchestrate")
async def orchestrate_v2(body: dict):
    """
    Cognitive Orchestrator V2 — Parallel Tool-Calling Router.
    Requires USE_ORCHESTRATOR_V2=true.
    Body: { "message": str, "vitals": dict (optional) }
    """
    if not USE_ORCHESTRATOR_V2 or orchestrator_v2 is None:
        return {"error": "Orchestrator V2 is disabled. Set USE_ORCHESTRATOR_V2=true in .env"}

    message = body.get("message", "")
    vitals  = body.get("vitals", {})
    if not message:
        return {"error": "message field is required"}

    try:
        state = await orchestrator_v2.route_and_execute(message, vitals)
        return {
            "orchestrator": "V2_TOOL_CALLING",
            "agent": state.get("current_agent"),
            "response": state.get("output"),
            "alert_level": state.get("alert_level"),
            "tools_invoked": state.get("tools_invoked", []),
            "provider": state.get("provider", "UNKNOWN"),
        }
    except Exception as exc:
        log.error("[V2_ORCHESTRATE] Error: %s", exc)
        return {"error": str(exc)}


# ─── Blackboard Inspect Endpoint ──────────────────────────────────────────────
@app.get("/api/v1/agents/blackboard/inspect")
async def blackboard_inspect():
    """
    Debug endpoint: inspect current Blackboard state.
    Returns latest clinical, emotional and context entries + backend stats.
    """
    bb = get_blackboard()
    stats = await bb.get_stats()

    clinical  = await bb.read_latest_clinical()
    emotional = await bb.read_latest_emotional()
    context   = await bb.read_latest_context()

    def _entry_to_dict(entry) -> dict:
        if entry is None:
            return None
        from dataclasses import asdict
        return asdict(entry)

    return {
        "backend": "redis" if bb._use_redis else "in_memory",
        "stats": stats,
        "latest_clinical":  _entry_to_dict(clinical),
        "latest_emotional": _entry_to_dict(emotional),
        "latest_context":   _entry_to_dict(context),
    }


# ─── Test Orchestrator Endpoint ───────────────────────────────────────────────
@app.post("/api/v1/agents/test/orchestrator")
async def test_orchestrator(body: dict):
    """
    Integration test endpoint: feed a synthetic message + vitals, get full
    orchestrator state back (useful for frontend demo of MoA behavior).
    Body: { "message": str, "vitals": dict (optional), "use_v2": bool }
    """
    message  = body.get("message", "Xin chào Hugo!")
    vitals   = body.get("vitals", {})
    use_v2   = body.get("use_v2", USE_ORCHESTRATOR_V2)

    if use_v2 and orchestrator_v2 is not None:
        state = await orchestrator_v2.route_and_execute(message, vitals)
        state["orchestrator_version"] = "V2"
    else:
        state = await orchestrator.route_and_execute(message, vitals)
        state["orchestrator_version"] = "V1"

    return state


if __name__ == "__main__":
    import logging.handlers
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8889,
        workers=1,
        loop="asyncio",
        log_level="info",
        access_log=False,
    )
