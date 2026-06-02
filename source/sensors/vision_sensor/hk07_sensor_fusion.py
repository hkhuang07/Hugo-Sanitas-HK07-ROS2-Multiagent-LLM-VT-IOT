import os
import sys
import cv2
import json
import time
import math
import random
import logging
import asyncio
import concurrent.futures
from contextlib import asynccontextmanager

# Set SelectorEventLoop on Windows to support aiomqtt (ProactorEventLoop doesn't support add_reader)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from fastapi import FastAPI, Request
import uvicorn
import aiomqtt
import mediapipe as mp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("hk07_fusion")

# ─────────────────────────────────────────────────────────────────────────────
# NETWORK & CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
IP_DIEN_THOAI = "10.129.151.70"
CAMERA_URL = f"http://{IP_DIEN_THOAI}:8080/video"

MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "hk07sim")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")

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

state = FusionState()

# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASK 1: ASYNC MQTT PUBLISHER
# ─────────────────────────────────────────────────────────────────────────────
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
                        is_falling_now = (g < 4.0) or (g > 20.0)
                        
                        if is_falling_now:
                            state.last_fall_time = now
                            log.warning(f"[ACCEL_ALERT] Fall G-force: {g:.2f} m/s^2")
                            
                        state.is_falling = (now - state.last_fall_time) < FALL_COOLDOWN_SEC
                        state.is_night_mode = state.light_lux < 10.0
                        state.obstacle_warning = state.proximity < 2.0
                        state.imu_online = True
                        
                    elif event_type == "VISION_TELEMETRY":
                        state.vision_fall = event.get("vision_fall", False)
                        state.vision_online = event.get("online", False)
                    
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
    
    log.info("[VISION_WORKER] Initializing OpenCV camera loop...")
    
    while True:
        try:
            log.info(f"[VISION_WORKER] Connecting to video feed: {CAMERA_URL}")
            cap = cv2.VideoCapture(CAMERA_URL)
            
            if not cap.isOpened():
                log.warning("[VISION_WORKER] Camera is OFFLINE.")
                # Report degradation cleanly to the queue
                asyncio.run_coroutine_threadsafe(
                    event_queue.put({"type": "VISION_TELEMETRY", "vision_fall": False, "online": False}),
                    loop
                )
                time.sleep(5.0)
                continue
                
            # Camera successfully online
            with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        log.warning("[VISION_WORKER] Video stream dropped.")
                        break
                    
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
                    asyncio.run_coroutine_threadsafe(
                        event_queue.put({"type": "VISION_TELEMETRY", "vision_fall": vision_fall, "online": True}),
                        loop
                    )
                    
                    # Render UI safely
                    try:
                        cv2.imshow("HK-07 Vision System", image)
                    except Exception:
                        pass
                        
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        log.info("[VISION_WORKER] Quit command.")
                        cap.release()
                        cv2.destroyAllWindows()
                        os._exit(0)
                        
            cap.release()
            asyncio.run_coroutine_threadsafe(
                event_queue.put({"type": "VISION_TELEMETRY", "vision_fall": False, "online": False}),
                loop
            )
            time.sleep(2.0)
            
        except Exception as e:
            log.error(f"[VISION_WORKER] Process failed: {e}")
            asyncio.run_coroutine_threadsafe(
                event_queue.put({"type": "VISION_TELEMETRY", "vision_fall": False, "online": False}),
                loop
            )
            time.sleep(5.0)

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP (TELEMETRY SERVER)
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # App Startup
    log.info("=== HK-07 ASYNC SENSOR FUSION BRIDGE ===")
    log.info(f"Target phone IP: {IP_DIEN_THOAI}")
    
    # 1. Launch MQTT Task
    app.state.mqtt_task = asyncio.create_task(mqtt_publisher_task())
    
    # 2. Launch Vision Worker in ThreadPoolExecutor
    loop = asyncio.get_running_loop()
    app.state.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    app.state.vision_task = loop.run_in_executor(app.state.executor, blocking_vision_worker, loop)
    
    yield
    
    # App Shutdown
    log.info("Shutting down fusion bridge...")
    app.state.mqtt_task.cancel()
    app.state.executor.shutdown(wait=False)

app = FastAPI(lifespan=lifespan)

@app.post("/data")
async def handle_telemetry_post(request: Request):
    try:
        data = await request.json()
        if not data or "payload" not in data:
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
    # Start the robust Uvicorn server
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="warning")
