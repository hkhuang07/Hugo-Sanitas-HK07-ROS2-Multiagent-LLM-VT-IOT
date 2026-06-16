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
# Prevent UnicodeEncodeError on Windows CP1252/other non-UTF-8 console encodings
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import warnings
from contextlib import asynccontextmanager

# Suppress unavoidable third-party Pydantic model namespace warnings
warnings.filterwarnings("ignore", message='Field "model_name" has conflict with protected namespace "model_"')

from dotenv import load_dotenv
# Load environment variables
load_dotenv()

import socket
import struct

def load_env_file():
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        checks = [
            os.path.join(curr_dir, ".env"),
            os.path.join(curr_dir, "backend", ".env"),
            os.path.join(curr_dir, "source", "backend", ".env"),
            os.path.join(curr_dir, "hk07-agent", ".env"),
        ]
        for path in checks:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if "=" in line:
                                key, val = line.split("=", 1)
                                key = key.strip()
                                val = val.strip().strip('"').strip("'")
                                if key:
                                    os.environ[key] = val
                    return
                except Exception:
                    pass
        parent = os.path.dirname(curr_dir)
        if parent == curr_dir:
            break
        curr_dir = parent

def get_default_gateway_ip() -> str:
    try:
        # Standard Linux/WSL2 routing table evaluation
        with open("/proc/net/route") as fh:
            for line in fh:
                fields = line.strip().split()
                if len(fields) > 2 and fields[1] == "00000000":
                    return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    except Exception:
        pass
    return "127.0.0.1"

async def run_network_ingestion_worker():
    """
    Background worker parsing local .env modifications and validating gateway IP every 5.0 seconds.
    """
    log.info("[NETWORK_WORKER] Network Ingestion worker started.")
    while True:
        try:
            load_env_file()
            gateway_ip = get_default_gateway_ip()
            os.environ["DEFAULT_GATEWAY"] = gateway_ip
            
            bb = get_blackboard()
            await bb.write_value("system:network:gateway", gateway_ip)
            await bb.write_value("system:network:status", "ONLINE" if gateway_ip != "127.0.0.1" else "LOCAL_LOOPBACK")
            
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"[NETWORK_WORKER] Error: {e}")
            await asyncio.sleep(5.0)

import uvicorn
import fastapi
from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware

from agents.agent_orchestrator import AgentOrchestrator
from agents.perception_agent import PerceptionAgent
from arbitrator.arbitrator import Arbitrator
from memory.lance_memory import LanceMemory
from services.agent_log_client import start_log_client, stop_log_client
from services.blackboard_service import get_blackboard, current_user_id, current_auth_token
from services.sensor_fusion_buffer import get_fusion_buffer, VitalsSample, CameraFrame



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
from services.knowledge_ingestion import KnowledgeIngestionService
ingestion_service = KnowledgeIngestionService(memory)
arbitrator = Arbitrator()
orchestrator = AgentOrchestrator(memory=memory, arbitrator=arbitrator)

# Orchestrator V2 (parallel tool-calling) — instantiated only when flag is on
orchestrator_v2 = AgentOrchestratorV2(memory=memory, arbitrator=arbitrator) if USE_ORCHESTRATOR_V2 else None

# Perception Agent (Tier 0.5) — on-demand scan, no background loop
perception_agent = PerceptionAgent(arbitrator=arbitrator)

_safety_tripped = False

async def run_subsumption_safety_worker():
    """
    Background worker mimicking Tầng 0 (Safety Logic).
    Monitors camera vision state via Blackboard clinical data and trips when critical.
    """
    global _safety_tripped
    import time
    import json
    log.info("[SAFETY_WORKER] Subsumption Safety Worker started.")
    
    # Wait for app startup
    await asyncio.sleep(2.0)
    
    while True:
        try:
            bb = get_blackboard()
            clinical = await bb.read_value("sensor:perception:clinical")
            trip = False
            reason = ""
            
            if clinical:
                facial_distress = clinical.get("facial_distress", {})
                env_hazards = clinical.get("environmental_hazards", {})
                visible_injuries = clinical.get("visible_injuries", {})
                
                # Check for critical/warning threats detected in vision
                if facial_distress.get("detected"):
                    trip = True
                    reason = f"Vision Safety Alert: Facial distress detected ({facial_distress.get('details')})"
                elif env_hazards.get("detected"):
                    trip = True
                    reason = f"Vision Safety Alert: Environmental hazard detected ({env_hazards.get('details')})"
                elif visible_injuries.get("detected"):
                    trip = True
                    reason = f"Vision Safety Alert: Visible injuries detected ({visible_injuries.get('details')})"
            else:
                if not hasattr(run_subsumption_safety_worker, "_logged_absent"):
                    log.info("[SAFETY_GUARDS] Awaiting IPWebcam clinical vision telemetry stream...")
                    run_subsumption_safety_worker._logged_absent = True
                    
            if trip:
                _safety_tripped = True
                arbitrator.inhibit("EMPATHETIC", duration_s=10)
                arbitrator.inhibit("MEDICAL", duration_s=10)
                
                # Write direct safety trip state to Blackboard
                try:
                    await bb.write_value("safety:tripped", True)
                    await bb.write_value("safety:reason", reason)
                except Exception as bb_err:
                    log.error(f"[SAFETY_WORKER] Blackboard write failed: {bb_err}")
                
                log.warning(f"[SAFETY_WORKER] TRIP: {reason}. Empathy and Medical streams overridden.")
            else:
                _safety_tripped = False
                try:
                    await bb.write_value("safety:tripped", False)
                except Exception:
                    pass
                
            await asyncio.sleep(0.5) # 2Hz loop
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"[SAFETY_WORKER] Error: {e}")
            await asyncio.sleep(1.0)


def start_isolated_heartbeat_thread():
    import threading
    import websockets
    import json
    import time

    def thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def isolated_heartbeat_loop():
            uri = "ws://localhost:9090"
            backoff = 1.0
            while True:
                try:
                    log.info(f"[ISOLATED_HEARTBEAT] Connecting to {uri}...")
                    async with websockets.connect(uri) as websocket:
                        log.info("[ISOLATED_HEARTBEAT] Connected to Rosbridge. Starting pulse check transmission.")
                        
                        # Advertise heartbeat topic type to Rosbridge
                        adv_msg = {
                            "op": "advertise",
                            "topic": "/system/heartbeat",
                            "type": "std_msgs/msg/Header"
                        }
                        await websocket.send(json.dumps(adv_msg))
                        
                        backoff = 1.0
                        while True:
                            t = time.time()
                            sec = int(t)
                            nanosec = int((t - sec) * 1e9)
                            msg = {
                                "op": "publish",
                                "topic": "/system/heartbeat",
                                "msg": {
                                    "stamp": {
                                        "sec": sec,
                                        "nanosec": nanosec
                                    },
                                    "frame_id": "system"
                                }
                            }
                            await websocket.send(json.dumps(msg))
                            await asyncio.sleep(1.0)
                except Exception as e:
                    log.error(f"[ISOLATED_HEARTBEAT_ERROR] Error in heartbeat loop: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, 30.0)

        loop.run_until_complete(isolated_heartbeat_loop())

    t = threading.Thread(target=thread_target, name="isolated-heartbeat-thread", daemon=True)
    t.start()


async def rosbridge_client_loop():
    import websockets
    import json
    import base64
    import struct
    import math
    from services.sensor_fusion_buffer import get_fusion_buffer, VitalsSample
    from services.blackboard_service import get_blackboard

    uri = "ws://localhost:9090"
    backoff = 1.0
    
    while True:
        try:
            log.info(f"[ROSBRIDGE_CLIENT] Connecting to {uri}...")
            async with websockets.connect(uri) as websocket:
                log.info("[ROSBRIDGE_CLIENT] Connected to rosbridge_suite.")
                backoff = 1.0
                
                # Subscribe to topics
                subscribe_topics = [
                    {"topic": "/telemetry/sensors/vitals", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/sensors/camera/thermal_rppg", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/vitals/wristband", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/imu", "type": "sensor_msgs/msg/Imu"},
                    {"topic": "/hk07/perception/clinical", "type": "std_msgs/msg/String"}
                ]
                for sub in subscribe_topics:
                    req = {
                        "op": "subscribe",
                        "topic": sub["topic"],
                        "type": sub["type"]
                    }
                    await websocket.send(json.dumps(req))
                
                async for message in websocket:
                    data = json.loads(message)
                    op = data.get("op")
                    if op == "publish":
                        topic = data.get("topic")
                        msg = data.get("msg", {})
                        
                        fusion_buf = get_fusion_buffer()
                        bb = get_blackboard()
                        
                        if topic == "/telemetry/sensors/vitals":
                            pos = msg.get("position", [])
                            if len(pos) >= 5:
                                sample = VitalsSample(
                                    heart_rate=float(pos[0]),
                                    spo2=float(pos[1]),
                                    body_temperature=float(pos[2]),
                                    step_count=0,
                                    alert_level="NORMAL"
                                )
                                await fusion_buf.push_vitals(sample)
                                
                        elif topic == "/sensors/camera/thermal_rppg":
                            pos = msg.get("position", [])
                            if len(pos) >= 2:
                                latest = await fusion_buf.latest_vitals()
                                sample = VitalsSample(
                                    heart_rate=float(pos[0]) if pos[0] > 0 else (latest.heart_rate if latest else 72.0),
                                    spo2=latest.spo2 if latest else 98.0,
                                    body_temperature=float(pos[1]) if pos[1] > 0 else (latest.body_temperature if latest else 36.6),
                                    alert_level="CRITICAL" if (len(pos) >= 3 and pos[2] > 0) else "NORMAL"
                                )
                                await fusion_buf.push_vitals(sample)
                                await bb.write_value("sensor:camera:fever_alert", bool(len(pos) >= 3 and pos[2] > 0))
                                
                        elif topic == "/vitals/wristband":
                            pos = msg.get("position", [])
                            if len(pos) >= 2:
                                is_falling = bool(pos[0])
                                emergency = bool(pos[1])
                                await bb.write_value("sensor:vitals:is_falling", is_falling)
                                await bb.write_value("sensor:vitals:emergency", emergency)
                            if len(pos) >= 41:
                                await bb.write_value("sensor:vitals:wrist_motion_magnitude", float(pos[40]))
                                
                        elif topic == "/telemetry/imu":
                            orientation = msg.get("orientation", {})
                            accel = msg.get("linear_acceleration", {})
                            gyro = msg.get("angular_velocity", {})
                            
                            ax = accel.get("x", 0.0)
                            ay = accel.get("y", 0.0)
                            az = accel.get("z", 9.81)
                            g_mag = (ax**2 + ay**2 + az**2) ** 0.5
                            
                            wrist_motion_mag = 0.0
                            try:
                                wrist_motion_mag = await bb.read_value("sensor:vitals:wrist_motion_magnitude") or 0.0
                            except Exception:
                                pass
                                
                            imu_data = {
                                "accel_x": ax,
                                "accel_y": ay,
                                "accel_z": az,
                                "gyro_x": gyro.get("x", 0.0),
                                "gyro_y": gyro.get("y", 0.0),
                                "gyro_z": gyro.get("z", 0.0),
                                "qw": orientation.get("w", 1.0),
                                "qx": orientation.get("x", 0.0),
                                "qy": orientation.get("y", 0.0),
                                "qz": orientation.get("z", 0.0),
                                "frame_id": msg.get("header", {}).get("frame_id", ""),
                                "wrist_motion_magnitude": wrist_motion_mag,
                                "g_magnitude": g_mag
                            }
                            await bb.write_value("sensor:imu:latest", imu_data)
                            

                            
                        elif topic == "/hk07/perception/clinical":
                            try:
                                clinical_data = json.loads(msg.get("data", "{}"))
                                await bb.write_value("sensor:perception:clinical", clinical_data)
                            except Exception:
                                pass
                                
        except Exception as e:
            log.error(f"[ROSBRIDGE_CLIENT_ERROR] Connection error: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown sequence for the agent engine"""
    log.info("+--------------------------------------------------+")
    log.info("|  HK-07 MULTI-AGENT ENGINE - STARTING             |")
    log.info("|  Architecture: Supervisor Node-Router Graph      |")
    log.info("|  MAS-STANDARD: ROUTER -> SAFETY/MED/EMP          |")
    log.info("+--------------------------------------------------+")

    # Active network config initialization directly in primary startup hook
    load_env_file()
    gateway_ip = get_default_gateway_ip()
    os.environ["DEFAULT_GATEWAY"] = gateway_ip
    log.info("[STARTUP] Materialized network config. Default Gateway: %s", gateway_ip)

    # Initialize LanceDB memory
    await memory.initialize()
    
    # Start agent log client for REST logging
    await start_log_client()

    # Launch background loops for all agents + memory compaction + rosbridge client + network worker
    active_orch = orchestrator_v2 if (USE_ORCHESTRATOR_V2 and orchestrator_v2) else orchestrator
    agent_tasks = [
        asyncio.create_task(active_orch.empathetic_agent.run_loop(), name="empathy-agent"),
        asyncio.create_task(active_orch.medical_agent.run_loop(), name="medical-agent"),
        asyncio.create_task(active_orch.safety_agent.run_loop(), name="safety-agent"),
        asyncio.create_task(memory.run_compaction_loop(), name="memory-compaction"),
        asyncio.create_task(run_subsumption_safety_worker(), name="subsumption-safety-worker"),
        asyncio.create_task(rosbridge_client_loop(), name="rosbridge-client"),
        asyncio.create_task(run_network_ingestion_worker(), name="network-ingestion-worker"),
    ]
    # Start isolated heartbeat background thread
    start_isolated_heartbeat_thread()
    log.info("[ENGINE] Dedicated isolated heartbeat thread started.")

    log.info("[ENGINE] All agent tasks + memory compaction + safety worker + rosbridge client launched on event loop")

    yield  # App is running — serve API requests

    # Graceful shutdown: cancel agent loops
    log.info("[SHUTDOWN] Cancelling agent tasks...")
    for task in agent_tasks:
        task.cancel()
    await asyncio.gather(*agent_tasks, return_exceptions=True)

    # Volatile data wipe (security protocol — RAM data cleared on shutdown)
    log.info("[VOLATILE_WIPE] Clearing in-RAM conversation context...")
    active_orch.empathetic_agent.clear_volatile_context()
    active_orch.medical_agent.clear_volatile_context()
    active_orch.safety_agent.clear_volatile_context()
    if active_orch is orchestrator_v2:
        orchestrator.empathetic_agent.clear_volatile_context()
        orchestrator.medical_agent.clear_volatile_context()
        orchestrator.safety_agent.clear_volatile_context()
    
    # Close client sessions
    await active_orch.close()
    if active_orch is orchestrator_v2:
        await orchestrator.close()
    
    # Flush logs
    await stop_log_client()
    log.info("[SHUTDOWN] Engine stopped cleanly.")


# ─── FastAPI Application ─────────────────────────────────────────────────────
app = FastAPI(
    title="HK-07 Multi-Agent Engine (Phase 2)",
    description="Baymax Cognitive Multi-Agent system — Blackboard + Orchestrator V2 + Perception Agent",
    version="2.0.0-phase2",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
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


@app.post("/api/v1/admin/ingest")
async def admin_ingest(body: dict):
    """
    Scrape and ingest guidelines from allowlisted URL.
    Body: { "url": str }
    """
    url = body.get("url", "")
    if not url:
        return {"status": "error", "message": "url field is required"}
    
    result = await ingestion_service.ingest_url(url)
    return result


@app.post("/agents/empathetic/interact")
async def empathetic_interact(body: dict, authorization: str = fastapi.Header(None)):
    """Unified interaction endpoint utilizing Supervisor Router and Agent Orchestrator"""
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)

    if _safety_tripped:
        return {
            "agent": "SAFETY",
            "response": "[SAFETY_ALERT]: Critical obstacle detected or sensor failure. Action inhibited.",
            "alert_level": "CRITICAL",
            "action": "SAFE_HOLD"
        }

    message = body.get("message", "")
    if not message:
        return {"error": "message field is required"}
    
    user_id = body.get("userId", "a0000000-0000-0000-0000-000000000001")
    current_user_id.set(user_id)
    
    # Retrieve current cached vitals to pass for medical/routing context
    latest_vitals = orchestrator.medical_agent.latest_vitals
    
    # Run orchestrator routing and state processing based on V2 feature flag
    if USE_ORCHESTRATOR_V2 and orchestrator_v2 is not None:
        state = await orchestrator_v2.route_and_execute(message, latest_vitals, user_id=user_id)
    else:
        state = await orchestrator.route_and_execute(message, latest_vitals, user_id=user_id)
    
    return {
        "agent": state.get("current_agent", "EMPATHETIC_CHAT"),
        "response": state.get("output", ""),
        "alert_level": state.get("alert_level", "NORMAL"),
        "action": state.get("action", "COMPANION_CHAT")
    }


# ─── Orchestrator V2 Endpoint ─────────────────────────────────────────────────
@app.post("/api/v1/agents/v2/orchestrate")
async def orchestrate_v2(body: dict, authorization: str = fastapi.Header(None)):
    """
    Cognitive Orchestrator V2 — Parallel Tool-Calling Router.
    Requires USE_ORCHESTRATOR_V2=true.
    Body: { "message": str, "vitals": dict (optional) }
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)

    if _safety_tripped:
        return {
            "orchestrator": "V2_TOOL_CALLING",
            "agent": "SAFETY",
            "response": "[SAFETY_ALERT]: Critical obstacle detected or sensor failure. Action inhibited.",
            "alert_level": "CRITICAL",
            "tools_invoked": [],
            "provider": "SAFETY_WORKER"
        }

    if not USE_ORCHESTRATOR_V2 or orchestrator_v2 is None:
        return {"error": "Orchestrator V2 is disabled. Set USE_ORCHESTRATOR_V2=true in .env"}

    message = body.get("message", "")
    vitals  = body.get("vitals", {})
    user_id = body.get("userId", "a0000000-0000-0000-0000-000000000001")
    current_user_id.set(user_id)
    
    if not message:
        return {"error": "message field is required"}

    try:
        state = await orchestrator_v2.route_and_execute(message, vitals, user_id=user_id)
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


# ─── Action Plan Endpoints (Phase 5) ──────────────────────────────────────────
@app.get("/api/v1/agents/action/plan/latest")
async def get_latest_action_plan(userId: str = "a0000000-0000-0000-0000-000000000001", authorization: str = Header(None)):
    """
    Get the latest ActionPlanEntry from Blackboard.
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    current_user_id.set(userId)
    bb = get_blackboard()
    plan = await bb.read_latest_action_plan()
    if plan is None:
        return {"status": "no_data", "plan": None}
    
    from dataclasses import asdict
    return {"status": "ok", "plan": asdict(plan)}

@app.post("/api/v1/agents/action/confirm")
async def confirm_action_plan(body: dict, authorization: str = Header(None)):
    """
    Confirm or cancel a pending action plan.
    Body: { "plan_id": str, "confirm": bool }
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    user_id = body.get("userId", "a0000000-0000-0000-0000-000000000001")
    current_user_id.set(user_id)
    
    plan_id = body.get("plan_id")
    confirm = body.get("confirm", False)
    if not plan_id:
        return {"status": "error", "message": "plan_id field is required"}
    
    if USE_ORCHESTRATOR_V2 and orchestrator_v2:
        agent = orchestrator_v2.action_agent
    else:
        agent = getattr(orchestrator, "action_agent", None)
        
    if not agent:
        return {"status": "error", "message": "Action agent is not loaded."}
        
    result = await agent.confirm_plan(plan_id, confirm)
    return {"status": "ok", "result": result}


# ─── FHIR Gateway Endpoints (Phase 20) ─────────────────────────────────────────
from services.fhir_gateway_service import FhirGatewayService

@app.get("/api/v1/fhir/observation/latest")
async def fhir_observation_latest():
    """
    Get the latest Blackboard ClinicalEntry formatted as a list of FHIR Observations.
    """
    bb = get_blackboard()
    clinical = await bb.read_latest_clinical()
    if clinical is None:
        return {"status": "no_data", "observations": []}
    
    observations = FhirGatewayService.to_fhir_observations(clinical)
    return {"status": "ok", "observations": observations}

@app.get("/api/v1/fhir/condition/latest")
async def fhir_condition_latest():
    """
    Get the latest Blackboard ClinicalEntry formatted as an HL7 FHIR Condition resource.
    """
    bb = get_blackboard()
    clinical = await bb.read_latest_clinical()
    if clinical is None:
        return {"status": "no_data", "condition": None}
    
    condition = FhirGatewayService.to_fhir_condition(clinical)
    return {"status": "ok", "condition": condition}

@app.get("/api/v1/fhir/clinical-bundle/latest")
async def fhir_clinical_bundle_latest():
    """
    Get the latest clinical status as a combined FHIR searchset transaction bundle.
    """
    bb = get_blackboard()
    clinical = await bb.read_latest_clinical()
    if clinical is None:
        return {"status": "no_data", "bundle": None}
    
    bundle = FhirGatewayService.to_fhir_bundle(clinical)
    return {"status": "ok", "bundle": bundle}


# ─── Test Orchestrator Endpoint ───────────────────────────────────────────────
@app.post("/api/v1/agents/test/orchestrator")
async def test_orchestrator(body: dict, authorization: str = Header(None)):
    """
    Integration test endpoint: feed a synthetic message + vitals, get full
    orchestrator state back (useful for frontend demo of MoA behavior).
    Body: { "message": str, "vitals": dict (optional), "use_v2": bool }
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    message  = body.get("message", "Xin chào Hugo!")
    vitals   = body.get("vitals", {})
    use_v2   = body.get("use_v2", USE_ORCHESTRATOR_V2)
    user_id  = body.get("userId", "a0000000-0000-0000-0000-000000000001")

    if use_v2 and orchestrator_v2 is not None:
        state = await orchestrator_v2.route_and_execute(message, vitals, user_id=user_id)
        state["orchestrator_version"] = "V2"
    else:
        state = await orchestrator.route_and_execute(message, vitals, user_id=user_id)
        state["orchestrator_version"] = "V1"

    return state


# ─── Perception Agent Endpoints ───────────────────────────────────────────────

@app.post("/api/v1/agents/perception/scan")
async def perception_scan(body: dict = None, authorization: str = Header(None)):
    """
    Trigger a full-body multi-modal perception scan.
    Pulls latest camera frame + vitals + LiDAR snapshot from SensorFusionBuffer,
    calls Vision LLM (Gemini Flash), writes PerceptionScan to Blackboard.
    Returns PerceptionScan JSON.
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    body_dict = body or {}
    user_id = body_dict.get("userId", "a0000000-0000-0000-0000-000000000001")
    current_user_id.set(user_id)

    # Optional: push synthetic camera frame path from request body
    if body:
        frame_path = body.get("frame_path", "")
        if frame_path and os.path.isfile(frame_path):
            import base64
            fusion_buf = get_fusion_buffer()
            with open(frame_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            from services.sensor_fusion_buffer import CameraFrame
            await fusion_buf.push_camera(CameraFrame(frame_path=frame_path, frame_b64=b64))

    try:
        scan = await perception_agent.execute_full_body_scan()
        return {
            "status": "ok",
            "scan": scan.to_dict(),
        }
    except Exception as exc:
        log.error("[PERCEPTION_SCAN] Error: %s", exc)
        return {"status": "error", "error": str(exc)}


@app.get("/api/v1/agents/perception/latest")
async def perception_latest(userId: str = "a0000000-0000-0000-0000-000000000001", authorization: str = Header(None)):
    """
    Return the latest cached PerceptionScan from Blackboard (no new scan).
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    current_user_id.set(userId)
    scan = await perception_agent.read_latest_scan()
    if scan is None:
        return {"status": "no_scan", "scan": None}
    return {"status": "ok", "scan": scan.to_dict()}


@app.get("/api/v1/agents/perception/status")
async def perception_status():
    """Agent status + SensorFusionBuffer stats"""
    fusion_buf = get_fusion_buffer()
    return {
        "agent": perception_agent.get_status(),
        "fusion_buffer": await fusion_buf.stats(),
    }


@app.post("/api/v1/sensors/vitals/push")
async def push_vitals(body: dict):
    """
    Lightweight endpoint for SensorFusionBuffer: push a vitals sample.
    (Spring Boot / wristband simulator can call this to feed the fusion buffer)
    Body: { heart_rate, spo2, systolic, diastolic, body_temperature, step_count, alert_level }
    """
    try:
        fusion_buf = get_fusion_buffer()
        sample = VitalsSample(
            heart_rate=body.get("heart_rate") or body.get("heartRate"),
            spo2=body.get("spo2"),
            systolic=body.get("systolic"),
            diastolic=body.get("diastolic"),
            body_temperature=body.get("body_temperature") or body.get("bodyTemperature"),
            step_count=body.get("step_count") or body.get("stepCount"),
            alert_level=body.get("alert_level", "NORMAL"),
        )
        await fusion_buf.push_vitals(sample)
        return {"status": "ok", "buffered_samples": (await fusion_buf.stats())["vitals_samples"]}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


if __name__ == "__main__":
    import logging.handlers
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        loop="asyncio",
        log_level="info",
        access_log=False,
    )
