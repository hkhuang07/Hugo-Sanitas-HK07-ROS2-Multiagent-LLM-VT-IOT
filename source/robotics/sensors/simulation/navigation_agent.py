import os
import sys
import time
import math
import struct
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

from geometry_msgs.msg import Twist, PoseStamped
from std_msgs.msg import String

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("navigation_agent")

class NavigationAgent(Node):
    def __init__(self):
        super().__init__('navigation_agent')
        
        # APF Parameters
        self.declare_parameter('k_attractive', 1.2)
        self.declare_parameter('k_repulsive', 8.0)
        self.declare_parameter('safety_radius', 1.0) # obstacle safety buffer
        self.declare_parameter('max_speed', 1.2)      # m/s max velocity
        
        # Robot States
        self.current_pos = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.target_pos = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.inhibit_state = "CLEAR"
        
        # Subscriptions
        self.target_sub = self.create_subscription(
            PoseStamped,
            '/control/motion/target_pose',
            self.target_callback,
            10
        )
        self.pose_sub = self.create_subscription(
            PoseStamped,
            '/telemetry/pose',
            self.pose_callback,
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
            '/control/motion/nav_cmd_vel',
            10
        )
        
        # Control Loop Timer (20Hz / 0.05s)
        self.timer = self.create_timer(0.05, self.control_loop)
        
        self.last_log_time = 0.0
        log.info("=== HK07 APF WAYPOINT NAVIGATION AGENT STARTED ===")
        log.info("Subscribing to current position, target waypoint, and PointCloud2 costmap...")

    def target_callback(self, msg):
        self.target_pos = {
            "x": msg.pose.position.x,
            "y": msg.pose.position.y,
            "z": msg.pose.position.z
        }

    def pose_callback(self, msg):
        self.current_pos = {
            "x": msg.pose.position.x,
            "y": msg.pose.position.y,
            "z": msg.pose.position.z
        }

    def inhibit_callback(self, msg):
        self.inhibit_state = msg.data



    def control_loop(self):
        now = time.time()
        
        # Load parameters
        k_att = self.get_parameter('k_attractive').value
        k_rep = self.get_parameter('k_repulsive').value
        safety_rad = self.get_parameter('safety_radius').value
        max_speed = self.get_parameter('max_speed').value
        
        # 1. Calculate Attractive Forces (relative distance on X-Z ground plane)
        dx = self.target_pos["x"] - self.current_pos["x"]
        dz = self.target_pos["z"] - self.current_pos["z"]
        
        f_att_x = k_att * dx
        f_att_z = k_att * dz
        
        # 3. Combine Forces
        f_tot_x = f_att_x
        f_tot_z = f_att_z
        
        # 4. Generate Corrective Twist Velocities
        cmd = Twist()
        
        # Safety Subsumption check
        if self.inhibit_state != "CLEAR" and self.inhibit_state != "NONE":
            cmd.linear.x = 0.0
            cmd.linear.y = 0.0
            cmd.linear.z = 0.0
            cmd.angular.z = 0.0
        else:
            # Map forces to linear velocities on ground plane
            cmd.linear.x = max(-max_speed, min(max_speed, f_tot_x))
            cmd.linear.z = max(-max_speed, min(max_speed, f_tot_z))
            cmd.linear.y = 0.0
            
            # Simple rotation controller: align yaw toward target if we are moving
            if abs(dx) > 0.1 or abs(dz) > 0.1:
                target_yaw = math.atan2(dz, dx)
                # For simplified steering, we can set angular yaw velocity to target heading error
                cmd.angular.z = 0.8 * target_yaw
                cmd.angular.z = max(-1.0, min(1.0, cmd.angular.z))
            else:
                cmd.angular.z = 0.0
                
        self.cmd_vel_pub.publish(cmd)
        
        # Throttled logging (1.0s interval)
        if now - self.last_log_time > 1.0:
            log.info(
                f"[NAV] Current=({self.current_pos['x']:.2f}, {self.current_pos['z']:.2f}) | "
                f"Target=({self.target_pos['x']:.2f}, {self.target_pos['z']:.2f}) | "
                f"CmdLinearX={cmd.linear.x:.3f} m/s, CmdLinearZ={cmd.linear.z:.3f} m/s | "
                f"Inhibit={self.inhibit_state}"
            )
            self.last_log_time = now

def main(args=None):
    rclpy.init(args=args)
    node = NavigationAgent()
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
