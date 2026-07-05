"""
FacialExpressionAnalyzer — Hugo-grade Facial Mood Analysis
HK-07 Agent Engine | Production Module

Architecture:
  Tier 1: MediaPipe FaceMesh (468 landmarks) — geometry-based expression mapping.
           Zero API calls. ~2ms latency. Runs at 10Hz.
  Tier 2: OpenCV HOG face detector fallback — detects face presence only.
  Tier 3: DeepFace library (optional, 1Hz) — fine-grained emotion if installed.

Expression categories (mapped to Hugo care decisions):
  - calm:     Neutral / content → companion chat
  - happy:    Smiling → positive engagement
  - sad:      Drooping mouth corners, soft gaze → empathetic support
  - stressed: Furrowed brow, tense jaw → stress relief conversation
  - fearful:  Wide eyes, raised brows → calming reassurance
  - angry:    Compressed brows, tense jaw → de-escalation
  - pain:     Grimace, brow crease, eye squeeze → medical check
  - tired:    Drooping eyelids (ptosis), slow blinks → rest reminder
  - unknown:  No face detected or insufficient landmarks

Output MoodSnapshot:
  - expression: str (one of above)
  - distress_score: float [0.0–1.0]
  - care_priority: str (COMPANION | EMOTIONAL_SUPPORT | MEDICAL_ATTENTION | ALERT)
  - brow_furrow_score: float
  - mouth_droop_score: float
  - eye_openness: float [0=closed, 1=wide open]
  - is_owner_detected: bool

DISCLAIMER: This is a behavioral observation tool.
  Outputs MUST NOT be used for clinical diagnosis.
  Emotion detection has known demographic and lighting biases.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

log = logging.getLogger("hk07.facial_expression_analyzer")


# ─── MediaPipe FaceMesh Landmark indices (subset) ────────────────────────────
# Derived from: https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
_FM = {
    # Mouth corners
    "mouth_left":  61,
    "mouth_right": 291,
    "mouth_top":   13,
    "mouth_bottom": 14,
    "upper_lip_center": 12,
    "lower_lip_center": 15,

    # Brow
    "left_brow_inner":  55,
    "right_brow_inner": 285,
    "left_brow_outer":  46,
    "right_brow_outer": 276,
    "left_brow_center": 52,
    "right_brow_center": 282,

    # Eyes
    "left_eye_upper":  159,  # upper lid center
    "left_eye_lower":  145,  # lower lid center
    "left_eye_inner":  33,
    "left_eye_outer":  133,
    "right_eye_upper": 386,
    "right_eye_lower": 374,
    "right_eye_inner": 362,
    "right_eye_outer": 263,

    # Nose
    "nose_tip": 1,
    "nose_bridge": 6,

    # Jaw / chin
    "chin": 199,
    "jaw_left": 172,
    "jaw_right": 397,
}


@dataclass
class MoodSnapshot:
    """
    Structured facial expression analysis output.
    Written to Blackboard and consumed by EmpatheticAgent + CareDecisionRouter.
    """
    expression:       str   = "unknown"
    distress_score:   float = 0.0       # 0.0=calm → 1.0=extreme distress
    care_priority:    str   = "COMPANION"  # COMPANION | EMOTIONAL_SUPPORT | MEDICAL_ATTENTION | ALERT
    brow_furrow_score: float = 0.0      # 0.0=relaxed → 1.0=deeply furrowed
    mouth_droop_score: float = 0.0      # 0.0=neutral → 1.0=strongly drooping
    eye_openness:      float = 0.8      # 0.0=closed → 1.0=wide open
    is_owner_detected: bool  = False
    confidence:        float = 0.0
    analyzer_tier:     str   = "OFFLINE"
    timestamp:         float = field(default_factory=time.time)

    disclaimer: str = (
        "⚠️ FacialExpressionAnalyzer: This is a heuristic behavioral observation "
        "from camera landmarks only. It is NOT a medical diagnosis, NOT a clinical "
        "assessment, and MUST NOT replace professional mental health evaluation."
    )

    def to_empathy_context(self) -> str:
        return (
            f"[FACIAL_CONTEXT] expression={self.expression} | "
            f"distress={self.distress_score:.2f} | "
            f"brow_furrow={self.brow_furrow_score:.2f} | "
            f"eye_openness={self.eye_openness:.2f} | "
            f"care_priority={self.care_priority} | "
            f"[NOTE: heuristic proxy — not clinical assessment]"
        )


def _fm_lm(landmarks: List[Any], key: str) -> Optional[Dict]:
    """Get FaceMesh landmark by key name."""
    idx = _FM.get(key)
    if idx is None or idx >= len(landmarks):
        return None
    lm = landmarks[idx]
    # FaceMesh landmarks: each has x, y, z (normalized to image size)
    if hasattr(lm, "x"):
        return {"x": lm.x, "y": lm.y, "z": getattr(lm, "z", 0.0)}
    elif isinstance(lm, dict):
        return lm
    return None


def _lm_dist(a: Optional[Dict], b: Optional[Dict]) -> Optional[float]:
    if not a or not b:
        return None
    return math.sqrt((a["x"] - b["x"])**2 + (a["y"] - b["y"])**2)


class FacialExpressionAnalyzer:
    """
    Stateful facial expression analyzer.
    Maintains temporal smoothing across frames.
    
    Usage:
        analyzer = FacialExpressionAnalyzer()
        
        # With MediaPipe FaceMesh results
        mood = analyzer.analyze_facemesh(facemesh_results, frame)
        
        # With raw frame only (fallback path)
        mood = analyzer.analyze_frame(frame_bytes)
    """

    HISTORY_LEN = 5

    def __init__(self):
        self._history: List[str] = []
        self._mp_face_mesh = None
        self._mp_face_detection = None
        self._face_detection = None
        self._face_mesh = None
        self._deepface_available = False
        self._last_heavy_ts: float = 0.0

        self._init_mediapipe()
        self._check_deepface()

    def _init_mediapipe(self) -> None:
        try:
            import mediapipe as mp
            self._mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._mp_face_detection = mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.5,
            )
            log.info("[FACIAL_ANALYZER] MediaPipe FaceMesh initialized (468-landmark mode).")
        except Exception as e:
            log.warning("[FACIAL_ANALYZER] MediaPipe FaceMesh unavailable: %s", e)

    def _check_deepface(self) -> None:
        try:
            import deepface  # noqa
            self._deepface_available = True
            log.info("[FACIAL_ANALYZER] DeepFace available (1Hz heavy analysis enabled).")
        except ImportError:
            self._deepface_available = False

    def analyze_frame(self, frame_bgr: np.ndarray) -> MoodSnapshot:
        """
        Main entry point. Accepts BGR frame from OpenCV.
        Returns MoodSnapshot.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return MoodSnapshot()

        # ── Tier 1: MediaPipe FaceMesh ────────────────────────────────────────
        if self._mp_face_mesh:
            try:
                import cv2
                rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                results = self._mp_face_mesh.process(rgb)
                if results.multi_face_landmarks:
                    return self._analyze_facemesh_landmarks(
                        results.multi_face_landmarks[0].landmark
                    )
            except Exception as e:
                log.debug("[FACIAL_ANALYZER] FaceMesh processing error: %s", e)

        # ── Tier 2: DeepFace (1Hz, heavy) ─────────────────────────────────────
        now = time.time()
        if self._deepface_available and (now - self._last_heavy_ts) >= 1.0:
            self._last_heavy_ts = now
            result = self._analyze_deepface(frame_bgr)
            if result:
                return result

        # ── Tier 3: OpenCV fallback (face presence only) ─────────────────────
        is_detected = self._detect_face_opencv(frame_bgr)
        return MoodSnapshot(
            expression="calm" if is_detected else "unknown",
            distress_score=0.0,
            care_priority="COMPANION",
            is_owner_detected=is_detected,
            confidence=0.3 if is_detected else 0.0,
            analyzer_tier="OPENCV_FALLBACK",
        )

    def _analyze_facemesh_landmarks(self, landmarks) -> MoodSnapshot:
        """
        Geometry-based expression mapping from 468 FaceMesh landmarks.
        Pure math — no API calls.
        """
        lms = landmarks  # list of 468 NormalizedLandmark objects

        # ── Eye Aspect Ratio (EAR) — detects closed eyes / tiredness ─────────
        left_upper  = _fm_lm(lms, "left_eye_upper")
        left_lower  = _fm_lm(lms, "left_eye_lower")
        left_inner  = _fm_lm(lms, "left_eye_inner")
        left_outer  = _fm_lm(lms, "left_eye_outer")
        right_upper = _fm_lm(lms, "right_eye_upper")
        right_lower = _fm_lm(lms, "right_eye_lower")
        right_inner = _fm_lm(lms, "right_eye_inner")
        right_outer = _fm_lm(lms, "right_eye_outer")

        ear_left  = self._eye_aspect_ratio(left_upper, left_lower, left_inner, left_outer)
        ear_right = self._eye_aspect_ratio(right_upper, right_lower, right_inner, right_outer)
        eye_openness = (ear_left + ear_right) / 2.0 if (ear_left and ear_right) else 0.8

        # ── Brow furrow — inner brows moving toward nose bridge ───────────────
        left_brow_inner  = _fm_lm(lms, "left_brow_inner")
        right_brow_inner = _fm_lm(lms, "right_brow_inner")
        nose_bridge      = _fm_lm(lms, "nose_bridge")
        brow_furrow_score = self._brow_furrow(left_brow_inner, right_brow_inner, nose_bridge)

        # ── Mouth droop — mouth corners below center ──────────────────────────
        mouth_left  = _fm_lm(lms, "mouth_left")
        mouth_right = _fm_lm(lms, "mouth_right")
        mouth_top   = _fm_lm(lms, "mouth_top")
        mouth_droop_score = self._mouth_droop(mouth_left, mouth_right, mouth_top)

        # ── Mouth open (speaking, pain) ───────────────────────────────────────
        mouth_bottom = _fm_lm(lms, "mouth_bottom")
        mouth_open_ratio = 0.0
        if mouth_top and mouth_bottom:
            vert = abs(mouth_bottom["y"] - mouth_top["y"])
            horiz = _lm_dist(mouth_left, mouth_right) or 0.1
            mouth_open_ratio = vert / horiz

        # ── Map to expression ─────────────────────────────────────────────────
        expression, distress_score, care_priority = self._classify_expression(
            eye_openness=eye_openness,
            brow_furrow=brow_furrow_score,
            mouth_droop=mouth_droop_score,
            mouth_open=mouth_open_ratio,
        )

        # Smooth expression label
        self._history.append(expression)
        if len(self._history) > self.HISTORY_LEN:
            self._history.pop(0)

        return MoodSnapshot(
            expression=expression,
            distress_score=round(distress_score, 3),
            care_priority=care_priority,
            brow_furrow_score=round(brow_furrow_score, 3),
            mouth_droop_score=round(mouth_droop_score, 3),
            eye_openness=round(eye_openness, 3),
            is_owner_detected=True,
            confidence=0.82,
            analyzer_tier="MEDIAPIPE_FACEMESH",
        )

    def _eye_aspect_ratio(
        self,
        upper: Optional[Dict], lower: Optional[Dict],
        inner: Optional[Dict], outer: Optional[Dict],
    ) -> Optional[float]:
        """
        EAR = vertical_distance / horizontal_distance.
        EAR ~0.3 = closed, ~0.8 = wide open.
        """
        v = _lm_dist(upper, lower)
        h = _lm_dist(inner, outer)
        if v is None or h is None or h < 1e-6:
            return None
        # Normalize: typical EAR range 0.15–0.40 → remap to 0.0–1.0
        raw = v / h
        return min(1.0, max(0.0, (raw - 0.10) / 0.30))

    def _brow_furrow(
        self,
        lb: Optional[Dict], rb: Optional[Dict], nose: Optional[Dict]
    ) -> float:
        """
        Brow furrow = how close inner brows are to nose bridge.
        Returns 0.0 (relaxed) → 1.0 (deep furrow).
        """
        if not lb or not rb or not nose:
            return 0.0
        dist_l = _lm_dist(lb, nose) or 1.0
        dist_r = _lm_dist(rb, nose) or 1.0
        avg_dist = (dist_l + dist_r) / 2.0
        # Typical relaxed distance ~0.06–0.10 in normalized coords
        # Furrowed: ~0.02–0.04
        furrow = max(0.0, 1.0 - (avg_dist / 0.08))
        return min(1.0, furrow)

    def _mouth_droop(
        self,
        left: Optional[Dict], right: Optional[Dict], top: Optional[Dict]
    ) -> float:
        """
        Mouth droop = corners below top-center.
        Positive = drooping (sad). Negative = raised (happy).
        Returns 0.0–1.0 (droop score, normalized).
        """
        if not left or not right or not top:
            return 0.0
        corner_y = (left["y"] + right["y"]) / 2.0
        droop = corner_y - top["y"]
        # Typical droop range 0.0–0.06 in normalized coords
        return min(1.0, max(0.0, droop / 0.05))

    def _classify_expression(
        self,
        eye_openness: float,
        brow_furrow: float,
        mouth_droop: float,
        mouth_open: float,
    ) -> Tuple[str, float, str]:
        """
        Maps geometric features → (expression, distress_score, care_priority).
        """
        distress = 0.0
        expression = "calm"
        care_priority = "COMPANION"

        # ── Tired / Drowsy: low eye openness ─────────────────────────────────
        if eye_openness < 0.35:
            expression = "tired"
            distress = 0.3
            care_priority = "EMOTIONAL_SUPPORT"
            return (expression, distress, care_priority)

        # ── Pain / Grimace: brow furrow + partial eye close + mouth open ──────
        if brow_furrow > 0.55 and eye_openness < 0.55 and mouth_open > 0.15:
            expression = "pain"
            distress = 0.75 + (brow_furrow * 0.25)
            care_priority = "MEDICAL_ATTENTION"
            return (expression, min(1.0, distress), care_priority)

        # ── Fearful: wide eyes + raised brows (low furrow) + open mouth ───────
        if eye_openness > 0.85 and brow_furrow < 0.2 and mouth_open > 0.1:
            expression = "fearful"
            distress = 0.70
            care_priority = "EMOTIONAL_SUPPORT"
            return (expression, distress, care_priority)

        # ── Stressed / Anxious: brow furrow + neutral eyes ────────────────────
        if brow_furrow > 0.45 and eye_openness >= 0.45:
            expression = "stressed"
            distress = 0.40 + (brow_furrow * 0.40)
            care_priority = "EMOTIONAL_SUPPORT"
            return (expression, min(1.0, distress), care_priority)

        # ── Sad: mouth droop + soft eyes ──────────────────────────────────────
        if mouth_droop > 0.45 and eye_openness < 0.65:
            expression = "sad"
            distress = 0.35 + (mouth_droop * 0.35)
            care_priority = "EMOTIONAL_SUPPORT"
            return (expression, min(1.0, distress), care_priority)

        # ── Happy: no droop, open eyes, no furrow ────────────────────────────
        if mouth_droop < 0.15 and brow_furrow < 0.2 and eye_openness > 0.60:
            expression = "happy"
            distress = 0.0
            care_priority = "COMPANION"
            return (expression, distress, care_priority)

        # ── Default: calm ────────────────────────────────────────────────────
        expression = "calm"
        distress = max(0.0, brow_furrow * 0.2 + mouth_droop * 0.1)
        care_priority = "COMPANION"
        return (expression, distress, care_priority)

    def _analyze_deepface(self, frame_bgr: np.ndarray) -> Optional[MoodSnapshot]:
        """
        DeepFace 1Hz heavy analysis (runs in thread — non-blocking).
        Requires deepface library.
        """
        try:
            from deepface import DeepFace  # type: ignore
            result = DeepFace.analyze(
                frame_bgr,
                actions=["emotion"],
                enforce_detection=False,
                silent=True,
            )
            if isinstance(result, list):
                result = result[0]

            dominant = result.get("dominant_emotion", "calm").lower()
            emotions = result.get("emotion", {})

            # Map DeepFace emotions to our labels
            EMOTION_MAP = {
                "happy":    ("happy",   0.0),
                "neutral":  ("calm",    0.0),
                "sad":      ("sad",     0.5),
                "angry":    ("angry",   0.65),
                "fear":     ("fearful", 0.70),
                "disgust":  ("stressed",0.55),
                "surprise": ("fearful", 0.40),
            }
            expr, base_distress = EMOTION_MAP.get(dominant, ("calm", 0.0))
            distress = min(1.0, base_distress + (emotions.get(dominant, 0) / 200.0))

            care_priority = "COMPANION"
            if distress >= 0.60:
                care_priority = "MEDICAL_ATTENTION"
            elif distress >= 0.35:
                care_priority = "EMOTIONAL_SUPPORT"

            return MoodSnapshot(
                expression=expr,
                distress_score=round(distress, 3),
                care_priority=care_priority,
                is_owner_detected=True,
                confidence=0.78,
                analyzer_tier="DEEPFACE",
            )
        except Exception as e:
            log.debug("[FACIAL_ANALYZER] DeepFace failed: %s", e)
            return None

    def _detect_face_opencv(self, frame_bgr: np.ndarray) -> bool:
        """Simple OpenCV Haar Cascade face presence check."""
        try:
            import cv2
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
            return len(faces) > 0
        except Exception:
            return False

    def smoothed_expression(self) -> str:
        """Return most frequent expression in sliding window."""
        if not self._history:
            return "unknown"
        counts: Dict[str, int] = {}
        for e in self._history:
            counts[e] = counts.get(e, 0) + 1
        return max(counts, key=counts.get)  # type: ignore

    def close(self) -> None:
        try:
            if self._mp_face_mesh:
                self._mp_face_mesh.close()
            if self._mp_face_detection:
                self._mp_face_detection.close()
        except Exception:
            pass


# Module-level singleton
_facial_analyzer: Optional[FacialExpressionAnalyzer] = None


def get_facial_expression_analyzer() -> FacialExpressionAnalyzer:
    """Get or create the singleton FacialExpressionAnalyzer."""
    global _facial_analyzer
    if _facial_analyzer is None:
        _facial_analyzer = FacialExpressionAnalyzer()
    return _facial_analyzer
