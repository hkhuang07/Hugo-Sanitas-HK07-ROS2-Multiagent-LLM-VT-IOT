import os
import sys
import time
import math
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

from sensor_msgs.msg import Imu
from geometry_msgs.msg import Twist
from std_msgs.msg import String

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("balance_controller")

class BalanceController(Node):
    def __init__(self):
        super().__init__('balance_controller')
        
        # PID Constants for Stance/Balance
        # Pitch PID (Forward/Backward tilt correction)
        self.declare_parameter('kp_pitch', 1.8)
        self.declare_parameter('ki_pitch', 0.05)
        self.declare_parameter('kd_pitch', 0.35)
        
        # Roll PID (Left/Right tilt correction)
        self.declare_parameter('kp_roll', 1.8)
        self.declare_parameter('ki_roll', 0.05)
        self.declare_parameter('kd_roll', 0.35)
        
        # Stance status
        self.inhibit_state = "CLEAR"
        self.last_time = time.time()
        
        # Errors and Integrals
        self.pitch_integral = 0.0
        self.roll_integral = 0.0
        self.last_pitch_error = 0.0
        self.last_roll_error = 0.0
        
        # Subscriptions
        self.imu_sub = self.create_subscription(
            Imu,
            '/sensors/imu/state',
            self.imu_callback,
            10
        )
        self.inhibit_sub = self.create_subscription(
            String,
            '/control/subsumption/inhibit',
            self.inhibit_callback,
            10
        )
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            '/control/motion/cmd_vel',
            10
        )
        
        self.last_log_time = 0.0
        log.info("=== HK07 STANDING BALANCE PID CONTROLLER STARTED ===")
        log.info("Monitoring '/sensors/imu/state' to enforce standing stability...")

    def inhibit_callback(self, msg):
        self.inhibit_state = msg.data
        if self.inhibit_state != "CLEAR":
            log.warning(f"[BALANCE INHIBITED] Safety subsumption active: {self.inhibit_state}")

    def imu_callback(self, msg):
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        
        if dt <= 0.0:
            dt = 0.02 # fallback to 50Hz standard
            
        # Get raw accelerations
        ax = msg.linear_acceleration.x
        ay = msg.linear_acceleration.y
        az = msg.linear_acceleration.z
        
        # Compute Tilt Angles (pitch, roll in radians)
        # Pitch: tilt about Y-axis (forward/backward)
        # Roll: tilt about X-axis (left/right)
        try:
            pitch = math.atan2(ax, math.sqrt(ay**2 + az**2))
            roll = math.atan2(ay, math.sqrt(ax**2 + az**2))
        except ZeroDivisionError:
            pitch = 0.0
            roll = 0.0
            
        # Target is 0 tilt (perfectly vertical standing)
        target_pitch = 0.0
        target_roll = 0.0
        
        pitch_error = target_pitch - pitch
        roll_error = target_roll - roll
        
        # PID calculations with anti-windup clamping on integral
        self.pitch_integral += pitch_error * dt
        self.pitch_integral = max(-1.0, min(1.0, self.pitch_integral))
        
        self.roll_integral += roll_error * dt
        self.roll_integral = max(-1.0, min(1.0, self.roll_integral))
        
        pitch_derivative = (pitch_error - self.last_pitch_error) / dt
        roll_derivative = (roll_error - self.last_roll_error) / dt
        
        self.last_pitch_error = pitch_error
        self.last_roll_error = roll_error
        
        # Load dynamic parameters
        kp_p = self.get_parameter('kp_pitch').value
        ki_p = self.get_parameter('ki_pitch').value
        kd_p = self.get_parameter('kd_pitch').value
        
        kp_r = self.get_parameter('kp_roll').value
        ki_r = self.get_parameter('ki_roll').value
        kd_r = self.get_parameter('kd_roll').value
        
        # Calculate controller output (corrective linear velocities)
        # If tilting forward (pitch > 0), pitch_error < 0, output < 0 -> corrective backward motion
        out_pitch = kp_p * pitch_error + ki_p * self.pitch_integral + kd_p * pitch_derivative
        # If tilting right (roll > 0), roll_error < 0, output < 0 -> corrective leftward motion
        out_roll = kp_r * roll_error + ki_r * self.roll_integral + kd_r * roll_derivative
        
        # Enforce maximum safety velocity limits (max 1.5 m/s corrective)
        out_pitch = max(-1.5, min(1.5, out_pitch))
        out_roll = max(-1.5, min(1.5, out_roll))
        
        # Instantiate Twist command
        cmd = Twist()
        
        # Gated by Subsumption Architecture: Safety always wins!
        if self.inhibit_state != "CLEAR" and self.inhibit_state != "NONE":
            cmd.linear.x = 0.0
            cmd.linear.y = 0.0
            cmd.linear.z = 0.0
        else:
            cmd.linear.x = out_pitch
            cmd.linear.y = out_roll
            cmd.linear.z = 0.0
            
        self.cmd_vel_pub.publish(cmd)
        
        # Throttled debug logs (1.0s interval)
        if now - self.last_log_time > 1.0:
            log.info(
                f"[BALANCE] Pitch={pitch:.3f} rad, Roll={roll:.3f} rad | "
                f"CmdLinearX(Pitch)={cmd.linear.x:.3f} m/s, "
                f"CmdLinearY(Roll)={cmd.linear.y:.3f} m/s | "
                f"Inhibit={self.inhibit_state}"
            )
            self.last_log_time = now

def main(args=None):
    rclpy.init(args=args)
    node = BalanceController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
