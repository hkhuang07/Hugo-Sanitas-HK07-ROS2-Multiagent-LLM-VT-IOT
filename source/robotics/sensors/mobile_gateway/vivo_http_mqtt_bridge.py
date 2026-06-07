import os
import sys
import math
import time
import random
import logging
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt
import json

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("vivo_bridge")

app = Flask(__name__)

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

import argparse
parser = argparse.ArgumentParser(description="Vivo HTTP MQTT Bridge", add_help=False)
parser.add_argument("--port", type=int, default=int(os.getenv("BRIDGE_PORT", "5005")), help="Port to run the bridge server on")
parser.add_argument("--mqtt-host", dest="mqtt_host", type=str, default=os.getenv("MQTT_BROKER_HOST", "localhost"), help="MQTT broker host")
parser.add_argument("--mqtt-port", dest="mqtt_port", type=int, default=int(os.getenv("MQTT_BROKER_PORT", "1883")), help="MQTT broker port")
parser.add_argument("--mqtt-user", dest="mqtt_user", type=str, default=os.getenv("MQTT_USERNAME", "hk07sim"), help="MQTT username")
parser.add_argument("--mqtt-pass", dest="mqtt_pass", type=str, default=os.getenv("MQTT_PASSWORD", ""), help="MQTT password")

args, unknown = parser.parse_known_args()

BRIDGE_PORT = args.port
MQTT_BROKER = args.mqtt_host
MQTT_PORT = args.mqtt_port
MQTT_USER = args.mqtt_user
MQTT_PASS = args.mqtt_pass

DEVICE_ID = "wristband-sim-001"
VITALS_TOPIC = f"hk07/sensors/wristband/{DEVICE_ID}/vitals"
IMU_TOPIC = "hk07/sensors/imu/state"
TELEMETRY_IMU_TOPIC = "hk07/sensors/imu/target"

FALL_COOLDOWN_SEC = 3.0
last_fall_time = 0.0
g_ema = None

# Complementary filter state variables
filt_pitch = 0.0
filt_roll = 0.0
last_update_time = 0.0

# Initialize MQTT Client
mqtt_client = mqtt.Client(client_id="vivo-http-bridge", protocol=mqtt.MQTTv311)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

def connect_mqtt():
    try:
        log.info(f"Connecting to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}...")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        log.info("MQTT Loop started successfully.")
    except Exception as e:
        log.error(f"Failed to connect to MQTT broker: {e}. Bridge will try to publish later.")

connect_mqtt()

@app.route("/data", methods=["POST"])
@app.route("/", methods=["POST"])
def handle_sensor_data():
    global last_fall_time, g_ema
    
    try:
        log.info(f"Received request from {request.remote_addr} to {request.path}")
        data = request.get_json(force=True)
        log.info(f"Raw data size: {len(request.data)} bytes. Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        if not data or "payload" not in data:
            log.warning(f"Payload not found in incoming JSON! Keys received: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            return jsonify({"status": "error", "message": "Invalid JSON format: 'payload' key is required"}), 400
        
        payload_list = data.get("payload", [])
        
        # Default gravity acceleration
        x, y, z = 0.0, 0.0, 9.81
        found_accel = False
        
        # Parse accelerometer data
        for item in payload_list:
            if item.get("name") == "accelerometer":
                values = item.get("values", {})
                x = values.get("x", 0.0)
                y = values.get("y", 0.0)
                z = values.get("z", 9.81)
                found_accel = True
                break
        
        # Perform Fall Detection math
        g_magnitude = math.sqrt(x**2 + y**2 + z**2)
        
        if g_ema is None:
            g_ema = g_magnitude
        else:
            g_ema = 0.9 * g_ema + 0.1 * g_magnitude
            
        is_linear = (g_ema < 3.0)
        
        # Trigger fall state on sudden shifts
        if is_linear:
            # Linear Accelerometer mode: rest is ~0. High user acceleration (>15.0) means impact/movement.
            is_falling_now = (g_magnitude > 15.0)
        else:
            # Raw Accelerometer mode: rest is ~9.81. Weightlessness (<4.0) or high-g impact (>20.0).
            is_falling_now = (g_magnitude < 4.0) or (g_magnitude > 20.0)
            
        now_time = time.time()
        
        if is_falling_now:
            last_fall_time = now_time
            log.warning(f"[FALL DETECTED] Sudden acceleration change: {g_magnitude:.2f} m/s^2 (x: {x:.2f}, y: {y:.2f}, z: {z:.2f}) [Mode: {'LINEAR' if is_linear else 'RAW'}]")
            
        # Maintain fall state for a brief cooldown duration to allow downstream systems to react
        is_falling = (now_time - last_fall_time) < FALL_COOLDOWN_SEC
        timestamp_ms = int(now_time * 1000)
        
        # Compile Vitals Payload (Simulating companion data for ECG charts)
        vitals_payload = {
            "heartRate": random.randint(70, 80) if not is_falling else random.randint(130, 160),
            "systolic": 120.0 if not is_falling else 160.0,
            "diastolic": 80.0 if not is_falling else 100.0,
            "bodyTemperature": 36.6,
            "spo2": round(random.uniform(96.0, 99.0), 1) if not is_falling else round(random.uniform(88.0, 92.0), 1),
            "emergency_button_pressed": is_falling,
            "timestamp_ms": timestamp_ms
        }
        
        # Compile Raw IMU Payload
        imu_payload = {
            "accel_x": x,
            "accel_y": y,
            "accel_z": z,
            "timestamp_ms": timestamp_ms
        }
        
        # Check for direct quaternion or orientation in payload list
        qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
        found_quat = False
        for item in payload_list:
            name = item.get("name")
            values = item.get("values", {})
            if name in ("orientation", "quaternion"):
                qw = values.get("w", values.get("qw", 1.0))
                qx = values.get("x", values.get("qx", 0.0))
                qy = values.get("y", values.get("qy", 0.0))
                qz = values.get("z", values.get("qz", 0.0))
                found_quat = True
                break
                
        if not found_quat:
            # Check for gyroscope
            gx, gy, gz = 0.0, 0.0, 0.0
            found_gyro = False
            for item in payload_list:
                if item.get("name") == "gyroscope":
                    vals = item.get("values", {})
                    gx = vals.get("x", 0.0)
                    gy = vals.get("y", 0.0)
                    gz = vals.get("z", 0.0)
                    found_gyro = True
                    break
            
            # Calculate accelerometer-based angles
            pitch_acc = math.atan2(y, math.sqrt(x**2 + z**2))
            roll_acc = math.atan2(-x, z)
            
            global filt_pitch, filt_roll, last_update_time
            dt = now_time - last_update_time if last_update_time > 0 else 0.016
            if dt <= 0 or dt > 1.0:
                dt = 0.016
            last_update_time = now_time
            
            if found_gyro:
                # Complementary filter fusion
                filt_pitch = 0.98 * (filt_pitch + gx * dt) + 0.02 * pitch_acc
                filt_roll = 0.98 * (filt_roll + gy * dt) + 0.02 * roll_acc
            else:
                filt_pitch = pitch_acc
                filt_roll = roll_acc
                
            # Convert Pitch/Roll/Yaw=0 to Quaternion
            yaw = 0.0
            cy = math.cos(yaw * 0.5)
            sy = math.sin(yaw * 0.5)
            cp = math.cos(filt_pitch * 0.5)
            sp = math.sin(filt_pitch * 0.5)
            cr = math.cos(filt_roll * 0.5)
            sr = math.sin(filt_roll * 0.5)

            qw = cr * cp * cy + sr * sp * sy
            qx = sr * cp * cy - cr * sp * sy
            qy = cr * sp * cy + sr * cp * sy
            qz = cr * cp * sy - sr * sp * cy
            
        # Simple relative position displacement translation matching gravity deviation
        x_pos = round(x * 0.05, 3)
        y_pos = round((y - 9.81 if z < 5.0 else y) * 0.05, 3)
        z_pos = round((z - 9.81 if z > 5.0 else z) * 0.05, 3)
        
        now_sec = int(now_time)
        now_nanosec = int((now_time - now_sec) * 1e9)
        kinematics_imu_payload = {
            "header": {
                "stamp": {
                    "sec": now_sec,
                    "nanosec": now_nanosec
                },
                "frame_id": "imu_link"
            },
            "orientation": {
                "w": round(qw, 5),
                "x": round(qx, 5),
                "y": round(qy, 5),
                "z": round(qz, 5)
            },
            "angular_velocity": {
                "x": round(gx, 4) if 'gx' in locals() else 0.0,
                "y": round(gy, 4) if 'gy' in locals() else 0.0,
                "z": round(gz, 4) if 'gz' in locals() else 0.0
            },
            "linear_acceleration": {
                "x": round(x, 4),
                "y": round(y, 4),
                "z": round(z, 4)
            },
            "position": {
                "x": x_pos,
                "y": y_pos,
                "z": z_pos
            }
        }
        
        # Publish to MQTT Broker
        if mqtt_client.is_connected():
            # Publish vital signs
            mqtt_client.publish(VITALS_TOPIC, json.dumps(vitals_payload), qos=1)
            
            # Publish IMU states if we processed a valid accelerometer packet
            if found_accel:
                mqtt_client.publish(IMU_TOPIC, json.dumps(imu_payload), qos=1)
                mqtt_client.publish(TELEMETRY_IMU_TOPIC, json.dumps(kinematics_imu_payload), qos=1)
                
            q = kinematics_imu_payload["orientation"]
            log.info(f"Forwarded: HR={vitals_payload['heartRate']} SpO2={vitals_payload['spo2']} FallState={is_falling} Q=({q['w']:.3f},{q['x']:.3f},{q['y']:.3f},{q['z']:.3f})")
        else:
            log.warning("MQTT not connected. Retrying connection...")
            connect_mqtt()
            
        return jsonify({
            "status": "success", 
            "g_force_ms2": round(g_magnitude, 2),
            "is_falling": is_falling
        }), 200
        
    except Exception as e:
        log.error(f"Error processing packet: {e}")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500

if __name__ == "__main__":
    # Listening on all interfaces (0.0.0.0) for phone push uplink
    log.info(f"Starting Multi-Protocol Bridge Server on 0.0.0.0:{BRIDGE_PORT}...")
    try:
        app.run(host="0.0.0.0", port=BRIDGE_PORT, debug=False)
    except OSError as e:
        if e.errno == 10013 or "forbidden" in str(e).lower() or "permission" in str(e).lower():
            log.error(f"[SYSTEM_ERROR] Port {BRIDGE_PORT} is blocked by Windows Firewall or Hyper-V/WSL port exclusions (WSAEACCES).")
            fallback_port = 8080 if BRIDGE_PORT != 8080 else 8081
            log.warning(f"[SYSTEM] Auto-switching to fallback port {fallback_port}...")
            try:
                app.run(host="0.0.0.0", port=fallback_port, debug=False)
            except Exception as fe:
                log.fatal(f"[FATAL] Fallback port {fallback_port} also failed: {fe}")
        elif e.errno == 10048 or "address already in use" in str(e).lower():
            log.error(f"[SYSTEM_ERROR] Port {BRIDGE_PORT} is already in use by another process.")
            fallback_port = 8080 if BRIDGE_PORT != 8080 else 8081
            log.warning(f"[SYSTEM] Auto-switching to fallback port {fallback_port}...")
            try:
                app.run(host="0.0.0.0", port=fallback_port, debug=False)
            except Exception as fe:
                log.fatal(f"[FATAL] Fallback port {fallback_port} also failed: {fe}")
        else:
            log.fatal(f"[FATAL] Server failed to start: {e}")
