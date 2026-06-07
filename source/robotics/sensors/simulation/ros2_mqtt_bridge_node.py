import os
import sys
import time
import json
import struct
import logging
import threading
import paho.mqtt.client as mqtt
try:
    import rclpy
    from rclpy.node import Node
except ImportError:
    print("=================================================================================")
    print(">>> [ROBOTICS ARCHITECTURE ERROR] ROS 2 client library 'rclpy' is not installed.")
    print(">>> This node MUST be executed inside the WSL (Ubuntu) environment where ROS 2 is sourced.")
    print(">>> Run: source /opt/ros/humble/setup.bash and try again.")
    print("=================================================================================")
    sys.exit(1)

from sensor_msgs.msg import Imu, JointState, PointCloud2
from geometry_msgs.msg import Twist
from std_msgs.msg import Header, String

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("mqtt_bridge")

# Load environment configurations
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

MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "hk07sim")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")

# Topics map
TOPIC_MQTT_IMU_TARGET = "hk07/sensors/imu/target"
TOPIC_MQTT_IMU_RESOLVED = "hk07/telemetry/imu"
TOPIC_MQTT_LIDAR_POINTS = "hk07/telemetry/lidar/points"
TOPIC_MQTT_AVOIDANCE = "hk07/telemetry/avoidance"
TOPIC_MQTT_JOINT_STATES = "hk07/telemetry/joint_states"
TOPIC_MQTT_PMU = "hk07/telemetry/pmu"
TOPIC_MQTT_PNEUMATIC = "hk07/telemetry/pneumatic"
TOPIC_MQTT_ACTUATORS_JOINTS = "hk07/telemetry/actuators/joints"
TOPIC_MQTT_TACTILE = "hk07/telemetry/sensors/tactile"
TOPIC_MQTT_VITALS = "hk07/telemetry/sensors/vitals"
TOPIC_MQTT_THERMAL_RPPG = "hk07/sensors/camera/thermal_rppg"

TOPIC_MQTT_SUB_IMU_STATE = "hk07/sensors/imu/state"
TOPIC_MQTT_SUB_WRISTBAND = "hk07/vitals/wristband"

class Ros2MqttBridge(Node):
    def __init__(self):
        super().__init__('ros2_mqtt_bridge_node')
        
        # Initialize MQTT Client
        self.mqtt_client = mqtt.Client(client_id="hk07-ros2-mqtt-bridge", protocol=mqtt.MQTTv311)
        self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        # Connect to MQTT Broker
        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            # Start MQTT loop in thread
            self.mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever, daemon=True)
            self.mqtt_thread.start()
            log.info(f"MQTT Client loop started. Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        except Exception as e:
            log.critical(f"Could not connect to MQTT Broker: {e}")
            
        # ROS 2 Publishers (for bridging MQTT -> ROS2)
        self.imu_state_pub = self.create_publisher(Imu, '/sensors/imu/state', 10)
        self.wristband_pub = self.create_publisher(JointState, '/vitals/wristband', 10)
        self.heartbeat_pub = self.create_publisher(Header, '/system/heartbeat', 10)
        self.subsumption_inhibit_pub = self.create_publisher(String, '/control/subsumption/inhibit', 10)
        
        # ROS 2 Subscriptions (for bridging ROS2 -> MQTT)
        self.target_sub = self.create_subscription(Imu, '/sensors/imu/target', self.ros_target_callback, 10)
        self.resolved_sub = self.create_subscription(Imu, '/telemetry/imu', self.ros_resolved_callback, 10)
        self.lidar_sub = self.create_subscription(PointCloud2, '/telemetry/lidar/points', self.ros_lidar_callback, 10)
        self.avoidance_sub = self.create_subscription(Twist, '/telemetry/avoidance', self.ros_avoidance_callback, 10)
        self.joint_states_sub = self.create_subscription(JointState, '/telemetry/joint_states', self.ros_joint_states_callback, 10)
        
        # Additional Telemetry from simulation
        self.pmu_sub = self.create_subscription(JointState, '/telemetry/pmu', self.ros_pmu_callback, 10)
        self.pneumatic_sub = self.create_subscription(JointState, '/telemetry/pneumatic', self.ros_pneumatic_callback, 10)
        self.joints_sub = self.create_subscription(JointState, '/telemetry/actuators/joints', self.ros_actuator_joints_callback, 10)
        self.tactile_sub = self.create_subscription(JointState, '/telemetry/sensors/tactile', self.ros_tactile_callback, 10)
        self.vitals_sub = self.create_subscription(JointState, '/telemetry/sensors/vitals', self.ros_vitals_callback, 10)
        self.thermal_rppg_sub = self.create_subscription(JointState, '/sensors/camera/thermal_rppg', self.ros_thermal_rppg_callback, 10)
        self.cmd_vel_sub = self.create_subscription(Twist, '/control/motion/cmd_vel', self.ros_cmd_vel_callback, 10)
        
        log.info("=== HK07 ROS2-MQTT BRIDGE NODE INITIALIZED ===")

    # MQTT Callbacks
    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("Bridge successfully connected to Mosquitto MQTT Broker.")
            client.subscribe(TOPIC_MQTT_SUB_IMU_STATE)
            client.subscribe(TOPIC_MQTT_SUB_WRISTBAND)
            client.subscribe("hk07/system/heartbeat")
            client.subscribe("hk07/control/subsumption/inhibit")
            log.info(f"Subscribed MQTT topics: {TOPIC_MQTT_SUB_IMU_STATE}, {TOPIC_MQTT_SUB_WRISTBAND}, hk07/system/heartbeat, hk07/control/subsumption/inhibit")
        else:
            log.error(f"Bridge failed to connect to Mosquitto, return code {rc}")

    def on_mqtt_message(self, client, userdata, msg):
        try:
            payload_data = json.loads(msg.payload.decode())
            stamp = self.get_clock().now().to_msg()
            
            if msg.topic == TOPIC_MQTT_SUB_IMU_STATE:
                # Bridge: JSON -> sensor_msgs/Imu
                x = float(payload_data.get("accel_x", 0.0))
                y = float(payload_data.get("accel_y", 0.0))
                z = float(payload_data.get("accel_z", 9.81))
                
                imu_msg = Imu()
                imu_msg.header.stamp = stamp
                imu_msg.header.frame_id = "imu_sensor_link"
                imu_msg.linear_acceleration.x = x
                imu_msg.linear_acceleration.y = y
                imu_msg.linear_acceleration.z = z
                
                # Optionals
                gyro_x = float(payload_data.get("gyro_x", 0.0))
                gyro_y = float(payload_data.get("gyro_y", 0.0))
                gyro_z = float(payload_data.get("gyro_z", 0.0))
                imu_msg.angular_velocity.x = gyro_x
                imu_msg.angular_velocity.y = gyro_y
                imu_msg.angular_velocity.z = gyro_z
                
                self.imu_state_pub.publish(imu_msg)
                
            elif msg.topic == TOPIC_MQTT_SUB_WRISTBAND:
                # Bridge: JSON -> JointState
                is_falling = bool(payload_data.get("is_falling", False))
                emergency_pressed = bool(payload_data.get("emergency_button_pressed", False))
                
                js_msg = JointState()
                js_msg.header.stamp = stamp
                js_msg.name = ["is_falling", "emergency_button_pressed"]
                js_msg.position = [float(is_falling), float(emergency_pressed)]
                
                self.wristband_pub.publish(js_msg)
                
            elif msg.topic == "hk07/system/heartbeat":
                hb_msg = Header()
                hb_msg.stamp = stamp
                hb_msg.frame_id = "middleware_heartbeat"
                self.heartbeat_pub.publish(hb_msg)
                
            elif msg.topic == "hk07/control/subsumption/inhibit":
                trigger = payload_data.get("trigger", "CLEAR")
                str_msg = String()
                str_msg.data = trigger
                self.subsumption_inhibit_pub.publish(str_msg)
                
        except Exception as e:
            log.error(f"Bridge error processing MQTT topic {msg.topic}: {e}")

    # ROS 2 Callbacks
    def ros_target_callback(self, msg):
        try:
            payload = {
                "header": {
                    "stamp": {
                        "sec": msg.header.stamp.sec,
                        "nanosec": msg.header.stamp.nanosec
                    },
                    "frame_id": msg.header.frame_id
                },
                "orientation": {
                    "w": round(msg.orientation.w, 5),
                    "x": round(msg.orientation.x, 5),
                    "y": round(msg.orientation.y, 5),
                    "z": round(msg.orientation.z, 5)
                },
                "position": {
                    "x": round(msg.angular_velocity.x, 3),
                    "y": round(msg.angular_velocity.y, 3),
                    "z": round(msg.angular_velocity.z, 3)
                }
            }
            self.mqtt_client.publish(TOPIC_MQTT_IMU_TARGET, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed target callback: {e}")

    def ros_resolved_callback(self, msg):
        try:
            payload = {
                "header": {
                    "stamp": {
                        "sec": msg.header.stamp.sec,
                        "nanosec": msg.header.stamp.nanosec
                    },
                    "frame_id": msg.header.frame_id
                },
                "orientation": {
                    "w": round(msg.orientation.w, 5),
                    "x": round(msg.orientation.x, 5),
                    "y": round(msg.orientation.y, 5),
                    "z": round(msg.orientation.z, 5)
                },
                "angular_velocity": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0
                },
                "linear_acceleration": {
                    "x": round(msg.linear_acceleration.x, 4),
                    "y": round(msg.linear_acceleration.y, 4),
                    "z": round(msg.linear_acceleration.z, 4)
                },
                "position": {
                    "x": round(msg.angular_velocity.x, 3),
                    "y": round(msg.angular_velocity.y, 3),
                    "z": round(msg.angular_velocity.z, 3)
                }
            }
            self.mqtt_client.publish(TOPIC_MQTT_IMU_RESOLVED, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed resolved callback: {e}")

    def ros_lidar_callback(self, msg):
        try:
            points = []
            point_step = msg.point_step
            data = msg.data
            num_points = msg.width * msg.height
            for i in range(num_points):
                offset = i * point_step
                if offset + 12 <= len(data):
                    x, y, z = struct.unpack_from('<fff', data, offset)
                    points.append({
                        "x": round(x, 3),
                        "y": round(y, 3),
                        "z": round(z, 3)
                    })
            payload = {
                "header": {
                    "stamp": {
                        "sec": msg.header.stamp.sec,
                        "nanosec": msg.header.stamp.nanosec
                    },
                    "frame_id": msg.header.frame_id
                },
                "height": msg.height,
                "width": msg.width,
                "points": points
            }
            self.mqtt_client.publish(TOPIC_MQTT_LIDAR_POINTS, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed LiDAR callback: {e}")

    def ros_avoidance_callback(self, msg):
        try:
            payload = {
                "linear": {
                    "x": round(msg.linear.x, 3),
                    "y": round(msg.linear.y, 3),
                    "z": round(msg.linear.z, 3)
                },
                "angular": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0
                }
            }
            self.mqtt_client.publish(TOPIC_MQTT_AVOIDANCE, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed avoidance callback: {e}")

    def ros_cmd_vel_callback(self, msg):
        try:
            payload = {
                "linear": {
                    "x": round(msg.linear.x, 3),
                    "y": round(msg.linear.y, 3),
                    "z": round(msg.linear.z, 3)
                },
                "angular": {
                    "x": round(msg.angular.x, 3),
                    "y": round(msg.angular.y, 3),
                    "z": round(msg.angular.z, 3)
                }
            }
            self.mqtt_client.publish("hk07/control/motion/cmd_vel", json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed cmd_vel callback: {e}")

    def ros_joint_states_callback(self, msg):
        try:
            payload = {
                "header": {
                    "stamp": {
                        "sec": msg.header.stamp.sec,
                        "nanosec": msg.header.stamp.nanosec
                    },
                    "frame_id": msg.header.frame_id
                },
                "name": msg.name,
                "position": [round(p, 4) for p in msg.position],
                "velocity": [round(v, 4) for v in msg.velocity],
                "effort": [round(e, 4) for e in msg.effort]
            }
            self.mqtt_client.publish(TOPIC_MQTT_JOINT_STATES, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed joint states callback: {e}")

    def ros_pmu_callback(self, msg):
        try:
            # Map JointState -> PMU JSON
            sec = msg.header.stamp.sec
            nanosec = msg.header.stamp.nanosec
            timestamp_ms = int((sec + nanosec / 1e9) * 1000)
            
            payload = {
                "voltage": round(msg.position[0], 2),
                "current": round(msg.position[1], 2),
                "soc": round(msg.position[2], 3),
                "temp": round(msg.position[3], 1),
                "timestamp_ms": timestamp_ms
            }
            self.mqtt_client.publish(TOPIC_MQTT_PMU, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed PMU callback: {e}")

    def ros_pneumatic_callback(self, msg):
        try:
            # Map JointState -> Pneumatic JSON
            sec = msg.header.stamp.sec
            nanosec = msg.header.stamp.nanosec
            timestamp_ms = int((sec + nanosec / 1e9) * 1000)
            
            payload = {
                "press_L": round(msg.position[0], 2),
                "press_R": round(msg.position[1], 2),
                "pump_active": bool(msg.position[2]),
                "relief_active": bool(msg.position[3]),
                "timestamp_ms": timestamp_ms
            }
            self.mqtt_client.publish(TOPIC_MQTT_PNEUMATIC, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed Pneumatics callback: {e}")

    def ros_actuator_joints_callback(self, msg):
        try:
            # Map JointState -> Actuators Joints Array
            payload = []
            for i, name in enumerate(msg.name):
                payload.append({
                    "name": name,
                    "angle": round(msg.position[i], 1),
                    "torque": round(msg.effort[i], 2),
                    "temp": round(msg.velocity[i], 1)
                })
            self.mqtt_client.publish(TOPIC_MQTT_ACTUATORS_JOINTS, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed Actuators Joints callback: {e}")

    def ros_tactile_callback(self, msg):
        try:
            sec = msg.header.stamp.sec
            nanosec = msg.header.stamp.nanosec
            timestamp_ms = int((sec + nanosec / 1e9) * 1000)
            
            payload = {
                "hug_force": round(msg.position[0], 1),
                "flex_rate": round(msg.position[1], 1),
                "timestamp_ms": timestamp_ms
            }
            self.mqtt_client.publish(TOPIC_MQTT_TACTILE, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed Tactile callback: {e}")

    def ros_vitals_callback(self, msg):
        try:
            sec = msg.header.stamp.sec
            nanosec = msg.header.stamp.nanosec
            timestamp_ms = int((sec + nanosec / 1e9) * 1000)
            
            payload = {
                "heartRate": int(msg.position[0]),
                "spo2": round(msg.position[1], 1),
                "bodyTemperature": round(msg.position[2], 1),
                "stress_gsr": int(msg.position[3]),
                "respiratory_rate": int(msg.position[4]),
                "timestamp_ms": timestamp_ms
            }
            self.mqtt_client.publish(TOPIC_MQTT_VITALS, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed Vitals callback: {e}")

    def ros_thermal_rppg_callback(self, msg):
        try:
            rppg_hr = 0.0
            temp_thermal = 0.0
            fever_alert = 0.0
            
            for i, name in enumerate(msg.name):
                if name == "rppg_heart_rate":
                    rppg_hr = msg.position[i]
                elif name == "thermal_temperature":
                    temp_thermal = msg.position[i]
                elif name == "fever_alert":
                    fever_alert = msg.position[i]
                    
            sec = msg.header.stamp.sec
            nanosec = msg.header.stamp.nanosec
            timestamp_ms = int((sec + nanosec / 1e9) * 1000)
            
            payload = {
                "rppg_heart_rate": round(rppg_hr, 1),
                "thermal_temperature": round(temp_thermal, 2),
                "fever_alert": bool(fever_alert),
                "timestamp_ms": timestamp_ms
            }
            self.mqtt_client.publish(TOPIC_MQTT_THERMAL_RPPG, json.dumps(payload), qos=1)
        except Exception as e:
            log.error(f"Bridge failed Thermal/rPPG callback: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = Ros2MqttBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.mqtt_client.disconnect()
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
