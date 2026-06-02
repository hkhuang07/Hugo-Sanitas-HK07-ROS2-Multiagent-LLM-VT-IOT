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
from contextlib import asynccontextmanager

from dotenv import load_dotenv
# Load environment variables
load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.agent_orchestrator_v2 import AgentOrchestratorV2
from arbitrator.arbitrator import Arbitrator
from memory.lance_memory import LanceMemory
from services.agent_log_client import start_log_client, stop_log_client

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

# ─── Global Orchestrator & Memory Setup ─────────────────────────────────────
memory = LanceMemory()
arbitrator = Arbitrator()
orchestrator = AgentOrchestratorV2(memory=memory, arbitrator=arbitrator)


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
    """Unified interaction endpoint utilizing Cognitive Orchestrator with Tool Calling"""
    message = body.get("message", "")
    if not message:
        return {"error": "message field is required"}
    
    # Retrieve current cached vitals to pass for orchestration context
    latest_vitals = orchestrator.medical_agent.latest_vitals
    
    # Run cognitive orchestrator with Tool Calling
    state = await orchestrator.route_and_execute(message, latest_vitals)
    
    # Compose response aggregating all agent outputs
    agent_responses = []
    for tool_name, output in state["outputs"].items():
        if tool_name != "_error":
            agent_responses.append({
                "agent": tool_name,
                "response": output
            })
    
    # Primary response: prefer medical findings if available
    primary_response = state["outputs"].get("analyze_clinical_symptoms", 
                       state["outputs"].get("speak_empathetic_response",
                       state["outputs"].get("search_medical_guidelines",
                       state["outputs"].get("fallback", "Unable to process"))))
    
    return {
        "agents_invoked": state["current_agents"],
        "primary_response": primary_response,
        "all_responses": agent_responses,
        "alert_level": state["alert_level"],
        "actions": state["actions"],
        "orchestration_note": state["raw_orchestration_response"]
    }


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
