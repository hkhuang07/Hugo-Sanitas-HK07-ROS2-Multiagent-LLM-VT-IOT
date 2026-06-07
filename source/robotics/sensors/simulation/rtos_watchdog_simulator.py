import os
import sys
import time
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

from std_msgs.msg import Header
from sensor_msgs.msg import JointState

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("rtos_watchdog")

class RtosWatchdogSimulator(Node):
    def __init__(self):
        super().__init__('rtos_watchdog_simulator')
        
        # State variables
        self.last_heartbeat_time = time.time()
        self.watchdog_tripped = False
        
        # ROS 2 Subscriptions
        self.heartbeat_sub = self.create_subscription(
            Header,
            '/system/heartbeat',
            self.heartbeat_callback,
            10
        )
        
        # ROS 2 Publishers
        self.wristband_pub = self.create_publisher(
            JointState,
            '/vitals/wristband',
            10
        )
        
        # Watchdog loop timer (10Hz / 0.1s check interval)
        self.timer = self.create_timer(0.1, self.watchdog_check_callback)
        
        log.info("=== RTOS WATCHDOG CO-PROCESSOR SIMULATOR NODE STARTED ===")
        log.info("Monitoring topic '/system/heartbeat' (3.0s timeout fail-safe)...")

    def heartbeat_callback(self, msg):
        now = time.time()
        self.last_heartbeat_time = now
        
        if self.watchdog_tripped:
            log.info("[RTOS WATCHDOG] Middleware heartbeat recovered. System online.")
            self.watchdog_tripped = False
            
            # Reset standard safety indicators
            js_msg = JointState()
            js_msg.header.stamp = self.get_clock().now().to_msg()
            js_msg.name = ["is_falling", "emergency_button_pressed"]
            js_msg.position = [0.0, 0.0]
            self.wristband_pub.publish(js_msg)

    def watchdog_check_callback(self):
        now = time.time()
        elapsed = now - self.last_heartbeat_time
        
        if elapsed > 3.0:
            if not self.watchdog_tripped:
                log.warning(
                    f"[RTOS WATCHDOG ALERT] HEARTBEAT LOST! Elapsed: {elapsed:.2f}s "
                    f"(Threshold: 3.0s). OS/Middleware frozen. TRIGGERING EMERGENCY SAFE SUIT DEFLATION."
                )
                self.watchdog_tripped = True
            
            # Continuously enforce E-STOP state until heartbeat is restored
            js_msg = JointState()
            js_msg.header.stamp = self.get_clock().now().to_msg()
            js_msg.name = ["is_falling", "emergency_button_pressed"]
            js_msg.position = [1.0, 1.0]
            self.wristband_pub.publish(js_msg)

def main(args=None):
    rclpy.init(args=args)
    node = RtosWatchdogSimulator()
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
