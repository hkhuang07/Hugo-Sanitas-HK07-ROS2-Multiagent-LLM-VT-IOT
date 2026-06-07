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

from sensor_msgs.msg import PointCloud2, PointField
from geometry_msgs.msg import Twist
import struct

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("lidar_sim")

class LidarPointCloudSim(Node):
    def __init__(self):
        super().__init__('lidar_pointcloud_sim')
        
        # Publishers
        self.points_pub = self.create_publisher(PointCloud2, '/telemetry/lidar/points', 10)
        self.avoidance_pub = self.create_publisher(Twist, '/telemetry/avoidance', 10)
        
        # Timer (10Hz)
        self.timer = self.create_timer(0.1, self.timer_callback)
        self.tick = 0
        
        log.info("=== HK07 LIDAR & OBSTACLE AVOIDANCE SIMULATOR NODE STARTED ===")

    def create_point_cloud2(self, points, stamp, frame_id="laser_frame"):
        msg = PointCloud2()
        msg.header.stamp = stamp
        msg.header.frame_id = frame_id
        msg.height = 1
        msg.width = len(points)
        msg.is_bigendian = False
        msg.point_step = 12  # float32 x, y, z -> 4 * 3 = 12 bytes
        msg.row_step = msg.point_step * msg.width
        msg.is_dense = True
        
        msg.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1)
        ]
        
        buffer = bytearray()
        for pt in points:
            buffer.extend(struct.pack('<fff', float(pt['x']), float(pt['y']), float(pt['z'])))
        msg.data = bytes(buffer)
        
        return msg

    def timer_callback(self):
        try:
            # Generate moving obstacle path
            # x oscillates between 0.3m and 2.3m to trigger the 1.0m warning zone
            x_obs = 1.3 + 1.0 * math.cos(self.tick * 0.1)
            y_obs = 1.1 # Center height of the robot torso
            z_obs = 0.0 # Straight on the X-axis
            
            # Generate a 3D point cloud cluster representing the obstacle
            points = []
            num_points = 25
            for _ in range(num_points):
                px = x_obs + random.uniform(-0.12, 0.12)
                py = y_obs + random.uniform(-0.35, 0.35)
                pz = z_obs + random.uniform(-0.12, 0.12)
                points.append({
                    "x": round(px, 3),
                    "y": round(py, 3),
                    "z": round(pz, 3)
                })
            
            # Calculate distance to robot center (assumed at 0, 1.1, 0)
            robot_x, robot_y, robot_z = 0.0, 1.1, 0.0
            dx = robot_x - x_obs
            dy = robot_y - y_obs
            dz = robot_z - z_obs
            dist = math.sqrt(dx**2 + dy**2 + dz**2)
            
            # Subsumption Repulsive Potential Field
            avoidance_vector = {"x": 0.0, "y": 0.0, "z": 0.0}
            threat_detected = False
            
            if dist < 1.0:
                threat_detected = True
                if dist > 0.01:
                    # Direction pointing away from the obstacle (push vector)
                    ux = dx / dist
                    uy = dy / dist
                    uz = dz / dist
                    
                    # Repulsion force scale: stronger as obstacle gets closer
                    # Capped at maximum 2.0 length for visual constraint
                    magnitude = min(2.0, 1.5 * (1.0 - dist) / (dist ** 2))
                    avoidance_vector = {
                        "x": round(ux * magnitude, 3),
                        "y": round(uy * magnitude, 3),
                        "z": round(uz * magnitude, 3)
                    }
            
            # Get current time stamp
            stamp = self.get_clock().now().to_msg()
            
            # Publish PointCloud2
            pc2_msg = self.create_point_cloud2(points, stamp)
            self.points_pub.publish(pc2_msg)
            
            # Publish Twist
            twist_msg = Twist()
            twist_msg.linear.x = float(avoidance_vector["x"])
            twist_msg.linear.y = float(avoidance_vector["y"])
            twist_msg.linear.z = float(avoidance_vector["z"])
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            self.avoidance_pub.publish(twist_msg)
            
            log.info(
                f"Obstacle at X={x_obs:.2f}m | Distance={dist:.2f}m | "
                f"Threat={threat_detected} | "
                f"Repulsion Vector=({avoidance_vector['x']:.2f}, {avoidance_vector['y']:.2f}, {avoidance_vector['z']:.2f})"
            )
            
            self.tick += 1
            
        except Exception as err:
            log.error(f"Error in timer callback: {err}")

def main(args=None):
    rclpy.init(args=args)
    node = LidarPointCloudSim()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
