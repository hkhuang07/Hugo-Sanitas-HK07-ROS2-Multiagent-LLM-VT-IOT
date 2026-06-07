import os
import sys
import time
import math
import random
import logging
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

from sensor_msgs.msg import Imu, JointState
from geometry_msgs.msg import Twist

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("baymax_sim")

# PhysicsEngineMock Class
class PhysicsEngineMock:
    def __init__(self):
        self.state = "IDLE"  # IDLE, WALKING, HUGGING, DISTRESSED
        self.soc = 100.0
        self.pressure_L = 1.8
        self.pressure_R = 1.8
        self.pump_active = False
        self.relief_active = False
        self.total_current = 0.7
        self.voltage = 24.0
        self.temp = 32.0
        self.tick = 0
        self.hug_force = 0.0
        self.flex_rate = 5.0
        self.stress = 15
        self.resp_rate = 14
        self.hr = 72
        self.spo2 = 98.0
        
        # Humanoid Kinematics coordinates
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.roll = 0.0
        self.qw = 1.0
        self.qx = 0.0
        self.qy = 0.0
        self.qz = 0.0

    def update(self, is_cushioning: bool):
        self.tick += 1
        
        if is_cushioning:
            self.state = "DISTRESSED"
        else:
            # Cycle states every 20 ticks (seconds)
            cycle = 20
            state_idx = (self.tick // cycle) % 3
            states = ["IDLE", "WALKING", "HUGGING"]
            self.state = states[state_idx]

        # Form follows physics
        if self.state == "IDLE":
            self.relief_active = False
            # Minor pressure leakage
            self.pressure_L = max(1.65, self.pressure_L - random.uniform(0.005, 0.015))
            self.pressure_R = max(1.65, self.pressure_R - random.uniform(0.005, 0.015))
            # Active pump if pressure low
            if self.pressure_L < 1.72 or self.pressure_R < 1.72:
                self.pump_active = True
            if self.pressure_L >= 1.85 and self.pressure_R >= 1.85:
                self.pump_active = False
                
            if self.pump_active:
                self.pressure_L = min(1.88, self.pressure_L + random.uniform(0.03, 0.07))
                self.pressure_R = min(1.88, self.pressure_R + random.uniform(0.03, 0.07))
            
            self.hug_force = 0.0
            self.flex_rate = 5.0
            
            # Low current (higher if pump active)
            self.total_current = 0.55 + (2.5 if self.pump_active else 0.0) + random.uniform(-0.02, 0.02)
            self.hr = random.randint(70, 75)
            self.spo2 = round(random.uniform(97.5, 99.0), 1)
            self.stress = random.randint(12, 18)
            self.resp_rate = random.randint(12, 15)
            
            # Position at rest
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            self.pitch = 0.0
            self.yaw = 0.0
            self.roll = 0.0
            
        elif self.state == "WALKING":
            self.relief_active = False
            self.pump_active = False
            # Mechanical motion creates slight pressure changes
            self.pressure_L = 1.8 + 0.08 * math.sin(self.tick * 0.5)
            self.pressure_R = 1.8 + 0.08 * math.cos(self.tick * 0.5)
            self.hug_force = 0.0
            self.flex_rate = 5.1 + 0.3 * math.sin(self.tick * 0.5)
            
            # High current draw due to leg actuators
            self.total_current = 1.4 + 1.6 * abs(math.sin(self.tick * 0.5)) + random.uniform(0, 0.1)
            self.hr = random.randint(85, 95)
            self.spo2 = round(random.uniform(96.0, 98.0), 1)
            self.stress = random.randint(22, 28)
            self.resp_rate = random.randint(16, 19)
            
            # Humanoid coordinates (sine-wave patrol)
            self.x = 1.2 * math.sin(self.tick * 0.25)
            self.y = 0.02 * abs(math.sin(self.tick * 0.5))  # slight walk bob
            self.z = 1.2 * math.cos(self.tick * 0.25)
            self.pitch = 0.04 * math.sin(self.tick * 0.5)
            self.yaw = -self.tick * 0.25 + math.pi / 2
            self.roll = 0.04 * math.cos(self.tick * 0.5)
            
        elif self.state == "HUGGING":
            self.relief_active = False
            self.pump_active = True
            # High target pressure for armor stiffness
            self.pressure_L = min(2.35, self.pressure_L + random.uniform(0.04, 0.08))
            self.pressure_R = min(2.35, self.pressure_R + random.uniform(0.04, 0.08))
            
            # Form follows physics: high pressure pump + active arm servos
            self.total_current = 0.5 + 2.5 + 1.2 + random.uniform(0, 0.2)
            self.hug_force = 14.0 + 6.0 * abs(math.sin(self.tick * 0.3)) + random.uniform(0, 0.8)
            self.flex_rate = 6.5 + 0.8 * abs(math.sin(self.tick * 0.3))
            
            self.hr = random.randint(73, 78)
            self.spo2 = round(random.uniform(97.2, 98.8), 1)
            self.stress = random.randint(14, 20)
            self.resp_rate = random.randint(13, 15)
            
            # Sway at origin while hugging
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            self.pitch = 0.0
            self.yaw = 0.0
            self.roll = 0.03 * math.sin(self.tick * 0.3)
            
        elif self.state == "DISTRESSED":
            self.relief_active = True
            self.pump_active = False
            # E-STOP rapid deflation
            self.pressure_L = max(0.0, self.pressure_L - 0.4)
            self.pressure_R = max(0.0, self.pressure_R - 0.4)
            self.hug_force = 0.0
            self.flex_rate = 1.5
            
            # Standard standby current
            self.total_current = 0.55 + random.uniform(-0.02, 0.02)
            self.hr = random.randint(128, 148)
            self.spo2 = round(random.uniform(88.5, 91.5), 1)
            self.stress = random.randint(82, 94)
            self.resp_rate = random.randint(27, 33)
            
            # Fall flat coordinates
            self.x = 0.0
            self.y = -0.85
            self.z = 0.0
            self.pitch = 1.35  # ~77 degrees pitch (fallen forward)
            self.yaw = 0.0
            self.roll = 0.0

        # PMU physics
        self.soc = max(0.0, self.soc - (0.0025 + (self.total_current * 0.0012)))
        self.voltage = max(20.0, 24.2 - (self.total_current * 0.14) + random.uniform(-0.01, 0.01))
        self.temp = 32.0 + (self.total_current * 0.8) + random.uniform(-0.1, 0.1)

        # Convert Euler angles to Quaternion
        cy = math.cos(self.yaw * 0.5)
        sy = math.sin(self.yaw * 0.5)
        cp = math.cos(self.pitch * 0.5)
        sp = math.sin(self.pitch * 0.5)
        cr = math.cos(self.roll * 0.5)
        sr = math.sin(self.roll * 0.5)

        self.qw = cr * cp * cy + sr * sp * sy
        self.qx = sr * cp * cy - cr * sp * sy
        self.qy = cr * sp * cy + sr * cp * sy
        self.qz = cr * cp * sy - sr * sp * cy

class BaymaxTelemetrySim(Node):
    def __init__(self):
        super().__init__('baymax_telemetry_sim')
        
        # State
        self.physics_engine = PhysicsEngineMock()
        self.last_fall_trigger_time = 0.0
        self.g_ema_sim = None
        self.current_cmd_vel = Twist()
        
        # Publishers
        self.pmu_pub = self.create_publisher(JointState, '/telemetry/pmu', 10)
        self.pneumatic_pub = self.create_publisher(JointState, '/telemetry/pneumatic', 10)
        self.joints_pub = self.create_publisher(JointState, '/telemetry/actuators/joints', 10)
        self.tactile_pub = self.create_publisher(JointState, '/telemetry/sensors/tactile', 10)
        self.vitals_pub = self.create_publisher(JointState, '/telemetry/sensors/vitals', 10)
        self.imu_pub = self.create_publisher(Imu, '/sensors/imu/target', 10)
        
        # Subscriptions
        self.imu_state_sub = self.create_subscription(Imu, '/sensors/imu/state', self.imu_state_callback, 10)
        self.vitals_wristband_sub = self.create_subscription(JointState, '/vitals/wristband', self.vitals_wristband_callback, 10)
        self.cmd_vel_sub = self.create_subscription(Twist, '/control/motion/cmd_vel', self.cmd_vel_callback, 10)
        
        # Timer (1.0Hz)
        self.timer = self.create_timer(1.0, self.timer_callback)
        
        log.info("=== BAYMAX PHYSICAL SYSTEM TELEMETRY SIMULATOR NODE STARTED ===")

    def imu_state_callback(self, msg):
        try:
            x = msg.linear_acceleration.x
            y = msg.linear_acceleration.y
            z = msg.linear_acceleration.z
            g = math.sqrt(x**2 + y**2 + z**2)
            
            if self.g_ema_sim is None:
                self.g_ema_sim = g
            else:
                self.g_ema_sim = 0.9 * self.g_ema_sim + 0.1 * g
                
            is_linear = (self.g_ema_sim < 3.0)
            is_falling = (g > 15.0) if is_linear else (g < 4.0 or g > 20.0)
            
            if is_falling:
                self.last_fall_trigger_time = time.time()
                log.warning(f"[E-STOP TRIGGER] Fall detected in IMU stream. Deflation activated.")
        except Exception as e:
            log.error(f"Error in IMU state callback: {e}")

    def vitals_wristband_callback(self, msg):
        try:
            is_falling = False
            emergency_button_pressed = False
            
            if 'is_falling' in msg.name:
                idx = msg.name.index('is_falling')
                is_falling = bool(msg.position[idx])
                
            if 'emergency_button_pressed' in msg.name:
                idx = msg.name.index('emergency_button_pressed')
                emergency_button_pressed = bool(msg.position[idx])
                
            if is_falling or emergency_button_pressed:
                self.last_fall_trigger_time = time.time()
                log.warning(f"[E-STOP TRIGGER] Fall or SOS reported by Wristband. Deflation activated.")
        except Exception as e:
            log.error(f"Error in wristband callback: {e}")

    def cmd_vel_callback(self, msg):
        self.current_cmd_vel = msg

    def timer_callback(self):
        try:
            now = time.time()
            stamp = self.get_clock().now().to_msg()
            
            # Check if fall cushioning mode is active
            is_cushioning = (now - self.last_fall_trigger_time) < 8.0
            
            # Update physical engine model
            self.physics_engine.update(is_cushioning)
            
            # If walking and received non-zero cmd_vel, integrate motion coordinates
            if self.physics_engine.state == "WALKING" and (
                abs(self.current_cmd_vel.linear.x) > 0.01 or 
                abs(self.current_cmd_vel.linear.z) > 0.01 or
                abs(self.current_cmd_vel.angular.z) > 0.01
            ):
                # timer is 1.0Hz, so dt = 1.0
                self.physics_engine.x += self.current_cmd_vel.linear.x * 1.0
                self.physics_engine.z += self.current_cmd_vel.linear.z * 1.0
                self.physics_engine.yaw += self.current_cmd_vel.angular.z * 1.0
                # bobbing & sway simulation matching WALK cycles
                self.physics_engine.y = 0.02 * abs(math.sin(self.physics_engine.tick * 0.5))
                self.physics_engine.pitch = 0.04 * math.sin(self.physics_engine.tick * 0.5)
                self.physics_engine.roll = 0.04 * math.cos(self.physics_engine.tick * 0.5)
            
            # 1. PMU JointState
            pmu_msg = JointState()
            pmu_msg.header.stamp = stamp
            pmu_msg.name = ["voltage", "current", "soc", "temp"]
            pmu_msg.position = [
                float(self.physics_engine.voltage),
                float(self.physics_engine.total_current),
                float(self.physics_engine.soc),
                float(self.physics_engine.temp)
            ]
            self.pmu_pub.publish(pmu_msg)
            
            # 2. Pneumatics JointState
            pne_msg = JointState()
            pne_msg.header.stamp = stamp
            pne_msg.name = ["press_L", "press_R", "pump_active", "relief_active"]
            pne_msg.position = [
                float(self.physics_engine.pressure_L),
                float(self.physics_engine.pressure_R),
                float(self.physics_engine.pump_active),
                float(self.physics_engine.relief_active)
            ]
            self.pneumatic_pub.publish(pne_msg)
            
            # 3. Actuator Joints
            joints = ["neck", "shoulder_L", "shoulder_R", "hip_L", "hip_R", "waist"]
            joint_msg = JointState()
            joint_msg.header.stamp = stamp
            joint_msg.name = joints
            joint_msg.position = []
            joint_msg.effort = []
            joint_msg.velocity = []
            
            for j in joints:
                if self.physics_engine.state == "WALKING" and j in ("hip_L", "hip_R", "shoulder_L", "shoulder_R"):
                    angle = 20.0 * math.sin(self.physics_engine.tick * 0.5 + (math.pi if "R" in j else 0))
                    torque = 2.5 + random.uniform(0, 0.5)
                    temp = 36.5 + random.uniform(0, 1.2)
                elif self.physics_engine.state == "HUGGING" and j in ("shoulder_L", "shoulder_R", "waist"):
                    angle = 15.0 if j.startswith("shoulder") else 5.0
                    torque = 3.2 + random.uniform(0, 0.4)
                    temp = 38.0 + random.uniform(0, 0.8)
                else:
                    angle = 0.0
                    torque = 0.1
                    temp = 32.2 + random.uniform(-0.2, 0.2)
                
                joint_msg.position.append(float(angle))
                joint_msg.effort.append(float(torque))
                joint_msg.velocity.append(float(temp))
            self.joints_pub.publish(joint_msg)
            
            # 4. Tactile
            tac_msg = JointState()
            tac_msg.header.stamp = stamp
            tac_msg.name = ["hug_force", "flex_rate"]
            tac_msg.position = [
                float(self.physics_engine.hug_force),
                float(self.physics_engine.flex_rate)
            ]
            self.tactile_pub.publish(tac_msg)
            
            # 5. Vitals
            vit_msg = JointState()
            vit_msg.header.stamp = stamp
            vit_msg.name = ["heartRate", "spo2", "bodyTemperature", "stress_gsr", "respiratory_rate"]
            vit_msg.position = [
                float(self.physics_engine.hr),
                float(self.physics_engine.spo2),
                36.6 if self.physics_engine.state != "DISTRESSED" else 37.8,
                float(self.physics_engine.stress),
                float(self.physics_engine.resp_rate)
            ]
            self.vitals_pub.publish(vit_msg)
            
            # 6. IMU Target
            imu_msg = Imu()
            imu_msg.header.stamp = stamp
            imu_msg.header.frame_id = "base_link"
            imu_msg.orientation.w = float(self.physics_engine.qw)
            imu_msg.orientation.x = float(self.physics_engine.qx)
            imu_msg.orientation.y = float(self.physics_engine.qy)
            imu_msg.orientation.z = float(self.physics_engine.qz)
            # Pack position into angular_velocity:
            imu_msg.angular_velocity.x = float(self.physics_engine.x)
            imu_msg.angular_velocity.y = float(self.physics_engine.y)
            imu_msg.angular_velocity.z = float(self.physics_engine.z)
            self.imu_pub.publish(imu_msg)
            
            log.info(
                f"[{self.physics_engine.state}] Published telemetry. "
                f"SOC={self.physics_engine.soc:.3f}% | "
                f"L/R={self.physics_engine.pressure_L:.2f}/{self.physics_engine.pressure_R:.2f}PSI | "
                f"Pump={self.physics_engine.pump_active} | "
                f"Hug={self.physics_engine.hug_force:.1f}N | "
                f"Pos=({self.physics_engine.x:.3f},{self.physics_engine.y:.3f},{self.physics_engine.z:.3f})"
            )
            
        except Exception as err:
            log.error(f"Error in simulator loop: {err}")

def main(args=None):
    rclpy.init(args=args)
    node = BaymaxTelemetrySim()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
