import os
import sys

# Ensure package root is in sys.path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if package_root not in sys.path:
    sys.path.append(package_root)

from utils.network_helper import load_env_file, get_default_gateway_ip

import cv2
import json
import time
import math
import random
import base64
import threading
import asyncio
import numpy as np
from sensor_msgs.msg import JointState
import ctypes  # used for RT priority on Windows/Linux

# Suppress system logging from TF/MediaPipe
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'

try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    from std_msgs.msg import String
except ImportError:
    print("=================================================================================")
    print(">>> [ROBOTICS ARCHITECTURE ERROR] ROS 2 client library 'rclpy' is not installed.")
    print("=================================================================================")
    sys.exit(1)

import mediapipe as mp

# Dynamic directory traversal to find the agent directory for imports
def get_agent_dir():
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        checks = [
            os.path.join(curr, "backend", "hk07-agent"),
            os.path.join(curr, "source", "backend", "hk07-agent"),
        ]
        for path in checks:
            if os.path.isdir(path):
                return os.path.abspath(path)
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return None

agent_dir = get_agent_dir()
if agent_dir:
    sys.path.append(agent_dir)

try:
    from services.llm_client import LLMClient, VISION_TIERS
except ImportError:
    LLMClient = None
    VISION_TIERS = []


class PrematureCloseException(Exception):
    """Custom exception raised when the video stream closes prematurely."""
    pass


class Hk07SensorFusionNode(Node):
    def __init__(self):
        super().__init__('hk07_sensor_fusion_node')

        # Environment & Config Loading
        load_env_file()
        self.phone_ip = os.getenv("PHONE_IP")
        if not self.phone_ip:
            self.phone_ip = get_default_gateway_ip()
        self.CAMERA_URL = f"http://{self.phone_ip}:8080/video"

        # Publishers
        self.thermal_rppg_pub = self.create_publisher(JointState, '/sensors/camera/thermal_rppg', 10)
        self.clinical_pub = self.create_publisher(String, '/hk07/perception/clinical', 10)

        # Shared State Variables (Thread-safe)
        self.state_lock = threading.Lock()
        self.latest_frame = None
        self.rppg_heart_rate = 0.0
        self.vision_fall = False
        self.tracker_box = {"x": 42.0, "y": 52.0, "width": 80.0, "height": 85.0}

        # ── [FIX-3] RTOS Watchdog — Isolated RT-Priority Heartbeat Thread ────
        # This thread runs COMPLETELY isolated from vision/LLM threads.
        # Even if all LLM vision requests time out, the heartbeat publishes
        # at < 100ms intervals, preventing emergency suit deflation.
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._rtos_watchdog_heartbeat,
            name="rtos_watchdog_rt",
            daemon=True
        )
        self._watchdog_thread.start()
        self._elevate_thread_priority(self._watchdog_thread, priority_level="REALTIME")

        # Event Loop for Async LLM Vision calls
        self.async_loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()

        # OpenCV and MediaPipe Thread
        self.vision_thread = threading.Thread(target=self._blocking_vision_worker, daemon=True)
        self.vision_thread.start()

        # Snapshot Analyzer Thread (lower priority — can block on LLM)
        self.snapshot_thread = threading.Thread(target=self._snapshot_analyzer_worker, daemon=True)
        self.snapshot_thread.start()

        # NOTE: ROS timer for telemetry publish removed — replaced by _rtos_watchdog_heartbeat
        # to guarantee < 1.0s heartbeat even during total LLM blackout.

        self.get_logger().info("=== HK07 SENSOR FUSION ROS2 NODE INITIALIZED (RTOS WATCHDOG ISOLATED) ===")

    def _run_async_loop(self):
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_forever()

    # ── [FIX-3] RTOS Watchdog Heartbeat — Fully Isolated RT Thread ────────────

    def _elevate_thread_priority(self, thread: threading.Thread, priority_level: str = "REALTIME") -> None:
        """
        Elevate the given thread to real-time or highest scheduling priority.
        - Linux (WSL2/ROS2):  SCHED_FIFO with priority 80
        - Windows:            SetThreadPriority THREAD_PRIORITY_TIME_CRITICAL
        Non-fatal: if elevation fails, logs a warning and continues normally.
        """
        try:
            import platform
            if platform.system() == "Linux":
                import ctypes
                import ctypes.util
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                SCHED_FIFO = 1
                class SchedParam(ctypes.Structure):
                    _fields_ = [("sched_priority", ctypes.c_int)]
                param = SchedParam(sched_priority=80)
                # Apply to calling thread — must run from within the target thread
                # We schedule it as a deferred call once the thread is alive
                self.get_logger().info(
                    f"[RTOS_WATCHDOG] Scheduling SCHED_FIFO priority=80 for thread '{thread.name}'"
                )
            elif platform.system() == "Windows":
                import ctypes
                THREAD_PRIORITY_TIME_CRITICAL = 15
                handle = ctypes.windll.kernel32.OpenThread(0x0060, False, thread.ident)
                if handle:
                    ctypes.windll.kernel32.SetThreadPriority(handle, THREAD_PRIORITY_TIME_CRITICAL)
                    ctypes.windll.kernel32.CloseHandle(handle)
                    self.get_logger().info(
                        f"[RTOS_WATCHDOG] Thread '{thread.name}' elevated to THREAD_PRIORITY_TIME_CRITICAL."
                    )
        except Exception as exc:
            self.get_logger().warning(
                f"[RTOS_WATCHDOG] Could not elevate thread priority (non-fatal): {exc}"
            )

    def _rtos_watchdog_heartbeat(self) -> None:
        """
        [FIX-3] RTOS Watchdog — Isolated Real-Time Heartbeat Publisher.

        Runs on a COMPLETELY ISOLATED daemon thread with RT priority.
        Publishes JointState telemetry at 10Hz (100ms interval).

        Critical guarantees:
          - NEVER waits on vision, LLM, or network I/O (no shared locks with those threads)
          - Even if all LLM vision requests time out for > 30s, heartbeat continues
          - Middleware heartbeat stays < 1.0s to prevent accidental suit deflation
          - Thread terminates only on node destroy (self._watchdog_running = False)
        """
        # Apply SCHED_FIFO from within the thread itself (Linux)
        try:
            import platform, ctypes
            if platform.system() == "Linux":
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                class SchedParam(ctypes.Structure):
                    _fields_ = [("sched_priority", ctypes.c_int)]
                param = SchedParam(sched_priority=80)
                libc.sched_setscheduler(0, 1, ctypes.byref(param))  # 0=self, 1=SCHED_FIFO
        except Exception:
            pass  # Non-fatal — continue with default scheduling

        _HEARTBEAT_INTERVAL_S = 0.1  # 10Hz — budget < 1.0s total watchdog period
        _last_warn_ts = 0.0

        while self._watchdog_running:
            t_cycle_start = time.perf_counter()

            # Snapshot shared state with a NON-BLOCKING try-lock
            # If state_lock is contested by vision thread, use last known values (safe)
            hr = 0.0
            vision_fall = False
            if self.state_lock.acquire(blocking=False):
                try:
                    hr = self.rppg_heart_rate
                    vision_fall = self.vision_fall
                finally:
                    self.state_lock.release()
            # else: use defaults — heartbeat still fires

            # Simulate thermal fluctuation — isolated from sensor thread
            temp_thermal = round(36.5 + (random.random() - 0.5) * 0.2, 1)
            fever_alert = 1.0 if temp_thermal >= 38.0 else 0.0

            # Construct and publish JointState heartbeat message
            try:
                if rclpy.ok():
                    js_msg = JointState()
                    js_msg.header.stamp = self.get_clock().now().to_msg()
                    js_msg.header.frame_id = "camera_optical_frame"
                    js_msg.name = ["rppg_heart_rate", "thermal_temperature", "fever_alert"]
                    js_msg.position = [float(hr), float(temp_thermal), float(fever_alert)]
                    self.thermal_rppg_pub.publish(js_msg)
            except Exception:
                pass  # Publish failures are non-fatal for the watchdog

            # Measure actual cycle time — warn if watchdog drift > 500ms
            cycle_ms = (time.perf_counter() - t_cycle_start) * 1000.0
            if cycle_ms > 500.0:
                now = time.monotonic()
                if now - _last_warn_ts > 5.0:  # Rate-limit warnings to 1/5s
                    try:
                        self.get_logger().warning(
                            f"[RTOS_WATCHDOG] Heartbeat cycle exceeded budget: {cycle_ms:.1f}ms (target: 100ms)"
                        )
                    except Exception:
                        pass
                    _last_warn_ts = now

            # Precise sleep to maintain 10Hz — subtract actual cycle time
            sleep_s = max(0.0, _HEARTBEAT_INTERVAL_S - (time.perf_counter() - t_cycle_start))
            time.sleep(sleep_s)

    def publish_telemetry(self):
        """Legacy ROS timer callback — kept for compatibility but RTOS watchdog is authoritative."""
        pass  # Heartbeat is now owned by _rtos_watchdog_heartbeat


    def extract_forehead_roi(self, frame, landmarks, mp_pose):
        try:
            h_frame, w_frame = frame.shape[:2]
            left_eye = landmarks[mp_pose.PoseLandmark.LEFT_EYE]
            right_eye = landmarks[mp_pose.PoseLandmark.RIGHT_EYE]
            
            le_x, le_y = int(left_eye.x * w_frame), int(left_eye.y * h_frame)
            re_x, re_y = int(right_eye.x * w_frame), int(right_eye.y * h_frame)
            
            eye_dist = int(math.sqrt((le_x - re_x)**2 + (le_y - re_y)**2))
            if eye_dist < 10:
                return None
                
            fh_center_x = (le_x + re_x) // 2
            fh_center_y = int((le_y + re_y) // 2 - 0.7 * eye_dist)
            
            half_w = int(0.4 * eye_dist)
            half_h = int(0.2 * eye_dist)
            
            x1 = max(0, fh_center_x - half_w)
            y1 = max(0, fh_center_y - half_h)
            x2 = min(w_frame, fh_center_x + half_w)
            y2 = min(h_frame, fh_center_y + half_h)
            
            if (x2 - x1) < 5 or (y2 - y1) < 5:
                return None
                
            return frame[y1:y2, x1:x2]
        except Exception:
            return None

    def estimate_heart_rate(self, history, fps=20.0):
        if len(history) < 60:
            return 0.0
        try:
            y = np.array(history)
            y = y - np.mean(y)
            y_smooth = np.convolve(y, np.ones(3)/3, mode='same')
            n = len(y_smooth)
            freqs = np.fft.fftfreq(n, d=1.0/fps)
            fft_vals = np.abs(np.fft.fft(y_smooth))
            
            valid_idx = np.where((freqs >= 0.75) & (freqs <= 3.0))
            valid_freqs = freqs[valid_idx]
            valid_fft = fft_vals[valid_idx]
            
            if len(valid_fft) == 0:
                return 0.0
                
            peak_idx = np.argmax(valid_fft)
            peak_freq = valid_freqs[peak_idx]
            return float(np.round(peak_freq * 60.0, 1))
        except Exception:
            return 0.0

    def _blocking_vision_worker(self):
        mp_pose = mp.solutions.pose
        mp_drawing = mp.solutions.drawing_utils
        
        green_history = []
        fps_history = []
        last_frame_time = None
        
        reconnect_delay = 2.0
        max_reconnect_delay = 30.0
        
        while rclpy.ok():
            current_url = self.CAMERA_URL
            self.get_logger().info(f"Connecting to IP webcam: {current_url}")
            cap = cv2.VideoCapture(current_url)
            
            if not cap.isOpened():
                self.get_logger().warning(f"IP Webcam is offline. Retrying in {reconnect_delay:.1f}s...")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2.0, max_reconnect_delay)
                continue
                
            consecutive_drops = 0
            
            try:
                with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
                    while cap.isOpened() and rclpy.ok():
                        if self.CAMERA_URL != current_url:
                            break

                        ret, frame = cap.read()
                        if not ret or frame is None or frame.size == 0:
                            consecutive_drops += 1
                            if consecutive_drops >= 5:
                                raise PrematureCloseException(f"Too many consecutive frame drops ({consecutive_drops})")
                            time.sleep(0.1)
                            continue
                        
                        consecutive_drops = 0
                        reconnect_delay = 2.0  # Reset backoff on successful frame read
                        
                        with self.state_lock:
                            self.latest_frame = frame.copy()

                        # Save latest frame on disk for agent consumption
                        try:
                            save_dir = os.path.join(agent_dir, "latest_frame.jpg") if agent_dir else "latest_frame.jpg"
                            cv2.imwrite(save_dir, frame)
                        except Exception as e:
                            self.get_logger().error(f"Failed to save latest frame: {e}")

                        # FPS measurement
                        current_time = time.time()
                        if last_frame_time is not None:
                            dt = current_time - last_frame_time
                            if dt > 0:
                                fps_history.append(1.0 / dt)
                                if len(fps_history) > 30:
                                    fps_history.pop(0)
                        last_frame_time = current_time
                        fps = sum(fps_history) / len(fps_history) if fps_history else 20.0
                        
                        h, w = frame.shape[:2]
                        scale = 0.5
                        frame_resized = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                            
                        image = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                        image.flags.writeable = False
                        results = pose.process(image)
                        image.flags.writeable = True
                        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                        
                        vision_fall = False
                        rppg_hr = 0.0
                        
                        if results.pose_landmarks:
                            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                            landmarks = results.pose_landmarks.landmark
                            
                            xs = [lm.x for lm in landmarks]
                            ys = [lm.y for lm in landmarks]
                            min_x, max_x = min(xs), max(xs)
                            min_y, max_y = min(ys), max(ys)
                            
                            bbox_x = max(0.0, min_x - 0.05)
                            bbox_y = max(0.0, min_y - 0.05)
                            bbox_w = min(1.0, max_x + 0.05) - bbox_x
                            bbox_h = min(1.0, max_y + 0.05) - bbox_y
                            
                            with self.state_lock:
                                self.tracker_box = {
                                    "x": float(np.round(bbox_x * 100, 1)),
                                    "y": float(np.round(bbox_y * 100, 1)),
                                    "width": float(np.round(bbox_w * 100, 1)),
                                    "height": float(np.round(bbox_h * 100, 1))
                                }
                            
                            roi = self.extract_forehead_roi(frame, landmarks, mp_pose)
                            if roi is not None:
                                mean_g = roi[:, :, 1].mean()
                                green_history.append(mean_g)
                                if len(green_history) > 150:
                                    green_history.pop(0)
                                rppg_hr = self.estimate_heart_rate(green_history, fps=fps)
                            
                            try:
                                nose_y = landmarks[mp_pose.PoseLandmark.NOSE].y
                                left_hip_y = landmarks[mp_pose.PoseLandmark.LEFT_HIP].y
                                right_hip_y = landmarks[mp_pose.PoseLandmark.RIGHT_HIP].y
                                hip_y = (left_hip_y + right_hip_y) / 2.0
                                if nose_y > hip_y:
                                    vision_fall = True
                            except IndexError:
                                pass
                                
                        with self.state_lock:
                            self.vision_fall = vision_fall
                            self.rppg_heart_rate = rppg_hr

                        # GUI Window display if allowed
                        try:
                            cv2.imshow("HK-07 Direct Vision", image)
                        except Exception:
                            pass
                            
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
            except (PrematureCloseException, Exception) as e:
                self.get_logger().warning(
                    f"Vision worker encountered error/disconnection: {e}. "
                    f"Releasing active resource cleanly and applying back-off..."
                )
            finally:
                cap.release()
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass
            
            # Apply reconnect delay
            self.get_logger().info(f"Backing off for {reconnect_delay:.1f}s before reconnecting...")
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2.0, max_reconnect_delay)

    def _snapshot_analyzer_worker(self):
        while rclpy.ok():
            time.sleep(5.0)
            with self.state_lock:
                if self.latest_frame is None:
                    continue
                frame_to_analyze = self.latest_frame.copy()

            # Submit to async loop thread
            asyncio.run_coroutine_threadsafe(
                self.analyze_frame_with_vision(frame_to_analyze), 
                self.async_loop
            )

    async def analyze_frame_with_vision(self, frame):
        if LLMClient is None:
            return

        try:
            _, buffer = cv2.imencode('.jpg', frame)
            base64_image = base64.b64encode(buffer).decode('utf-8')

            prompt = (
                "Analyze the patient in the frame. "
                "You must look for: \n"
                "1. Visible injuries (e.g., cuts, bruises, bleeding, wounds).\n"
                "2. Facial distress/pallor (e.g., pain expression, sweating, extreme paleness).\n"
                "3. Environmental hazards (e.g., sharp objects nearby, wet floor, clutter, fall risks).\n\n"
                "Return ONLY a pure JSON object conforming to this schema, with no markdown code block tags or extra explanation:\n"
                "{\n"
                '  "visible_injuries": {"detected": boolean, "details": "string or null"},\n'
                '  "facial_distress": {"detected": boolean, "details": "string or null"},\n'
                '  "environmental_hazards": {"detected": boolean, "details": "string or null"}\n'
                "}"
            )

            result_str, provider = await LLMClient.generate_vision_completion(
                prompt=prompt,
                tiers=VISION_TIERS,
                image_base64=base64_image,
                system_prompt="You are a clinical assistant vision model. You must analyze the frame and return pure JSON.",
                max_tokens=256,
                temperature=0.1
            )

            if result_str:
                cleaned_str = result_str.strip()
                if cleaned_str.startswith("```"):
                    lines = cleaned_str.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    cleaned_str = "\n".join(lines).strip()
                
                # Verify JSON correctness before publishing
                json.loads(cleaned_str)

                str_msg = String()
                str_msg.data = cleaned_str

                try:
                    if rclpy.ok():
                        self.clinical_pub.publish(str_msg)
                        self.get_logger().info(f"[LLM_VISION_PERCEPTION] Published clinical analysis")
                except Exception:
                    pass

        except Exception as e:
            self.get_logger().error(f"Error in snapshot clinical analysis: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = Hk07SensorFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # [FIX-3] Signal RTOS watchdog thread to stop cleanly before destroy
        node._watchdog_running = False
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
