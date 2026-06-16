#!/usr/bin/env python3
import os
import sys
import time
import logging
import random
try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import PointCloud2
except ImportError:
    pass

log = logging.getLogger("lidar_sim")

class Hk07LidarSimulator(Node):
    def __init__(self):
        super().__init__('hk07_lidar_simulator')
        self.lidar_hardware_absent = os.getenv("LIDAR_HARDWARE_ABSENT", "true").lower() == "true"
        
        # Publisher for pointcloud/scan topics if active
        self.lidar_pub = self.create_publisher(PointCloud2, '/sensors/lidar/scan', 10)
        
        if self.lidar_hardware_absent:
            log.info(">>> [LIDAR_DISARMED]: Physical hardware absent. Forcing LidarPoints to 0.")
            self.lidar_points = 0
            self.obstacles = []
            self.repulsion_vector = (0.00, 0.00, 0.00)
        else:
            log.info(">>> [LIDAR_ACTIVE]: Physical hardware simulated.")
            self.lidar_points = 360
            self.obstacles = [random.uniform(0.5, 5.0) for _ in range(360)]
            self.repulsion_vector = (0.1, 0.0, 0.1)

        self.timer = self.create_timer(0.1, self.publish_scan)

    def publish_scan(self):
        if self.lidar_hardware_absent:
            # Neutralize dummy obstacle generation arrays to prevent phantom repulsion vectors
            self.lidar_points = 0
            self.obstacles = []
            self.repulsion_vector = (0.00, 0.00, 0.00)
            return

        # Regular publishing mock code
        pass

def main(args=None):
    rclpy.init(args=args)
    node = Hk07LidarSimulator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
