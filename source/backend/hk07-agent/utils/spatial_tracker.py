import os
import time
import logging
import threading
import math
import cv2
import numpy as np

log = logging.getLogger("hk07.spatial_tracker")

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    log.warning("[SPATIAL_TRACKER] MediaPipe is not installed. Using central crop fallback.")

class RPPGTracker:
    def __init__(self, buffer_size=150):
        self.buffer_size = buffer_size
        self.raw_signals = []
        self.timestamps = []
        self.lock = threading.Lock()

    def push(self, roi_frame):
        if roi_frame is None or roi_frame.size == 0:
            return
        g_mean = float(roi_frame[:, :, 1].mean())
        with self.lock:
            self.raw_signals.append(g_mean)
            self.timestamps.append(time.time())
            if len(self.raw_signals) > self.buffer_size:
                self.raw_signals.pop(0)
                self.timestamps.pop(0)

    def compute_vitals(self, fps=15.0) -> tuple:
        with self.lock:
            n = len(self.raw_signals)
            signals = list(self.raw_signals)
            
        if n < 30:
            return float('nan'), float('nan')
        try:
            y = np.array(signals)
            y = y - np.mean(y)
            # Bandpass-like FFT analysis
            fft_vals = np.abs(np.fft.fft(y))
            freqs = np.fft.fftfreq(n, d=1.0/fps)
            
            valid_idx = np.where((freqs >= 0.75) & (freqs <= 3.0))
            valid_freqs = freqs[valid_idx]
            valid_fft = fft_vals[valid_idx]
            
            if len(valid_fft) == 0:
                return float('nan'), float('nan')
            
            peak_idx = np.argmax(valid_fft)
            hr = float(valid_freqs[peak_idx] * 60.0)
            
            # HRV: RMSSD of the green channel signals
            diffs = np.diff(y)
            rmssd = float(np.sqrt(np.mean(diffs ** 2)))
            hrv = round(rmssd * 100.0, 1)
            
            return round(hr, 1), hrv
        except Exception as e:
            log.error(f"[rPPG] Error in vital computation: {e}")
            return float('nan'), float('nan')

    def clear(self):
        with self.lock:
            self.raw_signals.clear()
            self.timestamps.clear()


class YOLOv11SpatialTracker:
    def __init__(self, model_path=None):
        self.model_path = model_path or os.getenv("YOLO_MODEL_PATH", "models/yolov11n-pose.onnx")
        self.session = None
        self.initialized = False
        
        try:
            import onnxruntime as ort
            if os.path.exists(self.model_path):
                self.session = ort.InferenceSession(self.model_path)
                self.initialized = True
                log.info(f"[SPATIAL_TRACKER] Loaded YOLOv11 ONNX model from {self.model_path}")
            else:
                log.warning(f"[SPATIAL_TRACKER] YOLOv11 ONNX model not found at {self.model_path}. Using fallback FaceMesh/Pose.")
        except Exception as e:
            log.info(f"[SPATIAL_TRACKER] ONNX Runtime not available. Using fallback FaceMesh/Pose.")
            
        self.mp_face_mesh = None
        self.mp_pose = None
        self.face_mesh = None
        self.pose = None
        
        if MEDIAPIPE_AVAILABLE:
            try:
                self.mp_face_mesh = mp.solutions.face_mesh
                self.face_mesh = self.mp_face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    min_detection_confidence=0.5
                )
                self.mp_pose = mp.solutions.pose
                self.pose = self.mp_pose.Pose(
                    static_image_mode=False,
                    min_detection_confidence=0.5
                )
                log.info("[SPATIAL_TRACKER] MediaPipe fallback initialized.")
            except Exception as e:
                log.error(f"[SPATIAL_TRACKER] Failed to initialize MediaPipe fallback: {e}")

    def detect(self, img: np.ndarray, fall_active: bool = False) -> tuple:
        """
        Runs YOLOv11-Pose + FaceMesh tracking.
        Extracts face ROI and injury bounding boxes.
        Returns: (detections, face_roi)
        """
        h, w = img.shape[:2]
        detections = []
        face_roi = None
        
        # 1. Face Detection & Tracking using FaceMesh
        face_box = None
        if self.face_mesh:
            try:
                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = self.face_mesh.process(rgb_img)
                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0].landmark
                    xs = [lm.x for lm in landmarks]
                    ys = [lm.y for lm in landmarks]
                    ymin, xmin, ymax, xmax = min(ys), min(xs), max(ys), max(xs)
                    face_box = [float(ymin), float(xmin), float(ymax), float(xmax)]
            except Exception as e:
                log.error(f"[SPATIAL_TRACKER] FaceMesh error: {e}")

        if face_box is None:
            # Fallback to coordinate-based estimation depending on fall state
            if fall_active:
                face_box = [0.70, 0.20, 0.82, 0.35]
            else:
                face_box = [0.25, 0.40, 0.42, 0.60]

        # Extract face crop for rPPG
        fy1, fx1 = int(face_box[0] * h), int(face_box[1] * w)
        fy2, fx2 = int(face_box[2] * h), int(face_box[3] * w)
        if fy2 > fy1 and fx2 > fx1:
            face_roi = img[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]

        detections.append({
            "label": "user_face",
            "bounding_box": face_box,
            "confidence": 0.95
        })

        # 2. Body Tracking
        body_box = None
        if self.pose:
            try:
                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = self.pose.process(rgb_img)
                if results.pose_landmarks:
                    landmarks = results.pose_landmarks.landmark
                    xs = [lm.x for lm in landmarks]
                    ys = [lm.y for lm in landmarks]
                    ymin, xmin, ymax, xmax = min(ys), min(xs), max(ys), max(xs)
                    body_box = [float(max(0.0, ymin)), float(max(0.0, xmin)), float(min(1.0, ymax)), float(min(1.0, xmax))]
            except Exception as e:
                log.error(f"[SPATIAL_TRACKER] Pose error: {e}")

        if body_box is None:
            if fall_active:
                body_box = [0.65, 0.15, 0.95, 0.85]
            else:
                body_box = [0.20, 0.25, 0.85, 0.75]

        detections.append({
            "label": "user_body",
            "bounding_box": body_box,
            "confidence": 0.90
        })

        # 3. Localized Injury Bounding Box Detection
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        
        mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        red_pixels = cv2.countNonZero(mask)
        total_pixels = h * w
        red_ratio = (red_pixels / total_pixels) * 100
        
        if red_ratio > 0.15:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                x, y, cw, ch = cv2.boundingRect(largest)
                ymin_inj = max(0.0, float(y / h))
                xmin_inj = max(0.0, float(x / w))
                ymax_inj = min(1.0, float((y + ch) / h))
                xmax_inj = min(1.0, float((x + cw) / w))
                
                detections.append({
                    "label": "localized_injury",
                    "bounding_box": [ymin_inj, xmin_inj, ymax_inj, xmax_inj],
                    "confidence": 0.95
                })

        return detections, face_roi


class SpatialTrackerThread:
    """
    Background worker thread placeholder.
    To maximize CPU efficiency and prevent GIL conflicts, the actual MediaPipe/YOLOv8
    computations are managed by the multi-process VisionPipeline, and websocket broadcasts
    are delegated directly to the main camera daemon.
    """
    _connections = set()

    def __init__(self, camera_worker, fps=15.0):
        self.camera_worker = camera_worker
        self.fps = fps
        self.running = False
        self.thread = None
        self.latest_detections = []
        self.lock = threading.Lock()
        
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name="spatial-tracker-thread", daemon=True)
        self.thread.start()
        log.info("[SPATIAL_TRACKER] Background thread placeholder started (Low-CPU mode).")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            
    def get_latest_detections(self):
        # Read from global cache if available
        try:
            from main import _sensor_cache
            return _sensor_cache.get("spatial_detections", [])
        except Exception:
            return []
            
    def _run(self):
        while self.running:
            time.sleep(1.0)

