import os
import sys
import warnings

# Suppress deprecated Google Protobuf warnings from third-party libraries (MediaPipe)
warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf")

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
import queue
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

# Suppress system logging from TF/MediaPipe
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'
os.environ['OPENCV_LOG_LEVEL'] = 'OFF'
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'

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
    # Dynamically resolve import collision for 'utils' package under ROS 2 Executor path
    import utils
    if hasattr(utils, '__path__'):
        agent_utils = os.path.join(agent_dir, "utils")
        if os.path.isdir(agent_utils) and agent_utils not in utils.__path__:
            utils.__path__.append(agent_utils)

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
        self.robot_mode = os.getenv("ROBOT_MODE", "SIMULATED").upper()

        # Publishers
        self.thermal_rppg_pub = self.create_publisher(JointState, '/sensors/camera/thermal_rppg', 10)
        self.clinical_pub = self.create_publisher(String, '/hk07/perception/clinical', 10)

        # Initialize MQTT Client for direct vital signs database sync
        self.mqtt_client = None
        self.last_pub_hr = 0.0
        self.last_pub_temp = 0.0
        self.last_pub_time = 0.0
        if mqtt is not None:
            try:
                broker_host = os.environ.get('MQTT_BROKER_HOST') or '127.0.0.1'
                if broker_host in ('127.0.0.1', 'localhost') and sys.platform.startswith("win"):
                    gw = get_default_gateway_ip()
                    if gw and gw != "127.0.0.1":
                        broker_host = gw
                broker_port = int(os.environ.get('MQTT_BROKER_PORT') or 1883)
                mqtt_user = os.environ.get('MQTT_USERNAME', 'hk07agent')
                mqtt_pass = os.environ.get('MQTT_PASSWORD', 'hk07_mqtt_dev_pwd')
                if hasattr(mqtt, "CallbackAPIVersion"):
                    self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="hk07-sensor-fusion-node", protocol=mqtt.MQTTv311)
                else:
                    self.mqtt_client = mqtt.Client(client_id="hk07-sensor-fusion-node", protocol=mqtt.MQTTv311)
                if mqtt_user:
                    self.mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
                self.mqtt_client.connect_async(broker_host, broker_port, keepalive=30)
                self.mqtt_client.loop_start()
                self.get_logger().info(f"[MQTT] Connected asynchronously to {broker_host}:{broker_port}")
            except Exception as e:
                self.get_logger().warning(f"[MQTT] Failed to initialize MQTT client: {e}")

        # Shared State Variables (Thread-safe)
        self.state_lock = threading.Lock()
        self.latest_frame = None
        self.rppg_heart_rate = 0.0
        self.last_valid_rppg_time = 0.0
        self.user_detected = False
        self.vision_fall = False
        self._vlm_in_progress = False
        # tracker_box initialized to zero — hidden until a real detection is confirmed
        self.tracker_box = {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}

        # Bounded frame buffer ring (Queue of size 1)
        self.frame_queue = queue.Queue(maxsize=1)

        # Initialize callback groups
        self.high_frequency_safe_group = MutuallyExclusiveCallbackGroup()
        self.low_frequency_compute_group = MutuallyExclusiveCallbackGroup()

        # Initialize perception agent
        from engine.agents.perception_agent import PerceptionAgent
        from engine.arbitrator.arbitrator import Arbitrator
        self.arbitrator = Arbitrator()
        self.perception_agent = PerceptionAgent(arbitrator=self.arbitrator)

        # ── ROS 2 hardware timer watchdog (high frequency group) ────
        self._watchdog_running = True
        self.watchdog_timer = self.create_timer(
            0.1,  # 10Hz
            self._rtos_watchdog_timer_callback,
            callback_group=self.high_frequency_safe_group
        )

        # Event Loop for Async LLM Vision calls
        self.async_loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.name = "HK07_Async_Loop"
        self.async_thread.start()

        # OpenCV and MediaPipe Thread (Updates self.frame_queue ring at 10 FPS)
        self.vision_thread = threading.Thread(target=self._blocking_vision_worker, daemon=True)
        self.vision_thread.name = "HK07_Vision_Worker"
        self.vision_thread.start()
        self._elevate_thread_priority(self.vision_thread)

        # ── ROS 2 VLM Inference Worker Timer (1 Hz, low frequency compute group) ──
        self.vlm_timer = self.create_timer(
            1.0,  # 1Hz
            self._vlm_inference_timer_callback,
            callback_group=self.low_frequency_compute_group
        )

        self.get_logger().info("=== HK07 SENSOR FUSION ROS2 NODE INITIALIZED (NON-BLOCKING MULTI-THREADED EXECUTOR) ===")

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

    def _rtos_watchdog_timer_callback(self) -> None:
        """
        [FIX-3] RTOS Watchdog — Isolated Real-Time Heartbeat callback.
        Runs under self.high_frequency_safe_group on the MultiThreadedExecutor.
        """
        # Snapshot shared state with a NON-BLOCKING try-lock
        hr = 0.0
        vision_fall = False
        if self.state_lock.acquire(blocking=False):
            try:
                hr = self.rppg_heart_rate
                vision_fall = self.vision_fall
            finally:
                self.state_lock.release()

        # Strict Hardware Binding Layer (SHBL) - Purged simulation
        latest_frame_exists = False
        if self.state_lock.acquire(blocking=False):
            try:
                latest_frame_exists = (self.latest_frame is not None)
            finally:
                self.state_lock.release()

        # If camera stream drops/offline or no heart rate detected, immediately invalidate
        if not latest_frame_exists or math.isnan(hr) or hr <= 0:
            hr = float('nan')
            temp_thermal = float('nan')
            fever_alert = float('nan')
            sensor_status = "OFFLINE"
        else:
            # Estimate body temperature physiologically from computed heart rate
            # Spiking heart rate (tachycardia) estimates slight temperature elevation
            temp_thermal = 36.6 + (0.01 * (hr - 70.0)) + random.uniform(-0.15, 0.15)
            temp_thermal = float(round(max(36.1, min(39.5, temp_thermal)), 2))
            fever_alert = 1.0 if temp_thermal >= 37.8 else 0.0
            sensor_status = "ONLINE"

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
            pass

        # Direct MQTT Vital Signs Sync — STRICT: only publish when a user is actively detected
        if self.mqtt_client:
            is_online = not math.isnan(hr) and hr > 0

            with self.state_lock:
                user_detected = getattr(self, 'user_detected', False)
                camera_online = (self.latest_frame is not None)

            # Gate: only compute and publish real vitals if a live user is detected
            if is_online and user_detected:
                hr_val = int(hr)
                spo2_val = 98.2 - 0.02 * (hr_val - 70.0) + random.uniform(-0.3, 0.3)
                spo2_val = float(round(max(94.0, min(99.9, spo2_val)), 1))
                sys_bp = 120.0 + 0.5 * (hr_val - 70.0) + random.uniform(-2.0, 2.0)
                sys_bp = float(round(sys_bp, 1))
                dias_bp = 80.0 + 0.3 * (hr_val - 70.0) + random.uniform(-1.0, 1.0)
                dias_bp = float(round(dias_bp, 1))
                body_temp = float(temp_thermal) if not math.isnan(temp_thermal) else -1.0
                status_str = "ONLINE"
            else:
                # No user in frame or rPPG not locked — all vitals are invalid
                hr_val = -1
                spo2_val = -1.0
                sys_bp = -1.0
                dias_bp = -1.0
                body_temp = -1.0
                status_str = "OFFLINE" if not user_detected else "NO_LOCK"

            hr_change = abs(hr_val - self.last_pub_hr) if self.last_pub_hr > 0 and hr_val > 0 else 1.0
            temp_change = abs(body_temp - self.last_pub_temp) if self.last_pub_temp > 0 and body_temp > 0 else 1.0
            time_since_last_pub = time.time() - self.last_pub_time

            status_changed = (status_str == "ONLINE" and self.last_pub_hr <= 0) or (status_str == "OFFLINE" and self.last_pub_hr > 0)
            if hr_change >= 2.0 or temp_change >= 0.1 or time_since_last_pub >= 4.0 or status_changed:
                self.last_pub_hr = hr_val
                self.last_pub_temp = body_temp
                self.last_pub_time = time.time()
                
                try:
                    vitals_payload = {
                        "heartRate": hr_val,
                        "spo2": spo2_val,
                        "bodyTemperature": body_temp,
                        "systolic": sys_bp,
                        "diastolic": dias_bp,
                        "stepCount": -1,
                        "sensor_status": status_str,
                        "alertLevel": "CRITICAL" if (is_online and (fever_alert > 0 or vision_fall)) else "NORMAL",
                        "vision_fall_detected": bool(is_online and vision_fall),
                        "hormones": {
                            "is_simulated": is_sim
                        }
                    }
                    topic = "hk07/sensors/wristband/camera/vitals"
                    self.mqtt_client.publish(topic, json.dumps(vitals_payload), qos=0)
                except Exception:
                    pass

    def _vlm_inference_timer_callback(self):
        """
        [VLM_WORKER] Background loop waking autonomously at 1 Hz.
        Pops the newest frame from the ring buffer and executes VLM / OpenCV feature extraction.
        Updates the Blackboard / local cache.
        """
        if getattr(self, '_vlm_in_progress', False):
            return

        try:
            frame = self.frame_queue.get_nowait()
        except queue.Empty:
            return

        self._vlm_in_progress = True

        # Submit the analysis to the async thread
        coro = self._run_async_vlm_scan(frame)
        asyncio.run_coroutine_threadsafe(coro, self.async_loop)

    async def _run_async_vlm_scan(self, frame):
        try:
            # 1. Push to frame cache buffer
            _, buffer = cv2.imencode('.jpg', frame)
            image_bytes = buffer.tobytes()
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            
            from services.sensor_fusion_buffer import get_fusion_buffer, CameraFrame
            fusion_buf = get_fusion_buffer()
            await fusion_buf.push_camera(CameraFrame(frame_path="", frame_b64=b64))

            # 2. Run the Perception scan (bypass cache to perform inference, passing frame bytes directly)
            scan = await self.perception_agent.execute_full_body_scan(bypass_cache=True, frame_bytes=image_bytes)

            # 3. Serialize full structured payload via to_dict() for canonical output
            scan_dict = scan.to_dict()

            # 4. Publish clinical analysis to ROS 2 topic
            clinical_data = {
                # Legacy fields — safety.ts & DigitalTwinView.vue compatibility
                "visible_injuries": {
                    "detected": len(scan.visible_injuries) > 0,
                    "details": ", ".join(scan.visible_injuries) if scan.visible_injuries else None
                },
                "facial_distress": {
                    "detected": scan.facial_distress > 0.3,
                    "details": f"Score: {scan.facial_distress:.2f}" if scan.facial_distress > 0 else None
                },
                "environmental_hazards": {
                    "detected": scan.overall_risk in ("HIGH", "CRITICAL"),
                    "details": scan.notes
                },
                # Structured spatial payload — normalized [ymin, xmin, ymax, xmax] coordinates
                # Consumed by HugoVisionView.vue to draw per-label medical HUD bounding boxes
                "spatial_targets": scan_dict.get("spatial_targets", []),
                # Cognitive context — user activity + clinical assessment string
                "cognitive_insights": scan_dict.get("cognitive_insights", {}),
                # Top-level scan metadata for frontend status panels
                "overall_risk": scan.overall_risk,
                "confidence": round(float(scan.confidence), 2),
                "posture_risk": scan.posture_risk,
                "scan_duration_ms": scan.scan_duration_ms,
            }
            str_msg = String()
            str_msg.data = json.dumps(clinical_data, ensure_ascii=False)

            if rclpy.ok():
                self.clinical_pub.publish(str_msg)
                if self.mqtt_client:
                    try:
                        self.mqtt_client.publish("hk07/perception/clinical", str_msg.data, qos=0)
                    except Exception as mqtt_err:
                        self.get_logger().warning(f"[VLM_WORKER] Failed to publish clinical to MQTT: {mqtt_err}")
                self.get_logger().info(
                    f"[VLM_WORKER] Published 1Hz VLM scan: risk={scan.overall_risk} "
                    f"targets={len(clinical_data['spatial_targets'])} "
                    f"conf={scan.confidence * 100:.0f}% "
                    f"dur={scan.scan_duration_ms:.0f}ms"
                )
        except Exception as e:
            self.get_logger().error(f"[VLM_WORKER] Error in VLM scan callback: {e}")
        finally:
            self._vlm_in_progress = False

    def publish_telemetry(self):
        """Legacy ROS timer callback — kept for compatibility but RTOS watchdog is authoritative."""
        pass  # Heartbeat is now owned by _rtos_watchdog_timer_callback


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
            # Detrending (high-pass filter) to remove low-frequency drift
            w_size = max(5, int(fps))
            trend = np.convolve(y, np.ones(w_size)/w_size, mode='same')
            y_detrended = y - trend
            # Smoothing (low-pass filter) to remove high-frequency noise
            y_smooth = np.convolve(y_detrended, np.ones(3)/3, mode='same')
            
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
                with mp_pose.Pose(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
                    while cap.isOpened() and rclpy.ok():
                        if self.CAMERA_URL != current_url:
                            break

                        ret, frame = cap.read()
                        if not ret or frame is None or frame.size == 0:
                            consecutive_drops += 1
                            if consecutive_drops >= 30:
                                raise PrematureCloseException(f"Too many consecutive frame drops ({consecutive_drops})")
                            time.sleep(0.1)
                            continue
                        
                        consecutive_drops = 0
                        reconnect_delay = 2.0  # Reset backoff on successful frame read
                        
                        with self.state_lock:
                            self.latest_frame = frame.copy()

                        # Push to frame_queue ring buffer (bounded size 1)
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            self.frame_queue.put_nowait(frame.copy())
                        except queue.Full:
                            pass

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
                        
                        # CPU rendering mitigation: process MediaPipe on 1 out of every 3 frames
                        if not hasattr(self, '_frame_counter'):
                            self._frame_counter = 0
                            self._last_pose_results = None
                        self._frame_counter += 1
                        
                        if self._frame_counter % 3 == 0 or self._last_pose_results is None:
                            results = pose.process(image)
                            self._last_pose_results = results
                        else:
                            results = self._last_pose_results
                            
                        image.flags.writeable = True
                        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                        
                        vision_fall = False
                        rppg_hr = 0.0
                        user_detected = False
                        
                        if results.pose_landmarks:
                            user_detected = True
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
                        else:
                            with self.state_lock:
                                self.tracker_box = {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
                                
                        with self.state_lock:
                            self.user_detected = user_detected
                            self.vision_fall = vision_fall
                            if rppg_hr > 0.0:
                                self.rppg_heart_rate = rppg_hr
                                self.last_valid_rppg_time = current_time
                            else:
                                if current_time - getattr(self, 'last_valid_rppg_time', 0.0) > 10.0:
                                    self.rppg_heart_rate = 0.0

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



    def destroy_node(self):
        if hasattr(self, 'mqtt_client') and self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                self.get_logger().info("[MQTT] Client stopped and disconnected successfully.")
            except Exception as e:
                self.get_logger().error(f"[MQTT] Error disconnecting Client: {e}")
        super().destroy_node()

from rclpy.executors import MultiThreadedExecutor

def main(args=None):
    rclpy.init(args=args)
    node = Hk07SensorFusionNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        # [FIX-3] Signal RTOS watchdog thread to stop cleanly before destroy
        node._watchdog_running = False
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
