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
        self.start_time = None
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
        log.info("Monitoring topic '/system/heartbeat' (10.0s timeout fail-safe)...")

    def _create_vitals_message(self, is_falling_val: float, emergency_val: float):
        js_msg = JointState()
        js_msg.header.stamp = self.get_clock().now().to_msg()
        js_msg.name = [
            "is_falling", "emergency_button_pressed", "heart_rate", "heart_status",
            "accel_status", "accel_x", "accel_y", "accel_z",
            "gyro_status", "gyro_x", "gyro_y", "gyro_z",
            "mag_status", "mag_x", "mag_y", "mag_z",
            "orient_status", "orient_w", "orient_x", "orient_y", "orient_z",
            "compass_status", "compass_heading",
            "gravity_status", "gravity_x", "gravity_y", "gravity_z",
            "light_status", "ambient_light",
            "baro_status", "barometric_pressure",
            "gps_status", "latitude", "longitude", "altitude",
            "pedometer_status", "pedometer_steps",
            "activity_status", "activity_type",
            "wrist_status", "wrist_motion_magnitude",
            "battery_level", "battery_temp"
        ]
        js_msg.position = [
            is_falling_val, emergency_val, float('nan'), 0.0,
            0.0, float('nan'), float('nan'), float('nan'),
            0.0, float('nan'), float('nan'), float('nan'),
            0.0, float('nan'), float('nan'), float('nan'),
            0.0, float('nan'), float('nan'), float('nan'), float('nan'),
            0.0, float('nan'),
            0.0, float('nan'), float('nan'), float('nan'),
            0.0, float('nan'),
            0.0, float('nan'),
            0.0, float('nan'), float('nan'), float('nan'),
            0.0, float('nan'),
            0.0, float('nan'),
            0.0, float('nan'),
            100.0, 32.0 # default battery level/temp values
        ]
        return js_msg

    def heartbeat_callback(self, msg):
        now = time.time()
        self.last_heartbeat_time = now
        
        if self.watchdog_tripped:
            log.info("[RTOS WATCHDOG] Middleware heartbeat recovered. System online.")
            self.watchdog_tripped = False
            
            # Reset standard safety indicators using unified schema
            js_msg = self._create_vitals_message(0.0, 0.0)
            try:
                if rclpy.ok():
                    self.wristband_pub.publish(js_msg)
            except Exception:
                pass

    def watchdog_check_callback(self):
        now = time.time()
        
        if self.start_time is None:
            self.start_time = now
            self.last_heartbeat_time = now
            return
            
        # Grace period: during the first 10 seconds of startup, keep refreshing last_heartbeat_time
        if now - self.start_time < 10.0:
            self.last_heartbeat_time = now
            return
            
        elapsed = now - self.last_heartbeat_time
        
        if elapsed > 10.0:
            if not self.watchdog_tripped:
                log.warning(
                    f"[RTOS SYSTEM WATCHDOG] MIDDLEWARE HEARTBEAT LOST! Elapsed: {elapsed:.2f}s "
                    f"(Threshold: 10.0s). OS/Middleware connection hang (COMMUNICATION_FAULT). "
                    f"Initiating safe standby hold. This is NOT a user physiological emergency."
                )
                self.watchdog_tripped = True
            
            # Publish nominal safe status (0.0, 0.0) instead of tripping safety E-STOP
            js_msg = self._create_vitals_message(0.0, 0.0)
            try:
                if rclpy.ok():
                    self.wristband_pub.publish(js_msg)
            except Exception:
                pass

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
