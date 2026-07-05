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
        
        # ─── Priority Action Arbitrator Configuration ───
        self.EMERGENCY = 1
        self.BALANCE = 2
        self.NAV_COMMAND = 3
        self.MONITOR_IDLE = 4
        
        # Dict to store latest command of each priority level:
        # structure: {priority_level: (timestamp, linear_x, linear_z, angular_z, action)}
        self.latest_commands = {
            self.EMERGENCY: None,
            self.BALANCE: None,
            self.NAV_COMMAND: None,
            self.MONITOR_IDLE: None
        }
        
        # Motor hardware power status & last motion timestamp
        self.motor_power_supplied = False
        self.last_motion_ts = time.time()
        
        # Subscriptions for four distinct priority levels
        self.emergency_sub = self.create_subscription(
            Twist,
            '/control/motion/emergency',
            self.emergency_callback,
            10
        )
        
        self.balance_sub = self.create_subscription(
            Twist,
            '/control/motion/balance_cmd_vel',
            self.balance_callback,
            10
        )
        
        self.nav_sub = self.create_subscription(
            Twist,
            '/control/motion/nav_cmd_vel',
            self.nav_callback,
            10
        )
        
        self.idle_sub = self.create_subscription(
            Twist,
            '/control/motion/idle',
            self.idle_callback,
            10
        )
        
        # Publishers
        self.joint_pub = self.create_publisher(JointState, '/telemetry/joint_states', 10)
        self.imu_pub = self.create_publisher(Imu, '/telemetry/imu', 10)
        
        from geometry_msgs.msg import PoseStamped
        self.pose_pub = self.create_publisher(PoseStamped, '/telemetry/pose', 10)
        
        # 50Hz Timer Loop for kinematics simulation
        self.timer = self.create_timer(0.02, self.control_step)
        
        log.info("=== HUGO KINEMATICS, MOTOR ARBITRATOR & POWER CONTROL NODE INITIALIZED ===")
        log.info("Priority Arbitrator registered topics:")
        log.info("  Level 1: /control/motion/emergency")
        log.info("  Level 2: /control/motion/balance_cmd_vel")
        log.info("  Level 3: /control/motion/nav_cmd_vel")
        log.info("  Level 4: /control/motion/idle")

    def emergency_callback(self, msg):
        """
        Callback for Priority 1: EMERGENCY (SOS/Ngã/Hụt chất dẫn truyền).
        Instantly preempts and drops lower priority command streams.
        """
        with self.state_lock:
            now = time.time()
            log.warning(
                f">>> [ARBITRATOR - EMERGENCY LEVEL 1] SOS/Fall/Biomarker fault trigger! "
                f"Preempting and purging lower-priority command buffer."
            )
            # Purge/drop lower priority command records
            self.latest_commands[self.BALANCE] = None
            self.latest_commands[self.NAV_COMMAND] = None
            self.latest_commands[self.MONITOR_IDLE] = None
            # Store emergency command
            self.latest_commands[self.EMERGENCY] = (now, msg.linear.x, msg.linear.z, msg.angular.z, msg.angular.x)

    def balance_callback(self, msg):
        """
        Callback for Priority 2: BALANCE (Standing balance controller PID feedback).
        """
        with self.state_lock:
            emerg = self.latest_commands[self.EMERGENCY]
            if emerg is not None and (time.time() - emerg[0]) < 10.0:
                return
            now = time.time()
            self.latest_commands[self.BALANCE] = (now, msg.linear.x, msg.linear.z, msg.angular.z, msg.angular.x)

    def nav_callback(self, msg):
        """
        Callback for Priority 3: NAV_COMMAND (Navigation agent APF waypoint).
        """
        with self.state_lock:
            emerg = self.latest_commands[self.EMERGENCY]
            if emerg is not None and (time.time() - emerg[0]) < 10.0:
                return
            bal = self.latest_commands[self.BALANCE]
            # If balance corrections are active (within 0.5s), ignore navigation commands
            if bal is not None and (time.time() - bal[0]) < 0.5:
                return
            now = time.time()
            self.latest_commands[self.NAV_COMMAND] = (now, msg.linear.x, msg.linear.z, msg.angular.z, msg.angular.x)

    def idle_callback(self, msg):
        """
        Callback for Priority 4: MONITOR_IDLE.
        Only executed if no higher levels are active.
        """
        with self.state_lock:
            now = time.time()
            self.latest_commands[self.MONITOR_IDLE] = (now, msg.linear.x, msg.linear.z, msg.angular.z, msg.angular.x)

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
        now = time.time()
        
        # State variables to process
        v_x = 0.0
        v_z = 0.0
        w_yaw = 0.0
        action = 0
        active_pri = self.MONITOR_IDLE
        with self.state_lock:
            # Check commands by priority: EMERGENCY (1), BALANCE (2), NAV_COMMAND (3), MONITOR_IDLE (4)
            cmd_emerg = self.latest_commands[self.EMERGENCY]
            if cmd_emerg is not None and (now - cmd_emerg[0]) < 10.0:
                v_x, v_z, w_yaw, action = cmd_emerg[1], cmd_emerg[2], cmd_emerg[3], int(cmd_emerg[4])
                active_pri = self.EMERGENCY
            else:
                cmd_bal = self.latest_commands[self.BALANCE]
                if cmd_bal is not None and (now - cmd_bal[0]) < 1.0:
                    v_x, v_z, w_yaw, action = cmd_bal[1], cmd_bal[2], cmd_bal[3], int(cmd_bal[4])
                    active_pri = self.BALANCE
                else:
                    cmd_nav = self.latest_commands[self.NAV_COMMAND]
                    if cmd_nav is not None and (now - cmd_nav[0]) < 2.0:
                        v_x, v_z, w_yaw, action = cmd_nav[1], cmd_nav[2], cmd_nav[3], int(cmd_nav[4])
                        active_pri = self.NAV_COMMAND
                    else:
                        cmd_idle = self.latest_commands[self.MONITOR_IDLE]
                        if cmd_idle is not None:
                            v_x, v_z, w_yaw, action = cmd_idle[1], cmd_idle[2], cmd_idle[3], int(cmd_idle[4])
                            active_pri = self.MONITOR_IDLE
            
            self.cmd_linear_x = v_x
            self.cmd_linear_z = v_z
            self.cmd_angular_z = w_yaw
            self.current_action = action
 
        # ─── Motor Power Line Simulation (Fail-safe Supply Control) ───
        is_moving = (abs(v_x) > 0.01 or abs(v_z) > 0.01 or abs(w_yaw) > 0.01 or action != 0)
        if is_moving:
            self.last_motion_ts = now
            if not self.motor_power_supplied:
                self.motor_power_supplied = True
                log.info(
                    f">>> [MOTOR_CONTROLLER] Command priority LEVEL {active_pri} detected! "
                    f"Power line ST1 ON (24V). Releasing safety electromagnetic brakes."
                )
            
            # Real-world Motor Electrical Logs
            import random
            motor_current = 0.5 + 1.2 * math.sqrt(v_x**2 + v_z**2) + random.uniform(-0.05, 0.05)
            log.info(
                f">>> [MOTOR_CONTROL] Hub motors active: speed={v_x:.2f}m/s, yaw_rate={w_yaw:.2f}rad/s. "
                f"PMU consumption: current={motor_current:.2f}A, power={motor_current*24.0:.1f}W."
            )
            if action == 3:
                log.info(
                    ">>> [PNEUMATIC_ARMOR] Soft-suit pump powered (24V, 2.8A). "
                    "Expanding chambers. Target pressure: 2.3 PSI."
                )
        else:
            if self.motor_power_supplied and (now - self.last_motion_ts) > 3.0:
                self.motor_power_supplied = False
                log.info(
                    f">>> [MOTOR_CONTROLLER] Hardware idle for 3.0s. Power line ST1 OFF (0V). "
                )
            
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
        
        # 4. Compile and Publish IMU & PoseStamped Telemetry
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
        
        # Simulated acceleration & actual angular velocity
        imu_msg.linear_acceleration.x = v_x / dt if dt > 0 else 0.0
        imu_msg.linear_acceleration.y = 0.0
        imu_msg.linear_acceleration.z = 9.81
        imu_msg.angular_velocity.x = 0.0
        imu_msg.angular_velocity.y = 0.0
        imu_msg.angular_velocity.z = w_yaw
        self.imu_pub.publish(imu_msg)
        
        # Publish PoseStamped for position tracking (eliminates topic hacking)
        from geometry_msgs.msg import PoseStamped
        pose_msg = PoseStamped()
        pose_msg.header.stamp = stamp
        pose_msg.header.frame_id = "odom"
        pose_msg.pose.position.x = self.pos_x
        pose_msg.pose.position.y = self.pos_y
        pose_msg.pose.position.z = self.pos_z
        pose_msg.pose.orientation.w = qw
        pose_msg.pose.orientation.x = qx
        pose_msg.pose.orientation.y = qy
        pose_msg.pose.orientation.z = qz
        self.pose_pub.publish(pose_msg)

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
