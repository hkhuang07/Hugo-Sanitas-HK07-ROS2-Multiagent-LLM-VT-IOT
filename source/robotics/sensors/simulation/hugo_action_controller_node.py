import os
import sys
import time
import math
import logging
import threading

try:
    import rclpy
    from rclpy.node import Node
except ImportError:
    print("=================================================================================")
    print(">>> [ROBOTICS ARCHITECTURE ERROR] ROS 2 client library 'rclpy' is not installed.")
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
log = logging.getLogger("action_controller")

class HugoActionControllerNode(Node):
    def __init__(self):
        super().__init__('hugo_action_controller_node')
        
        # State variables
        self.state_lock = threading.Lock()
        
        # Current linear/angular velocities
        self.cmd_linear_x = 0.0
        self.cmd_linear_z = 0.0
        self.cmd_angular_z = 0.0
        
        # Action code mapping: 0=idle, 1=cầm nắm, 2=phun, 3=ôm
        self.current_action = 0.0
        
        # Simulated positioning coordinates
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.pos_z = 0.0
        self.yaw = 0.0
        
        # Dimensions
        self.L1 = 0.35
        self.L2 = 0.30
        
        # Arm targets
        self.target_l_arm = {"theta_shoulder": 0.0, "theta_elbow": 0.0}
        self.target_r_arm = {"theta_shoulder": 0.0, "theta_elbow": 0.0}
        
        # Current smoothed joint states for arms
        self.curr_l_arm = {"theta_shoulder": 0.0, "theta_elbow": 0.0}
        self.curr_r_arm = {"theta_shoulder": 0.0, "theta_elbow": 0.0}
        
        # Sinusoidal timing
        self.time_t = 0.0
        
        # Subscriptions
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            '/control/motion/cmd_vel',
            self.cmd_vel_callback,
            10
        )
        
        # Publishers
        self.joint_pub = self.create_publisher(JointState, '/telemetry/joint_states', 10)
        self.imu_pub = self.create_publisher(Imu, '/telemetry/imu', 10)
        
        # 50Hz Timer Loop for kinematics simulation
        self.timer = self.create_timer(0.02, self.control_step)
        
        log.info("=== HUGO KINEMATICS & ACTION CONTROLLER NODE INITIALIZED ===")

    def cmd_vel_callback(self, msg):
        with self.state_lock:
            self.cmd_linear_x = msg.linear.x
            self.cmd_linear_z = msg.linear.z
            self.cmd_angular_z = msg.angular.z
            # Use angular.x to select actions via web UI (0=idle, 1=cầm nắm, 2=phun, 3=ôm)
            self.current_action = msg.angular.x

    def solve_arm_ik(self, tx, ty, tz, is_left=False):
        """
        Solves 2-Link analytical Inverse Kinematics.
        Target coordinates (tx, ty, tz) are relative to shoulder joints.
        """
        # Distance from shoulder to target
        d = math.sqrt(tx**2 + ty**2 + tz**2)
        max_reach = self.L1 + self.L2 - 0.01
        min_reach = 0.05
        
        if d > max_reach:
            d = max_reach
        elif d < min_reach:
            d = min_reach
            
        # Elbow angle (Law of Cosines)
        cos_elbow = (d**2 - self.L1**2 - self.L2**2) / (2.0 * self.L1 * self.L2)
        cos_elbow = max(-1.0, min(1.0, cos_elbow))
        theta_elbow = -math.acos(cos_elbow)
        
        # Shoulder angle
        alpha = math.atan2(ty, math.sqrt(tx**2 + tz**2))
        cos_beta = (self.L1**2 + d**2 - self.L2**2) / (2.0 * self.L1 * d)
        cos_beta = max(-1.0, min(1.0, cos_beta))
        beta = math.acos(cos_beta)
        
        theta_shoulder = alpha + beta
        
        if math.isnan(theta_shoulder):
             theta_shoulder = 0.0
        if math.isnan(theta_elbow):
             theta_elbow = 0.0
             
        # Invert shoulder rotation for left arm symmetry
        if is_left:
            theta_shoulder = -theta_shoulder
            
        return theta_shoulder, theta_elbow

    def control_step(self):
        dt = 0.02
        self.time_t += dt
        
        with self.state_lock:
            v_x = self.cmd_linear_x
            v_z = self.cmd_linear_z
            w_yaw = self.cmd_angular_z
            action = int(self.current_action)
            
        # 1. Integrate linear/angular velocities to update position and yaw
        # Simple Euler integration
        self.yaw += w_yaw * dt
        # Rotate linear velocities by current yaw angle
        dx = (v_x * math.cos(self.yaw) - v_z * math.sin(self.yaw)) * dt
        dz = (v_x * math.sin(self.yaw) + v_z * math.cos(self.yaw)) * dt
        self.pos_x += dx
        self.pos_z += dz
        
        # Determine walking state and sinusoidal parameters
        v_mag = math.sqrt(v_x**2 + v_z**2)
        if v_mag < 0.05:
            # dừng
            amplitude = 0.0
            omega = 0.0
            self.pos_y = 0.0
        elif v_mag < 0.25:
            # bước
            amplitude = 0.15
            omega = 2.5
            self.pos_y = 0.02 * abs(math.sin(self.time_t * omega))
        elif v_mag < 0.75:
            # đi
            amplitude = 0.3
            omega = 5.0
            self.pos_y = 0.04 * abs(math.sin(self.time_t * omega))
        else:
            # chạy
            amplitude = 0.5
            omega = 8.0
            self.pos_y = 0.06 * abs(math.sin(self.time_t * omega))
            
        # Sinusoidal swings for legs
        theta_l_leg = amplitude * math.sin(self.time_t * omega) if omega > 0 else 0.0
        theta_r_leg = -amplitude * math.sin(self.time_t * omega) if omega > 0 else 0.0
        
        # 2. Arm Inverse Kinematics Targets
        # Targets relative to respective shoulders
        if action == 1:
            # cầm nắm: right arm reaches forward
            r_tx, r_ty, r_tz = 0.25, 0.1, 0.15
            l_tx, l_ty, l_tz = -0.05, -0.3, 0.0
        elif action == 2:
            # phun: right arm points straight forward
            r_tx, r_ty, r_tz = 0.35, 0.0, 0.0
            l_tx, l_ty, l_tz = -0.05, -0.3, 0.0
        elif action == 3:
            # ôm: both arms reach forward and inward
            r_tx, r_ty, r_tz = 0.15, -0.1, 0.2
            l_tx, l_ty, l_tz = -0.15, -0.1, 0.2
        else:
            # idle: rest position
            r_tx, r_ty, r_tz = 0.08, -0.3, 0.0
            l_tx, l_ty, l_tz = -0.08, -0.3, 0.0
            
        # Solve IK for targets
        r_shoulder, r_elbow = self.solve_arm_ik(r_tx, r_ty, r_tz, is_left=False)
        l_shoulder, l_elbow = self.solve_arm_ik(l_tx, l_ty, l_tz, is_left=True)
        
        # Smooth interpolation to target joint coordinates (low-pass filter)
        alpha_smooth = 0.1
        self.curr_r_arm["theta_shoulder"] += alpha_smooth * (r_shoulder - self.curr_r_arm["theta_shoulder"])
        self.curr_r_arm["theta_elbow"] += alpha_smooth * (r_elbow - self.curr_r_arm["theta_elbow"])
        self.curr_l_arm["theta_shoulder"] += alpha_smooth * (l_shoulder - self.curr_l_arm["theta_shoulder"])
        self.curr_l_arm["theta_elbow"] += alpha_smooth * (l_elbow - self.curr_l_arm["theta_elbow"])
        
        # 3. Publish JointState
        stamp = self.get_clock().now().to_msg()
        js_msg = JointState()
        js_msg.header.stamp = stamp
        js_msg.header.frame_id = "base_link"
        
        js_msg.name = [
            "mixamorig_RightArm", "mixamorig_RightForeArm", "mixamorig_RightHand",
            "mixamorig_LeftArm", "mixamorig_LeftForeArm", "mixamorig_LeftHand",
            "mixamorig_LeftUpLeg", "mixamorig_LeftLeg", "mixamorig_RightUpLeg", "mixamorig_RightLeg"
        ]
        js_msg.position = [
            round(self.curr_r_arm["theta_shoulder"], 4),
            round(self.curr_r_arm["theta_elbow"], 4),
            0.0,
            round(self.curr_l_arm["theta_shoulder"], 4),
            round(self.curr_l_arm["theta_elbow"], 4),
            0.0,
            round(theta_l_leg, 4),
            round(theta_l_leg * 0.5, 4),  # knee bends slightly in sync
            round(theta_r_leg, 4),
            round(theta_r_leg * 0.5, 4)
        ]
        self.joint_pub.publish(js_msg)
        
        # 4. Compile and Publish IMU Telemetry (including integrated position)
        cy = math.cos(self.yaw * 0.5)
        sy = math.sin(self.yaw * 0.5)
        cp = math.cos(0.0) # pitch = 0
        sp = math.sin(0.0)
        cr = math.cos(0.0) # roll = 0
        sr = math.sin(0.0)
        
        qw = cr * cp * cy + sr * sp * sy
        qx = sr * cp * cy - cr * sp * sy
        qy = cr * sp * cy + sr * cp * sy
        qz = cr * cp * sy - sr * sp * cy
        
        imu_msg = Imu()
        imu_msg.header.stamp = stamp
        imu_msg.header.frame_id = "imu_link"
        imu_msg.orientation.w = qw
        imu_msg.orientation.x = qx
        imu_msg.orientation.y = qy
        imu_msg.orientation.z = qz
        
        # Simulated acceleration
        imu_msg.linear_acceleration.x = v_x / dt if dt > 0 else 0.0
        imu_msg.linear_acceleration.y = 0.0
        imu_msg.linear_acceleration.z = 9.81
        
        # Pack integrated physical position in angular_velocity
        imu_msg.angular_velocity.x = self.pos_x
        imu_msg.angular_velocity.y = self.pos_y
        imu_msg.angular_velocity.z = self.pos_z
        self.imu_pub.publish(imu_msg)

def main(args=None):
    rclpy.init(args=args)
    node = HugoActionControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
