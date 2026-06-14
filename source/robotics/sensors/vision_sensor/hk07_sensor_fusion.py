import os
import sys
import cv2
import json
import time
import math
import random
import base64
import threading
import asyncio
import numpy as np

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

class Hk07SensorFusionNode(Node):
    def __init__(self):
        super().__init__('hk07_sensor_fusion_node')

        # Environment & Config Loading
        self.load_env_file()
        self.phone_ip = os.getenv("PHONE_IP", "192.168.133.228")
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

        # Event Loop for Async LLM Vision calls
        self.async_loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()

        # OpenCV and MediaPipe Thread
        self.vision_thread = threading.Thread(target=self._blocking_vision_worker, daemon=True)
        self.vision_thread.start()

        # Snapshot Analyzer Thread
        self.snapshot_thread = threading.Thread(target=self._snapshot_analyzer_worker, daemon=True)
        self.snapshot_thread.start()

        # Timer to publish JointState at 10Hz
        self.timer = self.create_timer(0.1, self.publish_telemetry)

        self.get_logger().info("=== HK07 SENSOR FUSION ROS2 NODE INITIALIZED ===")

    def load_env_file(self):
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        for _ in range(10):
            checks = [
                os.path.join(curr_dir, "backend", ".env"),
                os.path.join(curr_dir, "source", "backend", ".env"),
                os.path.join(curr_dir, ".env"),
            ]
            for path in checks:
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line or line.startswith("#"):
                                    continue
                                if "=" in line:
                                    key, val = line.split("=", 1)
                                    key = key.strip()
                                    val = val.strip().strip('"').strip("'")
                                    if key and key not in os.environ:
                                        os.environ[key] = val
                        return
                    except Exception:
                        pass
            parent = os.path.dirname(curr_dir)
            if parent == curr_dir:
                break
            curr_dir = parent

    def _run_async_loop(self):
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_forever()

    def publish_telemetry(self):
        with self.state_lock:
            hr = self.rppg_heart_rate
            vision_fall = self.vision_fall

        # Simulate physiological temperature fluctuations
        temp_thermal = round(36.5 + (random.random() - 0.5) * 0.2, 1)
        fever_alert = 1.0 if temp_thermal >= 38.0 else 0.0

        # Construct ROS2 JointState message
        js_msg = JointState()
        js_msg.header.stamp = self.get_clock().now().to_msg()
        js_msg.header.frame_id = "camera_optical_frame"
        js_msg.name = ["rppg_heart_rate", "thermal_temperature", "fever_alert"]
        js_msg.position = [float(hr), float(temp_thermal), float(fever_alert)]

        try:
            if rclpy.ok():
                self.thermal_rppg_pub.publish(js_msg)
        except Exception:
            pass

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
        
        reconnect_delay = 1.0
        max_reconnect_delay = 16.0
        
        while rclpy.ok():
            current_url = self.CAMERA_URL
            self.get_logger().info(f"Connecting to IP webcam: {current_url}")
            cap = cv2.VideoCapture(current_url)
            
            if not cap.isOpened():
                self.get_logger().warning(f"IP Webcam is offline. Retrying in {reconnect_delay:.1f}s...")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2.0, max_reconnect_delay)
                continue
                
            reconnect_delay = 1.0
            consecutive_drops = 0
            
            with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
                while cap.isOpened() and rclpy.ok():
                    if self.CAMERA_URL != current_url:
                        break

                    ret, frame = cap.read()
                    if not ret or frame is None or frame.size == 0:
                        consecutive_drops += 1
                        if consecutive_drops < 5:
                            time.sleep(0.1)
                            continue
                        else:
                            self.get_logger().warning(
                                f"Vision worker: too many consecutive frame drops ({consecutive_drops}). "
                                f"Disconnecting and applying back-off reconnect delay: {reconnect_delay:.1f}s..."
                            )
                            time.sleep(reconnect_delay)
                            reconnect_delay = min(reconnect_delay * 2.0, max_reconnect_delay)
                            break
                    
                    consecutive_drops = 0
                    
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
            cap.release()
            cv2.destroyAllWindows()
            time.sleep(2.0)

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
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
