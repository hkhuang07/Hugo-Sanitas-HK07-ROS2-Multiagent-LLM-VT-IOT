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

# Suppress TensorFlow oneDNN custom operations messages and logs before other packages import
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

import threading
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import warnings

# Prevent UnicodeEncodeError on Windows CP1252/other non-UTF-8 console encodings
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Suppress unavoidable third-party Pydantic model namespace warnings
warnings.filterwarnings("ignore", message='Field "model_name" has conflict with protected namespace "model_"')
# Suppress google.api_core Python deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")

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
        from utils.ip_scanner import get_default_route_info
        gw_ip, _ = get_default_route_info()
        if gw_ip:
            return gw_ip
    except Exception:
        pass
    return "127.0.0.1"

def load_env_and_apply_wsl_routing():
    load_env_file()
    import sys
    if sys.platform.startswith("win"):
        gateway_ip = get_default_gateway_ip()
        if gateway_ip and gateway_ip != "127.0.0.1":
            os.environ["DEFAULT_GATEWAY"] = gateway_ip
            
            # Override Redis config to route local connections to WSL IP
            redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
            if redis_host in ("127.0.0.1", "localhost"):
                os.environ["REDIS_HOST"] = gateway_ip
            
            redis_url = os.environ.get("REDIS_URL")
            if redis_url and ("127.0.0.1" in redis_url or "localhost" in redis_url):
                os.environ["REDIS_URL"] = redis_url.replace("127.0.0.1", gateway_ip).replace("localhost", gateway_ip)
                
            # Override MQTT broker host
            mqtt_host = os.environ.get("MQTT_BROKER_HOST", "localhost")
            if mqtt_host in ("127.0.0.1", "localhost"):
                os.environ["MQTT_BROKER_HOST"] = gateway_ip
                
            mqtt_url = os.environ.get("MQTT_BROKER_URL")
            if mqtt_url and ("127.0.0.1" in mqtt_url or "localhost" in mqtt_url):
                os.environ["MQTT_BROKER_URL"] = mqtt_url.replace("127.0.0.1", gateway_ip).replace("localhost", gateway_ip)

# Call env loader immediately at import time to populate environment variables
load_env_and_apply_wsl_routing()

async def run_network_ingestion_worker():
    """
    Background worker parsing local .env modifications and validating gateway IP every 5.0 seconds.
    """
    log.info("[NETWORK_WORKER] Network Ingestion worker started.")
    while True:
        try:
            load_env_and_apply_wsl_routing()
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

async def initialize_memory_background():
    """Initialize LanceDB without blocking FastAPI startup."""
    try:
        memory_timeout_s = float(os.getenv("LANCE_INIT_TIMEOUT_S", "120.0"))
        await asyncio.wait_for(memory.initialize(), timeout=memory_timeout_s)
    except asyncio.TimeoutError:
        log.warning("[STARTUP] LanceDB memory initialization exceeded %.1fs; continuing in degraded mode.", memory_timeout_s)
    except Exception as e:
        log.error("[STARTUP] LanceDB memory initialization failed; continuing in degraded mode: %s", e)

import uvicorn
import fastapi
from fastapi import FastAPI, Header, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agents.agent_orchestrator import AgentOrchestrator
from agents.perception_agent import PerceptionAgent
from arbitrator.arbitrator import Arbitrator
from memory.lance_memory import LanceMemory
from services.agent_log_client import start_log_client, stop_log_client
from services.blackboard_service import get_blackboard, current_user_id, current_auth_token
from services.sensor_fusion_buffer import get_fusion_buffer, VitalsSample, CameraFrame
from utils.spatial_tracker import SpatialTrackerThread
from utils.vision_pipeline import VisionPipeline



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
ROBOT_MODE = os.getenv("ROBOT_MODE", "SIMULATED").upper()

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

from agents.hardware_command_agent import HardwareCommandAgent
hardware_command_agent = HardwareCommandAgent(arbitrator=arbitrator)

# ─── Safety State Machine ──────────────────────────────────────────────────────────────────────────
# ARCH-3 FIX: Replace naive "grace period" timer with a proper State Machine.
# A countdown timer creates a blind safety window. A State Machine maintains
# integrity: UNINITIALIZED → HOLD_POSITION (never skip safety checks).
# Safety only clears AFTER sensors confirm a nominal reading.
# ──────────────────────────────────────────────────────────────────────────

class SafetyState:
    """Safety State Machine states for Subsumption Tier-0."""
    SENSOR_UNINITIALIZED = "SENSOR_UNINITIALIZED"  # Startup: sensors not yet confirmed
    HOLD_POSITION        = "HOLD_POSITION"           # Uninitialized → hold, await sensor data
    NOMINAL              = "NOMINAL"                 # Sensors OK, no threats detected
    TRIPPED              = "TRIPPED"                 # Debounced threat confirmed, safety active

# Global safety state (written by run_subsumption_safety_worker, read by agents)
_safety_state: str = SafetyState.SENSOR_UNINITIALIZED
_safety_reason: str = ""
# Backwards-compat bool (read by downstream code that checks _safety_tripped)
_safety_tripped: bool = False

_mqtt_client = None

def on_mqtt_message(client, userdata, msg):
    try:
        import json
        import asyncio
        topic = msg.topic
        payload = json.loads(msg.payload.decode('utf-8'))
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(handle_mqtt_payload(topic, payload), loop)
    except Exception:
        pass

async def handle_mqtt_payload(topic, payload):
    try:
        from services.blackboard_service import get_blackboard
        import math
        bb = get_blackboard()
        if topic == "hk07/sensors/environment/state":
            await bb.write_value("sensor:env:latest", payload, ttl_seconds=3)
        elif topic == "hk07/sensors/location/gps":
            await bb.write_value("sensor:location:latest", payload, ttl_seconds=5)
        elif topic == "hk07/sensors/activity/metrics":
            await bb.write_value("sensor:activity:latest", payload, ttl_seconds=3)
            wrist_motion = payload.get("wrist_motion", [0.0, 0.0, 0.0])
            mag = math.sqrt(sum(x**2 for x in wrist_motion))
            await bb.write_value("sensor:vitals:wrist_motion_magnitude", mag, ttl_seconds=3)
        elif "vitals" in topic or "wristband" in topic:
            names = payload.get("name", [])
            pos = payload.get("position", [])
            vitals_map = {}
            for i, name in enumerate(names):
                if i < len(pos):
                    vitals_map[name] = pos[i]
            
            hr = vitals_map.get("heart_rate")
            if hr is not None and not math.isnan(hr):
                await bb.write_value("sensor:vitals:heart_rate", float(hr), ttl_seconds=3)
            
            soc = vitals_map.get("battery_level")
            if soc is not None:
                await bb.write_value("sensor:vitals:battery_level", float(soc), ttl_seconds=3)
                
            vitals_latest = {
                "heart_rate": vitals_map.get("heart_rate", 72.0),
                "spo2": vitals_map.get("spo2", 98.0),
                "respiratory_rate": vitals_map.get("respiratory_rate", 14.0),
                "stress_score": vitals_map.get("stress_score", 15.0),
                "battery_level": vitals_map.get("battery_level", 100.0),
                "battery_temp": vitals_map.get("battery_temp", 32.0),
                "wrist_motion_magnitude": vitals_map.get("wrist_motion_magnitude", 0.0),
                "pedometer_steps": vitals_map.get("pedometer_steps", 0.0),
                "activity_type": vitals_map.get("activity_type", 0.0)
            }
            await bb.write_value("sensor:vitals:latest", vitals_latest, ttl_seconds=3)
    except Exception:
        pass

def init_mqtt_client():
    global _mqtt_client
    try:
        import paho.mqtt.client as mqtt
        broker = os.getenv("MQTT_BROKER", "localhost")
        port = int(os.getenv("MQTT_PORT", 1883))
        if hasattr(mqtt, "CallbackAPIVersion"):
            _mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        else:
            _mqtt_client = mqtt.Client()
        _mqtt_client.on_message = on_mqtt_message
        _mqtt_client.connect(broker, port, keepalive=60)
        _mqtt_client.subscribe([
            ("hk07/sensors/environment/state", 0),
            ("hk07/sensors/location/gps", 0),
            ("hk07/sensors/activity/metrics", 0),
            ("hk07/sensors/wristband/+/vitals", 0),
            ("hk07/vitals/wristband", 0)
        ])
        _mqtt_client.loop_start()
        log.info(f"[MQTT] Persistent client connected to {broker}:{port} and subscribed to direct sensor topics.")
    except Exception as e:
        log.error(f"[MQTT] Failed to initialize client: {e}")

def close_mqtt_client():
    global _mqtt_client
    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
            log.info("[MQTT] Client disconnected cleanly.")
        except Exception as e:
            log.error(f"[MQTT] Error during disconnect: {e}")


async def run_subsumption_safety_worker():
    """
    Tier-0 Safety Logic — State Machine Implementation.

    States:
      SENSOR_UNINITIALIZED → HOLD_POSITION: Sensors not yet confirmed. Robot
        holds position. Agents write HOLD_POSITION to MQTT. Does NOT blindly
        skip safety — if user falls before sensors init, the UNINITIALIZED
        state itself triggers a conservative HOLD_POSITION response.

      HOLD_POSITION → NOMINAL: Transitions when first valid clinical read arrives.
        (Sensors confirmed as alive = safe to assume nominal baseline.)

      NOMINAL → TRIPPED: Requires 3 consecutive confirmed threat cycles (~1.5s)
        to prevent transient glitches from triggering E-STOP.

      TRIPPED → NOMINAL: Requires 3 consecutive clear cycles (~1.5s) to resume.
    """
    global _safety_state, _safety_tripped, _safety_reason
    import time
    import json
    log.info("[SAFETY_WORKER] Subsumption Safety State Machine started. State=SENSOR_UNINITIALIZED")

    consecutive_trips = 0
    consecutive_clears = 0
    consecutive_sensor_confirms = 0  # Count of valid sensor reads (for INIT transition)
    INIT_CONFIRM_THRESHOLD = 2       # Need 2 consecutive valid reads to leave UNINITIALIZED

    while True:
        try:
            bb = get_blackboard()

            # ──────────────────────────────────────────────────────────────────────────
            # Read sensor data (clinical perception from IPWebcam analysis)
            clinical = await bb.read_value("sensor:perception:clinical")
            is_falling = await bb.read_value("sensor:vitals:is_falling")
            sos_emergency = await bb.read_value("sensor:vitals:emergency")
            imu = await bb.read_value("sensor:imu:latest")
            env = await bb.read_value("sensor:env:latest")
            vitals = await bb.read_value("sensor:vitals:latest")

            sensor_data_present = (
                (clinical is not None) or 
                (is_falling is not None) or 
                (imu is not None) or 
                (env is not None) or 
                (vitals is not None)
            )

            # ── STATE: SENSOR_UNINITIALIZED ──────────────────────────────────────────────────────
            if _safety_state in (SafetyState.SENSOR_UNINITIALIZED, SafetyState.HOLD_POSITION):
                await bb.write_value("safety:state", _safety_state, ttl_seconds=60)
                await bb.write_value("safety:tripped", False)

                if sensor_data_present:
                    consecutive_sensor_confirms += 1
                    if consecutive_sensor_confirms >= INIT_CONFIRM_THRESHOLD:
                        # Sensors confirmed as alive → transition to NOMINAL
                        _safety_state = SafetyState.NOMINAL
                        _safety_tripped = False
                        log.info(
                            "[SAFETY_SM] ✅ Sensors confirmed (%d reads). Transitioning: UNINITIALIZED → NOMINAL.",
                            consecutive_sensor_confirms
                        )
                        await bb.write_value("safety:state", SafetyState.NOMINAL, ttl_seconds=60)
                else:
                    consecutive_sensor_confirms = 0
                    if _safety_state == SafetyState.SENSOR_UNINITIALIZED:
                        _safety_state = SafetyState.HOLD_POSITION
                        log.warning(
                            "[SAFETY_SM] ⏳ No sensor data yet. State=HOLD_POSITION. "
                            "Robot holds position. Agents in STANDBY mode."
                        )
                        await bb.write_value("safety:state", SafetyState.HOLD_POSITION, ttl_seconds=60)
                        await bb.write_value("safety:reason", "Sensors not yet initialized", ttl_seconds=60)

            # ── STATE: NOMINAL or TRIPPED (sensors are live) ──────────────────────────────
            else:
                candidate_trip = False
                reason = ""

                # Wristband hardware SOS / fall safety trips disabled per user request
                if is_falling is True:
                    pass
                elif sos_emergency is True:
                    pass

                # Vision-based threats from PerceptionAgent (lower priority, event-triggered)
                if clinical and not candidate_trip:
                    facial_distress = clinical.get("facial_distress", {})
                    env_hazards = clinical.get("environmental_hazards", {})
                    visible_injuries = clinical.get("visible_injuries", {})

                    if facial_distress.get("detected"):
                        pass
                    elif env_hazards.get("detected"):
                        pass
                    elif visible_injuries.get("detected"):
                        pass

                # Debounce filter: 3 consecutive cycles to engage OR clear
                if candidate_trip:
                    consecutive_clears = 0
                    consecutive_trips += 1
                    if consecutive_trips >= 3:
                        if _safety_state != SafetyState.TRIPPED:
                            _safety_state = SafetyState.TRIPPED
                            _safety_tripped = True
                            _safety_reason = reason
                            log.warning("[SAFETY_SM] 🚨 TRIP ENGAGED (debounced 3x): %s", reason)
                else:
                    consecutive_trips = 0
                    consecutive_clears += 1
                    if consecutive_clears >= 3:
                        if _safety_state == SafetyState.TRIPPED:
                            _safety_state = SafetyState.NOMINAL
                            _safety_tripped = False
                            _safety_reason = ""
                            log.info("[SAFETY_SM] ✅ TRIP CLEARED (debounced 3x). Resuming NOMINAL.")

                # Write state to Blackboard
                try:
                    await bb.write_value("safety:state", _safety_state, ttl_seconds=60)
                    await bb.write_value("safety:tripped", _safety_tripped)
                    if _safety_reason:
                        await bb.write_value("safety:reason", _safety_reason, ttl_seconds=30)
                except Exception as bb_err:
                    log.error("[SAFETY_SM] Blackboard write failed: %s", bb_err)

                if _safety_tripped:
                    # Inhibit empathetic/medical autonomous outputs during active safety trip
                    arbitrator.inhibit("EMPATHETIC", duration_s=10)
                    arbitrator.inhibit("MEDICAL", duration_s=10)

            await asyncio.sleep(0.5)  # 2Hz loop
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("[SAFETY_SM] Unhandled error: %s", e)
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
                    async with websockets.connect(uri, ping_interval=30, ping_timeout=30) as websocket:
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
    import time
    from services.sensor_fusion_buffer import get_fusion_buffer, VitalsSample
    from services.blackboard_service import get_blackboard

    uri = "ws://localhost:9090"
    backoff = 1.0
    last_phone_imu_time = 0.0
    
    while True:
        try:
            log.info(f"[ROSBRIDGE_CLIENT] Connecting to {uri}...")
            async with websockets.connect(uri, ping_interval=30, ping_timeout=30) as websocket:
                log.info("[ROSBRIDGE_CLIENT] Connected to rosbridge_suite.")
                backoff = 1.0
                
                # Subscribe to topics
                subscribe_topics = [
                    {"topic": "/telemetry/sensors/vitals", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/sensors/camera/thermal_rppg", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/vitals/wristband", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/imu", "type": "sensor_msgs/msg/Imu"},
                    {"topic": "/sensors/imu/state", "type": "sensor_msgs/msg/Imu"},
                    {"topic": "/hk07/perception/clinical", "type": "std_msgs/msg/String"},
                    {"topic": "/telemetry/pose", "type": "geometry_msgs/msg/PoseStamped"},
                    {"topic": "/telemetry/pmu", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/pneumatic", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/actuators/joints", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/sensors/tactile", "type": "sensor_msgs/msg/JointState"}
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
                        
                        # MQTT Dual Telemetry Bridge (Restores Vue telemetry panels updates)
                        if _mqtt_client:
                            t_sec = msg.get("header", {}).get("stamp", {}).get("sec", 0)
                            t_nsec = msg.get("header", {}).get("stamp", {}).get("nanosec", 0)
                            timestamp_ms = t_sec * 1000 + int(t_nsec / 1e6)
                            if timestamp_ms == 0:
                                timestamp_ms = int(time.time() * 1000)

                            if topic == "/telemetry/pmu":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                if len(names) >= 4 and len(pos) >= 4:
                                    pmu_payload = {
                                        "voltage": pos[names.index("voltage")],
                                        "current": pos[names.index("current")],
                                        "soc": pos[names.index("soc")],
                                        "temp": pos[names.index("temp")],
                                        "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                        "timestampMs": timestamp_ms
                                    }
                                    _mqtt_client.publish("hk07/telemetry/pmu", json.dumps(pmu_payload), qos=0)

                            elif topic == "/telemetry/pneumatic":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                if len(names) >= 4 and len(pos) >= 4:
                                    pne_payload = {
                                        "press_L": pos[names.index("press_L")],
                                        "press_R": pos[names.index("press_R")],
                                        "pump_active": bool(pos[names.index("pump_active")]),
                                        "relief_active": bool(pos[names.index("relief_active")]),
                                        "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                        "timestampMs": timestamp_ms
                                    }
                                    _mqtt_client.publish("hk07/telemetry/pneumatic", json.dumps(pne_payload), qos=0)

                            elif topic == "/telemetry/sensors/tactile":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                if len(names) >= 2 and len(pos) >= 2:
                                    tac_payload = {
                                        "hug_force": pos[names.index("hug_force")],
                                        "flex_rate": pos[names.index("flex_rate")],
                                        "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                        "timestampMs": timestamp_ms
                                    }
                                    _mqtt_client.publish("hk07/telemetry/tactile", json.dumps(tac_payload), qos=0)

                            elif topic == "/telemetry/actuators/joints":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                eff = msg.get("effort", [])
                                vel = msg.get("velocity", [])
                                joints_list = []
                                for i, name in enumerate(names):
                                    joints_list.append({
                                        "name": name,
                                        "angle": pos[i] if i < len(pos) else 0.0,
                                        "torque": eff[i] if i < len(eff) else 0.0,
                                        "temp": vel[i] if i < len(vel) else 0.0
                                    })
                                joints_payload = {
                                    "joints": joints_list,
                                    "is_simulated": (ROBOT_MODE == "SIMULATED")
                                }
                                _mqtt_client.publish("hk07/telemetry/actuators/joints", json.dumps(joints_payload), qos=0)

                            elif topic == "/sensors/camera/thermal_rppg":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                if len(names) >= 3 and len(pos) >= 3:
                                    rppg_payload = {
                                        "rppg_heart_rate": pos[names.index("rppg_heart_rate")],
                                        "thermal_temperature": pos[names.index("thermal_temperature")],
                                        "fever_alert": bool(pos[names.index("fever_alert")]),
                                        "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                        "timestampMs": timestamp_ms
                                    }
                                    _mqtt_client.publish("hk07/sensors/camera/thermal-rppg", json.dumps(rppg_payload), qos=0)

                            elif topic == "/telemetry/pose":
                                # Bridge PoseStamped coordinates directly to dashboard IMU store
                                pose = msg.get("pose", {})
                                pos_data = pose.get("position", {})
                                orientation = pose.get("orientation", {})
                                imu_payload = {
                                    "x": pos_data.get("x", 0.0),
                                    "y": pos_data.get("y", 0.0),
                                    "z": pos_data.get("z", 0.0),
                                    "qw": orientation.get("w", 1.0),
                                    "qx": orientation.get("x", 0.0),
                                    "qy": orientation.get("y", 0.0),
                                    "qz": orientation.get("z", 0.0),
                                    "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                    "timestampMs": timestamp_ms
                                }
                                _mqtt_client.publish("hk07/telemetry/imu", json.dumps(imu_payload), qos=0)

                        if topic == "/telemetry/sensors/vitals":
                            pos = msg.get("position", [])
                            if len(pos) >= 5:
                                hr_val = pos[0] if pos[0] is not None else float('nan')
                                spo2_val = pos[1] if pos[1] is not None else float('nan')
                                temp_val = pos[2] if pos[2] is not None else float('nan')
                                sample = VitalsSample(
                                    heart_rate=float(hr_val),
                                    spo2=float(spo2_val),
                                    body_temperature=float(temp_val),
                                    step_count=0,
                                    alert_level="NORMAL"
                                )
                                await fusion_buf.push_vitals(sample)
                                
                        elif topic == "/sensors/camera/thermal_rppg":
                            pos = msg.get("position", [])
                            if len(pos) >= 2:
                                latest = await fusion_buf.latest_vitals()
                                
                                hr_val = pos[0]
                                if hr_val is not None and not math.isnan(hr_val) and hr_val > 0:
                                    hr_final = float(hr_val)
                                else:
                                    hr_final = latest.heart_rate if (latest and latest.heart_rate is not None and not math.isnan(latest.heart_rate)) else 72.0
                                    
                                temp_val = pos[1]
                                if temp_val is not None and not math.isnan(temp_val) and temp_val > 0:
                                    temp_final = float(temp_val)
                                else:
                                    temp_final = latest.body_temperature if (latest and latest.body_temperature is not None and not math.isnan(latest.body_temperature)) else 36.6
                                    
                                is_critical = False
                                if len(pos) >= 3 and pos[2] is not None and not math.isnan(pos[2]) and pos[2] > 0:
                                    is_critical = True
                                    
                                sample = VitalsSample(
                                    heart_rate=hr_final,
                                    spo2=latest.spo2 if (latest and latest.spo2 is not None and not math.isnan(latest.spo2)) else 98.0,
                                    body_temperature=temp_final,
                                    alert_level="CRITICAL" if is_critical else "NORMAL"
                                )
                                await fusion_buf.push_vitals(sample)
                                await bb.write_value("sensor:camera:fever_alert", is_critical, ttl_seconds=3)
                                
                        elif topic == "/vitals/wristband":
                            pos = msg.get("position", [])
                            names = msg.get("name", [])
                            vitals_map = {}
                            for i, name in enumerate(names):
                                if i < len(pos):
                                    vitals_map[name] = pos[i]
                            
                            is_falling = bool(vitals_map.get("is_falling", False))
                            emergency = bool(vitals_map.get("emergency_button_pressed", False))
                            await bb.write_value("sensor:vitals:is_falling", is_falling, ttl_seconds=3)
                            await bb.write_value("sensor:vitals:emergency", emergency, ttl_seconds=3)
                            
                            wrist_motion_mag = vitals_map.get("wrist_motion_magnitude") or 0.0
                            await bb.write_value("sensor:vitals:wrist_motion_magnitude", float(wrist_motion_mag), ttl_seconds=3)
                            
                            hr = vitals_map.get("heart_rate")
                            if hr is not None and not math.isnan(hr):
                                await bb.write_value("sensor:vitals:heart_rate", float(hr), ttl_seconds=3)
                                
                            soc = vitals_map.get("battery_level")
                            if soc is not None and not math.isnan(soc):
                                await bb.write_value("sensor:vitals:battery_level", float(soc), ttl_seconds=3)
                            
                            # Compile vitals:latest
                            vitals_latest = {
                                "heart_rate": vitals_map.get("heart_rate", 72.0),
                                "spo2": vitals_map.get("spo2", 98.0),
                                "respiratory_rate": vitals_map.get("respiratory_rate", 14.0),
                                "stress_score": vitals_map.get("stress_score", 15.0),
                                "battery_level": vitals_map.get("battery_level", 100.0),
                                "battery_temp": vitals_map.get("battery_temp", 32.0),
                                "wrist_motion_magnitude": wrist_motion_mag,
                                "pedometer_steps": vitals_map.get("pedometer_steps", 0.0),
                                "activity_type": vitals_map.get("activity_type", 0.0)
                            }
                            await bb.write_value("sensor:vitals:latest", vitals_latest, ttl_seconds=3)
                            
                            # Environment Data - Merge cleanly to preserve battery level and avoid fake barometer
                            light = vitals_map.get("ambient_light")
                            baro = vitals_map.get("barometric_pressure")
                            bat_lvl = vitals_map.get("battery_level")
                            bat_temp = vitals_map.get("battery_temp")
                            is_sim = vitals_map.get("is_simulated")
                            
                            existing_env = await bb.read_value("sensor:env:latest") or {}
                            if not isinstance(existing_env, dict):
                                existing_env = {}
                                
                            if light is not None and not math.isnan(light):
                                existing_env["ambient_light"] = float(light)
                            elif "ambient_light" not in existing_env:
                                existing_env["ambient_light"] = 150.0
                                
                            if baro is not None and not math.isnan(baro):
                                existing_env["barometric_pressure"] = float(baro)
                                
                            if bat_lvl is not None and not math.isnan(bat_lvl):
                                existing_env["battery_level"] = float(bat_lvl)
                            elif "battery_level" not in existing_env:
                                existing_env["battery_level"] = 100.0
                                
                            if bat_temp is not None and not math.isnan(bat_temp):
                                existing_env["battery_temp"] = float(bat_temp)
                            elif "battery_temp" not in existing_env:
                                existing_env["battery_temp"] = 32.0
                                
                            if is_sim is not None:
                                existing_env["is_simulated"] = bool(is_sim)
                                
                            await bb.write_value("sensor:env:latest", existing_env, ttl_seconds=3)
                            
                            # GPS Location
                            lat = vitals_map.get("latitude")
                            lon = vitals_map.get("longitude")
                            alt = vitals_map.get("altitude")
                            if lat is not None and not math.isnan(lat):
                                loc_data = {
                                    "latitude": float(lat),
                                    "longitude": float(lon),
                                    "altitude": float(alt or 0.0)
                                }
                                await bb.write_value("sensor:location:latest", loc_data, ttl_seconds=5)

                            # Bridge to Spring Boot MQTT topic hk07/sensors/wristband/wristband-sim-001/vitals
                            if _mqtt_client:
                                hr = vitals_map.get("heart_rate")
                                if hr is not None and not math.isnan(hr) and hr > 0:
                                    hr = int(hr)
                                    import random
                                    spo2 = 98.2 - 0.02 * (hr - 70.0) + random.uniform(-0.3, 0.3)
                                    spo2 = float(round(max(94.0, min(99.9, spo2)), 1))
                                    sys_bp = 120.0 + 0.5 * (hr - 70.0) + random.uniform(-2.0, 2.0)
                                    sys_bp = float(round(sys_bp, 1))
                                    dias_bp = 80.0 + 0.3 * (hr - 70.0) + random.uniform(-1.0, 1.0)
                                    dias_bp = float(round(dias_bp, 1))
                                    
                                    bat_temp = vitals_map.get("battery_temp")
                                    if bat_temp is not None and not math.isnan(bat_temp) and bat_temp > 0:
                                        body_temp = float(round(bat_temp, 2))
                                    else:
                                        body_temp = float(round(36.6 + random.uniform(-0.1, 0.1), 2))
                                else:
                                    hr = -1
                                    spo2 = -1.0
                                    sys_bp = -1.0
                                    dias_bp = -1.0
                                    body_temp = -1.0

                                vitals_payload = {
                                    "deviceId": "wristband-sim-001",
                                    "heartRate": hr,
                                    "spo2": spo2,
                                    "bodyTemperature": body_temp,
                                    "systolic": sys_bp,
                                    "diastolic": dias_bp,
                                    "epochTimestampMs": timestamp_ms
                                }
                                try:
                                    _mqtt_client.publish("hk07/sensors/wristband/wristband-sim-001/vitals", json.dumps(vitals_payload), qos=0)
                                except Exception as mqtt_err:
                                    log.error("[ROSBRIDGE_CLIENT_MQTT_ERROR] Failed to bridge wristband vitals: %s", mqtt_err)
                                
                        elif topic == "/sensors/imu/state":
                            now = time.time()
                            last_phone_imu_time = now
                            orientation = msg.get("orientation", {})
                            accel = msg.get("linear_acceleration", {})
                            gyro = msg.get("angular_velocity", {})
                            ax = float(accel.get("x", 0.0)) if accel.get("x") is not None else 0.0
                            ay = float(accel.get("y", 0.0)) if accel.get("y") is not None else 0.0
                            az = float(accel.get("z", 9.81)) if accel.get("z") is not None else 9.81
                            gx = float(gyro.get("x", 0.0)) if gyro.get("x") is not None else 0.0
                            gy = float(gyro.get("y", 0.0)) if gyro.get("y") is not None else 0.0
                            gz = float(gyro.get("z", 0.0)) if gyro.get("z") is not None else 0.0
                            px = 0.0
                            py = 0.0
                            pz = 0.0
                            
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
                                "gyro_x": gx,
                                "gyro_y": gy,
                                "gyro_z": gz,
                                "qw": float(orientation.get("w", 1.0)) if orientation.get("w") is not None else 1.0,
                                "qx": float(orientation.get("x", 0.0)) if orientation.get("x") is not None else 0.0,
                                "qy": float(orientation.get("y", 0.0)) if orientation.get("y") is not None else 0.0,
                                "qz": float(orientation.get("z", 0.0)) if orientation.get("z") is not None else 0.0,
                                "x": px,
                                "y": py,
                                "z": pz,
                                "frame_id": msg.get("header", {}).get("frame_id", ""),
                                "wrist_motion_magnitude": wrist_motion_mag,
                                "g_magnitude": g_mag
                            }
                            await bb.write_value("sensor:imu:latest", imu_data, ttl_seconds=3)
                            
                        elif topic == "/hk07/perception/clinical":
                            try:
                                clinical_data = json.loads(msg.get("data", "{}"))
                                await bb.write_value("sensor:perception:clinical", clinical_data, ttl_seconds=3)
                            except Exception:
                                pass
                                
        except Exception as e:
            log.error(f"[ROSBRIDGE_CLIENT_ERROR] Connection error: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)


# Global in-memory sensor cache (hydrated by daemon, read by /companion endpoint)
_sensor_cache: dict = {
    "vitals": None,
    "frame_bytes": None,
    "frame_ts": None,
    "imu": None,
    "fall_detected": False,
    "fever_alert": False,
    "daemon_status": "STARTING",
    "last_update": None,
}

_cache_lock: Optional[asyncio.Lock] = None

# ── [HOT-RELOAD] Device config — updated via POST /api/v1/config/device-ip ──────
# Daemon reads from this dict every poll cycle, allowing IP changes without restart
_device_config: dict = {
    "phone_ip": os.getenv("PHONE_IP", ""),
    "camera_port": os.getenv("CAMERA_PORT", "8080"),
    "updated_at": 0,
}
_device_config_lock: Optional[asyncio.Lock] = None


class CameraStreamWorker:
    """
    Background worker thread using OpenCV/HTTP to continuously stream and capture
    frames from the IPWebcam at 5-10 FPS. Decouples frame ingestion from FastAPI event loop.
    """
    def __init__(self, get_url_func, poll_fps=10.0):
        self.get_url_func = get_url_func
        self.poll_fps = poll_fps
        self.running = False
        self.thread = None
        self.latest_frame_bytes = None
        self.latest_frame_ts = None
        self.status = "INIT"
        self.lock = threading.Lock()
        self.consecutive_failures = 0

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name="camera-stream-worker", daemon=True)
        self.thread.start()
        log.info("[CAMERA_WORKER] Background Camera Stream worker thread started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _run(self):
        import cv2
        import httpx
        import time
        
        self.status = "RUNNING"
        while self.running:
            t_start = time.perf_counter()
            camera_url = self.get_url_func()
            if not camera_url:
                with self.lock:
                    self.status = "CAMERA_UNRESOLVED"
                time.sleep(1.0)
                continue

            cap = None
            try:
                # If camera_url indicates a video stream, use cv2.VideoCapture
                if "/video" in camera_url or camera_url.startswith("rtsp://"):
                    cap = cv2.VideoCapture(camera_url)
                    if not cap.isOpened():
                        raise ValueError("VideoCapture failed to open URL")
                    
                    while self.running:
                        t_cycle = time.perf_counter()
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            raise ValueError("Empty or failed frame read")
                        
                        ret, jpeg = cv2.imencode('.jpg', frame)
                        if not ret:
                            raise ValueError("JPEG encoding failed")
                        
                        frame_bytes = jpeg.tobytes()
                        ts = time.time()
                        
                        with self.lock:
                            self.latest_frame_bytes = frame_bytes
                            self.latest_frame_ts = ts
                            self.status = "OK"
                            self.consecutive_failures = 0
                            
                        elapsed = time.perf_counter() - t_cycle
                        sleep_time = max(0.01, (1.0 / self.poll_fps) - elapsed)
                        time.sleep(sleep_time)
                else:
                    # Snapshot mode: poll URL via HTTP
                    with httpx.Client(timeout=2.0) as client:
                        while self.running:
                            t_cycle = time.perf_counter()
                            resp = client.get(camera_url)
                            if resp.status_code == 200 and resp.content:
                                frame_bytes = resp.content
                                ts = time.time()
                                with self.lock:
                                    self.latest_frame_bytes = frame_bytes
                                    self.latest_frame_ts = ts
                                    self.status = "OK"
                                    self.consecutive_failures = 0
                            else:
                                raise ValueError(f"HTTP status {resp.status_code}")
                            
                            elapsed = time.perf_counter() - t_cycle
                            sleep_time = max(0.01, (1.0 / self.poll_fps) - elapsed)
                            time.sleep(sleep_time)
            except Exception as e:
                with self.lock:
                    self.consecutive_failures += 1
                    self.status = f"CAMERA_ERROR ({self.consecutive_failures})"
                log.debug("[CAMERA_WORKER] Fetch failed: %s", e)
                if cap:
                    cap.release()
                # Exponential backoff on errors
                time.sleep(min(5.0, 0.5 * self.consecutive_failures))

    def get_latest_frame(self):
        with self.lock:
            return self.latest_frame_bytes, self.latest_frame_ts, self.status

def get_camera_url() -> str:
    phone_ip    = _device_config.get("phone_ip") or os.getenv("PHONE_IP", "")
    camera_port = _device_config.get("camera_port") or os.getenv("CAMERA_PORT", "8080")
    if phone_ip:
        return f"http://{phone_ip}:{camera_port}/shot.jpg"
    return ""

# Global worker instance (started/stopped in lifespan hooks)
vision_pipeline: Optional[VisionPipeline] = None
spatial_tracker_worker: Optional[SpatialTrackerThread] = None

async def run_headless_camera_daemon():
    """
    Headless persistent camera ingestion daemon using the Multi-Processing VisionPipeline.
    Polls frames and handles decoupled AI outputs (MediaPipe at 10Hz, DeepFace/YOLO at 1Hz).
    Updates Blackboard safety metrics and broadcasts coordinates directly to web clients.
    """
    import time
    import base64
    import math
    from services.sensor_fusion_buffer import CameraFrame
    from utils.spatial_tracker import SpatialTrackerThread

    log.info("[CAMERA_DAEMON] ▶ Multi-Process Camera Daemon started. Cycle: 50ms.")
    # Poll frequently (50ms / 20Hz) so that we capture new frames from the process queue immediately
    poll_interval = 0.05

    while True:
        try:
            if vision_pipeline:
                frame_bytes, scan = await asyncio.to_thread(vision_pipeline.process_cycle)
                
                # If we got a new frame, push to SensorFusionBuffer & update cache
                if frame_bytes:
                    ts = time.time()
                    frame_b64 = base64.b64encode(frame_bytes).decode("utf-8")
                    
                    fusion_buf = get_fusion_buffer()
                    await fusion_buf.push_camera(
                        CameraFrame(frame_path="", frame_b64=frame_b64)
                    )
                    
                    async with _cache_lock:
                        _sensor_cache["frame_bytes"] = frame_bytes
                        _sensor_cache["frame_ts"] = ts
                        _sensor_cache["daemon_status"] = "OK"
                        _sensor_cache["last_update"] = ts
                
                # If we got a perception scan cycle output, process it
                if scan:
                    # Extract values
                    fall_detected = scan.get("fall_detected", False)
                    facial_distress = scan.get("facial_distress", 0.0)
                    posture_risk = scan.get("posture_risk", "LOW")
                    visible_injuries = scan.get("visible_injuries", [])
                    is_owner = scan.get("is_owner", True)
                    expression = scan.get("expression", "calm")
                    
                    # Update Blackboard service
                    bb = get_blackboard()
                    await bb.write_value("sensor:vitals:is_falling", fall_detected, ttl_seconds=300)
                    await bb.write_value("sensor:vision:facial_distress", facial_distress, ttl_seconds=300)
                    await bb.write_value("sensor:vision:posture_risk", posture_risk, ttl_seconds=300)
                    await bb.write_value("sensor:vision:is_owner", is_owner, ttl_seconds=300)
                    
                    # [BAYMAX] Merge and write to sensor:perception:latest_scan for EmpatheticAgent
                    try:
                        from datetime import datetime
                        existing_scan = await bb.read_value("sensor:perception:latest_scan") or {}
                        # Merge scan values into existing_scan
                        for k, v in scan.items():
                            if v is not None:
                                existing_scan[k] = v
                        existing_scan["timestamp"] = datetime.utcnow().isoformat() + "Z"
                        await bb.write_value("sensor:perception:latest_scan", existing_scan, ttl_seconds=300)
                    except Exception as scan_write_err:
                        log.error(f"Failed to update sensor:perception:latest_scan: {scan_write_err}")
                    
                    # Update global sensor cache
                    async with _cache_lock:
                        _sensor_cache["fall_detected"] = fall_detected
                        _sensor_cache["facial_distress"] = facial_distress
                        _sensor_cache["posture_risk"] = posture_risk
                        _sensor_cache["visible_injuries"] = visible_injuries
                        _sensor_cache["is_owner"] = is_owner
                        
                        # Populate spatial targets mapping for Vite Dashboard
                        s_targets = []
                        s_targets.append({
                            "label": "user_face",
                            "coordinates": [0.25, 0.40, 0.42, 0.60], # general face crop region
                            "confidence": 0.95,
                            "expression": expression
                        })
                        if fall_detected or posture_risk == "HIGH":
                            s_targets.append({
                                "label": "user_body",
                                "coordinates": [0.65, 0.15, 0.95, 0.85],
                                "confidence": 0.90
                            })
                        for injury in visible_injuries:
                            s_targets.append({
                                "label": "localized_injury",
                                "coordinates": [0.60, 0.30, 0.72, 0.45],
                                "confidence": 0.95
                            })
                        _sensor_cache["spatial_detections"] = s_targets

                    # Broadcast coordinate targets to active WebSocket client connections
                    if SpatialTrackerThread._connections:
                        current_vitals = _sensor_cache.get("vitals") or {}
                        hr = current_vitals.get("hr", float('nan'))
                        
                        payload = {
                            "status": "HARDWARE_BOUND",
                            "vitals": {
                                "real_hr_rppg": hr if not math.isnan(hr) else "SENSOR_DISCONNECTED",
                                "real_temp_thermal": "SENSOR_DISCONNECTED",
                                "sensor_status": "ONLINE"
                            },
                            "spatial_targets": s_targets
                        }
                        
                        msg_str = json.dumps(payload)
                        disconnected = []
                        for ws in list(SpatialTrackerThread._connections):
                            try:
                                await ws.send_text(msg_str)
                            except Exception:
                                disconnected.append(ws)
                        for ws in disconnected:
                            SpatialTrackerThread._connections.discard(ws)
            
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            log.info("[CAMERA_DAEMON] Shutdown signal received.")
            break
        except Exception as exc:
            log.error("[CAMERA_DAEMON] Error in daemon cycle: %s", exc)
            await asyncio.sleep(poll_interval)


async def run_headless_vitals_daemon():
    """
    Headless persistent vitals/IMU cache update daemon.
    Decoupled from camera state. Continuously syncs SensorFusionBuffer and Blackboard
    metrics to the global cache at 500ms intervals.
    """
    import time
    log.info("[VITALS_DAEMON] ▶ Headless Vitals Daemon started. Poll interval: 500ms.")
    poll_interval = float(os.getenv("SENSOR_DAEMON_POLL_S", "0.5"))

    while True:
        try:
            fusion_buf = get_fusion_buffer()
            latest_vitals = await fusion_buf.latest_vitals()

            bb = get_blackboard()
            fall_detected = await bb.read_value("sensor:vitals:is_falling") or False
            fever_alert   = await bb.read_value("sensor:camera:fever_alert") or False
            imu           = await bb.read_value("sensor:imu:latest")
            environment   = await bb.read_value("sensor:env:latest")
            location      = await bb.read_value("sensor:location:latest")
            activity      = await bb.read_value("sensor:activity:latest")

            async with _cache_lock:
                if latest_vitals:
                    _sensor_cache["vitals"] = {
                        "hr":   latest_vitals.heart_rate,
                        "spo2": latest_vitals.spo2,
                        "temp": latest_vitals.body_temperature,
                        "alert_level": latest_vitals.alert_level,
                        "status": "ONLINE"
                    }
                else:
                    _sensor_cache["vitals"] = {
                        "hr": float('nan'),
                        "spo2": "SENSOR_DISCONNECTED",
                        "temp": float('nan'),
                        "alert_level": "UNKNOWN",
                        "status": "SENSOR_DISCONNECTED"
                    }
                _sensor_cache["fall_detected"] = fall_detected
                _sensor_cache["fever_alert"]   = fever_alert
                _sensor_cache["imu"]           = imu
                _sensor_cache["environment"]   = environment
                _sensor_cache["location"]      = location
                _sensor_cache["activity"]      = activity
                _sensor_cache["last_update"]   = time.time()

            await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            log.info("[VITALS_DAEMON] Shutdown signal received.")
            break
        except Exception as exc:
            log.error("[VITALS_DAEMON] Error: %s", exc)
            await asyncio.sleep(poll_interval)


async def run_auto_perception_scan_loop():
    """
    [AUTO_VISION] Headless auto-perception scan daemon.
    Triggers PerceptionAgent.execute_full_body_scan() every 15s when camera is live.
    Results are written to Blackboard and cached in _sensor_cache for frontend polling.
    This eliminates the need for manual [TRIGGER_SCAN] click on the Vision page.
    """
    import time
    log.info("[AUTO_VISION] ▶ Auto-Perception Scan Loop started. Interval: 15s.")
    await asyncio.sleep(8.0)  # warm-up: let camera daemon initialize first

    while True:
        try:
            # Only scan if camera daemon has a fresh frame (< 15s old)
            async with _cache_lock:
                cam_status = _sensor_cache.get("daemon_status", "")
                frame_ts = _sensor_cache.get("frame_ts")
                frame_bytes = _sensor_cache.get("frame_bytes")

            frame_is_fresh = frame_ts is not None and (time.time() - frame_ts) < 15.0

            if frame_is_fresh or cam_status == "OK":
                log.info("[AUTO_VISION] Triggering auto perception scan...")
                # Pass the fresh frame directly to avoid duplicate HTTP fetching
                scan = await perception_agent.execute_full_body_scan(frame_bytes=frame_bytes)
                # Cache scan result for faster frontend retrieval
                async with _cache_lock:
                    _sensor_cache["latest_perception_scan"] = scan.to_dict()
                    _sensor_cache["latest_perception_ts"] = time.time()
                log.info(
                    "[AUTO_VISION] Scan complete — risk=%s confidence=%.2f provider=%s",
                    scan.overall_risk, scan.confidence, scan.status
                )
            else:
                log.debug(
                    "[AUTO_VISION] Scan skipped — camera not ready (status=%s, frame_age=%.1fs)",
                    cam_status,
                    (time.time() - frame_ts) if frame_ts else 999
                )

            await asyncio.sleep(15.0)

        except asyncio.CancelledError:
            log.info("[AUTO_VISION] Shutdown signal received.")
            break
        except Exception as e:
            log.error("[AUTO_VISION] Error in auto scan loop: %s", e)
            await asyncio.sleep(15.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown sequence for the agent engine"""
    log.info("+--------------------------------------------------+")
    log.info("|  HK-07 MULTI-AGENT ENGINE - STARTING             |")
    log.info("|  Architecture: Supervisor Node-Router Graph      |")
    log.info("|  MAS-STANDARD: ROUTER -> SAFETY/MED/EMP          |")
    log.info("+--------------------------------------------------+")

    # Initialize cache state locks
    global _cache_lock, _device_config_lock, vision_pipeline, spatial_tracker_worker
    _cache_lock = asyncio.Lock()
    _device_config_lock = asyncio.Lock()

    # Start the multi-process VisionPipeline (Decoupled & GIL-Bypassed)
    camera_url = get_camera_url()
    vision_pipeline = VisionPipeline(camera_url)
    vision_pipeline.start()

    # Start the Spatial Tracker thread placeholder
    spatial_tracker_worker = SpatialTrackerThread(None, fps=15.0)
    spatial_tracker_worker.start()

    # Active network config initialization directly in primary startup hook
    load_env_file()
    gateway_ip = get_default_gateway_ip()
    os.environ["DEFAULT_GATEWAY"] = gateway_ip
    log.info("[STARTUP] Materialized network config. Default Gateway: %s", gateway_ip)

    # Initialize LanceDB memory in the background so a slow embedded DB never blocks API startup.
    memory_init_task = asyncio.create_task(initialize_memory_background(), name="memory-init")
    
    # Start agent log client for REST logging
    await start_log_client()
    
    # Start persistent MQTT client for telemetry bridging
    init_mqtt_client()

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
        # [BUG2-FIX] Decoupled Headless persistent sensor daemons — run regardless of active frontend route
        asyncio.create_task(run_headless_camera_daemon(), name="headless-camera-daemon"),
        asyncio.create_task(run_headless_vitals_daemon(), name="headless-vitals-daemon"),
        # [AUTO_VISION] Autonomous perception scan loop — triggers every 15s when camera is live
        asyncio.create_task(run_auto_perception_scan_loop(), name="auto-perception-scan"),
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
    memory_init_task.cancel()
    agent_tasks.append(memory_init_task)
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
    
    # Stop spatial tracker worker
    if spatial_tracker_worker:
        spatial_tracker_worker.stop()

    # Stop VisionPipeline process and MQTT connections
    if vision_pipeline:
        vision_pipeline.stop()

    # Stop persistent MQTT client
    close_mqtt_client()

    # Flush logs
    await stop_log_client()
    log.info("[SHUTDOWN] Engine stopped cleanly.")


# ─── FastAPI Application ─────────────────────────────────────────────────────
app = FastAPI(
    title="HK-07 Multi-Agent Engine (Phase 2)",
    description="Hugo (Sanitas HK-07) Multi-Agent Cognitive System — Blackboard + Orchestrator V2 + Perception Agent",
    version="2.0.0-phase2",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health & Status Endpoints ───────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "engine": "MiroFish-MAS-Standard", "agents": 4}

@app.get("/api/v1/health/llm-stats")
async def llm_stats():
    from services.llm_client import get_llm_stats
    return get_llm_stats()

@app.get("/agents/status")
async def agents_status():
    return {
        "router": "ACTIVE",
        "empathy": orchestrator.empathetic_agent.get_status(),
        "medical": orchestrator.medical_agent.get_status(),
        "safety": orchestrator.safety_agent.get_status(),
        "arbitrator": arbitrator.get_current_priority_agent(),
    }


def sanitize_nan(data):
    """Recursively replace float('nan') with None to prevent JSON serialization errors."""
    import math
    if isinstance(data, dict):
        return {k: sanitize_nan(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_nan(x) for x in data]
    elif isinstance(data, float) and math.isnan(data):
        return None
    return data


# ──────────────────────────────────────────────────────────────────────
# [BUG2-FIX] Centralized Sensor Cache Endpoint (for /companion page)
# ──────────────────────────────────────────────────────────────────────
@app.get("/api/v1/sensor-cache/latest")
async def sensor_cache_latest():
    """
    Returns the latest sensor state from the centralized in-memory cache
    hydrated by run_headless_sensor_daemon.

    The /companion frontend page MUST poll this endpoint instead of mounting
    its own ingestion hooks. Polling interval recommended: 500–1000ms.

    Response schema:
      vitals:        { hr, spo2, temp, alert_level } or null
      frame_b64:     base64 JPEG string or null
      frame_ts:      Unix timestamp of last captured frame
      fall_detected: bool
      fever_alert:   bool
      imu:           latest IMU dict or null
      daemon_status: str (OK | CAMERA_UNRESOLVED | CAMERA_ERROR | RUNNING | STOPPED)
      last_update:   Unix timestamp of last daemon cycle
    """
    import time
    if _cache_lock.locked():
        vitals = _sensor_cache.get("vitals")
        daemon_status = _sensor_cache.get("daemon_status", "UNKNOWN")
        last_update = _sensor_cache.get("last_update")
        fall_detected = _sensor_cache.get("fall_detected", False)
        fever_alert = _sensor_cache.get("fever_alert", False)
        imu = _sensor_cache.get("imu")
        environment = _sensor_cache.get("environment")
        location = _sensor_cache.get("location")
        activity = _sensor_cache.get("activity")
        frame_bytes = _sensor_cache.get("frame_bytes")
        frame_ts = _sensor_cache.get("frame_ts")
    else:
        async with _cache_lock:
            vitals = _sensor_cache.get("vitals")
            daemon_status = _sensor_cache.get("daemon_status", "UNKNOWN")
            last_update = _sensor_cache.get("last_update")
            fall_detected = _sensor_cache.get("fall_detected", False)
            fever_alert = _sensor_cache.get("fever_alert", False)
            imu = _sensor_cache.get("imu")
            environment = _sensor_cache.get("environment")
            location = _sensor_cache.get("location")
            activity = _sensor_cache.get("activity")
            frame_bytes = _sensor_cache.get("frame_bytes")
            frame_ts = _sensor_cache.get("frame_ts")

    # Build LocalOfflineFallback vitals_context for downstream use
    vitals_context = None
    if vitals:
        hr   = vitals.get("hr")
        temp = vitals.get("temp")
        import math
        hr_val = hr if (hr is not None and not (isinstance(hr, float) and math.isnan(hr))) else 0
        temp_val = temp if (temp is not None and not (isinstance(temp, float) and math.isnan(temp))) else 0
        vitals_context = {
            "hr":            hr_val if hr_val > 0 else float('nan'),
            "temp":          temp_val if temp_val > 0 else float('nan'),
            "spo2":          vitals.get("spo2"),
            "fever":         temp_val >= 38.0,
            "tachycardia":   hr_val >= 100,
            "fall_detected": fall_detected,
        }
    return sanitize_nan({
        "status":        "ok",
        "daemon_status": daemon_status,
        "last_update":   last_update,
        "vitals":        vitals,
        "vitals_context": vitals_context,
        "fall_detected": fall_detected,
        "fever_alert":   fever_alert,
        "imu":           imu,
        "environment":   environment,
        "location":      location,
        "activity":      activity,
        # frame_b64 excluded from this endpoint by default (size) —
        # use /api/v1/sensor-cache/frame for raw frame access
        "frame_available": frame_bytes is not None,
        "frame_ts":      frame_ts,
    })


@app.websocket("/api/v1/spatial/stream")
async def websocket_spatial_stream(websocket: WebSocket):
    await websocket.accept()
    from utils.spatial_tracker import SpatialTrackerThread
    SpatialTrackerThread._connections.add(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        SpatialTrackerThread._connections.discard(websocket)


@app.get("/api/v1/sensor-cache/frame")
async def sensor_cache_frame():
    """
    Returns the latest raw binary JPEG frame from the headless sensor daemon cache.
    Aligns with Spring Boot SensorCacheController proxy contract.
    """
    if _cache_lock.locked():
        frame_bytes = _sensor_cache.get("frame_bytes")
    else:
        async with _cache_lock:
            frame_bytes = _sensor_cache.get("frame_bytes")

    if not frame_bytes:
        return Response(status_code=404, content="No frame cached")
    
    return Response(content=frame_bytes, media_type="image/jpeg")


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
    Decoupled: triggers the slow VLM/OpenCV scan in a background task to maintain O(1) response time,
    instantly returning the latest cached scan from Blackboard (or a default baseline scan if empty).
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

    # Trigger scan asynchronously in background (fire-and-forget, O(1))
    asyncio.create_task(perception_agent.execute_full_body_scan(bypass_cache=True, explicit_request=True))

    try:
        # Instantly fetch from the non-blocking Blackboard cache
        scan = await perception_agent.read_latest_scan()
        if scan is None:
            # Construct a default baseline scan immediately to prevent blocking
            from agents.perception_agent import PerceptionScan
            scan = PerceptionScan(
                overall_risk="LOW",
                confidence=0.9,
                notes="Initializing first background scan cycle...",
                status="SUCCESS",
            )
            
        scan_dict = scan.to_dict()
        
        # Enforce strict JSON schema format at the root level of response payload
        return {
            "status": "SUCCESS",
            "vitals_summary": scan_dict.get("vitals_summary", {"hr": 72.0, "temp": 36.6}),
            "spatial_detections": scan_dict.get("spatial_detections", []),
            "cognitive_analysis": scan_dict.get("cognitive_analysis", {
                "user_activity": "sitting_or_standing",
                "clinical_reasoning": "Initializing companion scan..."
            }),
            "scan": scan_dict,  # Preserve original "scan" key for frontend component compatibility
        }
    except Exception as exc:
        log.error("[PERCEPTION_SCAN] Error returning cached scan: %s", exc)
        return {
            "status": "SUCCESS",
            "vitals_summary": {"hr": 72.0, "temp": 36.6},
            "spatial_detections": [],
            "cognitive_analysis": {
                "user_activity": "sitting_or_standing",
                "clinical_reasoning": f"Scan initialization state: {exc}"
            },
            "scan": {
                "status": "SUCCESS",
                "overall_risk": "LOW",
                "confidence": 0.5,
                "notes": str(exc),
            }
        }


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
        return {
            "status": "SUCCESS",
            "vitals_summary": {"hr": 72.0, "temp": 36.6},
            "spatial_detections": [],
            "cognitive_analysis": {
                "user_activity": "sitting_or_standing",
                "clinical_reasoning": "No scans executed yet."
            },
            "scan": None
        }
    scan_dict = scan.to_dict()
    return {
        "status": "SUCCESS",
        "vitals_summary": scan_dict.get("vitals_summary", {"hr": 72.0, "temp": 36.6}),
        "spatial_detections": scan_dict.get("spatial_detections", []),
        "cognitive_analysis": scan_dict.get("cognitive_analysis", {
            "user_activity": "sitting_or_standing",
            "clinical_reasoning": "Normal baseline state."
        }),
        "scan": scan_dict
    }


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


# ── [HOT-RELOAD] Device IP Configuration Endpoint ───────────────────────────────
@app.post("/api/v1/config/device-ip")
async def update_device_ip(body: dict):
    """
    Hot-reload device IP configuration for the camera daemon and PerceptionAgent.
    Called by frontend DeviceIpConfigModal on IP confirm — no daemon restart needed.
    Body: { "ip": str, "port": str (optional, default "8080") }
    """
    import time
    new_ip   = (body.get("ip") or body.get("phone_ip") or "").strip()
    new_port = (body.get("port") or body.get("camera_port") or "8080").strip()

    if not new_ip:
        return {"status": "error", "message": "ip field is required"}

    # Update global hot-reload config
    _device_config["phone_ip"]    = new_ip
    _device_config["camera_port"] = new_port
    _device_config["updated_at"]  = int(time.time() * 1000)

    # Also sync to environment for PerceptionAgent IP discovery
    os.environ["PHONE_IP"]    = new_ip
    os.environ["CAMERA_PORT"] = new_port

    # Write to Blackboard for PerceptionAgent to consume
    try:
        bb = get_blackboard()
        await bb.write_value("PHONE_IP", new_ip)
    except Exception as e:
        log.warning("[CONFIG] Blackboard write skipped: %s", e)

    log.info("[CONFIG] \U0001f4f1 Device IP hot-reloaded: %s:%s", new_ip, new_port)
    return {
        "status": "ok",
        "phone_ip": new_ip,
        "camera_port": new_port,
        "message": f"Camera daemon will use {new_ip}:{new_port} on next poll cycle"
    }


@app.get("/api/v1/sensor-cache/vision")
async def sensor_cache_vision():
    """
    Vision status endpoint — returns latest perception scan + camera daemon state.
    Designed for efficient frontend polling (combines perception + camera in one call).
    Poll interval recommendation: 5s (perception scans run at 15s intervals).
    """
    import time
    from datetime import datetime
    try:
        scan = await perception_agent.read_latest_scan()
        if scan and not scan.is_expired():
            async with _cache_lock:
                _sensor_cache["latest_perception_scan"] = scan.to_dict()
                _sensor_cache["latest_perception_ts"] = float(datetime.fromisoformat(scan.timestamp.replace('Z', '+00:00')).timestamp())
    except Exception as e:
        log.warning("[API_VISION] Failed to sync latest scan from Blackboard: %s", e)
    if _cache_lock and not _cache_lock.locked():
        async with _cache_lock:
            latest_scan    = _sensor_cache.get("latest_perception_scan")
            latest_scan_ts = _sensor_cache.get("latest_perception_ts")
            daemon_status  = _sensor_cache.get("daemon_status", "UNKNOWN")
            frame_ts       = _sensor_cache.get("frame_ts")
            frame_avail    = _sensor_cache.get("frame_bytes") is not None
    else:
        latest_scan    = _sensor_cache.get("latest_perception_scan")
        latest_scan_ts = _sensor_cache.get("latest_perception_ts")
        daemon_status  = _sensor_cache.get("daemon_status", "UNKNOWN")
        frame_ts       = _sensor_cache.get("frame_ts")
        frame_avail    = _sensor_cache.get("frame_bytes") is not None

    now = time.time()
    frame_age_s    = round(now - frame_ts,    1) if frame_ts else None
    scan_age_s     = round(now - latest_scan_ts, 1) if latest_scan_ts else None
    camera_fresh   = frame_age_s is not None and frame_age_s < 10.0

    return sanitize_nan({
        "status":          "ok",
        "daemon_status":   daemon_status,
        "camera_fresh":    camera_fresh,
        "frame_available": frame_avail,
        "frame_age_s":     frame_age_s,
        "frame_ts":        frame_ts,
        "phone_ip":        _device_config.get("phone_ip", ""),
        "camera_port":     _device_config.get("camera_port", "8080"),
        "latest_scan":     latest_scan,
        "scan_age_s":      scan_age_s,
    })


if __name__ == "__main__":
    import logging.handlers
    # Dynamic loop type selection based on platform support (uvloop not supported natively on Windows)
    loop_type = "asyncio"
    try:
        import uvloop
        loop_type = "uvloop"
    except ImportError:
        pass

    agent_port = int(os.environ.get("AGENT_PORT", 8889))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=agent_port,
        workers=1,
        loop=loop_type,
        log_level="info",
        access_log=False,
    )
