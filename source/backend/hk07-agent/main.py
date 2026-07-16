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

# Suppress TensorFlow oneDNN custom operations messages and logs before other packages import
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

# Prevent UnicodeEncodeError on Windows CP1252/other non-UTF-8 console encodings
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

warnings.filterwarnings("ignore", message='Field "model_name" has conflict with protected namespace "model_"')
warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize Config (WSL Routing & Env load)
import core.config

# Import State to initialize globals early
import core.state

from core.background import (
    initialize_memory_background,
    run_network_ingestion_worker,
    run_subsumption_safety_worker,
    start_isolated_heartbeat_thread,
    run_headless_camera_daemon,
    run_headless_vitals_daemon,
    run_auto_perception_scan_loop
)
from services.sensor_mqtt_client import init_mqtt_client, close_mqtt_client
from services.rosbridge_client import rosbridge_client_loop
from services.agent_log_client import start_log_client, stop_log_client
from utils.spatial_tracker import SpatialTrackerThread

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("[STARTUP] Initializing HK-07 Core System...")
    
    # 1. Start Log Client
    await start_log_client()

    # 2. MQTT and ROS Bridge
    init_mqtt_client()
    loop = asyncio.get_event_loop()
    loop.create_task(rosbridge_client_loop())

    # 3. Memory & Workers
    loop.create_task(initialize_memory_background())
    network_task = loop.create_task(run_network_ingestion_worker())
    safety_task = loop.create_task(run_subsumption_safety_worker())
    camera_daemon_task = loop.create_task(run_headless_camera_daemon())
    vitals_daemon_task = loop.create_task(run_headless_vitals_daemon())
    perception_task = loop.create_task(run_auto_perception_scan_loop())
    
    start_isolated_heartbeat_thread()

    # 4. Spatial Tracker Thread
    from core.state import camera_worker
    spatial_tracker = SpatialTrackerThread(camera_worker=camera_worker)
    spatial_tracker.start()

    yield

    log.info("[SHUTDOWN] Terminating system...")
    close_mqtt_client()
    spatial_tracker.stop()
    await stop_log_client()

app = FastAPI(
    title="HK-07 Orchestration Core",
    description="Multi-Agent System for HK-07 Robotic Companion",
    version="2.5.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Include API Routers ──────────────────────────────────────────────────────
from api.routes import system, sensors, agents, fhir, stream  # Phase B: SSE stream router

app.include_router(system.router)
app.include_router(sensors.router)
app.include_router(agents.router)
app.include_router(fhir.router)
app.include_router(stream.router)  # Phase B: Real-time agent event SSE stream

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("AGENT_PORT", os.getenv("PORT", 8889)))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, ws_max_size=104857600)
