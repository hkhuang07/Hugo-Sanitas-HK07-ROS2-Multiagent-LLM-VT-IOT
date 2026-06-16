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
    print(">>> This node MUST be executed inside the WSL (Ubuntu) environment where ROS 2 is sourced.")
    print(">>> Run: source /opt/ros/humble/setup.bash and try again.")
    print("=================================================================================")
    sys.exit(1)

from sensor_msgs.msg import Imu, JointState
from geometry_msgs.msg import Twist
import struct

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("physics_node")

class Hk07PhysicsNode(Node):
    def __init__(self):
        super().__init__('hk07_physics_node')
        
        # Thread locks and state variables
        self.state_lock = threading.Lock()
        
        # Sim targets (desired states)
        self.target_pos = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.target_rot = {"qw": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0}
        
        # Obstacles and Avoidance Vectors
        self.avoidance_twist = {"linear": {"x": 0.0, "y": 0.0, "z": 0.0}}
        
        # Resolved states (physical states)
        self.phys_pos = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.phys_vel = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.phys_rot = {"qw": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0}
        
        # Visual lengths of upper arm and forearm
        self.L1 = 0.35
        self.L2 = 0.30
        
        # Subscriptions
        self.target_sub = self.create_subscription(Imu, '/sensors/imu/target', self.target_callback, 10)
        self.avoidance_sub = self.create_subscription(Twist, '/telemetry/avoidance', self.avoidance_callback, 10)
        
        # Publishers
        self.joint_pub = self.create_publisher(JointState, '/telemetry/joint_states', 10)
        self.imu_pub = self.create_publisher(Imu, '/telemetry/imu', 10)
        
        # Timer (50Hz)
        self.timer = self.create_timer(0.02, self.physics_step)
        
        log.info("=== HK07 PHYSICS & IK SOLVER NODE STARTED ===")

    def target_callback(self, msg):
        with self.state_lock:
            # Target position packed in angular_velocity
            self.target_pos = {
                "x": msg.angular_velocity.x,
                "y": msg.angular_velocity.y,
                "z": msg.angular_velocity.z
            }
            self.target_rot = {
                "qw": msg.orientation.w,
                "qx": msg.orientation.x,
                "qy": msg.orientation.y,
                "qz": msg.orientation.z
            }



    def avoidance_callback(self, msg):
        with self.state_lock:
            self.avoidance_twist = {
                "linear": {
                    "x": msg.linear.x,
                    "y": msg.linear.y,
                    "z": msg.linear.z
                }
            }

    def solve_right_arm_ik(self, av_x, av_y, av_z):
        """
        Solves 2-Link analytical Inverse Kinematics for the right arm.
        Shoulder pivot is fixed relative to robot pelvis root at (0.4, 0.6, 0.0).
        Hand target starts at (0.48, 0.3, 0.0) and is offset by the avoidance vector.
        """
        # Target position relative to shoulder joint
        tx = 0.08 + av_x
        ty = -0.3 + av_y
        tz = av_z
        
        # Distance from shoulder to target
        d = math.sqrt(tx**2 + ty**2 + tz**2)
        # Clamp distance to reach limit of upper arm + forearm
        max_reach = self.L1 + self.L2 - 0.01
        min_reach = 0.05
        if d > max_reach:
            d = max_reach
        elif d < min_reach:
            d = min_reach
            
        # Solve elbow angle (Law of Cosines)
        cos_elbow = (d**2 - self.L1**2 - self.L2**2) / (2.0 * self.L1 * self.L2)
        cos_elbow = max(-1.0, min(1.0, cos_elbow))
        # Standard fold angle
        theta_elbow = -math.acos(cos_elbow)
        
        # Solve shoulder angle
        alpha = math.atan2(ty, tx)
        cos_beta = (self.L1**2 + d**2 - self.L2**2) / (2.0 * self.L1 * d)
        cos_beta = max(-1.0, min(1.0, cos_beta))
        beta = math.acos(cos_beta)
        
        theta_shoulder = alpha + beta
        
        # Check for NaN and clamp
        if math.isnan(theta_shoulder):
             theta_shoulder = -math.pi / 8
        if math.isnan(theta_elbow):
             theta_elbow = -math.pi / 10
             
        return theta_shoulder, theta_elbow

    def physics_step(self):
        dt = 0.02  # 50Hz loop rate
        mass = 1.0
        
        try:
            with self.state_lock:
                # Copy shared variables for execution
                t_pos = dict(self.target_pos)
                t_rot = dict(self.target_rot)
                av = dict(self.avoidance_twist["linear"])
                
            # Spring force pulling robot towards desired target
            spring_k = 180.0
            damping = 18.0
            
            # Torso height offset center is at y + 1.28
            fx = spring_k * (t_pos["x"] - self.phys_pos["x"]) - damping * self.phys_vel["x"]
            fy = spring_k * (t_pos["y"] - self.phys_pos["y"]) - damping * self.phys_vel["y"]
            fz = spring_k * (t_pos["z"] - self.phys_pos["z"]) - damping * self.phys_vel["z"]
            
            # 3. Integrate Equations of Motion
            self.phys_vel["x"] += (fx / mass) * dt
            self.phys_vel["y"] += (fy / mass) * dt
            self.phys_vel["z"] += (fz / mass) * dt
            
            # Apply air resistance damping
            self.phys_vel["x"] *= 0.88
            self.phys_vel["y"] *= 0.88
            self.phys_vel["z"] *= 0.88
            
            self.phys_pos["x"] += self.phys_vel["x"] * dt
            self.phys_pos["y"] += self.phys_vel["y"] * dt
            self.phys_pos["z"] += self.phys_vel["z"] * dt
            
            # Direct match orientation
            self.phys_rot = t_rot
            
            # 4. Resolve Inverse Kinematics for right arm joints
            theta_shoulder, theta_elbow = self.solve_right_arm_ik(av["x"], av["y"], av["z"])
            
            # 5. Compile and Publish Standard JointState
            stamp = self.get_clock().now().to_msg()
            
            joint_msg = JointState()
            joint_msg.header.stamp = stamp
            joint_msg.header.frame_id = "base_link"
            joint_msg.name = ["mixamorig_RightArm", "mixamorig_RightForeArm", "mixamorig_RightHand"]
            joint_msg.position = [
                round(theta_shoulder, 4),
                round(theta_elbow, 4),
                0.0
            ]
            joint_msg.velocity = [0.0, 0.0, 0.0]
            joint_msg.effort = [0.0, 0.0, 0.0]
            self.joint_pub.publish(joint_msg)
            
            # 6. Compile and Publish Resolved IMU Telemetry
            imu_msg = Imu()
            imu_msg.header.stamp = stamp
            imu_msg.header.frame_id = "imu_link"
            imu_msg.orientation.w = round(self.phys_rot["qw"], 5)
            imu_msg.orientation.x = round(self.phys_rot["qx"], 5)
            imu_msg.orientation.y = round(self.phys_rot["qy"], 5)
            imu_msg.orientation.z = round(self.phys_rot["qz"], 5)
            
            imu_msg.linear_acceleration.x = round(fx, 4)
            imu_msg.linear_acceleration.y = round(fy, 4)
            imu_msg.linear_acceleration.z = round(fz, 4)
            
            # Pack physical position in angular_velocity
            imu_msg.angular_velocity.x = round(self.phys_pos["x"], 3)
            imu_msg.angular_velocity.y = round(self.phys_pos["y"], 3)
            imu_msg.angular_velocity.z = round(self.phys_pos["z"], 3)
            self.imu_pub.publish(imu_msg)
            
        except Exception as loop_error:
            log.error(f"Error in physics calculation cycle: {loop_error}")

def main(args=None):
    rclpy.init(args=args)
    node = Hk07PhysicsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
