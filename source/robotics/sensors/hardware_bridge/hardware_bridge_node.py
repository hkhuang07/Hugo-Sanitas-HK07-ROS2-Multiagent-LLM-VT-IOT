#!/usr/bin/env python3
"""
hardware_bridge_node.py — HK-07 ROS2 Hardware Bridge Node (Phase 6)

Bridges between physical ESP32 hardware (via MQTT) and the ROS2 ecosystem.

Key responsibilities:
  1. Receive MQTT telemetry from S3 (already SNTP epoch stamped)
  2. Convert epoch_ms → builtin_interfaces/Time (prevents TF "time travel" errors)
  3. Publish sensor data to ROS2 topics
  4. Subscribe to ROS2 command topics → forward to S3 via MQTT

★ SNTP Integration: Uses timestamp_ms from S3 payload (NOT local clock or millis())
★ Dead Man Monitor: Warns when system_state == 'ESTOP'

Usage (after colcon build):
    ros2 run sensors hardware_bridge_node

Topics published:
    /hardware/sensors/imu/robot    → sensor_msgs/Imu
    /hardware/sensors/vitals       → std_msgs/Float32MultiArray
    /hardware/sensors/environment  → std_msgs/Float32MultiArray
    /hardware/sensors/ultrasonic   → std_msgs/Float32MultiArray
    /hardware/status               → std_msgs/String

Topics subscribed:
    /hardware/control/cmd_vel      → geometry_msgs/Twist (→ MQTT hk07/robot/command)
    /hardware/control/emergency    → std_msgs/Empty     (→ CAN 0x300 E-Stop)

MQTT connection: uses .env from backend or env variables:
    HK07_MQTT_BROKER_IP    (default: 192.168.1.100)
    HK07_MQTT_BROKER_PORT  (default: 1883)
"""

import os
import json
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from builtin_interfaces.msg import Time
from sensor_msgs.msg import Imu, MagneticField
from std_msgs.msg import Float32MultiArray, String, Empty
from geometry_msgs.msg import Twist, Vector3

import paho.mqtt.client as mqtt

# ─── Configuration ─────────────────────────────────────────────────────────────
MQTT_BROKER_IP   = os.environ.get('HK07_MQTT_BROKER_IP',   '192.168.1.100')
MQTT_BROKER_PORT = int(os.environ.get('HK07_MQTT_BROKER_PORT', '1883'))
MQTT_CLIENT_ID   = 'hk07-ros2-bridge'

TOPIC_TELEMETRY  = 'hk07/robot/telemetry'
TOPIC_COMMAND    = 'hk07/robot/command'
TOPIC_STATUS     = 'hk07/robot/status'


def epoch_ms_to_ros_time(epoch_ms: int) -> Time:
    """
    ★ Convert S3's SNTP epoch milliseconds → ROS2 builtin_interfaces/Time.
    This is the key bridge to prevent TF 'time travel' errors.
    """
    t = Time()
    t.sec     = int(epoch_ms // 1000)
    t.nanosec = int((epoch_ms % 1000) * 1_000_000)
    return t


class HardwareBridgeNode(Node):

    def __init__(self):
        super().__init__('hardware_bridge_node')

        # ── QoS ────────────────────────────────────────────────────────────────
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # ── ROS2 Publishers ────────────────────────────────────────────────────
        self.imu_pub = self.create_publisher(
            Imu, '/hardware/sensors/imu/robot', sensor_qos)

        self.vitals_pub = self.create_publisher(
            Float32MultiArray, '/hardware/sensors/vitals', sensor_qos)

        self.env_pub = self.create_publisher(
            Float32MultiArray, '/hardware/sensors/environment', sensor_qos)

        self.ultrasonic_pub = self.create_publisher(
            Float32MultiArray, '/hardware/sensors/ultrasonic', sensor_qos)

        self.status_pub = self.create_publisher(
            String, '/hardware/status', 10)

        # ── ROS2 Subscribers ───────────────────────────────────────────────────
        self.cmd_vel_sub = self.create_subscription(
            Twist, '/hardware/control/cmd_vel',
            self._on_cmd_vel, 10)

        self.estop_sub = self.create_subscription(
            Empty, '/hardware/control/emergency',
            self._on_emergency_stop, 10)

        # ── MQTT Client ────────────────────────────────────────────────────────
        self._mqtt = mqtt.Client(client_id=MQTT_CLIENT_ID)
        self._mqtt.on_connect    = self._mqtt_on_connect
        self._mqtt.on_disconnect = self._mqtt_on_disconnect
        self._mqtt.on_message    = self._mqtt_on_message
        self._mqtt_connected = False

        # ── State tracking ─────────────────────────────────────────────────────
        self._last_seq    = -1
        self._system_state = 'UNKNOWN'
        self._msg_count   = 0

        # ── Connect MQTT ───────────────────────────────────────────────────────
        self._mqtt_connect()

        self.get_logger().info(
            f'★ HardwareBridgeNode initialized — MQTT: {MQTT_BROKER_IP}:{MQTT_BROKER_PORT}')

    # ─── MQTT Internals ────────────────────────────────────────────────────────

    def _mqtt_connect(self):
        try:
            self._mqtt.connect_async(MQTT_BROKER_IP, MQTT_BROKER_PORT, keepalive=60)
            self._mqtt.loop_start()
        except Exception as e:
            self.get_logger().error(f'MQTT connect failed: {e}')

    def _mqtt_on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._mqtt_connected = True
            client.subscribe(TOPIC_TELEMETRY, qos=1)
            client.subscribe(TOPIC_STATUS, qos=0)
            self.get_logger().info(f'★ MQTT connected — subscribed to {TOPIC_TELEMETRY}')
        else:
            self.get_logger().warn(f'MQTT connect failed rc={rc}')

    def _mqtt_on_disconnect(self, client, userdata, rc):
        self._mqtt_connected = False
        self.get_logger().warn(f'MQTT disconnected (rc={rc}), will auto-reconnect')

    def _mqtt_on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            if msg.topic == TOPIC_TELEMETRY:
                self._process_telemetry(payload)
            elif msg.topic == TOPIC_STATUS:
                self._process_status(payload)
        except json.JSONDecodeError as e:
            self.get_logger().warn(f'MQTT JSON parse error: {e}')
        except Exception as e:
            self.get_logger().error(f'MQTT message error: {e}')

    # ─── Telemetry Processing ──────────────────────────────────────────────────

    def _process_telemetry(self, payload: dict):
        """
        ★ Core function: extract SNTP timestamp from S3, convert to ROS2 Time,
        publish all sensor topics with accurate timestamps.
        """
        # ── Extract SNTP epoch timestamp (from S3) ─────────────────────────────
        epoch_ms = payload.get('timestamp_ms', 0)
        if epoch_ms == 0:
            self.get_logger().warn('No SNTP timestamp in payload — skipping')
            return

        ros_stamp = epoch_ms_to_ros_time(epoch_ms)

        # Check system state for Dead Man's Switch monitoring
        system_state = payload.get('system_state', 0)
        if system_state == 3:  # STATE_ESTOP
            self.get_logger().warn('★ Dead Man Switch ACTIVE — motors LOCKED (state=ESTOP)')

        sensor = payload.get('sensor', {})
        if not sensor:
            return

        # ── IMU Message ────────────────────────────────────────────────────────
        imu_msg = Imu()
        imu_msg.header.stamp    = ros_stamp  # ★ SNTP epoch, NOT local clock
        imu_msg.header.frame_id = 'robot_imu_link'

        imu_msg.linear_acceleration.x = float(sensor.get('robot_accel_x', 0.0))
        imu_msg.linear_acceleration.y = float(sensor.get('robot_accel_y', 0.0))
        imu_msg.linear_acceleration.z = float(sensor.get('robot_accel_z', 0.0))

        imu_msg.angular_velocity.x = float(sensor.get('robot_gyro_x', 0.0))
        imu_msg.angular_velocity.y = float(sensor.get('robot_gyro_y', 0.0))
        imu_msg.angular_velocity.z = float(sensor.get('robot_gyro_z', 0.0))

        # Covariance: -1 = unknown (proper calibration sets real values)
        imu_msg.orientation_covariance[0]          = -1.0
        imu_msg.angular_velocity_covariance[0]     = 0.01
        imu_msg.linear_acceleration_covariance[0]  = 0.1

        self.imu_pub.publish(imu_msg)

        # ── Vitals Message ─────────────────────────────────────────────────────
        vitals_msg = Float32MultiArray()
        vitals_msg.data = [
            float(sensor.get('heart_rate',        0.0)),   # [0] BPM
            float(sensor.get('spo2',              0.0)),   # [1] %
            float(sensor.get('body_temperature',  0.0)),   # [2] °C
        ]
        self.vitals_pub.publish(vitals_msg)

        # ── Environment Message ────────────────────────────────────────────────
        env_msg = Float32MultiArray()
        env_msg.data = [
            float(sensor.get('env_temperature', 0.0)),    # [0] °C
            float(sensor.get('humidity',         0.0)),   # [1] %RH
            float(sensor.get('pressure',         0.0)),   # [2] hPa
        ]
        self.env_pub.publish(env_msg)

        # ── Ultrasonic Message ─────────────────────────────────────────────────
        ultrasonic_msg = Float32MultiArray()
        ultrasonic_msg.data = [
            float(sensor.get('dist_front', -1.0)),  # [0] m (-1 = invalid)
            float(sensor.get('dist_left',  -1.0)),  # [1] m
            float(sensor.get('dist_right', -1.0)),  # [2] m
        ]
        self.ultrasonic_pub.publish(ultrasonic_msg)

        self._msg_count += 1
        if self._msg_count % 200 == 0:
            self.get_logger().info(
                f'[Bridge] {self._msg_count} msgs | epoch={epoch_ms} | '
                f'HR={vitals_msg.data[0]:.0f} | SpO2={vitals_msg.data[1]:.1f}% | '
                f'Dist_F={ultrasonic_msg.data[0]:.2f}m')

    def _process_status(self, payload: dict):
        status_msg = String()
        status_msg.data = json.dumps(payload)
        self.status_pub.publish(status_msg)

    # ─── Command Publishers ────────────────────────────────────────────────────

    def _on_cmd_vel(self, msg: Twist):
        """Receive ROS2 Twist → convert to HK-07 JSON command → MQTT publish"""
        if not self._mqtt_connected:
            self.get_logger().warn('MQTT not connected — command dropped')
            return

        linear_x  = msg.linear.x
        angular_z = msg.angular.z

        # Determine command type from velocities
        if abs(linear_x) < 0.01 and abs(angular_z) < 0.01:
            command = 0x00  # STOP
            speed   = 0.0
        elif linear_x > 0:
            command = 0x01  # MOVE_FORWARD
            speed   = min(abs(linear_x) * 100.0, 100.0)
        elif linear_x < 0:
            command = 0x02  # MOVE_BACKWARD
            speed   = min(abs(linear_x) * 100.0, 100.0)
        elif angular_z > 0:
            command = 0x03  # TURN_LEFT
            speed   = min(abs(angular_z) * 50.0, 100.0)
        else:
            command = 0x04  # TURN_RIGHT
            speed   = min(abs(angular_z) * 50.0, 100.0)

        cmd_payload = json.dumps({
            'command':  command,
            'param1':   round(speed, 2),
            'param2':   0.0,
            'priority': 1
        })

        self._mqtt.publish(TOPIC_COMMAND, cmd_payload, qos=1)
        self.get_logger().debug(f'CMD_VEL → MQTT: cmd=0x{command:02X} speed={speed:.1f}')

    def _on_emergency_stop(self, msg: Empty):
        """Forward emergency stop to robot via MQTT"""
        estop_payload = json.dumps({
            'command':  0xFF,
            'param1':   0.0,
            'param2':   0.0,
            'priority': 255
        })
        self._mqtt.publish(TOPIC_COMMAND, estop_payload, qos=2)
        self.get_logger().error('★ EMERGENCY STOP forwarded to robot via MQTT')

    def destroy_node(self):
        self._mqtt.loop_stop()
        self._mqtt.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = HardwareBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
