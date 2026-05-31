"""
HK-07 Multi-Agent Engine — FastAPI Entry Point

Architecture:
    3 Independent Agents running as async coroutines on Python event loop:
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
    │ EmpathicAgent   │  │ MedicalAgent    │  │ SafetyAgent (Tầng 0)│
    │ (Tầng 2 - Low)  │  │ (Tầng 1 - Mid)  │  │ HIGHEST PRIORITY    │
    └─────────────────┘  └─────────────────┘  └─────────────────────┘
              └──────────────────┬──────────────────────┘
                          [Arbitrator]
                       (Subsumption Logic)
                          [MQTT Publish]

Memory budget: 120MB total (fastapi + agents + lancedb batch)
Hardware: WSL2 Ubuntu 22.04 on Dell Latitude E7270 (i5-6300U, 8GB RAM)
"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.empathetic_agent import EmpathyAgent
from agents.medical_agent import MedicalAgent
from agents.safety_agent import SafetyAgent
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
        # File handler with 1MB size limit (hardware constraint)
        logging.handlers.RotatingFileHandler(
            "logs/hk07-agent.log", maxBytes=1_000_000, backupCount=2
        ) if os.path.exists("logs") else logging.NullHandler()
    ]
)
log = logging.getLogger("hk07.main")

# ─── Global Agent Instances ─────────────────────────────────────────────────
memory = LanceMemory()
arbitrator = Arbitrator()
empathy_agent = EmpathyAgent(memory=memory, arbitrator=arbitrator)
medical_agent = MedicalAgent(memory=memory, arbitrator=arbitrator)
safety_agent = SafetyAgent(arbitrator=arbitrator)   # Safety: no long-term memory needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown sequence for the agent engine"""
    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║  HK-07 MULTI-AGENT ENGINE — STARTING             ║")
    log.info("║  Agents: Empathetic | Medical | Safety           ║")
    log.info("║  Subsumption: Safety(0) > Medical(1) > Emp(2)    ║")
    log.info("╚══════════════════════════════════════════════════╝")

    # Initialize LanceDB memory (loads vector index from disk, ~50-100ms startup)
    await memory.initialize()
    
    # Start agent log client for REST logging
    await start_log_client()

    # Launch 3 agent event loops as concurrent async tasks
    agent_tasks = [
        asyncio.create_task(empathy_agent.run_loop(), name="empathy-agent"),
        asyncio.create_task(medical_agent.run_loop(), name="medical-agent"),
        asyncio.create_task(safety_agent.run_loop(), name="safety-agent"),
    ]
    log.info("[ENGINE] All 3 agent tasks launched on event loop")

    yield  # App is running — serve API requests

    # Graceful shutdown: cancel agent loops
    log.info("[SHUTDOWN] Cancelling agent tasks...")
    for task in agent_tasks:
        task.cancel()
    await asyncio.gather(*agent_tasks, return_exceptions=True)

    # Volatile data wipe (security protocol — RAM data cleared on shutdown)
    log.info("[VOLATILE_WIPE] Clearing in-RAM conversation context...")
    empathy_agent.clear_volatile_context()
    medical_agent.clear_volatile_context()
    
    # Flush logs
    await stop_log_client()
    log.info("[SHUTDOWN] Engine stopped cleanly.")


# ─── FastAPI Application ─────────────────────────────────────────────────────
app = FastAPI(
    title="HK-07 Multi-Agent Engine",
    description="MiroFish 3-Agent AI system for Hugo Sanitas HK-07 Robot Companion",
    version="1.0.0-ALPHA",
    lifespan=lifespan,
    docs_url="/docs",   # Swagger UI for development
    redoc_url=None,     # Disable Redoc to save memory
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
    return {"status": "ok", "engine": "MiroFish-v1", "agents": 3}


@app.get("/agents/status")
async def agents_status():
    return {
        "empathy": empathy_agent.get_status(),
        "medical": medical_agent.get_status(),
        "safety": safety_agent.get_status(),
        "arbitrator": arbitrator.get_current_priority_agent(),
    }


@app.post("/agents/empathetic/interact")
async def empathetic_interact(body: dict):
    """Direct text interaction with Empathetic Agent (for dashboard chat)"""
    message = body.get("message", "")
    if not message:
        return {"error": "message field is required"}
    response = await empathy_agent.process_text_interaction(message)
    return {"agent": "EMPATHETIC", "response": response}


if __name__ == "__main__":
    import logging.handlers
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8889,
        # Single worker — CPU constraint; async handles concurrency
        workers=1,
        loop="asyncio",
        log_level="info",
        access_log=False,   # Disable access logs to reduce I/O
    )
