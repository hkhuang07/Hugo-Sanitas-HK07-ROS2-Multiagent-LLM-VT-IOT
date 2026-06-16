import os
import sys

# Ensure package root is in sys.path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if package_root not in sys.path:
    sys.path.append(package_root)

from utils.network_helper import load_env_file, get_default_gateway_ip

import time
import math
import random
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

from sensor_msgs.msg import JointState

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("rppg_thermal")

class RppgThermalNode(Node):
    def __init__(self):
        super().__init__('rppg_thermal_node')
        
        # Initialize MediaPipe face detection
        self.face_detection = None
        if MEDIAPIPE_AVAILABLE:
            try:
                self.mp_face_detection = mp.solutions.face_detection
                self.face_detection = self.mp_face_detection.FaceDetection(
                    model_selection=0,
                    min_detection_confidence=0.5
                )
                log.info("[rPPG_THERMAL] MediaPipe Face Detection initialized successfully.")
            except Exception as e:
                log.error(f"[rPPG_THERMAL] Failed to initialize MediaPipe Face Detection: {e}")
        else:
            log.warning("[rPPG_THERMAL] MediaPipe is not installed. Face-detection-based ROI is disabled. Using default central ROI.")
        
        # Environment & Config Loading
        load_env_file()
        phone_ip = os.getenv("PHONE_IP")
        if not phone_ip:
            phone_ip = get_default_gateway_ip()
        
        use_ip_webcam = os.getenv("USE_IP_WEBCAM", "false").lower() == "true"

        # Publishers
        self.telemetry_pub = self.create_publisher(JointState, '/sensors/camera/thermal_rppg', 10)
        
        # Declare video source parameters without type constraint to accept both int (camera index) and string (RTSP URL)
        self.declare_parameter('video_source', value=None)
        param = self.get_parameter('video_source')
        
        if param.value is None:
            video_src_str = os.getenv('RTSP_CAMERA_URL', f"http://{phone_ip}:8080/video")
        else:
            video_src_str = str(param.value)
            
        # Completely bypass physical camera index 0 and redirect to network stream if requested
        if video_src_str == '0' and use_ip_webcam:
            video_src_str = f"http://{phone_ip}:8080/video"
            
        try:
            self.video_source = int(video_src_str)
        except ValueError:
            self.video_source = video_src_str
            
        self.cap = None
        self.is_using_real_camera = False
        self.try_open_camera()
        
        # Timer (10Hz)
        self.timer = self.create_timer(0.1, self.timer_callback)
        self.tick = 0
        
        # Simulated parameters
        self.target_hr = 72.0  # target heart rate to simulate
        self.target_temp = 36.6  # target temperature to simulate
        
        # Green channel buffer (for rPPG FFT computation)
        # 100 samples at 10Hz = 10 seconds sliding window
        self.g_buffer = []
        self.buffer_maxlen = 100
        
        log.info("=== HK07 OPENCV rPPG & THERMAL VISION NODE STARTED ===")

    def try_open_camera(self):
        try:
            import cv2
            log.info(f"[rPPG_THERMAL] Opening OpenCV video source: {self.video_source}")
            self.cap = cv2.VideoCapture(self.video_source)
            if self.cap.isOpened():
                # Set lower resolution to reduce processing overhead
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                log.info("[rPPG_THERMAL] Video capture source opened successfully.")
            else:
                log.warning("[rPPG_THERMAL] Video capture source could not be opened. Fallback to synthetic data active.")
        except Exception as e:
            log.error(f"[rPPG_THERMAL] Exception initializing VideoCapture: {e}")
            self.cap = None

    def compute_rppg_heart_rate(self) -> float:
        """
        Performs Fast Fourier Transform (FFT) on the green channel intensity buffer
        to extract the peak frequency (pulse rate).
        """
        n = len(self.g_buffer)
        if n < 30:
            # Insufficient samples, return moving average or target HR
            return self.target_hr + random.uniform(-0.5, 0.5)

        # 1. Detrend signal (subtract mean)
        mean_g = sum(self.g_buffer) / n
        detrended = [g - mean_g for g in self.g_buffer]

        # 2. Compute Discrete Fourier Transform (DFT) for frequency analysis
        # (Standard numpy-like FFT implementation in pure Python for zero-dependency)
        amplitudes = []
        frequencies = []
        
        # Sample rate is 10Hz (0.1s interval)
        fs = 10.0
        
        # Check frequencies in standard human heart rate range: 45 to 150 bpm
        # Frequency range: 0.75 Hz to 2.5 Hz
        for k in range(1, n // 2):
            freq = k * fs / n
            if 0.75 <= freq <= 2.5:
                # Calculate real and imaginary parts of DFT
                real = sum(detrended[t] * math.cos(2 * math.pi * k * t / n) for t in range(n))
                imag = sum(detrended[t] * math.sin(2 * math.pi * k * t / n) for t in range(n))
                amp = math.sqrt(real**2 + imag**2)
                amplitudes.append(amp)
                frequencies.append(freq)

        if not amplitudes:
            return self.target_hr + random.uniform(-0.5, 0.5)

        # Find peak amplitude frequency
        max_idx = amplitudes.index(max(amplitudes))
        peak_freq = frequencies[max_idx]
        
        # Convert Hz to bpm
        computed_hr = peak_freq * 60.0
        return round(computed_hr, 1)
    def timer_callback(self):
        try:
            # 1. Capture frame from OpenCV camera if active
            self.is_using_real_camera = False
            g_val = 0.0
            
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    h, w, _ = frame.shape
                    roi = None
                    
                    if self.face_detection:
                        try:
                            import cv2
                            # Convert frame to RGB for MediaPipe face detection
                            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            results = self.face_detection.process(rgb_frame)
                            if results.detections:
                                detection = results.detections[0]
                                bbox = detection.location_data.relative_bounding_box
                                
                                # Convert relative coordinates to pixel values
                                x = int(bbox.xmin * w)
                                y = int(bbox.ymin * h)
                                width = int(bbox.width * w)
                                height = int(bbox.height * h)
                                
                                # Forehead Region of Interest (ROI) selection
                                rx_min = max(0, x + int(width * 0.25))
                                rx_max = min(w, x + int(width * 0.75))
                                ry_min = max(0, y + int(height * 0.15))
                                ry_max = min(h, y + int(height * 0.45))
                                
                                if rx_max > rx_min and ry_max > ry_min:
                                    roi = frame[ry_min:ry_max, rx_min:rx_max]
                        except Exception as e:
                            log.error(f"[rPPG_THERMAL] Error processing face detection: {e}")
                    
                    if roi is None:
                        # Fallback to central 100x100 box
                        cx, cy = w // 2, h // 2
                        roi = frame[max(0, cy-50):min(h, cy+50), max(0, cx-50):min(w, cx+50)]
                        
                    g_val = float(roi[:, :, 1].mean())  # Channel 1 is Green in BGR format
                    self.is_using_real_camera = True
                    
            if not self.is_using_real_camera:
                # Fallback to simulated green channel intensity G(t) with sine pulse + noise
                pulse_freq = self.target_hr / 60.0
                noise = random.uniform(-0.02, 0.02)
                g_val = 128.0 + 1.2 * math.sin(2 * math.pi * pulse_freq * (self.tick * 0.1)) + noise
            
            self.g_buffer.append(g_val)
            if len(self.g_buffer) > self.buffer_maxlen:
                self.g_buffer.pop(0)

                
            # 2. Compute heart rate using rPPG frequency extraction
            hr_rppg = self.compute_rppg_heart_rate()
            
            # 3. Simulate thermal reading with slight physiological fluctuation
            temp_thermal = self.target_temp + 0.15 * math.sin(self.tick * 0.05) + random.uniform(-0.05, 0.05)
            
            # Fever threshold check (> 38.0 C)
            fever_alert = 1.0 if temp_thermal >= 38.0 else 0.0
            
            # 4. Compile and publish ROS2 JointState message
            stamp = self.get_clock().now().to_msg()
            
            msg = JointState()
            msg.header.stamp = stamp
            msg.header.frame_id = "camera_optical_frame"
            msg.name = ["rppg_heart_rate", "thermal_temperature", "fever_alert"]
            msg.position = [float(hr_rppg), float(temp_thermal), float(fever_alert)]
            
            self.telemetry_pub.publish(msg)
            
            # Periodically shift simulated state to test transitions
            if self.tick % 300 == 0:
                # Randomly trigger high temperature / high HR alert scenarios
                scenario = random.choice(["NORMAL", "FEVER", "TACHYCARDIA"])
                if scenario == "NORMAL":
                    self.target_hr = 72.0
                    self.target_temp = 36.6
                elif scenario == "FEVER":
                    self.target_hr = 95.0
                    self.target_temp = 38.8
                elif scenario == "TACHYCARDIA":
                    self.target_hr = 135.0
                    self.target_temp = 36.8
                log.info(f"[rPPG_THERMAL] Transitioned simulated scenario to {scenario}")
                
            if self.tick % 50 == 0:
                log.info(
                    f"[rPPG_THERMAL] Published: rPPG_HR={hr_rppg} bpm | "
                    f"Thermal_Temp={temp_thermal:.2f} C | "
                    f"Fever_Alert={bool(fever_alert)}"
                )
                
            self.tick += 1
            
        except Exception as e:
            log.error(f"Error in rPPG/Thermal simulation loop: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = RppgThermalNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if getattr(node, 'cap', None) and node.cap is not None:
            node.cap.release()
            log.info("[rPPG_THERMAL] OpenCV video capture resource released.")
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
