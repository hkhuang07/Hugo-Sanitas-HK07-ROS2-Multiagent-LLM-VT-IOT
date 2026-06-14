import os
import sys
import math
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

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

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "Empty body"}')
                return

            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # Pass payload to the parent ROS2 Node
            self.server.node.process_payload(data)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "success"}')
        except Exception as e:
            self.send_response(500)
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

        # ROS 2 Publishers
        self.imu_pub = self.create_publisher(Imu, '/telemetry/imu', 10)
        self.vitals_pub = self.create_publisher(JointState, '/vitals/wristband', 10)

        # Start HTTP server thread
        self.server = None
        self.server_thread = None
        self.start_http_server()

        # Initialize MQTT Client for publishing mobile telemetry to Spring Boot backend
        self.mqtt_client = None
        if mqtt is not None:
            try:
                broker_host = os.environ.get('MQTT_HOST') or os.environ.get('MQTT_BROKER_HOST') or '127.0.0.1'
                broker_port = int(os.environ.get('MQTT_PORT') or os.environ.get('MQTT_BROKER_PORT') or 1883)
                mqtt_user = os.environ.get('MQTT_USERNAME', 'hk07agent')
                mqtt_pass = os.environ.get('MQTT_PASSWORD', 'hk07_mqtt_dev_pwd')
                self.mqtt_client = mqtt.Client(client_id="hk07-perception-bridge", protocol=mqtt.MQTTv311)
                if mqtt_user:
                    self.mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
                self.mqtt_client.connect_async(broker_host, broker_port, keepalive=30)
                self.mqtt_client.loop_start()
                self.get_logger().info(f"MQTT Bridge connected to {broker_host}:{broker_port} as user {mqtt_user}")
            except Exception as e:
                self.get_logger().warning(f"MQTT Bridge failed to initialize: {e}")

        self.get_logger().info("=== HUGO PERCEPTION ROS2 BRIDGE NODE INITIALIZED ===")

    def start_http_server(self):
        # Find an open port starting at 5005
        port = int(os.getenv("BRIDGE_PORT", "5005"))
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
            for k in ["value", "val", "steps", "lux", "light", "heart_rate", "heartRate", "activity"]:
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
        sensor_map = {
            item.get("name"): item.get("values", {})
            for item in payload_list
            if item.get("name")
        }

        if not sensor_map:
            return

        # Thread-safe telemetry processing
        with self.state_lock:
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
                raw_x = float(values.get("x", 0.0))
                raw_y = float(values.get("y", 0.0))
                raw_z = float(values.get("z", 9.80665))
                found_accel = True
            elif isinstance(values, (list, tuple)) and len(values) >= 3:
                try:
                    raw_x = float(values[0])
                    raw_y = float(values[1])
                    raw_z = float(values[2])
                    found_accel = True
                except (ValueError, TypeError):
                    pass
        else:
            raw_x = self.x * 9.80665
            raw_y = self.y * 9.80665
            raw_z = self.z * 9.80665

        raw_magnitude = math.sqrt(raw_x**2 + raw_y**2 + raw_z**2)
        self.x = raw_x / 9.80665
        self.y = raw_y / 9.80665
        self.z = raw_z / 9.80665
        self.g_magnitude = raw_magnitude / 9.80665

        if self.g_ema is None:
            self.g_ema = self.g_magnitude
        else:
            self.g_ema = 0.9 * self.g_ema + 0.1 * self.g_magnitude

        is_linear = (self.g_ema < 3.0)
        if is_linear:
            is_falling_now = (self.g_magnitude > 15.0)
        else:
            is_falling_now = (self.g_magnitude < 4.0) or (self.g_magnitude > 20.0)

        if is_falling_now:
            self.last_fall_time = now_time
            self.get_logger().warning(f"[FALL DETECTED] Sudden G-force spikes: {self.g_magnitude:.2f} Gs")

        # 2. Extract environment pressure delta
        try:
            if "barometer" in sensor_map:
                self.barometric_pressure = self._extract_float(sensor_map["barometer"], self.barometric_pressure)
        except Exception:
            pass

        self.pressure_buffer.append(self.barometric_pressure)
        if len(self.pressure_buffer) > self.buffer_size:
            self.pressure_buffer.pop(0)

        pressure_delta = 0.0
        if len(self.pressure_buffer) > 1:
            pressure_delta = self.pressure_buffer[-1] - self.pressure_buffer[0]

        # Dual-factor trigger verification
        is_fall_pressure_drop = (pressure_delta <= -5.0)
        is_fall_accel_spike = (self.g_magnitude > 2.5) or (is_linear and self.g_magnitude > 15.0)
        if is_fall_accel_spike and is_fall_pressure_drop:
            self.last_fall_time = now_time
            self.get_logger().critical(f"DUAL-FACTOR FALL TRIGGERED: accel={self.g_magnitude:.2f}g, pressure_delta={pressure_delta:.2f}hPa")

        # Check fallback cooldown state
        is_falling = (now_time - self.last_fall_time) < self.FALL_COOLDOWN_SEC

        # Auto-unlatch condition: if g_magnitude stays within standard earth gravity ranges (~1.0g) for over 1.5s
        is_gravity_normal = (0.85 <= self.g_magnitude <= 1.15)
        if is_gravity_normal:
            if not hasattr(self, "_safe_gravity_start_time") or self._safe_gravity_start_time is None:
                self._safe_gravity_start_time = now_time
        else:
            self._safe_gravity_start_time = None

        if is_falling and self._safe_gravity_start_time is not None:
            if (now_time - self._safe_gravity_start_time) >= 1.5:
                is_falling = False
                self.last_fall_time = 0.0
                self.get_logger().info("[FALL_RESET] Acceleration stabilized inside standard gravity range for 1.5s. Force-releasing E-STOP.")

        # 3. Process angles & complementary filter
        if "gyroscope" in sensor_map:
            vals = sensor_map["gyroscope"]
            if isinstance(vals, dict):
                self.gx = float(vals.get("x", 0.0))
                self.gy = float(vals.get("y", 0.0))
                self.gz = float(vals.get("z", 0.0))

        if "magnetometer" in sensor_map:
            mag_vals = sensor_map["magnetometer"]
            if isinstance(mag_vals, dict):
                self.mag_x = float(mag_vals.get("x", 0.0))
                self.mag_y = float(mag_vals.get("y", 0.0))
                self.mag_z = float(mag_vals.get("z", 0.0))

        # Extract compass / magneticHeading
        if "compass" in sensor_map:
            values = sensor_map["compass"]
            if isinstance(values, dict):
                self.compass_heading = float(values.get("heading", 0.0))
        elif "magneticHeading" in sensor_map:
            values = sensor_map["magneticHeading"]
            if isinstance(values, dict):
                self.compass_heading = float(values.get("heading", 0.0))

        # Extract heart rate
        try:
            raw_hr = None
            if "heart_rate" in sensor_map:
                raw_hr = sensor_map["heart_rate"]
            elif "heartRate" in sensor_map:
                raw_hr = sensor_map["heartRate"]
            if raw_hr is not None:
                self.heart_rate = self._extract_float(raw_hr, self.heart_rate)
        except Exception:
            pass

        # Extract light
        try:
            if "light" in sensor_map:
                self.ambient_light = self._extract_float(sensor_map["light"], self.ambient_light)
        except Exception:
            pass

        # Extract pedometer steps
        try:
            if "pedometer" in sensor_map:
                self.pedometer_steps = self._extract_float(sensor_map["pedometer"], self.pedometer_steps)
        except Exception:
            pass

        # Extract activity
        try:
            if "activity" in sensor_map:
                raw_act = sensor_map["activity"]
                act_num = self._extract_float(raw_act, None)
                if act_num is not None:
                    self.activity_type = act_num
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
        except Exception:
            pass

        # Extract location (GPS)
        try:
            if "location" in sensor_map:
                loc = sensor_map["location"]
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
                elif isinstance(loc, (list, tuple)):
                    self.latitude = float(loc[0]) if len(loc) > 0 else 0.0
                    self.longitude = float(loc[1]) if len(loc) > 1 else 0.0
                    self.altitude = float(loc[2]) if len(loc) > 2 else 0.0
        except Exception:
            pass

        # Extract gravity
        if "gravity" in sensor_map:
            grav = sensor_map["gravity"]
            if isinstance(grav, dict):
                self.gravity_x = float(grav.get("x", 0.0))
                self.gravity_y = float(grav.get("y", 0.0))
                self.gravity_z = float(grav.get("z", 9.80665))
            elif isinstance(grav, (list, tuple)) and len(grav) >= 3:
                try:
                    self.gravity_x = float(grav[0])
                    self.gravity_y = float(grav[1])
                    self.gravity_z = float(grav[2])
                except (ValueError, TypeError):
                    pass

        # Quaternions computation
        found_quat = False
        if "orientation" in sensor_map or "quaternion" in sensor_map:
            values = sensor_map.get("orientation") or sensor_map.get("quaternion", {})
            if isinstance(values, dict):
                self.qw = float(values.get("w", values.get("qw", 1.0)))
                self.qx = float(values.get("x", values.get("qx", 0.0)))
                self.qy = float(values.get("y", values.get("qy", 0.0)))
                self.qz = float(values.get("z", values.get("qz", 0.0)))
                found_quat = True

        if not found_quat:
            pitch_acc = math.atan2(self.y, math.sqrt(self.x**2 + self.z**2))
            roll_acc = math.atan2(-self.x, self.z)
            
            dt = now_time - self.last_update_time if self.last_update_time > 0 else 0.016
            if dt <= 0 or dt > 1.0:
                dt = 0.016
            self.last_update_time = now_time

            self.filt_pitch = 0.98 * (self.filt_pitch + self.gx * dt) + 0.02 * pitch_acc
            self.filt_roll = 0.98 * (self.filt_roll + self.gy * dt) + 0.02 * roll_acc
            
            if self.mag_x != 0.0 or self.mag_y != 0.0 or self.mag_z != 0.0:
                mag_mag = math.sqrt(self.mag_x**2 + self.mag_y**2 + self.mag_z**2)
                if mag_mag > 1e-6:
                    mag_yaw_rad = math.atan2(self.mag_y / mag_mag, self.mag_x / mag_mag)
                    mag_yaw_deg = math.degrees(mag_yaw_rad)
                    if self.compass_heading > 0:
                        self.filt_yaw = 0.9 * self.filt_yaw + 0.1 * self.compass_heading
                    else:
                        self.filt_yaw = 0.9 * self.filt_yaw + 0.1 * mag_yaw_deg

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

        # Publish IMU Message
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
                self.imu_pub.publish(imu_msg)
        except Exception:
            pass

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
            "wrist_status", "wrist_motion_magnitude"
        ]
        js_msg.position = [
            float(is_falling), float(is_falling), float(self.heart_rate), 1.0,
            1.0, float(self.x), float(self.y), float(self.z),
            1.0, float(self.gx), float(self.gy), float(self.gz),
            1.0, float(self.mag_x), float(self.mag_y), float(self.mag_z),
            1.0, float(self.qw), float(self.qx), float(self.qy), float(self.qz),
            1.0, float(self.compass_heading),
            1.0, float(self.gravity_x), float(self.gravity_y), float(self.gravity_z),
            1.0, float(self.ambient_light),
            1.0, float(self.barometric_pressure),
            1.0, float(self.latitude), float(self.longitude), float(self.altitude),
            1.0, float(self.pedometer_steps),
            1.0, float(self.activity_type),
            1.0, float(self.g_magnitude)
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
                imu_payload = {
                    "orientation": {
                        "w": self.qw,
                        "x": self.qx,
                        "y": self.qy,
                        "z": self.qz
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
                        "x": self.mag_x,
                        "y": self.mag_y,
                        "z": self.mag_z
                    },
                    "compass_heading": self.compass_heading,
                    "position": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0
                    },
                    "timestamp_ms": timestamp_ms
                }
                self.mqtt_client.publish("hk07/sensors/imu/target", json.dumps(imu_payload), qos=0)

                # Environment State
                env_payload = {
                    "ambient_light": self.ambient_light,
                    "barometric_pressure": self.barometric_pressure,
                    "pressure_delta_hpa": pressure_delta,
                    "timestamp_ms": timestamp_ms
                }
                self.mqtt_client.publish("hk07/sensors/environment/state", json.dumps(env_payload), qos=0)

                # Location GPS
                loc_payload = {
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "altitude": self.altitude,
                    "timestamp_ms": timestamp_ms
                }
                self.mqtt_client.publish("hk07/sensors/location/gps", json.dumps(loc_payload), qos=0)

                # Activity Metrics
                act_str_map = {
                    1.0: "stationary",
                    2.0: "walking",
                    3.0: "running",
                    4.0: "automotive",
                    5.0: "cycling",
                    0.0: "unknown"
                }
                activity_str = act_str_map.get(self.activity_type, "unknown")
                act_payload = {
                    "pedometer_steps": int(self.pedometer_steps),
                    "activity_type": activity_str,
                    "wrist_motion": [self.x, self.y, self.z],
                    "timestamp_ms": timestamp_ms
                }
                self.mqtt_client.publish("hk07/sensors/activity/metrics", json.dumps(act_payload), qos=0)
            except Exception as e:
                self.get_logger().error(f"Failed to publish telemetry to MQTT: {e}")

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
