import os
import sys
import math
import time
import json
import threading
import socket
import struct
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

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

def get_default_gateway_wsl() -> str:
    try:
        with open("/proc/net/route", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    gw_hex = parts[2]
                    gw_bytes = struct.pack("<I", int(gw_hex, 16))
                    return socket.inet_ntoa(gw_bytes)
    except Exception:
        pass
    return "127.0.0.1"

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import Imu, JointState
except ImportError:
    print("=================================================================================")
    print(">>> [ROBOTICS ARCHITECTURE ERROR] ROS 2 client library 'rclpy' is not installed.")
    print("=================================================================================")
    sys.exit(1)

class SensorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress request logging to avoid stdout flooding
        pass

    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if hasattr(self.server, 'node') and self.server.node:
                self.server.node.get_logger().info(
                    f"[HTTP_GATEWAY] Received POST request on path '{self.path}' with content-length={content_length}"
                )

            if content_length == 0:
                self.send_response(400)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "Empty body"}')
                return

            post_data = self.rfile.read(content_length)
            decoded_data = post_data.decode('utf-8')

            try:
                curr_dir = os.path.dirname(os.path.abspath(__file__))
                sensors_dir = os.path.abspath(os.path.join(curr_dir, ".."))
                payload_path = os.path.join(sensors_dir, "sensor_log_payload.json")
                with open(payload_path, "w", encoding="utf-8") as f:
                    f.write(decoded_data)
            except Exception as file_err:
                if hasattr(self.server, 'node') and self.server.node:
                    self.server.node.get_logger().warning(f"Failed to write payload file: {file_err}")

            data = json.loads(decoded_data)

            # Route for dynamically updating phone IP from frontend config form
            if self.path == '/api/v1/config/device-ip':
                new_ip = data.get('ip')
                if new_ip and hasattr(self.server, 'node') and self.server.node:
                    self.server.node.get_logger().info(f"[HTTP_GATEWAY] Configured target phone IP dynamically to: {new_ip}")
                    os.environ["PHONE_IP"] = new_ip
            else:
                if hasattr(self.server, 'node') and self.server.node:
                    self.server.node.process_payload(data)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(b'{"status": "success"}')
        except Exception as e:
            if hasattr(self.server, 'node') and self.server.node:
                self.server.node.get_logger().error(f"Error handling POST request: {e}")
            self.send_response(500)
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(f'{{"status": "error", "message": "{str(e)}"}}'.encode('utf-8'))

class HugoPerceptionBridgeNode(Node):
    def __init__(self):
        super().__init__('hugo_perception_bridge_node')

        # State Variables
        self.state_lock = threading.Lock()
        self.last_fall_time = 0.0
        self.g_ema = None

        # Complementary Filter Variables
        self.filt_pitch = 0.0
        self.filt_roll = 0.0
        self.filt_yaw = 0.0
        self.last_update_time = 0.0

        # Barometric pressure tracking for dual-factor fall detection
        self.pressure_buffer = []
        self.buffer_size = 10
        self.FALL_COOLDOWN_SEC = 3.0

        # Persistent telemetry state to avoid overwriting valid hardware state
        self.heart_rate = 72.0
        self.ambient_light = 500.0
        self.barometric_pressure = 1013.25
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.pedometer_steps = 0.0
        self.activity_type = 0.0
        self.x = 0.0
        self.y = 0.0
        self.z = 9.80665
        self.battery_level = 100.0
        self.battery_temp = 32.0
        self.gx = 0.0
        self.gy = 0.0
        self.gz = 0.0
        self.mag_x = 0.0
        self.mag_y = 0.0
        self.mag_z = 0.0
        self.compass_heading = 0.0
        self.gravity_x = 0.0
        self.gravity_y = 0.0
        self.gravity_z = 9.80665
        self.qw = 1.0
        self.qx = 0.0
        self.qy = 0.0
        self.qz = 0.0
        self.g_magnitude = 1.0

        # Last update times for sensor online status
        self.last_accel_time = 0.0
        self.last_gyro_time = 0.0
        self.last_mag_time = 0.0
        self.last_orient_time = 0.0
        self.last_compass_time = 0.0
        self.last_heart_rate_time = 0.0
        self.last_light_time = 0.0
        self.last_pedometer_time = 0.0
        self.last_activity_time = 0.0
        self.last_location_time = 0.0
        self.last_baro_time = 0.0


        self.imu_target_pub = self.create_publisher(Imu, '/sensors/imu/target', 10)
        self.imu_state_pub = self.create_publisher(Imu, '/sensors/imu/state', 10)
        self.vitals_pub = self.create_publisher(JointState, '/vitals/wristband', 10)

        # Start HTTP server thread
        self.server = None
        self.server_thread = None
        self.start_http_server()

        # Initialize MQTT Client for publishing mobile telemetry to Spring Boot backend
        self.mqtt_client = None
        if mqtt is not None:
            try:
                load_env_file()
                
                broker_host = os.environ.get('MQTT_HOST') or os.environ.get('MQTT_BROKER_HOST') or '127.0.0.1'
                broker_port = int(os.environ.get('MQTT_PORT') or os.environ.get('MQTT_BROKER_PORT') or 1883)
                mqtt_user = os.environ.get('MQTT_USERNAME', 'hk07agent')
                mqtt_pass = os.environ.get('MQTT_PASSWORD', 'hk07_mqtt_dev_pwd')
                
                self.get_logger().info(f"[MQTT] Connecting directly to configured broker: {broker_host}")

                if hasattr(mqtt, "CallbackAPIVersion"):
                    self.mqtt_client = mqtt.Client(
                        mqtt.CallbackAPIVersion.VERSION2,
                        client_id="hk07-perception-bridge",
                        protocol=mqtt.MQTTv311
                    )
                    # VERSION2 requires explicit callback signatures
                    def _on_connect_v2(client, userdata, flags, reason_code, properties):
                        if reason_code.is_failure:
                            self.get_logger().warning(f"[MQTT] Connection failed: {reason_code}")
                        else:
                            self.get_logger().info(f"MQTT Bridge connected to {broker_host}:{broker_port} as user {mqtt_user}")
                    def _on_disconnect_v2(client, userdata, disconnect_flags, reason_code, properties):
                        self.get_logger().warning(f"[MQTT] Disconnected: {reason_code}")
                    self.mqtt_client.on_connect = _on_connect_v2
                    self.mqtt_client.on_disconnect = _on_disconnect_v2
                else:
                    self.mqtt_client = mqtt.Client(client_id="hk07-perception-bridge", protocol=mqtt.MQTTv311)
                if mqtt_user:
                    self.mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
                self.mqtt_client.connect_async(broker_host, broker_port, keepalive=30)
                self.mqtt_client.loop_start()
                self.get_logger().info(f"[MQTT] Broker connection initiated to {broker_host}:{broker_port}")
            except Exception as e:
                self.get_logger().warning(f"MQTT Bridge failed to initialize: {e}")

        # Initialize simulation state
        self.robot_mode = os.getenv("ROBOT_MODE", "SIMULATED").upper()
        self.is_simulated = (self.robot_mode == "SIMULATED")
        self.sim_timer = self.create_timer(1.0, self.sim_timer_callback)

        self.get_logger().info("=== HUGO PERCEPTION ROS2 BRIDGE NODE INITIALIZED ===")

    def start_http_server(self):
        # Find an open port starting at 5006 (port 5005 is reserved by Windows system services)
        port = int(os.getenv("BRIDGE_PORT", "5006"))
        while port < 65535:
            try:
                self.server = HTTPServer(('0.0.0.0', port), SensorHandler)
                self.server.node = self
                self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
                self.server_thread.start()
                self.get_logger().info(f"Listening for SensorLogs HTTP POST requests on 0.0.0.0:{port}")
                break
            except OSError:
                self.get_logger().warning(f"Port {port} in use, trying next port...")
                port += 1

    def _multi_get(self, sensor_map: dict, *keys):
        for key in keys:
            val = sensor_map.get(key)
            if val is not None:
                return val
        return None

    def _extract_float(self, data, fallback=0.0):
        if data is None:
            return fallback
        if isinstance(data, (int, float)):
            return float(data)
        if isinstance(data, dict):
            for k in ["value", "val", "steps", "lux", "light", "heart_rate", "heartRate", "activity", "batteryLevel", "battery_level", "battery", "temperature"]:
                val = data.get(k)
                if val is not None:
                    if isinstance(val, (int, float)):
                        return float(val)
                    if isinstance(val, dict):
                        return self._extract_float(val, fallback)
            if len(data) == 1:
                val = list(data.values())[0]
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, dict):
                    return self._extract_float(val, fallback)
        try:
            return float(data)
        except (ValueError, TypeError):
            pass
        return fallback

    def process_payload(self, data):
        if not data or "payload" not in data:
            self.get_logger().warning("Received empty or invalid SensorLogs packet (missing 'payload')")
            return

        payload_list = data.get("payload", [])
        if not payload_list:
            return
        
        # Build lookup map
        sensor_map = {}
        for item in payload_list:
            name = item.get("name")
            if name:
                val = item.get("values")
                if val is None:
                    val = item.get("value")
                if val is None:
                    val = item
                sensor_map[name] = val

        if not sensor_map:
            return

        # Thread-safe telemetry processing
        with self.state_lock:
            self.is_simulated = False
            self.last_accel_time = time.time()
            self._process_imu_and_vitals(sensor_map)

    def _process_imu_and_vitals(self, sensor_map):
        now_time = time.time()
        timestamp_ms = int(now_time * 1000)

        # 1. Accelerometer reading
        raw_x, raw_y, raw_z = 0.0, 0.0, 9.80665
        found_accel = False
        if "accelerometer" in sensor_map:
            values = sensor_map["accelerometer"]
            if isinstance(values, dict):
                raw_x = float(values.get("x", values.get("X", 0.0)))
                raw_y = float(values.get("y", values.get("Y", 0.0)))
                raw_z = float(values.get("z", values.get("Z", 9.80665)))
                found_accel = True
            elif isinstance(values, (list, tuple)) and len(values) >= 3:
                try:
                    raw_x = float(values[0])
                    raw_y = float(values[1])
                    raw_z = float(values[2])
                    found_accel = True
                except (ValueError, TypeError):
                    pass
        elif "accelerometerX" in sensor_map and "accelerometerY" in sensor_map and "accelerometerZ" in sensor_map:
            raw_x = self._extract_float(sensor_map["accelerometerX"], 0.0)
            raw_y = self._extract_float(sensor_map["accelerometerY"], 0.0)
            raw_z = self._extract_float(sensor_map["accelerometerZ"], 9.80665)
            found_accel = True
        else:
            raw_x = self.x
            raw_y = self.y
            raw_z = self.z

        raw_magnitude = math.sqrt(raw_x**2 + raw_y**2 + raw_z**2)
        # Unit Standard correction: standard ROS2 linear acceleration expects m/s^2
        self.x = raw_x
        self.y = raw_y
        self.z = raw_z
        self.g_magnitude = raw_magnitude / 9.80665

        # 1b. Real PMU / Battery Extraction from SensorLogs
        found_battery = False
        try:
            bat_key = next((k for k in ["batteryLevel", "battery_level", "battery"] if k in sensor_map), None)
            if bat_key:
                val = self._extract_float(sensor_map[bat_key], self.battery_level)
                if val <= 1.0:
                    val *= 100.0
                self.battery_level = val
                found_battery = True
        except Exception:
            pass

        try:
            bat_temp_key = next((k for k in ["batteryTemp", "batteryTemperature", "battery_temp", "battery temp"] if k in sensor_map), None)
            if bat_temp_key:
                self.battery_temp = self._extract_float(sensor_map[bat_temp_key], self.battery_temp)
                found_battery = True
        except Exception:
            pass

        if self.g_ema is None:
            self.g_ema = self.g_magnitude
        else:
            self.g_ema = 0.9 * self.g_ema + 0.1 * self.g_magnitude

        is_linear = (self.g_ema < 3.0)
        # Automatic E-STOP/fall triggers disabled per user request to avoid jamming the companion robot
        is_falling_now = False

        # 2. Extract environment pressure delta
        # NOTE: Phone (Vivo Android) does NOT have a barometer sensor in its payload.
        # Keys searched: barometer, pressure, altimeter, barometricPressure, pressure_hpa.
        # When none found, we mark barometric_pressure as None (no sensor reading available).
        found_barometer = False
        try:
            baro_key = next((k for k in ["barometer", "pressure", "altimeter", "barometricPressure", "altitudeBarometer", "pressure_hpa"] if k in sensor_map), None)
            if baro_key:
                val = self._extract_float(sensor_map[baro_key], None)
                if val is not None and val > 0:
                    self.barometric_pressure = val
                    found_barometer = True
            # If no barometer sensor at all, keep self.barometric_pressure = None so downstream
            # consumers can distinguish "no sensor" from a valid reading.
            if not found_barometer:
                self.barometric_pressure = None
        except Exception:
            self.barometric_pressure = None

        # Only append valid pressure readings to buffer (skip None when no barometer)
        if self.barometric_pressure is not None:
            self.pressure_buffer.append(self.barometric_pressure)
            if len(self.pressure_buffer) > self.buffer_size:
                self.pressure_buffer.pop(0)

        pressure_delta = 0.0
        if found_barometer and len(self.pressure_buffer) > 1:
            pressure_delta = self.pressure_buffer[-1] - self.pressure_buffer[0]

        # Dual-factor trigger verification disabled per user request
        is_fall_pressure_drop = False
        is_fall_accel_spike = False
        is_falling = False
        self.last_fall_time = 0.0

        # 3. Process angles & complementary filter
        found_gyro = False
        if "gyroscope" in sensor_map:
            vals = sensor_map["gyroscope"]
            if isinstance(vals, dict):
                self.gx = float(vals.get("x", vals.get("X", 0.0)))
                self.gy = float(vals.get("y", vals.get("Y", 0.0)))
                self.gz = float(vals.get("z", vals.get("Z", 0.0)))
                found_gyro = True
            elif isinstance(vals, (list, tuple)) and len(vals) >= 3:
                try:
                    self.gx = float(vals[0])
                    self.gy = float(vals[1])
                    self.gz = float(vals[2])
                    found_gyro = True
                except (ValueError, TypeError):
                    pass
        elif "gyroX" in sensor_map and "gyroY" in sensor_map and "gyroZ" in sensor_map:
            self.gx = self._extract_float(sensor_map["gyroX"], 0.0)
            self.gy = self._extract_float(sensor_map["gyroY"], 0.0)
            self.gz = self._extract_float(sensor_map["gyroZ"], 0.0)
            found_gyro = True
        elif "rotationRateX" in sensor_map and "rotationRateY" in sensor_map and "rotationRateZ" in sensor_map:
            self.gx = self._extract_float(sensor_map["rotationRateX"], 0.0)
            self.gy = self._extract_float(sensor_map["rotationRateY"], 0.0)
            self.gz = self._extract_float(sensor_map["rotationRateZ"], 0.0)
            found_gyro = True

        found_mag = False
        if "magnetometer" in sensor_map:
            mag_vals = sensor_map["magnetometer"]
            if isinstance(mag_vals, dict):
                self.mag_x = float(mag_vals.get("x", mag_vals.get("X", 0.0)))
                self.mag_y = float(mag_vals.get("y", mag_vals.get("Y", 0.0)))
                self.mag_z = float(mag_vals.get("z", mag_vals.get("Z", 0.0)))
                found_mag = True
            elif isinstance(mag_vals, (list, tuple)) and len(mag_vals) >= 3:
                try:
                    self.mag_x = float(mag_vals[0])
                    self.mag_y = float(mag_vals[1])
                    self.mag_z = float(mag_vals[2])
                    found_mag = True
                except (ValueError, TypeError):
                    pass
        elif "magnetometerX" in sensor_map and "magnetometerY" in sensor_map and "magnetometerZ" in sensor_map:
            self.mag_x = self._extract_float(sensor_map["magnetometerX"], 0.0)
            self.mag_y = self._extract_float(sensor_map["magnetometerY"], 0.0)
            self.mag_z = self._extract_float(sensor_map["magnetometerZ"], 0.0)
            found_mag = True
        elif "magneticFieldX" in sensor_map and "magneticFieldY" in sensor_map and "magneticFieldZ" in sensor_map:
            self.mag_x = self._extract_float(sensor_map["magneticFieldX"], 0.0)
            self.mag_y = self._extract_float(sensor_map["magneticFieldY"], 0.0)
            self.mag_z = self._extract_float(sensor_map["magneticFieldZ"], 0.0)
            found_mag = True

        # Extract compass / magneticHeading
        # Phone sends: {"name": "compass", "values": {"magneticBearing": 55.63}} OR
        #              {"name": "magnetometer", "values": {"magneticBearing": 55.63}}
        # Also handles legacy formats: {"heading": ...} or scalar.
        found_compass = False
        if "compass" in sensor_map:
            values = sensor_map["compass"]
            if isinstance(values, dict):
                # Primary field from SensorLogger app: magneticBearing
                bearing = values.get("magneticBearing") or values.get("magnetic_bearing")
                if bearing is not None:
                    self.compass_heading = float(bearing)
                    found_compass = True
                else:
                    heading = values.get("heading") or values.get("trueHeading") or values.get("magneticHeading")
                    if heading is not None:
                        self.compass_heading = float(heading)
                        found_compass = True
            elif isinstance(values, (int, float)):
                self.compass_heading = float(values)
                found_compass = True
        elif "magneticHeading" in sensor_map:
            values = sensor_map["magneticHeading"]
            if isinstance(values, dict):
                self.compass_heading = float(values.get("heading", values.get("magneticBearing", 0.0)))
                found_compass = True
            elif isinstance(values, (int, float)):
                self.compass_heading = float(values)
                found_compass = True

        # Fallback: derive compass_heading from magnetometer when magnetometer has magneticBearing
        if not found_compass and "magnetometer" in sensor_map:
            mag_vals = sensor_map["magnetometer"]
            if isinstance(mag_vals, dict):
                bearing = mag_vals.get("magneticBearing") or mag_vals.get("magnetic_bearing")
                if bearing is not None:
                    self.compass_heading = float(bearing)
                    found_compass = True
                elif mag_vals.get("x") is not None and mag_vals.get("y") is not None:
                    # Derive 2D heading from raw Gauss X/Y if no magneticBearing provided
                    mx = float(mag_vals.get("x", 0.0))
                    my = float(mag_vals.get("y", 0.0))
                    if mx != 0.0 or my != 0.0:
                        heading_rad = math.atan2(my, mx)
                        self.compass_heading = (math.degrees(heading_rad) + 360.0) % 360.0
                        found_compass = True

        # Extract heart rate
        found_heart_rate = False
        try:
            raw_hr = None
            if "heart_rate" in sensor_map:
                raw_hr = sensor_map["heart_rate"]
            elif "heartRate" in sensor_map:
                raw_hr = sensor_map["heartRate"]
            if raw_hr is not None:
                self.heart_rate = self._extract_float(raw_hr, self.heart_rate)
                found_heart_rate = True
        except Exception:
            pass

        # Extract light
        found_light = False
        try:
            light_key = next((k for k in ["light", "ambientLight", "brightness", "lux"] if k in sensor_map), None)
            if light_key:
                self.ambient_light = self._extract_float(sensor_map[light_key], self.ambient_light)
                found_light = True
        except Exception:
            pass

        # Extract pedometer steps
        found_pedometer = False
        try:
            ped_key = next((k for k in ["pedometer", "steps", "stepCount", "pedometerSteps", "numberOfSteps", "step_count"] if k in sensor_map), None)
            if ped_key:
                self.pedometer_steps = self._extract_float(sensor_map[ped_key], self.pedometer_steps)
                found_pedometer = True
        except Exception:
            pass

        # Extract activity
        found_activity = False
        try:
            act_key = next((k for k in ["activity", "activityType", "activity_type", "userActivity", "activityMode"] if k in sensor_map), None)
            if act_key:
                raw_act = sensor_map[act_key]
                act_num = self._extract_float(raw_act, None)
                if act_num is not None:
                    self.activity_type = act_num
                    found_activity = True
                else:
                    act_val = None
                    if isinstance(raw_act, dict):
                        act_val = raw_act.get("value") or raw_act.get("activity")
                    else:
                        act_val = raw_act
                    if act_val is not None:
                        act_str = str(act_val).lower()
                        if "station" in act_str:
                            self.activity_type = 1.0
                        elif "walk" in act_str:
                            self.activity_type = 2.0
                        elif "run" in act_str:
                            self.activity_type = 3.0
                        elif "automotive" in act_str or "vehicle" in act_str:
                            self.activity_type = 4.0
                        elif "cycle" in act_str:
                            self.activity_type = 5.0
                        else:
                            self.activity_type = 0.0
                        found_activity = True
        except Exception:
            pass

        # Extract location (GPS)
        found_location = False
        try:
            loc_key = next((k for k in ["location", "gps", "position"] if k in sensor_map), None)
            if loc_key:
                loc = sensor_map[loc_key]
                if isinstance(loc, dict):
                    lat_val = loc.get("latitude") or loc.get("lat")
                    if lat_val is None and "value" in loc:
                        val_dict = loc.get("value")
                        if isinstance(val_dict, dict):
                            lat_val = val_dict.get("latitude") or val_dict.get("lat")
                    lon_val = loc.get("longitude") or loc.get("lon")
                    if lon_val is None and "value" in loc:
                        val_dict = loc.get("value")
                        if isinstance(val_dict, dict):
                            lon_val = val_dict.get("longitude") or val_dict.get("lon")
                    alt_val = loc.get("altitude") or loc.get("alt")
                    if alt_val is None and "value" in loc:
                        val_dict = loc.get("value")
                        if isinstance(val_dict, dict):
                            alt_val = val_dict.get("altitude") or val_dict.get("alt")
                            
                    if lat_val is not None:
                        self.latitude = float(lat_val)
                    if lon_val is not None:
                        self.longitude = float(lon_val)
                    if alt_val is not None:
                        self.altitude = float(alt_val)
                    found_location = True
                elif isinstance(loc, (list, tuple)):
                    self.latitude = float(loc[0]) if len(loc) > 0 else 0.0
                    self.longitude = float(loc[1]) if len(loc) > 1 else 0.0
                    self.altitude = float(loc[2]) if len(loc) > 2 else 0.0
                    found_location = True
            elif "locationLatitude" in sensor_map and "locationLongitude" in sensor_map:
                self.latitude = self._extract_float(sensor_map["locationLatitude"], 0.0)
                self.longitude = self._extract_float(sensor_map["locationLongitude"], 0.0)
                self.altitude = self._extract_float(sensor_map.get("locationAltitude"), 0.0)
                found_location = True
        except Exception:
            pass

        # Extract gravity
        found_gravity = False
        if "gravity" in sensor_map:
            grav = sensor_map["gravity"]
            if isinstance(grav, dict):
                self.gravity_x = float(grav.get("x", grav.get("X", 0.0)))
                self.gravity_y = float(grav.get("y", grav.get("Y", 0.0)))
                self.gravity_z = float(grav.get("z", grav.get("Z", 9.80665)))
                found_gravity = True
            elif isinstance(grav, (list, tuple)) and len(grav) >= 3:
                try:
                    self.gravity_x = float(grav[0])
                    self.gravity_y = float(grav[1])
                    self.gravity_z = float(grav[2])
                    found_gravity = True
                except (ValueError, TypeError):
                    pass
        elif "gravityX" in sensor_map and "gravityY" in sensor_map and "gravityZ" in sensor_map:
            self.gravity_x = self._extract_float(sensor_map["gravityX"], 0.0)
            self.gravity_y = self._extract_float(sensor_map["gravityY"], 0.0)
            self.gravity_z = self._extract_float(sensor_map["gravityZ"], 9.80665)
            found_gravity = True

        # Quaternions computation
        found_orient = False
        if "quaternionW" in sensor_map and "quaternionX" in sensor_map and "quaternionY" in sensor_map and "quaternionZ" in sensor_map:
            self.qw = self._extract_float(sensor_map["quaternionW"], 1.0)
            self.qx = self._extract_float(sensor_map["quaternionX"], 0.0)
            self.qy = self._extract_float(sensor_map["quaternionY"], 0.0)
            self.qz = self._extract_float(sensor_map["quaternionZ"], 0.0)
            found_orient = True
        elif "orientationRoll" in sensor_map and "orientationPitch" in sensor_map and "orientationYaw" in sensor_map:
            roll = self._extract_float(sensor_map["orientationRoll"], 0.0)
            pitch = self._extract_float(sensor_map["orientationPitch"], 0.0)
            yaw = self._extract_float(sensor_map["orientationYaw"], 0.0)
            roll_rad = math.radians(roll)
            pitch_rad = math.radians(pitch)
            yaw_rad = math.radians(yaw)
            cy = math.cos(yaw_rad * 0.5)
            sy = math.sin(yaw_rad * 0.5)
            cp = math.cos(pitch_rad * 0.5)
            sp = math.sin(pitch_rad * 0.5)
            cr = math.cos(roll_rad * 0.5)
            sr = math.sin(roll_rad * 0.5)
            self.qw = cr * cp * cy + sr * sp * sy
            self.qx = sr * cp * cy - cr * sp * sy
            self.qy = cr * sp * cy + sr * cp * sy
            self.qz = cr * cp * sy - sr * sp * cy
            found_orient = True
        elif "attitudeRoll" in sensor_map and "attitudePitch" in sensor_map and "attitudeYaw" in sensor_map:
            roll = self._extract_float(sensor_map["attitudeRoll"], 0.0)
            pitch = self._extract_float(sensor_map["attitudePitch"], 0.0)
            yaw = self._extract_float(sensor_map["attitudeYaw"], 0.0)
            roll_rad = math.radians(roll)
            pitch_rad = math.radians(pitch)
            yaw_rad = math.radians(yaw)
            cy = math.cos(yaw_rad * 0.5)
            sy = math.sin(yaw_rad * 0.5)
            cp = math.cos(pitch_rad * 0.5)
            sp = math.sin(pitch_rad * 0.5)
            cr = math.cos(roll_rad * 0.5)
            sr = math.sin(roll_rad * 0.5)
            self.qw = cr * cp * cy + sr * sp * sy
            self.qx = sr * cp * cy - cr * sp * sy
            self.qy = cr * sp * cy + sr * cp * sy
            self.qz = cr * cp * sy - sr * sp * cy
            found_orient = True
        else:
            orient_key = next((k for k in ["orientation", "quaternion", "attitude", "deviceMotion"] if k in sensor_map), None)
            if orient_key:
                values = sensor_map[orient_key]
                if isinstance(values, dict) and "attitude" in values:
                    values = values["attitude"]
                if isinstance(values, dict) and "quaternion" in values:
                    values = values["quaternion"]
                    
                if isinstance(values, dict):
                    has_quat_keys = any(k in values for k in ("w", "qw", "qW"))
                    if has_quat_keys:
                        self.qw = float(values.get("w") or values.get("qw") or values.get("qW") or 1.0)
                        self.qx = float(values.get("x") or values.get("qx") or values.get("qX") or 0.0)
                        self.qy = float(values.get("y") or values.get("qy") or values.get("qY") or 0.0)
                        self.qz = float(values.get("z") or values.get("qz") or values.get("qZ") or 0.0)
                        found_orient = True
                    else:
                        roll = float(values.get("roll") or values.get("roll_deg") or values.get("r") or values.get("x") or 0.0)
                        pitch = float(values.get("pitch") or values.get("pitch_deg") or values.get("p") or values.get("y") or 0.0)
                        yaw = float(values.get("yaw") or values.get("yaw_deg") or values.get("y") or values.get("z") or values.get("heading") or 0.0)
                        
                        roll_rad = math.radians(roll)
                        pitch_rad = math.radians(pitch)
                        yaw_rad = math.radians(yaw)
                        
                        cy = math.cos(yaw_rad * 0.5)
                        sy = math.sin(yaw_rad * 0.5)
                        cp = math.cos(pitch_rad * 0.5)
                        sp = math.sin(pitch_rad * 0.5)
                        cr = math.cos(roll_rad * 0.5)
                        sr = math.sin(roll_rad * 0.5)
                        
                        self.qw = cr * cp * cy + sr * sp * sy
                        self.qx = sr * cp * cy - cr * sp * sy
                        self.qy = cr * sp * cy + sr * cp * sy
                        self.qz = cr * cp * sy - sr * sp * cy
                        found_orient = True

        if getattr(self, 'is_simulated', False):
            found_accel = True
            found_gyro = True
            found_mag = True
            found_orient = True
            found_compass = True
            found_light = True
            found_barometer = True
            found_battery = True
            found_location = True
            found_pedometer = True
            found_activity = True
            found_heart_rate = True

        if found_orient:
            # Stable Quaternion-to-Euler conversion for display/logging
            sinr_cosp = 2.0 * (self.qw * self.qx + self.qy * self.qz)
            cosr_cosp = 1.0 - 2.0 * (self.qx**2 + self.qy**2)
            self.filt_roll = math.atan2(sinr_cosp, cosr_cosp)

            sinp = 2.0 * (self.qw * self.qy - self.qz * self.qx)
            if abs(sinp) >= 1.0:
                self.filt_pitch = math.copysign(math.pi / 2.0, sinp)
            else:
                self.filt_pitch = math.asin(sinp)

            siny_cosp = 2.0 * (self.qw * self.qz + self.qx * self.qy)
            cosy_cosp = 1.0 - 2.0 * (self.qy**2 + self.qz**2)
            self.filt_yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp))
        else:
            if not found_gyro:
                # Lock to static identity quaternion to prevent drift spinning
                self.qw = 1.0
                self.qx = 0.0
                self.qy = 0.0
                self.qz = 0.0
                self.filt_pitch = 0.0
                self.filt_roll = 0.0
                self.filt_yaw = 0.0
            else:
                # IMU Noise Gate & Free Fall Fallback to filter static sensor noise
                accel_mag = math.sqrt(self.x**2 + self.y**2 + self.z**2)
                if accel_mag > 0.5:
                    pitch_acc = math.atan2(self.y, math.sqrt(self.x**2 + self.z**2))
                    roll_acc = math.atan2(-self.x, self.z)
                else:
                    pitch_acc = 0.0
                    roll_acc = 0.0
                
                dt = now_time - self.last_update_time if self.last_update_time > 0 else 0.016
                if dt <= 0 or dt > 1.0:
                    dt = 0.016
                self.last_update_time = now_time

                # Gyro noise gate to prevent integration of static noise drift
                gyro_mag = math.sqrt(self.gx**2 + self.gy**2 + self.gz**2)
                if gyro_mag < 0.05:
                    self.gx = 0.0
                    self.gy = 0.0
                    self.gz = 0.0

                self.filt_pitch = 0.98 * (self.filt_pitch + self.gx * dt) + 0.02 * pitch_acc
                self.filt_roll = 0.98 * (self.filt_roll + self.gy * dt) + 0.02 * roll_acc
                
                # Integrate gyro yaw (convert rad/s to deg/s, then integrate)
                if gyro_mag >= 0.05:
                    self.filt_yaw += math.degrees(self.gz * dt)
                
                # Normalize yaw to [-180, 180] degrees
                self.filt_yaw = (self.filt_yaw + 180) % 360 - 180

                if self.mag_x != 0.0 or self.mag_y != 0.0 or self.mag_z != 0.0:
                    mag_mag = math.sqrt(self.mag_x**2 + self.mag_y**2 + self.mag_z**2)
                    if mag_mag > 1e-6:
                        mag_yaw_rad = math.atan2(self.mag_y / mag_mag, self.mag_x / mag_mag)
                        mag_yaw_deg = math.degrees(mag_yaw_rad)
                        if self.compass_heading > 0:
                            self.filt_yaw = 0.98 * self.filt_yaw + 0.02 * self.compass_heading
                        else:
                            self.filt_yaw = 0.98 * self.filt_yaw + 0.02 * mag_yaw_deg
                else:
                    # Without magnetometer, keep the integrated gyro yaw completely stable (no decay)
                    pass

                yaw_rad = math.radians(self.filt_yaw)
                cy = math.cos(yaw_rad * 0.5)
                sy = math.sin(yaw_rad * 0.5)
                cp = math.cos(self.filt_pitch * 0.5)
                sp = math.sin(self.filt_pitch * 0.5)
                cr = math.cos(self.filt_roll * 0.5)
                sr = math.sin(self.filt_roll * 0.5)

                self.qw = cr * cp * cy + sr * sp * sy
                self.qx = sr * cp * cy - cr * sp * sy
                self.qy = cr * sp * cy + sr * cp * sy
                self.qz = cr * cp * sy - sr * sp * cy

        # Publish IMU Message only if new IMU data is present in the current request
        if found_accel or found_gyro or found_orient or found_mag or found_compass:
            imu_msg = Imu()
            imu_msg.header.stamp = self.get_clock().now().to_msg()
            imu_msg.header.frame_id = "imu_sensor_link"
            
            imu_msg.linear_acceleration.x = self.x
            imu_msg.linear_acceleration.y = self.y
            imu_msg.linear_acceleration.z = self.z
            
            imu_msg.angular_velocity.x = self.gx
            imu_msg.angular_velocity.y = self.gy
            imu_msg.angular_velocity.z = self.gz
    
            imu_msg.orientation.w = self.qw
            imu_msg.orientation.x = self.qx
            imu_msg.orientation.y = self.qy
            imu_msg.orientation.z = self.qz
    
            try:
                if rclpy.ok():
                    self.imu_target_pub.publish(imu_msg)
                    self.imu_state_pub.publish(imu_msg)
            except Exception:
                pass

        # Update last update times
        if found_accel: self.last_accel_time = now_time
        if found_gyro: self.last_gyro_time = now_time
        if found_mag: self.last_mag_time = now_time
        if found_orient: self.last_orient_time = now_time
        if found_compass: self.last_compass_time = now_time
        if found_heart_rate: self.last_heart_rate_time = now_time
        if found_light: self.last_light_time = now_time
        if found_barometer: self.last_baro_time = now_time
        if found_location: self.last_location_time = now_time
        if found_pedometer: self.last_pedometer_time = now_time
        if found_activity: self.last_activity_time = now_time

        # Check active online status based on 8-second timeout
        TIMEOUT = 8.0
        accel_online = (now_time - self.last_accel_time < TIMEOUT)
        gyro_online = (now_time - self.last_gyro_time < TIMEOUT)
        mag_online = (now_time - self.last_mag_time < TIMEOUT)
        orient_online = (now_time - self.last_orient_time < TIMEOUT)
        compass_online = (now_time - self.last_compass_time < TIMEOUT)
        hr_online = (now_time - self.last_heart_rate_time < TIMEOUT)
        light_online = (now_time - self.last_light_time < TIMEOUT)
        baro_online = (now_time - self.last_baro_time < TIMEOUT)
        loc_online = (now_time - self.last_location_time < TIMEOUT)
        ped_online = (now_time - self.last_pedometer_time < TIMEOUT)
        act_online = (now_time - self.last_activity_time < TIMEOUT)

        # Publish Wristband JointState message
        js_msg = JointState()
        js_msg.header.stamp = self.get_clock().now().to_msg()
        js_msg.name = [
            "is_falling", "emergency_button_pressed", "heart_rate", "heart_status",
            "accel_status", "accel_x", "accel_y", "accel_z",
            "gyro_status", "gyro_x", "gyro_y", "gyro_z",
            "mag_status", "mag_x", "mag_y", "mag_z",
            "orient_status", "orient_w", "orient_x", "orient_y", "orient_z",
            "compass_status", "compass_heading",
            "gravity_status", "gravity_x", "gravity_y", "gravity_z",
            "light_status", "ambient_light",
            "baro_status", "barometric_pressure",
            "gps_status", "latitude", "longitude", "altitude",
            "pedometer_status", "pedometer_steps",
            "activity_status", "activity_type",
            "wrist_status", "wrist_motion_magnitude",
            "battery_level", "battery_temp"
        ]
        js_msg.position = [
            float(is_falling),
            float(is_falling),
            float(self.heart_rate) if hr_online else float('nan'),
            float(hr_online),
            
            float(accel_online),
            float(self.x) if accel_online else float('nan'),
            float(self.y) if accel_online else float('nan'),
            float(self.z) if accel_online else float('nan'),
            
            float(gyro_online),
            float(self.gx) if gyro_online else float('nan'),
            float(self.gy) if gyro_online else float('nan'),
            float(self.gz) if gyro_online else float('nan'),
            
            float(mag_online),
            float(self.mag_x) if mag_online else float('nan'),
            float(self.mag_y) if mag_online else float('nan'),
            float(self.mag_z) if mag_online else float('nan'),
            
            float(orient_online),
            float(self.qw) if orient_online else float('nan'),
            float(self.qx) if orient_online else float('nan'),
            float(self.qy) if orient_online else float('nan'),
            float(self.qz) if orient_online else float('nan'),
            
            float(compass_online),
            float(self.compass_heading) if compass_online else float('nan'),
            
            float(accel_online),
            float(self.gravity_x) if accel_online else float('nan'),
            float(self.gravity_y) if accel_online else float('nan'),
            float(self.gravity_z) if accel_online else float('nan'),
            
            float(light_online),
            float(self.ambient_light) if light_online else float('nan'),
            
            float(baro_online),
            float(self.barometric_pressure) if baro_online else float('nan'),
            
            float(loc_online),
            float(self.latitude) if loc_online else float('nan'),
            float(self.longitude) if loc_online else float('nan'),
            float(self.altitude) if loc_online else float('nan'),
            
            float(ped_online),
            float(self.pedometer_steps) if ped_online else float('nan'),
            
            float(act_online),
            float(self.activity_type) if act_online else float('nan'),
            
            float(accel_online),
            float(self.g_magnitude) if accel_online else float('nan'),
            float(self.battery_level),
            float(self.battery_temp)
        ]
        try:
            if rclpy.ok():
                self.vitals_pub.publish(js_msg)
        except Exception:
            pass

        self.get_logger().info(
            f"[INGESTION] Accel=({self.x:.2f}, {self.y:.2f}, {self.z:.2f}) | "
            f"Yaw={self.filt_yaw:.1f}deg | FallState={is_falling}"
        )

        # Bridge to MQTT for Spring Boot Backend & Dashboard
        if self.mqtt_client:
            try:
                # IMU Target
                if found_accel or found_gyro or found_mag or found_orient or found_compass:
                    # Magnetometer: if we have never parsed a magnetometer or heading (all zeros), send None to indicate NO HW
                    has_mag = (self.mag_x != 0.0 or self.mag_y != 0.0 or self.mag_z != 0.0)
                    has_compass = (self.compass_heading != 0.0)
                    
                    imu_payload = {
                        "orientation": {
                            "qw": self.qw,
                            "qx": self.qx,
                            "qy": self.qy,
                            "qz": self.qz
                        },
                        "angular_velocity": {
                            "x": self.gx,
                            "y": self.gy,
                            "z": self.gz
                        },
                        "linear_acceleration": {
                            "x": self.x,
                            "y": self.y,
                            "z": self.z
                        },
                        "magnetometer": {
                            "x": self.mag_x if has_mag else None,
                            "y": self.mag_y if has_mag else None,
                            "z": self.mag_z if has_mag else None
                        },
                        "compass_heading": self.compass_heading if has_compass else None,
                        "position": {
                            "x": 0.0,
                            "y": 0.0,
                            "z": 0.0
                        },
                        "is_simulated": getattr(self, 'is_simulated', False),
                        "timestamp_ms": timestamp_ms
                    }
                    self.mqtt_client.publish("hk07/sensors/imu/target", json.dumps(imu_payload), qos=0)
                    self.get_logger().info(f"[PUBLISH MQTT] Topic: hk07/sensors/imu/target | Fields: {list(imu_payload.keys())} | Data: {json.dumps(imu_payload)}")

                # Environment State
                # BUG FIX: barometric_pressure is None when phone has no barometer sensor.
                # Publish the field as null-safe: use None → JSON null to avoid misleading 1013.25 constant.
                if found_light or found_barometer or found_battery:
                    env_payload = {
                        "ambient_light": self.ambient_light,
                        "barometric_pressure": self.barometric_pressure,  # None → JSON null when no sensor
                        "pressure_delta_hpa": pressure_delta if found_barometer else None,
                        "battery_level": self.battery_level,
                        "battery_temp": self.battery_temp,
                        "is_simulated": getattr(self, 'is_simulated', False),
                        "timestamp_ms": timestamp_ms
                    }
                    self.mqtt_client.publish("hk07/sensors/environment/state", json.dumps(env_payload), qos=0)
                    self.get_logger().info(f"[PUBLISH MQTT] Topic: hk07/sensors/environment/state | Fields: {list(env_payload.keys())} | Data: {json.dumps(env_payload)}")

                # Location GPS
                if found_location:
                    loc_payload = {
                        "latitude": self.latitude,
                        "longitude": self.longitude,
                        "altitude": self.altitude,
                        "is_simulated": getattr(self, 'is_simulated', False),
                        "timestamp_ms": timestamp_ms
                    }
                    self.mqtt_client.publish("hk07/sensors/location/gps", json.dumps(loc_payload), qos=0)
                    self.get_logger().info(f"[PUBLISH MQTT] Topic: hk07/sensors/location/gps | Fields: {list(loc_payload.keys())} | Data: {json.dumps(loc_payload)}")

                # Activity Metrics
                if found_pedometer or found_activity or found_accel:
                    act_str_map = {
                        1.0: "stationary",
                        2.0: "walking",
                        3.0: "running",
                        4.0: "automotive",
                        5.0: "cycling",
                        0.0: "unknown"
                    }
                    activity_str = act_str_map.get(self.activity_type, "unknown") if found_activity else "unknown"
                    act_payload = {
                        "pedometer_steps": int(self.pedometer_steps) if found_pedometer else 0,
                        "activity_type": activity_str,
                        "wrist_motion": [self.x, self.y, self.z] if found_accel else [0.0, 0.0, 0.0],
                        "is_simulated": getattr(self, 'is_simulated', False),
                        "timestamp_ms": timestamp_ms
                    }
                    self.mqtt_client.publish("hk07/sensors/activity/metrics", json.dumps(act_payload), qos=0)
                    self.get_logger().info(f"[PUBLISH MQTT] Topic: hk07/sensors/activity/metrics | Fields: {list(act_payload.keys())} | Data: {json.dumps(act_payload)}")
            except Exception as e:
                self.get_logger().error(f"Failed to publish telemetry to MQTT: {e}")

    def sim_timer_callback(self):
        # Only run if ROBOT_MODE is SIMULATED
        if self.robot_mode != "SIMULATED":
            return
        
        now = time.time()
        # If no real data has been received for 5 seconds
        if now - self.last_accel_time > 5.0:
            # Generate simulated/mock sensor data
            self.tick = getattr(self, 'tick', 0) + 1
            
            # Accelerometer Z should be around 9.8 (gravity)
            ax = 0.1 * math.sin(self.tick * 0.1) + random.uniform(-0.02, 0.02)
            ay = -0.01 * math.cos(self.tick * 0.1) + random.uniform(-0.02, 0.02)
            az = 9.80665 + 0.1 * math.sin(self.tick * 0.05) + random.uniform(-0.02, 0.02)
            
            # Gyro
            gx = 0.005 * math.sin(self.tick * 0.1)
            gy = 0.005 * math.cos(self.tick * 0.1)
            gz = 0.002 * math.sin(self.tick * 0.05)
            
            # Mag
            mx = -2.0 + 0.5 * math.sin(self.tick * 0.1)
            my = 42.0 + 2.0 * math.cos(self.tick * 0.1)
            mz = -8.0 + 1.0 * math.sin(self.tick * 0.05)
            
            # Compass
            compass = (self.tick * 2.0) % 360
            
            # Light (lux)
            light = 50.0 + 10.0 * math.sin(self.tick * 0.01) + random.uniform(-1, 1)
            
            # Barometer (hPa)
            baro = 1013.25 + 0.5 * math.sin(self.tick * 0.02)
            
            # Battery
            bat_level = max(20.0, 100.0 - (self.tick * 0.01) % 80)
            bat_temp = 32.0 + 2.0 * math.sin(self.tick * 0.05)
            
            # Location
            lat = 10.395481 + 0.0001 * math.sin(self.tick * 0.01)
            lon = 105.421268 + 0.0001 * math.cos(self.tick * 0.01)
            alt = 12.0
            
            # Pedometer
            steps = self.tick // 5
            
            # Activity type: 1 = stationary, 2 = walking
            act_type = 2.0 if (self.tick % 60 > 30) else 1.0
            
            with self.state_lock:
                self.is_simulated = True
                self.x = ax
                self.y = ay
                self.z = az
                self.gx = gx
                self.gy = gy
                self.gz = gz
                self.mag_x = mx
                self.mag_y = my
                self.mag_z = mz
                self.compass_heading = compass
                self.ambient_light = light
                self.barometric_pressure = baro
                self.battery_level = bat_level
                self.battery_temp = bat_temp
                self.latitude = lat
                self.longitude = lon
                self.altitude = alt
                self.pedometer_steps = steps
                self.activity_type = act_type
                
                # Setup values that mimic a parsed payload list
                sensor_map = {
                    "accelerometer": True, "gyroscope": True, "magnetometer": True,
                    "compass": True, "light": True, "barometer": True,
                    "batteryLevel": True, "batteryTemp": True, "location": True,
                    "pedometer": True, "activity": True
                }
                self._process_imu_and_vitals(sensor_map)

    def destroy_node(self):
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                self.get_logger().info("MQTT Client stopped and disconnected successfully.")
            except Exception as e:
                self.get_logger().error(f"Error disconnecting MQTT Client: {e}")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = HugoPerceptionBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.server:
            node.server.shutdown()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
