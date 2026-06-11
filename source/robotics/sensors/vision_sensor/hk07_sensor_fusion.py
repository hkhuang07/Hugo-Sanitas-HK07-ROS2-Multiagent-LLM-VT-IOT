import os
import sys

# Suppress C++ system logging from TensorFlow/MediaPipe and silence warning streams
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'

import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import cv2
import json
import time
import math
import random
import logging
import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
import base64

# Configure logging first to prevent NameError in imports
# Configure logging robustly by forcing root logger setup
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)
h_stream = logging.StreamHandler(sys.stdout)
h_stream.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s"))
root_logger.addHandler(h_stream)
log = logging.getLogger("hk07_fusion")

# Dynamic directory traversal to find the agent directory for imports
def get_agent_dir():
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        checks = [
            os.path.join(curr, "backend", "hk07-agent"),
            os.path.join(curr, "source", "backend", "hk07-agent"),
        ]
        for path in checks:
            if os.path.isdir(path):
                return os.path.abspath(path)
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return None

agent_dir = get_agent_dir()
if agent_dir:
    sys.path.append(agent_dir)

try:
    from services.llm_client import LLMClient, VISION_TIERS
    log.info("[VISION_LLM] LLMClient loaded successfully.")
except ImportError as ie:
    log.error(f"[VISION_LLM] Failed to load LLMClient: {ie}")
    LLMClient = None
    VISION_TIERS = []

# Set SelectorEventLoop on Windows to support aiomqtt (ProactorEventLoop doesn't support add_reader)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from fastapi import FastAPI, Request
import uvicorn
import aiomqtt
import mediapipe as mp

# ─────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT & CONFIGURATION RESOLUTION (Parent Traversal search)
# ─────────────────────────────────────────────────────────────────────────────
def load_env_file():
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        checks = [
            os.path.join(curr_dir, "backend", ".env"),
            os.path.join(curr_dir, "source", "backend", ".env"),
            os.path.join(curr_dir, ".env"),
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
                                if key and key not in os.environ:
                                    os.environ[key] = val
                    log.info(f"Loaded environment variables from {path}")
                    return True
                except Exception as e:
                    log.warning(f"Failed to read .env at {path}: {e}")
        parent = os.path.dirname(curr_dir)
        if parent == curr_dir:
            break
        curr_dir = parent
    return False

load_env_file()
log.info(f"[SYSTEM] DISPLAY={os.environ.get('DISPLAY')}, WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY')}")

import argparse
parser = argparse.ArgumentParser(description="HK-07 Sensor Fusion Bridge", add_help=False)
parser.add_argument("--phone-ip", dest="phone_ip", type=str, default=os.getenv("PHONE_IP", "192.168.210.17"), help="IP address of the phone")
parser.add_argument("--port", type=int, default=int(os.getenv("FUSION_PORT", "5005")), help="Port to run the fusion server on")
parser.add_argument("--mqtt-host", dest="mqtt_host", type=str, default=os.getenv("MQTT_BROKER_HOST", "localhost"), help="MQTT broker host")
parser.add_argument("--mqtt-port", dest="mqtt_port", type=int, default=int(os.getenv("MQTT_BROKER_PORT", "1883")), help="MQTT broker port")
parser.add_argument("--mqtt-user", dest="mqtt_user", type=str, default=os.getenv("MQTT_USERNAME", "hk07sim"), help="MQTT username")
parser.add_argument("--mqtt-pass", dest="mqtt_pass", type=str, default=os.getenv("MQTT_PASSWORD", ""), help="MQTT password")

def _is_wsl2_virtual_ip(ip: str) -> bool:
    """Return True if IP is in WSL2 / Hyper-V virtual adapter range (172.16.0.0/12)."""
    import struct
    try:
        packed = struct.unpack("!I", socket.inet_aton(ip))[0]
        return 0xAC100000 <= packed <= 0xAC1FFFFF
    except Exception:
        return False

def _is_valid_gateway(ip: str) -> bool:
    try:
        socket.inet_aton(ip)
        return ip not in ("0.0.0.0", "127.0.0.1", "255.255.255.255") and not _is_wsl2_virtual_ip(ip)
    except Exception:
        return False

def detect_phone_gateway_ip():
    import subprocess
    import socket

    # Strategy 1: PowerShell targeting Wi-Fi adapter only (no inner single quotes — WSL2 fix)
    try:
        cmd = ["powershell.exe", "-NoProfile", "-Command",
               "Get-NetRoute -DestinationPrefix 0.0.0.0/0 -InterfaceAlias Wi-Fi | Select-Object -ExpandProperty NextHop"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode("utf-8").strip()
        for ip in out.split():
            if _is_valid_gateway(ip):
                return ip
    except Exception:
        pass

    # Strategy 2: All routes via PowerShell, skip WSL2 172.16.0.0/12 range
    try:
        cmd = ["powershell.exe", "-NoProfile", "-Command",
               "Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Select-Object -ExpandProperty NextHop"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode("utf-8").strip()
        for ip in out.split():
            if _is_valid_gateway(ip):
                return ip
    except Exception:
        pass

    # Strategy 3: Linux ip route (pure Linux without WSL2)
    try:
        import sys
        if sys.platform != "win32":
            out = subprocess.check_output("ip route show default", shell=True, timeout=3).decode("utf-8").strip()
            for line in out.splitlines():
                if "default via" in line:
                    parts = line.split()
                    idx = parts.index("via")
                    if idx + 1 < len(parts):
                        gw = parts[idx + 1]
                        if _is_valid_gateway(gw):
                            return gw
    except Exception:
        pass
    return None

args, unknown = parser.parse_known_args()

# Check if user explicitly passed --phone-ip on command line
user_override = any(arg.startswith("--phone-ip") for arg in sys.argv)
detected_ip = detect_phone_gateway_ip()

if not user_override and detected_ip:
    log.info(f"┌────────────────────────────────────────────────────────┐")
    log.info(f"│ [CONNECTED_PHONE_GATEWAY] Hotspot Phone Gateway detected │")
    log.info(f"│ IP: {detected_ip:<50} │")
    log.info(f"│ Auto-configuring IP_DIEN_THOAI to match gateway.      │")
    log.info(f"└────────────────────────────────────────────────────────┘")
    IP_DIEN_THOAI = detected_ip
else:
    IP_DIEN_THOAI = args.phone_ip

FUSION_PORT = args.port
MQTT_BROKER = args.mqtt_host
MQTT_PORT = args.mqtt_port
MQTT_USER = args.mqtt_user
MQTT_PASS = args.mqtt_pass

CAMERA_URL = f"http://{IP_DIEN_THOAI}:8080/video"

PRIMARY_TOPIC = "hk07/vitals/wristband"
COMPAT_TOPIC = "hk07/sensors/wristband/wristband-sim-001/vitals"

FALL_COOLDOWN_SEC = 3.0

# ─────────────────────────────────────────────────────────────────────────────
# EVENT-DRIVEN STATE & QUEUES
# ─────────────────────────────────────────────────────────────────────────────
event_queue = asyncio.Queue()

# Internal state mutated safely in the single asyncio event loop
class FusionState:
    def __init__(self):
        self.accel_x = 0.0
        self.accel_y = 0.0
        self.accel_z = 9.81
        self.light_lux = 15.0
        self.proximity = 5.0
        self.is_falling = False
        self.last_fall_time = 0.0
        self.is_night_mode = False
        self.obstacle_warning = False
        self.vision_fall = False
        self.vision_online = False
        self.imu_online = True # Assumed true if server running
        self.g_ema = None
        self.latest_frame = None

state = FusionState()

# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASK 1: ASYNC MQTT PUBLISHER & SUBSCRIBER
# ─────────────────────────────────────────────────────────────────────────────
async def mqtt_subscriber_loop(client):
    try:
        # Subscribe to IMU topic published by vivo_http_mqtt_bridge.py
        await client.subscribe("hk07/sensors/imu/state")
        log.info("[MQTT_SUBSCRIBER] Subscribed to topic: hk07/sensors/imu/state")
        
        async for message in client.messages:
            try:
                payload_data = json.loads(message.payload.decode())
                # Push event to queue for immediate fusion
                await event_queue.put({
                    "type": "IMU_TELEMETRY",
                    "accel_x": payload_data.get("accel_x", 0.0),
                    "accel_y": payload_data.get("accel_y", 0.0),
                    "accel_z": payload_data.get("accel_z", 9.81),
                    # Fallbacks for other telemetry
                    "light_lux": payload_data.get("light_lux", 15.0),
                    "proximity": payload_data.get("proximity", 5.0)
                })
            except Exception as parse_err:
                log.error(f"[MQTT_SUBSCRIBER] Parse error: {parse_err}")
    except Exception as sub_err:
        log.error(f"[MQTT_SUBSCRIBER] Subscription loop error: {sub_err}")

async def mqtt_publisher_task():
    log.info("[MQTT_PUBLISHER] Task started. Waiting for events...")
    
    while True:
        try:
            # aiomqtt handles auto-reconnect gracefully within the context manager
            async with aiomqtt.Client(
                hostname=MQTT_BROKER,
                port=MQTT_PORT,
                username=MQTT_USER,
                password=MQTT_PASS,
                identifier="hk07-vision-publisher"
            ) as client:
                log.info(f"[MQTT] Connected to broker {MQTT_BROKER}:{MQTT_PORT}")
                
                # Auto-failover: activate subscriber if port 5005 is occupied
                use_sub = False
                try:
                    use_sub = app.state.use_mqtt_subscriber
                except Exception:
                    pass
                    
                if use_sub:
                    log.info("[MQTT_SUBSCRIBER] Activating IMU MQTT Subscriber mode...")
                    asyncio.create_task(mqtt_subscriber_loop(client))
                
                while True:
                    # Sleep (0% CPU) until an event is pushed into the queue
                    event = await event_queue.get()
                    
                    event_type = event.get("type")
                    now = time.time()
                    
                    if event_type == "IMU_TELEMETRY":
                        state.accel_x = event.get("accel_x", state.accel_x)
                        state.accel_y = event.get("accel_y", state.accel_y)
                        state.accel_z = event.get("accel_z", state.accel_z)
                        state.light_lux = event.get("light_lux", state.light_lux)
                        state.proximity = event.get("proximity", state.proximity)
                        
                        g = math.sqrt(state.accel_x**2 + state.accel_y**2 + state.accel_z**2)
                        
                        if state.g_ema is None:
                            state.g_ema = g
                        else:
                            state.g_ema = 0.9 * state.g_ema + 0.1 * g
                            
                        is_linear = (state.g_ema < 3.0)
                        
                        if is_linear:
                            is_falling_now = (g > 15.0)
                        else:
                            is_falling_now = (g < 4.0) or (g > 20.0)
                        
                        if is_falling_now:
                            state.last_fall_time = now
                            log.warning(f"[ACCEL_ALERT] Fall G-force: {g:.2f} m/s^2 [Mode: {'LINEAR' if is_linear else 'RAW'}]")
                            
                        state.is_falling = (now - state.last_fall_time) < FALL_COOLDOWN_SEC
                        state.is_night_mode = state.light_lux < 10.0
                        state.obstacle_warning = state.proximity < 2.0
                        state.imu_online = True
                        
                    elif event_type == "VISION_TELEMETRY":
                        state.vision_fall = event.get("vision_fall", False)
                        state.vision_online = event.get("online", False)
                    
                    elif event_type == "CLINICAL_PERCEPTION":
                        payload = event.get("payload")
                        await client.publish("hk07/perception/clinical", json.dumps(payload), qos=1)
                        log.info(f"[PUBLISH] Clinical perception updated: {payload}")
                        event_queue.task_done()
                        continue
                    
                    master_emergency = state.is_falling or state.vision_fall
                    
                    # Generate logical vitals based on emergency
                    hr = random.randint(70, 80) if not master_emergency else random.randint(130, 160)
                    spo2 = random.randint(95, 99) if not master_emergency else random.randint(88, 92)
                    
                    payload = {
                        "heartRate": hr,
                        "systolic": 120.0 if not master_emergency else 165.0,
                        "diastolic": 80.0 if not master_emergency else 105.0,
                        "bodyTemperature": 36.6 if not master_emergency else 37.9,
                        "spo2": float(spo2),
                        "emergency_button_pressed": master_emergency,
                        "is_falling": state.is_falling,
                        "vision_fall_detected": state.vision_fall,
                        "is_night_mode": state.is_night_mode,
                        "obstacle_warning": state.obstacle_warning,
                        "light_lux": state.light_lux,
                        "proximity": state.proximity,
                        "accelerometer": {
                            "x": state.accel_x,
                            "y": state.accel_y,
                            "z": state.accel_z
                        },
                        "sensor_health": {
                            "vision": "ONLINE" if state.vision_online else "OFFLINE",
                            "imu": "ONLINE" if state.imu_online else "OFFLINE"
                        },
                        "timestamp_ms": int(now * 1000)
                    }
                    
                    await client.publish(PRIMARY_TOPIC, json.dumps(payload), qos=1)
                    await client.publish(COMPAT_TOPIC, json.dumps(payload), qos=1)
                    
                    log.info(f"[PUBLISH] SOS={master_emergency} (Sens={state.is_falling}, Cam={state.vision_fall}) | Health: Vis={payload['sensor_health']['vision']} IMU={payload['sensor_health']['imu']}")
                    
                    event_queue.task_done()
                    
        except aiomqtt.MqttError as e:
            log.warning(f"[MQTT] Connection lost: {e}. Reconnecting in 3 seconds...")
            await asyncio.sleep(3.0)
        except Exception as e:
            log.error(f"[MQTT] Fatal publisher error: {e}")
            await asyncio.sleep(3.0)


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASK 2: COMPUTER VISION THREAD POOL WORKER
# ─────────────────────────────────────────────────────────────────────────────
def blocking_vision_worker(loop):
    """
    Runs isolated in a ThreadPoolExecutor. Heavy CPU bound operations (OpenCV/MediaPipe)
    will not block the FastAPI or MQTT async event loop.
    """
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    
    def safe_submit_event(event):
        if loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(event_queue.put(event), loop)
            except Exception as e:
                log.debug(f"[VISION_WORKER] Failed to submit event: {e}")
        else:
            log.debug(f"[VISION_WORKER] Loop not running, discarding event: {event}")
            
    log.info("[VISION_WORKER] Initializing OpenCV camera loop...")
    
    while True:
        if not loop.is_running():
            log.info("[VISION_WORKER] Event loop is no longer running. Exiting worker thread.")
            break
            
        try:
            log.info(f"[VISION_WORKER] Connecting to video feed: {CAMERA_URL}")
            cap = cv2.VideoCapture(CAMERA_URL)
            
            if not cap.isOpened():
                log.warning("[VISION_WORKER] Camera is OFFLINE.")
                # Report degradation cleanly to the queue
                safe_submit_event({"type": "VISION_TELEMETRY", "vision_fall": False, "online": False})
                time.sleep(5.0)
                continue
                
            # Camera successfully online
            with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
                while cap.isOpened() and loop.is_running():
                    ret, frame = cap.read()
                    if not ret:
                        log.warning("[VISION_WORKER] Video stream dropped.")
                        break
                    
                    # Store latest frame for the LLM Vision snapshot analyzer
                    state.latest_frame = frame.copy()
                    
                    # Save frame immediately to shared file buffer
                    try:
                        cv2.imwrite("d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/latest_frame.jpg", frame)
                    except Exception as e:
                        log.error(f"[VISION_WORKER] Failed to save frame: {e}")
                    
                    # Resize frame to reduce CPU load and display a smaller window
                    h, w = frame.shape[:2]
                    scale = 0.5
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                        
                    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image.flags.writeable = False
                    results = pose.process(image)
                    image.flags.writeable = True
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                    
                    vision_fall = False
                    
                    if results.pose_landmarks:
                        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                        landmarks = results.pose_landmarks.landmark
                        try:
                            nose_y = landmarks[mp_pose.PoseLandmark.NOSE].y
                            left_hip_y = landmarks[mp_pose.PoseLandmark.LEFT_HIP].y
                            right_hip_y = landmarks[mp_pose.PoseLandmark.RIGHT_HIP].y
                            hip_y = (left_hip_y + right_hip_y) / 2.0
                            
                            if nose_y > hip_y:
                                vision_fall = True
                                cv2.putText(
                                    image, "VISION: FALL DETECTED", (15, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA
                                )
                        except IndexError:
                            pass
                            
                    # Fire event safely back to the Asyncio loop
                    safe_submit_event({"type": "VISION_TELEMETRY", "vision_fall": vision_fall, "online": True})
                    
                    # Render UI safely
                    try:
                        cv2.imshow("HK-07 Vision System", image)
                    except Exception as e:
                        log.error(f"[VISION_WORKER] cv2.imshow exception: {e}")
                        
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        log.info("[VISION_WORKER] Quit command.")
                        cap.release()
                        cv2.destroyAllWindows()
                        os._exit(0)
                        
            cap.release()
            safe_submit_event({"type": "VISION_TELEMETRY", "vision_fall": False, "online": False})
            time.sleep(2.0)
            
        except Exception as e:
            if not loop.is_running():
                log.info("[VISION_WORKER] Process exception handler caught closed loop. Exiting.")
                break
            log.error(f"[VISION_WORKER] Process failed: {e}")
            safe_submit_event({"type": "VISION_TELEMETRY", "vision_fall": False, "online": False})
            time.sleep(5.0)

# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASK 3: CLINICAL LLM VISION SNAPSHOT ANALYZER (5s interval)
# ─────────────────────────────────────────────────────────────────────────────
async def analyze_frame_with_vision(frame):
    if LLMClient is None:
        log.warning("[VISION_LLM] LLMClient is not available. Skipping frame analysis.")
        return

    try:
        # Encode image to base64 jpeg
        _, buffer = cv2.imencode('.jpg', frame)
        base64_image = base64.b64encode(buffer).decode('utf-8')

        prompt = (
            "Analyze the patient in the frame. "
            "You must look for: \n"
            "1. Visible injuries (e.g., cuts, bruises, bleeding, wounds).\n"
            "2. Facial distress/pallor (e.g., pain expression, sweating, extreme paleness).\n"
            "3. Environmental hazards (e.g., sharp objects nearby, wet floor, clutter, fall risks).\n\n"
            "Return ONLY a pure JSON object conforming to this schema, with no markdown code block tags or extra explanation:\n"
            "{\n"
            '  "visible_injuries": {"detected": boolean, "details": "string or null"},\n'
            '  "facial_distress": {"detected": boolean, "details": "string or null"},\n'
            '  "environmental_hazards": {"detected": boolean, "details": "string or null"}\n'
            "}"
        )

        log.info("[VISION_LLM] Submitting snapshot to LLM Vision API...")
        result_str, provider = await LLMClient.generate_vision_completion(
            prompt=prompt,
            tiers=VISION_TIERS,
            image_base64=base64_image,
            system_prompt="You are a clinical assistant vision model. You must analyze the frame and return pure JSON.",
            max_tokens=256,
            temperature=0.1
        )

        if result_str:
            cleaned_str = result_str.strip()
            if cleaned_str.startswith("```"):
                lines = cleaned_str.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_str = "\n".join(lines).strip()
            
            try:
                parsed_json = json.loads(cleaned_str)
                log.info(f"[VISION_LLM] Received clinical result from {provider}: {parsed_json}")
                await event_queue.put({
                    "type": "CLINICAL_PERCEPTION",
                    "payload": parsed_json
                })
            except json.JSONDecodeError as jde:
                log.error(f"[VISION_LLM] JSON decode error: {jde}. Raw response was: {result_str}")
        else:
            log.warning("[VISION_LLM] Vision completion returned empty string or failed.")

    except Exception as e:
        log.error(f"[VISION_LLM] Exception in frame analysis: {e}")

async def snapshot_analyzer_loop():
    log.info("[VISION_LLM] Snapshot Analyzer loop active. Waiting for camera frames...")
    while True:
        try:
            await asyncio.sleep(5.0)
            if state.latest_frame is not None:
                # Capture frame copy to process in background
                frame_to_analyze = state.latest_frame.copy()
                # Run the async vision analysis
                asyncio.create_task(analyze_frame_with_vision(frame_to_analyze))
        except asyncio.CancelledError:
            log.info("[VISION_LLM] Snapshot Analyzer task cancelled.")
            break
        except Exception as e:
            log.error(f"[VISION_LLM] Error in snapshot loop: {e}")
            await asyncio.sleep(2.0)

# FASTAPI APP (TELEMETRY SERVER)
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # App Startup
    log.info("=== HK-07 ASYNC SENSOR FUSION BRIDGE ===")
    log.info(f"Target phone IP: {IP_DIEN_THOAI}")
    
    # 1. Launch MQTT Task
    app.state.mqtt_task = asyncio.create_task(mqtt_publisher_task())
    
    # 2. Launch LLM Vision Snapshot Analyzer Task
    app.state.snapshot_task = asyncio.create_task(snapshot_analyzer_loop())
    
    # 3. Launch Vision Worker in ThreadPoolExecutor
    loop = asyncio.get_running_loop()
    app.state.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    app.state.vision_task = loop.run_in_executor(app.state.executor, blocking_vision_worker, loop)
    
    yield
    
    # App Shutdown
    log.info("Shutting down fusion bridge...")
    app.state.mqtt_task.cancel()
    app.state.snapshot_task.cancel()
    app.state.executor.shutdown(wait=False)

app = FastAPI(lifespan=lifespan)

@app.post("/data")
@app.post("/")
async def handle_telemetry_post(request: Request):
    try:
        log.info(f"Received request from {request.client.host} to {request.url.path}")
        data = await request.json()
        log.info(f"Raw data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        if not data or "payload" not in data:
            log.warning(f"Payload not found in incoming JSON! Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            return {"status": "error", "message": "No payload"}
            
        payload = data.get("payload", [])
        
        accel_x, accel_y, accel_z = state.accel_x, state.accel_y, state.accel_z
        light_lux = state.light_lux
        proximity = state.proximity
        
        for item in payload:
            name = item.get("name")
            values = item.get("values", {})
            if name == "accelerometer":
                accel_x = values.get("x", accel_x)
                accel_y = values.get("y", accel_y)
                accel_z = values.get("z", accel_z)
            elif name == "light":
                light_lux = values.get("lux", light_lux)
            elif name == "proximity":
                proximity = values.get("proximity", proximity)
                
        # Push event to queue for immediate handling
        await event_queue.put({
            "type": "IMU_TELEMETRY",
            "accel_x": accel_x,
            "accel_y": accel_y,
            "accel_z": accel_z,
            "light_lux": light_lux,
            "proximity": proximity
        })
        
        return {"status": "ok"}
        
    except Exception as e:
        log.error(f"[TELEMETRY_ERROR] Error handling HTTP POST: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import socket
    
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return False
            except OSError:
                return True
                
    run_port = FUSION_PORT
    if is_port_in_use(run_port):
        log.warning(f"[SYSTEM] Port {run_port} is already occupied! Auto-activating Redundant MQTT Subscriber Mode for Sensor data...")
        app.state.use_mqtt_subscriber = True
        run_port = run_port + 1
        log.info(f"[SYSTEM] Swapping Fusion Server API port to {run_port}")
    else:
        log.info(f"[SYSTEM] Port {run_port} is free. Operating in Direct HTTP Receiver mode.")
        app.state.use_mqtt_subscriber = False
        
    # Start the robust Uvicorn server
    uvicorn.run(app, host="0.0.0.0", port=run_port, log_level="warning")
