import unittest
import os
import sys
import numpy as np
import cv2

# Ensure package paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.spatial_tracker import YOLOv8SpatialTracker, SpatialTrackerThread
from services.llm_client import LocalOfflineFallback
from agents.perception_agent import PerceptionScan

class TestSpatialCognitiveHUD(unittest.TestCase):
    def setUp(self):
        # Create a dummy image
        self.img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Create a red region to simulate hematoma
        self.img[100:150, 150:200] = [0, 0, 255]
        _, self.img_bytes = cv2.imencode('.jpg', self.img)
        self.img_bytes = self.img_bytes.tobytes()

    def test_yolo_tracker_detect(self):
        tracker = YOLOv8SpatialTracker()
        # Normal state
        detections = tracker.detect(self.img, fall_active=False, fever_active=False, hr=72.0)
        self.assertTrue(len(detections) >= 2)
        labels = [d["label"] for d in detections]
        self.assertIn("user_body", labels)
        self.assertIn("user_face", labels)
        
        # Check coordinates type and format
        for d in detections:
            self.assertEqual(len(d["bounding_box"]), 4)
            self.assertTrue(isinstance(d["bounding_box"][0], float))

    def test_local_vlm_reasoning(self):
        rois = [
            {"label": "user_face", "bytes": self.img_bytes},
            {"label": "hematoma", "bytes": self.img_bytes}
        ]
        vitals = {"hr": 132, "temp": 38.9}
        res = LocalOfflineFallback.get_local_vlm_reasoning(self.img_bytes, rois, vitals)
        
        self.assertEqual(res["user_activity"], "sitting_or_standing")
        self.assertIn("Sếp exhibits", res["clinical_reasoning"])
        self.assertIn("high fever", res["clinical_reasoning"])
        self.assertIn("acute tachycardia", res["clinical_reasoning"])
        self.assertIn("contusion/hematoma", res["clinical_reasoning"])

    def test_perception_scan_serialization(self):
        scan = PerceptionScan(
            heart_rate=132.0,
            body_temperature=38.9,
            posture_risk="LOW",
            facial_distress=0.6,
            visible_injuries=["hematoma"],
            notes="High fever with tachycardia.",
        )
        
        d = scan.to_dict()
        self.assertEqual(d["status"], "SUCCESS")
        self.assertEqual(d["vitals_summary"]["hr"], 132.0)
        self.assertEqual(d["vitals_summary"]["temp"], 38.9)
        
        # Spatial detections must contain labels
        labels = [s["label"] for s in d["spatial_detections"]]
        self.assertIn("user_face", labels)
        self.assertIn("hematoma", labels)
        
        # Cognitive analysis fields
        self.assertEqual(d["cognitive_analysis"]["user_activity"], "sitting_or_standing")
        self.assertEqual(d["cognitive_analysis"]["clinical_reasoning"], "High fever with tachycardia.")

if __name__ == "__main__":
    unittest.main()
