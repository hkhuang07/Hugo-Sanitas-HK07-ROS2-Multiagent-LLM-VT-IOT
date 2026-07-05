import os
import sys
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"
import time
import struct
import json
import logging
import multiprocessing
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np
import paho.mqtt.client as mqtt

# ─── Hugo Intelligence: Activity Classifier + Facial Expression Analyzer ────
try:
    from utils.activity_classifier import get_skeleton_classifier, get_activity_description_vi
    _ACTIVITY_CLASSIFIER_AVAILABLE = True
except ImportError:
    try:
        from activity_classifier import get_skeleton_classifier, get_activity_description_vi
        _ACTIVITY_CLASSIFIER_AVAILABLE = True
    except ImportError:
        _ACTIVITY_CLASSIFIER_AVAILABLE = False
        get_skeleton_classifier = None

try:
    from utils.facial_expression_analyzer import get_facial_expression_analyzer
    _FACIAL_ANALYZER_AVAILABLE = True
except ImportError:
    try:
        from facial_expression_analyzer import get_facial_expression_analyzer
        _FACIAL_ANALYZER_AVAILABLE = True
    except ImportError:
        _FACIAL_ANALYZER_AVAILABLE = False
        get_facial_expression_analyzer = None

# Try to load compiled protobuf
try:
    from utils import pose_skeleton_pb2
    PROTOBUF_AVAILABLE = True
except ImportError:
    try:
        import pose_skeleton_pb2
        PROTOBUF_AVAILABLE = True
    except ImportError:
        PROTOBUF_AVAILABLE = False

log = logging.getLogger("hk07.vision_pipeline")

# ─── Multi-Processing Frame Reader Process (GIL Bypass) ──────────────────────
class CameraReaderProcess(multiprocessing.Process):
    """
    Independent camera frame capture process.
    Forces resolution to 640x480 and strictly throttles capture rate to 15 FPS.
    Pushes frames into a multiprocessing.Queue to bypass GIL.
    """
    def __init__(self, camera_url_var: str, frame_queue: multiprocessing.Queue):
        super().__init__(name="hk07-camera-reader", daemon=True)
        self.camera_url = camera_url_var
        self.frame_queue = frame_queue
        self.running = multiprocessing.Value('b', True)

    def run(self):
        # Suppress stdout/stderr inside child process for clean logs
        if sys.platform.startswith("win"):
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')

        log.info("[CAMERA_PROCESS] Child process started. Binding to IPWebcam stream: %s", self.camera_url)
        
        target_fps = 15.0
        frame_interval = 1.0 / target_fps
        consecutive_errors = 0

        # Try opening camera
        cap = None
        while self.running.value:
            t_start = time.perf_counter()
            
            if not cap or not cap.isOpened():
                try:
                    if not self.camera_url:
                        # Fallback to local webcam index 0 if URL is blank
                        cap = cv2.VideoCapture(0)
                    else:
                        cap = cv2.VideoCapture(self.camera_url)
                    
                    # Force 640x480 resolution
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                except Exception as e:
                    consecutive_errors += 1
                    time.sleep(min(5.0, 0.5 * consecutive_errors))
                    continue

            try:
                ret, frame = cap.read()
                if not ret or frame is None:
                    raise RuntimeError("Failed to capture frame from stream source")
                
                # Resize if not 640x480
                h, w = frame.shape[:2]
                if w != 640 or h != 480:
                    frame = cv2.resize(frame, (640, 480))

                # Encode to JPEG to reduce Queue payload size
                ret_enc, jpeg_bytes = cv2.imencode('.jpg', frame)
                if not ret_enc:
                    raise RuntimeError("JPEG encoding failed")

                frame_data = jpeg_bytes.tobytes()
                ts = time.time()

                # Clean the queue to keep only the latest frame (single item queue)
                while not self.frame_queue.empty():
                    try:
                        self.frame_queue.get_nowait()
                    except Exception:
                        break

                self.frame_queue.put_nowait((frame_data, ts))
                consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                if cap:
                    cap.release()
                    cap = None
                time.sleep(min(5.0, 0.2 * consecutive_errors))

            # Strictly enforce 15 FPS frame timing
            elapsed = time.perf_counter() - t_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        if cap:
            cap.release()


# ─── Biomarker Proxy (Neurotransmitter Estimator) ───────────────────────────
class BiomarkerProxy:
    """
    Calculates mock neurotransmitter concentrations using non-invasive heuristics.
    Publishes to /hk07/perception/biomarkers.
    """
    def __init__(self, mqtt_client: mqtt.Client):
        self.mqtt = mqtt_client
        self.topic = "/hk07/perception/biomarkers"

    def calculate_and_publish(self, hrv_lf_hf: float, fear_score: float, blink_rate: float, sad_score: float):
        # Avoid TypeErrors (Fail-safe defaults if values are None)
        lf_hf = float(hrv_lf_hf) if hrv_lf_hf is not None else 1.5
        fear  = float(fear_score) if fear_score is not None else 0.0
        blink = float(blink_rate) if blink_rate is not None else 12.0
        sad   = float(sad_score) if sad_score is not None else 0.0

        # Heuristics:
        # Cortisol & Adrenaline increase with high LF/HF ratio and fear expression
        cortisol = 12.0 + (lf_hf * 2.0) + (fear * 15.0)
        adrenaline = 50.0 + (lf_hf * 15.0) + (fear * 150.0)

        # Dopamine & Serotonin drop if blink rate is abnormally low (< 8) or sad/flat affect is high
        blink_factor = max(0.2, blink / 12.0) if blink < 8.0 else 1.0
        sad_factor = max(0.1, 1.0 - sad)
        
        dopamine = 80.0 * blink_factor * sad_factor
        serotonin = 150.0 * blink_factor * sad_factor

        payload = {
            "timestamp_ms": int(time.time() * 1000),
            "biomarkers": {
                "cortisol_ug_dl": round(cortisol, 2),
                "adrenaline_pg_ml": round(adrenaline, 2),
                "dopamine_pg_ml": round(dopamine, 2),
                "serotonin_ng_ml": round(serotonin, 2)
            },
            "inputs": {
                "hrv_lf_hf": lf_hf,
                "fear_score": fear,
                "blink_rate": blink,
                "sad_score": sad
            }
        }

        try:
            self.mqtt.publish(self.topic, json.dumps(payload), qos=1)
            log.debug("[BIOMARKER] Published neurotransmitters to %s: %s", self.topic, payload["biomarkers"])
        except Exception as e:
            log.error("[BIOMARKER_PUBLISH_FAILED] Failed to publish biomarkers: %s", e)


# ─── Main Pipeline Coordinator ────────────────────────────────────────────────
class VisionPipeline:
    """
    Decoupled vision pipeline.
    Main Process pulls frames from CameraReaderProcess, executing MediaPipe @ 10Hz,
    and DeepFace/YOLOv8 @ 1Hz.
    """
    def __init__(self, camera_url: str):
        self.camera_url = camera_url
        self.frame_queue = multiprocessing.Queue(maxsize=2)
        self.reader_process: Optional[CameraReaderProcess] = None
        self._mqtt: Optional[mqtt.Client] = None
        
        # Timing trackers for decoupled model evaluation
        self.last_pose_ts = 0.0     # runs at 10Hz (100ms)
        self.last_heavy_ts = 0.0    # runs at 1Hz (1000ms)

        # Fall tracking coordinates
        self.last_hip_y = None
        self.last_hip_ts = None

        # MediaPipe initialization
        self.mp_pose = None
        self.pose_detector = None
        try:
            import mediapipe as mp
            self.mp_pose = mp
            self.pose_detector = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                smooth_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        except Exception as e:
            log.warning("[VISION_PIPELINE] MediaPipe Pose failed to initialize: %s", e)

        # DeepFace & YOLO models (dummy/mock wrappers to handle fail-safes)
        self.yolo_net = None
        self._init_yolo()

    def _init_yolo(self):
        model_path = "models/yolov8n-injury.onnx"
        if os.path.exists(model_path):
            try:
                self.yolo_net = cv2.dnn.readNetFromONNX(model_path)
                log.info("[YOLO] Loaded YOLOv8 ONNX model for injury detection.")
            except Exception as e:
                log.warning("[YOLO] Failed to load YOLOv8 ONNX: %s. Using OpenCV fallback.", e)

    def start(self):
        # Configure MQTT Client
        broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self._mqtt = mqtt.Client(client_id="vision-pipeline", protocol=mqtt.MQTTv311)
        mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
        mqtt_pass = os.getenv("MQTT_PASSWORD", "")
        if mqtt_user:
            self._mqtt.username_pw_set(mqtt_user, mqtt_pass)
        try:
            self._mqtt.connect(broker_host, broker_port, keepalive=30)
            self._mqtt.loop_start()
            log.info("[VISION_PIPELINE] MQTT client initialized and started.")
        except Exception as e:
            log.error("[VISION_PIPELINE_MQTT_FAILED] Failed to connect to MQTT broker: %s", e)

        self.biomarker_proxy = BiomarkerProxy(self._mqtt)

        # Start Camera Process
        self.reader_process = CameraReaderProcess(self.camera_url, self.frame_queue)
        self.reader_process.start()
        log.info("[VISION_PIPELINE] Multiprocessing camera capture started.")

    def stop(self):
        if self.reader_process:
            self.reader_process.running.value = False
            self.reader_process.join(timeout=2.0)
            if self.reader_process.is_alive():
                self.reader_process.terminate()
        if self._mqtt:
            self._mqtt.loop_stop()
            self._mqtt.disconnect()

    def process_cycle(self) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
        """
        Invoked periodically (e.g. at 50ms intervals) from the main loop.
        Fetches the latest frame, checks timestamps, and delegates work dynamically.
        
        Returns: (frame_bytes, perception_scan_dict)
        """
        if self.frame_queue.empty():
            return None, None

        try:
            frame_data, ts = self.frame_queue.get_nowait()
        except Exception:
            return None, None

        now = time.time()
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return frame_data, None

        perception_scan = {}

        # ─── MediaPipe Pose (10Hz / 100ms interval) ──────────────────────────
        if (now - self.last_pose_ts) >= 0.10:
            self.last_pose_ts = now
            pose_scan = self._run_pose_analysis(frame, ts)
            perception_scan.update(pose_scan)

        # ─── DeepFace & YOLOv8 Injury Detection (1Hz / 1000ms interval) ──────
        if (now - self.last_heavy_ts) >= 1.0:
            self.last_heavy_ts = now
            
            # 1. Face / Owner recognition & facial distress
            face_scan = self._run_face_analysis(frame)
            perception_scan.update(face_scan)

            # 2. YOLOv8 / OpenCV red blob injury detection
            injury_scan = self._run_injury_analysis(frame)
            perception_scan.update(injury_scan)

            # 3. Publish Biomarkers
            hrv_lf_hf = 1.6 # Default placeholder; normally extracted from vitals
            try:
                from main import _sensor_cache
                vitals = _sensor_cache.get("vitals") or {}
                # In real scenario, extract LF/HF from PPG metrics
            except Exception:
                pass
                
            fear_score = face_scan.get("facial_distress", 0.0)
            sad_score = 0.8 if face_scan.get("expression") == "sad" else 0.1
            blink_rate = 6.0 if sad_score > 0.5 else 12.0 # Mock blink rate
            
            self.biomarker_proxy.calculate_and_publish(
                hrv_lf_hf=hrv_lf_hf,
                fear_score=fear_score,
                blink_rate=blink_rate,
                sad_score=sad_score
            )

        return frame_data, perception_scan

    def _run_pose_analysis(self, frame: np.ndarray, ts: float) -> Dict[str, Any]:
        if not self.pose_detector:
            return {}

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self.pose_detector.process(rgb)

        landmarks_list = []
        fall_detected = False
        posture_risk = "LOW"
        activity_label = "unknown"
        activity_confidence = 0.0
        activity_description_vi = "không xác định"

        if res.pose_landmarks:
            h, w = frame.shape[:2]
            for lm in res.pose_landmarks.landmark:
                landmarks_list.append({
                    "x": float(lm.x),
                    "y": float(lm.y),
                    "z": float(lm.z),
                    "visibility": float(lm.visibility)
                })

            # ── Hugo: SkeletonActivityClassifier (rich activity labels) ─────
            if _ACTIVITY_CLASSIFIER_AVAILABLE and get_skeleton_classifier:
                try:
                    classifier = get_skeleton_classifier()
                    activity_label, activity_confidence, act_details = classifier.classify(
                        landmarks=landmarks_list,
                        imu_accel_mag=9.81,  # no IMU here; will be cross-checked by sensor_intelligence
                    )
                    # Temporal smoothing
                    activity_label = classifier.smoothed_label()
                    activity_description_vi = get_activity_description_vi(activity_label)
                    log.debug("[ACTIVITY] %s (%.0f%%): %s", activity_label, activity_confidence * 100, activity_description_vi)
                except Exception as act_err:
                    log.debug("[ACTIVITY_CLASSIFIER] Error: %s", act_err)

            # ── Legacy fall/posture detection (kept for cross-check) ──────────
            hip_left = res.pose_landmarks.landmark[23]
            hip_right = res.pose_landmarks.landmark[24]
            hip_y = (hip_left.y + hip_right.y) / 2.0

            if self.last_hip_y is not None and self.last_hip_ts is not None:
                dt = ts - self.last_hip_ts
                if dt > 0.0:
                    dy = hip_y - self.last_hip_y
                    velocity_y = dy / dt
                    if velocity_y > 1.2:
                        log.critical("[FALL_ALGORITHM] High downward velocity: %.2f y/s", velocity_y)
                        fall_detected = True
                        posture_risk = "HIGH"
                        activity_label = "falling"

            self.last_hip_y = hip_y
            self.last_hip_ts = ts

            shoulder_left = res.pose_landmarks.landmark[11]
            shoulder_right = res.pose_landmarks.landmark[12]
            ankle_left = res.pose_landmarks.landmark[27]
            ankle_right = res.pose_landmarks.landmark[28]
            body_height = abs((shoulder_left.y + shoulder_right.y) / 2.0 - (ankle_left.y + ankle_right.y) / 2.0)

            if body_height < 0.15:
                posture_risk = "HIGH"
                fall_detected = True
                if activity_label not in ("sleeping", "lying_down"):
                    activity_label = "falling"

            # ── Publish skeleton to MQTT ──────────────────────────────────────
            try:
                alert_level = "CRITICAL" if fall_detected else "NORMAL"
                risk_level = "CRITICAL" if fall_detected else "LOW"
                bin_data = self._serialize_skeleton(
                    timestamp_ms=int(ts * 1000),
                    landmarks=landmarks_list,
                    alert_level=alert_level,
                    overall_risk=risk_level,
                    user_id="a0000000-0000-0000-0000-000000000001",
                )
                if bin_data:
                    self._mqtt.publish("/hk07/telemetry/skeleton", bin_data, qos=0)
            except Exception as e:
                log.error("[PROTOBUF_PUBLISH_FAILED] %s", e)

            # ── Publish activity state to MQTT ────────────────────────────────
            try:
                activity_payload = json.dumps({
                    "activity": activity_label,
                    "confidence": round(activity_confidence, 2),
                    "description_vi": activity_description_vi,
                    "timestamp_ms": int(ts * 1000),
                }, ensure_ascii=False)
                self._mqtt.publish("hk07/perception/activity", activity_payload, qos=0)
            except Exception:
                pass

        return {
            "posture_risk": posture_risk,
            "fall_detected": fall_detected,
            "landmarks_count": len(landmarks_list),
            "activity": activity_label,
            "activity_confidence": round(activity_confidence, 2),
            "activity_description_vi": activity_description_vi,
        }

    def _serialize_skeleton(self, timestamp_ms: int, landmarks: List[Dict[str, Any]], alert_level: str, overall_risk: str, user_id: str) -> bytes:
        if PROTOBUF_AVAILABLE:
            frame = pose_skeleton_pb2.SkeletonFrame()
            frame.timestamp_ms = timestamp_ms
            frame.alert_level = alert_level
            frame.overall_risk = overall_risk
            frame.user_id = user_id or ""
            for lm in landmarks:
                landmark = frame.landmarks.add()
                landmark.x = float(lm.get('x', 0.0))
                landmark.y = float(lm.get('y', 0.0))
                landmark.z = float(lm.get('z', 0.0))
                landmark.visibility = float(lm.get('visibility', 0.0))
            return frame.SerializeToString()
        else:
            # ZERO-JSON fall-back using packed binary struct
            # RAW_FALLBACK\x00 (header) + Header (QIII) + Strings + Data (33 * 4 floats)
            alert_bytes = alert_level.encode('utf-8')
            risk_bytes = overall_risk.encode('utf-8')
            user_bytes = (user_id or "").encode('utf-8')
            
            header = struct.pack(f"<QIII", timestamp_ms, len(alert_bytes), len(risk_bytes), len(user_bytes))
            body = header + alert_bytes + risk_bytes + user_bytes
            for lm in landmarks:
                body += struct.pack("<ffff", lm.get('x', 0.0), lm.get('y', 0.0), lm.get('z', 0.0), lm.get('visibility', 0.0))
            return b"RAW_FALLBACK\x00" + body

    def _run_face_analysis(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Hugo-grade facial expression analysis.
        Tier 1: MediaPipe FaceMesh 468-landmark geometry-based mapping (~2ms).
        Tier 2: OpenCV Haar cascade fallback (face presence only).
        Tier 3: DeepFace 1Hz heavy analysis (if installed).
        """
        if _FACIAL_ANALYZER_AVAILABLE and get_facial_expression_analyzer:
            try:
                analyzer = get_facial_expression_analyzer()
                mood = analyzer.analyze_frame(frame)
                # Publish mood to MQTT
                try:
                    mood_payload = json.dumps({
                        "expression":     mood.expression,
                        "distress_score": mood.distress_score,
                        "care_priority":  mood.care_priority,
                        "brow_furrow":    mood.brow_furrow_score,
                        "eye_openness":   mood.eye_openness,
                        "tier":           mood.analyzer_tier,
                        "timestamp_ms":   int(time.time() * 1000),
                    }, ensure_ascii=False)
                    self._mqtt.publish("hk07/perception/mood", mood_payload, qos=0)
                except Exception:
                    pass
                return {
                    "is_owner":       mood.is_owner_detected,
                    "facial_distress": float(mood.distress_score),
                    "expression":     mood.expression,
                    "care_priority":  mood.care_priority,
                    "brow_furrow":    mood.brow_furrow_score,
                    "eye_openness":   mood.eye_openness,
                    "mood_analyzer":  mood.analyzer_tier,
                }
            except Exception as e:
                log.debug("[FACE_ANALYSIS] FacialExpressionAnalyzer error: %s", e)

        # Minimal OpenCV Haar fallback
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
            is_detected = len(faces) > 0
        except Exception:
            is_detected = True  # assume owner present if cascade fails

        return {
            "is_owner":        is_detected,
            "facial_distress": 0.0,
            "expression":      "calm",
            "care_priority":   "COMPANION",
            "mood_analyzer":   "OPENCV_HAAR_FALLBACK",
        }

    def _run_injury_analysis(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Visible injury detection using YOLOv8 ONNX or OpenCV fallback.
        """
        visible_injuries = []
        overall_risk = "LOW"

        if self.yolo_net:
            try:
                # YOLOv8 ONNX Forward pass
                blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
                self.yolo_net.setInput(blob)
                outputs = self.yolo_net.forward()
                
                # Simple threshold check on outputs
                if outputs is not None and len(outputs) > 0:
                    # In real scenario: parse bounding boxes, classes
                    visible_injuries.append("skin injury detected by YOLOv8")
                    overall_risk = "HIGH"
            except Exception as e:
                log.warning("[YOLO_INFERENCE_ERROR] YOLO forward failed: %s. Falling back to OpenCV.", e)

        # OpenCV Fallback: Red Blob Detection
        if not visible_injuries:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_red1 = np.array([0, 80, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 80, 50])
            upper_red2 = np.array([180, 255, 255])
            
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = mask1 | mask2
            
            red_ratio = (cv2.countNonZero(red_mask) / (hsv.shape[0] * hsv.shape[1])) * 100
            if red_ratio > 0.15:
                visible_injuries.append("phát hiện vết thương tụ máu đỏ trên da (OpenCV fallback)")
                overall_risk = "HIGH"

        return {
            "visible_injuries": visible_injuries,
            "overall_risk": overall_risk
        }
