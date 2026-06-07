import unittest
from unittest.mock import MagicMock, patch
import math
import sys
import os

# Add the simulation path to sys.path so we can import directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Clean mocks for rclpy and messages
sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['sensor_msgs'] = MagicMock()
sys.modules['sensor_msgs.msg'] = MagicMock()
sys.modules['geometry_msgs'] = MagicMock()
sys.modules['geometry_msgs.msg'] = MagicMock()
sys.modules['std_msgs'] = MagicMock()
sys.modules['std_msgs.msg'] = MagicMock()

# Concrete lightweight mock classes for ROS 2 messages
class MockVector3:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

class MockTwist:
    def __init__(self):
        self.linear = MockVector3()
        self.angular = MockVector3()

class MockImu:
    def __init__(self):
        self.linear_acceleration = MockVector3()
        self.angular_velocity = MockVector3()
        self.orientation = MagicMock()

class MockString:
    def __init__(self):
        self.data = ""

sys.modules['geometry_msgs.msg'].Twist = MockTwist
sys.modules['sensor_msgs.msg'].Imu = MockImu
sys.modules['std_msgs.msg'].String = MockString

# Mock Node class
class MockNode:
    def __init__(self, node_name):
        self.node_name = node_name
        self.parameters = {}
        
    def declare_parameter(self, name, default_value):
        self.parameters[name] = default_value
        
    def get_parameter(self, name):
        val = self.parameters.get(name, 1.0)
        mock_param = MagicMock()
        mock_param.value = val
        return mock_param
        
    def create_subscription(self, msg_type, topic, callback, qos):
        mock_sub = MagicMock()
        return mock_sub
        
    def create_publisher(self, msg_type, topic, qos):
        mock_pub = MagicMock()
        return mock_pub
        
    def create_timer(self, interval, callback):
        mock_timer = MagicMock()
        return mock_timer
        
    def get_clock(self):
        mock_clock = MagicMock()
        mock_clock.now.return_value.to_msg.return_value = MagicMock(sec=100, nanosec=200)
        return mock_clock

# Assign MockNode to sys.modules
sys.modules['rclpy.node'].Node = MockNode

# Now we can import the controllers safely!
from balance_controller import BalanceController
from navigation_agent import NavigationAgent

class TestBalanceAndNavigation(unittest.TestCase):
    def test_balance_controller_math(self):
        node = BalanceController()
        node.parameters['kp_pitch'] = 1.0
        node.parameters['ki_pitch'] = 0.0
        node.parameters['kd_pitch'] = 0.0
        node.parameters['kp_roll'] = 1.0
        node.parameters['ki_roll'] = 0.0
        node.parameters['kd_roll'] = 0.0
        
        node.cmd_vel_pub = MagicMock()
        
        # Create an IMU message tilted forward (accel_x > 0)
        msg = MagicMock()
        msg.linear_acceleration.x = 1.0
        msg.linear_acceleration.y = 0.0
        msg.linear_acceleration.z = 9.81
        
        # Trigger IMU callback
        node.imu_callback(msg)
        
        # Check that cmd_vel_pub.publish was called
        self.assertTrue(node.cmd_vel_pub.publish.called)
        published_msg = node.cmd_vel_pub.publish.call_args[0][0]
        
        # Pitch > 0 -> Error = 0 - pitch < 0 -> output < 0
        self.assertLess(published_msg.linear.x, 0.0)
        self.assertEqual(published_msg.linear.y, 0.0)
        
    def test_balance_controller_inhibit(self):
        node = BalanceController()
        node.cmd_vel_pub = MagicMock()
        
        # Set inhibit state to active
        inhibit_msg = MagicMock()
        inhibit_msg.data = "OBSTACLE"
        node.inhibit_callback(inhibit_msg)
        
        msg = MagicMock()
        msg.linear_acceleration.x = 1.0
        msg.linear_acceleration.y = 0.0
        msg.linear_acceleration.z = 9.81
        
        node.imu_callback(msg)
        
        published_msg = node.cmd_vel_pub.publish.call_args[0][0]
        # Velocity should be inhibited (0.0)
        self.assertEqual(published_msg.linear.x, 0.0)
        self.assertEqual(published_msg.linear.y, 0.0)
        
    def test_navigation_agent_apf_forces(self):
        node = NavigationAgent()
        node.parameters['k_attractive'] = 1.0
        node.parameters['k_repulsive'] = 5.0
        node.parameters['safety_radius'] = 1.0
        node.parameters['max_speed'] = 1.5
        
        node.cmd_vel_pub = MagicMock()
        
        # Target position is at (2.0, 0.0, 2.0)
        node.target_pos = {"x": 2.0, "y": 0.0, "z": 2.0}
        # Current position is at (0.0, 0.0, 0.0)
        node.current_pos = {"x": 0.0, "y": 0.0, "z": 0.0}
        
        # No obstacles
        node.lidar_points = []
        
        # Run control loop
        node.control_loop()
        
        self.assertTrue(node.cmd_vel_pub.publish.called)
        published_msg = node.cmd_vel_pub.publish.call_args[0][0]
        self.assertGreater(published_msg.linear.x, 0.0)
        self.assertGreater(published_msg.linear.z, 0.0)

        # Let's add an obstacle right in front of target (e.g. at 0.5, 0.0, 0.0)
        node.lidar_points = [{"x": 0.5, "y": 0.0, "z": 0.0}]
        node.control_loop()
        published_msg_obs = node.cmd_vel_pub.publish.call_args[0][0]
        
        # Repulsive force pushes us backward, so linear.x is smaller than before
        self.assertLess(published_msg_obs.linear.x, published_msg.linear.x)
        
if __name__ == '__main__':
    unittest.main()
