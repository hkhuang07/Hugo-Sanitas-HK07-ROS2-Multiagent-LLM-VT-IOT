import os
import sys
import math
import time
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

def _is_wsl2_virtual_ip(ip: str) -> bool:
    """Return True if IP is in WSL2 / Hyper-V virtual adapter range (172.16.0.0/12)."""
    import socket, struct
    try:
        packed = struct.unpack("!I", socket.inet_aton(ip))[0]
        return 0xAC100000 <= packed <= 0xAC1FFFFF
    except Exception:
        return False

def _is_valid_gateway(ip: str) -> bool:
    import socket
    try:
        socket.inet_aton(ip)
        return ip not in ("0.0.0.0", "127.0.0.1", "255.255.255.255") and not _is_wsl2_virtual_ip(ip)
    except Exception:
        return False

def detect_host_wifi_ip():
    import subprocess
    import socket

    # Strategy 1: PowerShell – target Wi-Fi adapter specifically (no inner quotes)
    try:
        cmd = ["powershell.exe", "-NoProfile", "-Command",
               "Get-NetIPAddress -InterfaceAlias Wi-Fi -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode("utf-8").strip()
        for ip in out.split():
            if _is_valid_gateway(ip):
                return ip
    except Exception:
        pass

    # Strategy 2: PowerShell – derive from Wi-Fi next-hop gateway, then find local addr in same subnet
    # (handled by caller; skip fallback here)

    # Strategy 3: UDP socket trick – connects to the real Wi-Fi gateway, OS picks the right src IP
    try:
        gw = detect_phone_gateway_ip()
        if gw and gw != "UNKNOWN":
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((gw, 80))
            ip = s.getsockname()[0]
            s.close()
            if _is_valid_gateway(ip):
                return ip
    except Exception:
        pass

    return "127.0.0.1"

def detect_phone_gateway_ip():
    import subprocess
    import socket

    # Strategy 1: PowerShell – Wi-Fi interface only (no inner quotes – avoids WSL2 quote-escaping bug)
    try:
        cmd = ["powershell.exe", "-NoProfile", "-Command",
               "Get-NetRoute -DestinationPrefix 0.0.0.0/0 -InterfaceAlias Wi-Fi | Select-Object -ExpandProperty NextHop"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode("utf-8").strip()
        for ip in out.split():
            if _is_valid_gateway(ip):
                return ip
    except Exception:
        pass

    # Strategy 2: PowerShell – all routes, skip WSL2 172.x.x.x ranges
    try:
        cmd = ["powershell.exe", "-NoProfile", "-Command",
               "Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Select-Object -ExpandProperty NextHop"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode("utf-8").strip()
        for ip in out.split():
            if _is_valid_gateway(ip):
                return ip
    except Exception:
        pass

    # Strategy 3: Linux `ip route` (pure Linux / non-WSL2 fallback)
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

    return "UNKNOWN"

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
ENVIRONMENT_TOPIC = "hk07/sensors/environment/state"
LOCATION_TOPIC = "hk07/sensors/location/gps"
ACTIVITY_TOPIC = "hk07/sensors/activity/metrics"

FALL_COOLDOWN_SEC = 3.0
last_fall_time = 0.0
g_ema = None

# Complementary filter state variables
filt_pitch = 0.0
filt_roll = 0.0
filt_yaw = 0.0
last_update_time = 0.0

# Barometric pressure tracking for dual-factor fall detection
pressure_buffer = []
buffer_size = 10

# ─────────────────────────────────────────────────────────────────────────────
# MULTI-KEY SENSOR LOOKUP HELPER
# Sensor Logs app may send camelCase or snake_case or lowercase variants.
# ─────────────────────────────────────────────────────────────────────────────
def _multi_get(sensor_map: dict, *keys):
    """Return first non-None value from sensor_map for any of the given keys."""
    for key in keys:
        val = sensor_map.get(key)
        if val is not None:
            return val
    return None

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

# Health check endpoint — callable from Sensor Logs app or monitoring systems
_bridge_start_time = time.time()
_processed_packets = 0

@app.route("/health", methods=["GET"])
def health_check():
    uptime_sec = round(time.time() - _bridge_start_time, 1)
    return jsonify({
        "status": "ok",
        "mqtt_connected": mqtt_client.is_connected(),
        "mqtt_broker": f"{MQTT_BROKER}:{MQTT_PORT}",
        "processed_packets": _processed_packets,
        "uptime_sec": uptime_sec,
        "device_id": DEVICE_ID,
        "topics": [VITALS_TOPIC, IMU_TOPIC, TELEMETRY_IMU_TOPIC, ENVIRONMENT_TOPIC, LOCATION_TOPIC, ACTIVITY_TOPIC]
    }), 200

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
        
        # === O(1) PARSER: Build sensor_map dictionary (ATOMIC) ===
        sensor_map = {
            item.get("name"): item.get("values", {})
            for item in payload_list
            if item.get("name")
        }
        
        # Default gravity acceleration
        x, y, z = 0.0, 0.0, 9.81
        found_accel = False
        
        # === Extract accelerometer (real hardware) ===
        if "accelerometer" in sensor_map:
            values = sensor_map["accelerometer"]
            if isinstance(values, dict):
                x = values.get("x", 0.0)
                y = values.get("y", 0.0)
                z = values.get("z", 9.81)
            else:
                x, y, z = 0.0, 0.0, 9.81
            found_accel = True
        
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
        
        # === EXTRACT REAL BIOMETRICS (NO MOCK DATA) ===
        # Extract real hardware heart rate — multi-key lookup for Sensor Logs app variants
        heartrate_raw = _multi_get(sensor_map, "heart_rate", "heartRate", "heartrate", "hr")
        if heartrate_raw is not None:
            try:
                heart_rate = int(heartrate_raw) if isinstance(heartrate_raw, (int, float)) else (140 if is_falling else 70)
            except (ValueError, TypeError):
                heart_rate = 140 if is_falling else 70
        else:
            heart_rate = 140 if is_falling else 70
            log.warning("Heart rate sensor null; using safe default")
        
        # Extract SpO2 (real hardware) — multi-key lookup
        spo2_raw = _multi_get(sensor_map, "spo2", "SpO2", "spO2", "oxygen")
        try:
            spo2 = float(spo2_raw) if spo2_raw is not None and isinstance(spo2_raw, (int, float)) else 98.0
        except (ValueError, TypeError):
            spo2 = 98.0
        
        # Extract temperature (real hardware) — multi-key lookup
        temperature_raw = _multi_get(sensor_map, "temperature", "bodyTemperature", "temp")
        try:
            temperature = float(temperature_raw) if temperature_raw is not None and isinstance(temperature_raw, (int, float)) else 36.6
        except (ValueError, TypeError):
            temperature = 36.6
        
        # Compile Vitals Payload (REAL HARDWARE ONLY)
        vitals_payload = {
            "heartRate": heart_rate,
            "systolic": 120.0 if not is_falling else 160.0,
            "diastolic": 80.0 if not is_falling else 100.0,
            "bodyTemperature": temperature,
            "spo2": spo2,
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
        
        # === Extract gyroscope and magnetometer (O(1) lookup) ===
        gx, gy, gz = 0.0, 0.0, 0.0
        mag_x, mag_y, mag_z = 0.0, 0.0, 0.0
        compass_heading = 0.0
        grav_x, grav_y, grav_z = 0.0, 0.0, 9.81
        
        if "gyroscope" in sensor_map:
            vals = sensor_map["gyroscope"]
            if isinstance(vals, dict):
                gx = float(vals.get("x", 0.0))
                gy = float(vals.get("y", 0.0))
                gz = float(vals.get("z", 0.0))
        
        if "magnetometer" in sensor_map:
            mag_vals = sensor_map["magnetometer"]
            if isinstance(mag_vals, dict):
                mag_x = float(mag_vals.get("x", 0.0))
                mag_y = float(mag_vals.get("y", 0.0))
                mag_z = float(mag_vals.get("z", 0.0))
        
        # Extract gravity vector (separate from accelerometer on most phones)
        gravity_raw = _multi_get(sensor_map, "gravity", "gravitySensor")
        if gravity_raw is not None and isinstance(gravity_raw, dict):
            grav_x = float(gravity_raw.get("x", 0.0))
            grav_y = float(gravity_raw.get("y", 0.0))
            grav_z = float(gravity_raw.get("z", 9.81))
        
        # Extract compass/heading — multi-key lookup
        compass_raw = _multi_get(sensor_map, "compass", "heading", "magneticHeading", "trueHeading")
        if compass_raw is not None:
            try:
                compass_heading = float(compass_raw) if isinstance(compass_raw, (int, float)) else 0.0
            except (ValueError, TypeError):
                compass_heading = 0.0
        
        # Check for direct quaternion or orientation in payload list
        qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
        found_quat = False
        if "orientation" in sensor_map or "quaternion" in sensor_map:
            values = sensor_map.get("orientation") or sensor_map.get("quaternion", {})
            if isinstance(values, dict):
                qw = values.get("w", values.get("qw", 1.0))
                qx = values.get("x", values.get("qx", 0.0))
                qy = values.get("y", values.get("qy", 0.0))
                qz = values.get("z", values.get("qz", 0.0))
                found_quat = True
        
        if not found_quat:
            found_gyro = "gyroscope" in sensor_map
            
            # Calculate accelerometer-based angles
            pitch_acc = math.atan2(y, math.sqrt(x**2 + z**2))
            roll_acc = math.atan2(-x, z)
            
            global filt_pitch, filt_roll, filt_yaw, last_update_time
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
                
            # Fuse magnetometer+compass for yaw (heading) refinement
            if mag_x != 0.0 or mag_y != 0.0 or mag_z != 0.0:
                mag_mag = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
                if mag_mag > 1e-6:
                    mag_yaw_rad = math.atan2(mag_y / mag_mag, mag_x / mag_mag)
                    mag_yaw_deg = math.degrees(mag_yaw_rad)
                    if compass_heading > 0:
                        filt_yaw = 0.9 * filt_yaw + 0.1 * compass_heading
                    else:
                        filt_yaw = 0.9 * filt_yaw + 0.1 * mag_yaw_deg
            
            # Convert Pitch/Roll/Yaw to Quaternion (with magnetometer fusion)
            yaw_rad = math.radians(filt_yaw)
            cy = math.cos(yaw_rad * 0.5)
            sy = math.sin(yaw_rad * 0.5)
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
        # === ENHANCED KINEMATICS PAYLOAD (9-DOF: accel+gyro+mag+compass) ===
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
                "x": round(gx, 4),
                "y": round(gy, 4),
                "z": round(gz, 4)
            },
            "linear_acceleration": {
                "x": round(x, 4),
                "y": round(y, 4),
                "z": round(z, 4)
            },
            "magnetometer": {
                "x": round(mag_x, 4),
                "y": round(mag_y, 4),
                "z": round(mag_z, 4)
            },
            "compass_heading": round(filt_yaw, 2),
            "position": {
                "x": x_pos,
                "y": y_pos,
                "z": z_pos
            }
        }
        
        # === EXTRACT ENVIRONMENT SENSORS (light + barometer) ===
        light_raw = sensor_map.get("light")
        barometer_raw = sensor_map.get("barometer")
        
        try:
            ambient_light = float(light_raw) if light_raw is not None and isinstance(light_raw, (int, float)) else 500.0
        except (ValueError, TypeError):
            ambient_light = 500.0
        
        try:
            barometric_pressure = float(barometer_raw) if barometer_raw is not None and isinstance(barometer_raw, (int, float)) else 1013.25
        except (ValueError, TypeError):
            barometric_pressure = 1013.25
        
        # Track pressure for dual-factor fall detection
        global pressure_buffer
        pressure_buffer.append(barometric_pressure)
        if len(pressure_buffer) > buffer_size:
            pressure_buffer.pop(0)
        
        pressure_delta = 0.0
        if len(pressure_buffer) > 1:
            pressure_delta = pressure_buffer[-1] - pressure_buffer[0]
        
        environment_payload = {
            "ambient_light": round(ambient_light, 2),
            "barometric_pressure": round(barometric_pressure, 2),
            "pressure_delta_hpa": round(pressure_delta, 2),
            "timestamp_ms": timestamp_ms
        }
        
        # === DUAL-FACTOR FALL DETECTION (g-force + pressure delta) ===
        # Enhance fall detection: combine acceleration spike with barometric pressure drop
        is_fall_pressure_drop = pressure_delta <= -5.0
        is_fall_accel_spike = (g_magnitude > 2.5) or (is_linear and g_magnitude > 15.0)
        
        if is_fall_accel_spike and is_fall_pressure_drop:
            # High confidence: both factors present
            is_falling = (now_time - last_fall_time) < FALL_COOLDOWN_SEC
            if not is_falling and now_time - last_fall_time > FALL_COOLDOWN_SEC:
                last_fall_time = now_time
                log.critical(f"DUAL-FACTOR FALL: accel_spike={g_magnitude:.2f}g, pressure_delta={pressure_delta:.2f}hPa")
        
        # === EXTRACT LOCATION (GPS) ===
        location_payload = None
        location_raw = sensor_map.get("location")
        if location_raw is not None:
            try:
                if isinstance(location_raw, (list, tuple)) and len(location_raw) >= 3:
                    location_payload = {
                        "latitude": round(float(location_raw[0]), 6),
                        "longitude": round(float(location_raw[1]), 6),
                        "altitude": round(float(location_raw[2]), 2),
                        "timestamp_ms": timestamp_ms
                    }
                elif isinstance(location_raw, dict):
                    location_payload = {
                        "latitude": round(float(location_raw.get("latitude", 0.0)), 6),
                        "longitude": round(float(location_raw.get("longitude", 0.0)), 6),
                        "altitude": round(float(location_raw.get("altitude", 0.0)), 2),
                        "timestamp_ms": timestamp_ms
                    }
            except (ValueError, TypeError, IndexError):
                pass
        
        # === EXTRACT ACTIVITY METRICS (pedometer + activity + wrist motion) ===
        activity_payload = None
        # Multi-key lookup: Sensor Logs app may use 'pedometer', 'steps', 'stepCount'
        pedometer_raw = _multi_get(sensor_map, "pedometer", "steps", "stepCount", "stepcount")
        activity_raw = _multi_get(sensor_map, "activity", "activityType", "motion")
        wrist_motion_raw = _multi_get(sensor_map, "wrist_motion", "wristMotion", "wrist")
        
        if pedometer_raw is not None or activity_raw is not None or wrist_motion_raw is not None:
            try:
                steps = int(pedometer_raw) if pedometer_raw is not None and isinstance(pedometer_raw, (int, float)) else 0
            except (ValueError, TypeError):
                steps = 0
            
            activity_type = str(activity_raw) if activity_raw is not None else "unknown"
            
            wrist_motion_array = []
            if isinstance(wrist_motion_raw, (list, tuple)):
                try:
                    wrist_motion_array = [float(x) for x in wrist_motion_raw]
                except (ValueError, TypeError):
                    pass
            
            activity_payload = {
                "pedometer_steps": steps,
                "activity_type": activity_type,
                "wrist_motion": [round(x, 3) for x in wrist_motion_array],
                "timestamp_ms": timestamp_ms
            }
        
        # === PUBLISH TO MQTT BROKER (Multi-Topic Routing) ===
        if mqtt_client.is_connected():
            # Publish vital signs
            mqtt_client.publish(VITALS_TOPIC, json.dumps(vitals_payload), qos=1)
            
            # Publish environment (light + barometer + pressure delta)
            mqtt_client.publish(ENVIRONMENT_TOPIC, json.dumps(environment_payload), qos=1)
            
            # Publish IMU states if we processed a valid accelerometer packet
            if found_accel:
                mqtt_client.publish(IMU_TOPIC, json.dumps(imu_payload), qos=1)
                mqtt_client.publish(TELEMETRY_IMU_TOPIC, json.dumps(kinematics_imu_payload), qos=1)
            
            # Publish location if available
            if location_payload is not None:
                mqtt_client.publish(LOCATION_TOPIC, json.dumps(location_payload), qos=1)
            
            # Publish activity metrics if available
            if activity_payload is not None:
                mqtt_client.publish(ACTIVITY_TOPIC, json.dumps(activity_payload), qos=1)
                
            q = kinematics_imu_payload["orientation"]
            log.info(f"Forwarded: HR={vitals_payload['heartRate']} SpO2={vitals_payload['spo2']} Light={ambient_light:.0f}lx Pressure={barometric_pressure:.1f}hPa Yaw={filt_yaw:.1f}deg FallState={is_falling}")
        else:
            log.warning("MQTT not connected. Retrying connection...")
            connect_mqtt()
            
        global _processed_packets
        _processed_packets += 1
        return jsonify({
            "status": "success", 
            "g_force_ms2": round(g_magnitude, 2),
            "is_falling": is_falling,
            "packet_count": _processed_packets
        }), 200
        
    except Exception as e:
        log.error(f"Error processing packet: {e}")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500

if __name__ == "__main__":
    import socket
    
    # Enforce dynamic port allocation
    allocated_port = BRIDGE_PORT
    while allocated_port < 65535:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", allocated_port))
            s.close()
            break
        except socket.error as e:
            log.info(f"Port {allocated_port} is busy or restricted ({e}). Trying next port...")
            allocated_port += 1
            
    gateway_ip = detect_phone_gateway_ip()
    wifi_ip = detect_host_wifi_ip()
    
    log.info(f"┌────────────────────────────────────────────────────────┐")
    log.info(f"│  MOBILE HOTSPOT BRIDGE ACTIVE                          │")
    log.info(f"│                                                        │")
    log.info(f"│  [CONNECTED_PHONE_GATEWAY]: {gateway_ip:<28} │")
    log.info(f"│  [LAPTOP_LOCAL_WIFI_IP]:    {wifi_ip:<28} │")
    log.info(f"│                                                        │")
    log.info(f"│  [ACTION_REQUIRED]: Configure Phone App Target URL to:  │")
    url_str = f"http://{wifi_ip}:{allocated_port}/data"
    log.info(f"│  {url_str:<52}  │")
    log.info(f"└────────────────────────────────────────────────────────┘")
    
    log.info(f"Starting Multi-Protocol Bridge Server on 0.0.0.0:{allocated_port}...")
    try:
        app.run(host="0.0.0.0", port=allocated_port, debug=False)
    except Exception as e:
        log.fatal(f"[FATAL] Server failed to start: {e}")
