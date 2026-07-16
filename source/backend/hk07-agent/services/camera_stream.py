import threading
import time
import logging
import os
import cv2
from core.shared import _device_config

log = logging.getLogger("hk07.camera")

class CameraStreamWorker:
    """
    Background worker thread using OpenCV/HTTP to continuously stream and capture
    frames from the IPWebcam at 5-10 FPS. Decouples frame ingestion from FastAPI event loop.
    """
    def __init__(self, get_url_func, poll_fps=10.0):
        self.get_url_func = get_url_func
        self.poll_fps = poll_fps
        self.running = False
        self.thread = None
        self.latest_frame_bytes = None
        self.latest_frame_ts = None
        self.status = "INIT"
        self.lock = threading.Lock()
        self.consecutive_failures = 0

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name="camera-stream-worker", daemon=True)
        self.thread.start()
        log.info("[CAMERA_WORKER] Background Camera Stream worker thread started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _run(self):
        import cv2
        import httpx
        import time
        
        self.status = "RUNNING"
        while self.running:
            t_start = time.perf_counter()
            camera_url = self.get_url_func()
            if not camera_url:
                with self.lock:
                    self.status = "CAMERA_UNRESOLVED"
                time.sleep(1.0)
                continue

            cap = None
            try:
                # If camera_url indicates a video stream, use cv2.VideoCapture
                if "/video" in camera_url or camera_url.startswith("rtsp://"):
                    cap = cv2.VideoCapture(camera_url)
                    if not cap.isOpened():
                        raise ValueError("VideoCapture failed to open URL")
                    
                    while self.running:
                        t_cycle = time.perf_counter()
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            raise ValueError("Empty or failed frame read")
                        
                        ret, jpeg = cv2.imencode('.jpg', frame)
                        if not ret:
                            raise ValueError("JPEG encoding failed")
                        
                        frame_bytes = jpeg.tobytes()
                        ts = time.time()
                        
                        with self.lock:
                            self.latest_frame_bytes = frame_bytes
                            self.latest_frame_ts = ts
                            self.status = "OK"
                            self.consecutive_failures = 0
                            
                        elapsed = time.perf_counter() - t_cycle
                        sleep_time = max(0.01, (1.0 / self.poll_fps) - elapsed)
                        time.sleep(sleep_time)
                else:
                    # Snapshot mode: poll URL via HTTP
                    with httpx.Client(timeout=2.0) as client:
                        while self.running:
                            t_cycle = time.perf_counter()
                            resp = client.get(camera_url)
                            if resp.status_code == 200 and resp.content:
                                frame_bytes = resp.content
                                ts = time.time()
                                with self.lock:
                                    self.latest_frame_bytes = frame_bytes
                                    self.latest_frame_ts = ts
                                    self.status = "OK"
                                    self.consecutive_failures = 0
                            else:
                                raise ValueError(f"HTTP status {resp.status_code}")
                            
                            elapsed = time.perf_counter() - t_cycle
                            sleep_time = max(0.01, (1.0 / self.poll_fps) - elapsed)
                            time.sleep(sleep_time)
            except Exception as e:
                with self.lock:
                    self.consecutive_failures += 1
                    self.status = f"CAMERA_ERROR ({self.consecutive_failures})"
                log.debug("[CAMERA_WORKER] Fetch failed: %s", e)
                if cap:
                    cap.release()
                # Exponential backoff on errors
                time.sleep(min(5.0, 0.5 * self.consecutive_failures))

    def get_latest_frame(self):
        with self.lock:
            return self.latest_frame_bytes, self.latest_frame_ts, self.status

def get_camera_url() -> str:
    phone_ip    = _device_config.get("phone_ip") or os.getenv("PHONE_IP", "")
    camera_port = _device_config.get("camera_port") or os.getenv("CAMERA_PORT", "8080")
    if phone_ip:
        return f"http://{phone_ip}:{camera_port}/shot.jpg"
    return ""

