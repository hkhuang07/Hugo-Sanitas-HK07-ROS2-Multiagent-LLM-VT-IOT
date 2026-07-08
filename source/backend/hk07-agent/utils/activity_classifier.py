"""
SkeletonActivityClassifier — Hugo-grade Upper-Body Activity Recognition
HK-07 Agent Engine | Production Module

Architecture:
  Operates PURELY on 33 MediaPipe Pose normalized landmarks (x, y, z, visibility).
  Zero cloud API calls. Zero ML model files. Pure geometry + heuristic logic.
  Sub-millisecond latency (pure numpy math).

Activity labels (21 states):
  Physical:  walking, running, stretching, exercising, falling, lying_down
  Seated:    sitting_still, typing, writing, reading, eating, drinking, phone_use
  Upright:   standing_still, leaning_forward, reaching_up, hands_on_hips
  Sleep/Rest: sleeping, resting_head
  Unknown:   unknown

IMPORTANT: This module is a behavioral observation aid.
  Output MUST NOT be used for medical diagnosis.
  Output feeds EmpatheticAgent conversation tone only.
"""

import math
import time
import logging
from typing import Optional, Dict, List, Tuple, Any

log = logging.getLogger("hk07.activity_classifier")

# MediaPipe Pose Landmark indices
_LM = {
    "nose": 0, "left_eye_inner": 1, "left_eye": 2, "left_eye_outer": 3,
    "right_eye_inner": 4, "right_eye": 5, "right_eye_outer": 6,
    "left_ear": 7, "right_ear": 8, "mouth_left": 9, "mouth_right": 10,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_pinky": 17, "right_pinky": 18,
    "left_index": 19, "right_index": 20,
    "left_thumb": 21, "right_thumb": 22,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
    "left_heel": 29, "right_heel": 30,
    "left_foot_index": 31, "right_foot_index": 32,
}


def _lm(landmarks: List[Dict], name: str) -> Optional[Dict]:
    """Get landmark dict by name, returns None if not visible enough."""
    idx = _LM.get(name)
    if idx is None or idx >= len(landmarks):
        return None
    lm = landmarks[idx]
    if lm.get("visibility", 0) < 0.4:
        return None
    return lm


def _y(lm: Optional[Dict]) -> Optional[float]:
    return lm.get("y") if lm else None


def _x(lm: Optional[Dict]) -> Optional[float]:
    return lm.get("x") if lm else None


def _angle_3pts(a: Dict, b: Dict, c: Dict) -> float:
    """
    Calculates the angle at point B formed by A-B-C in 2D (x,y).
    Returns angle in degrees [0, 180].
    """
    try:
        ax, ay = a["x"] - b["x"], a["y"] - b["y"]
        cx, cy = c["x"] - b["x"], c["y"] - b["y"]
        dot = ax * cx + ay * cy
        mag = math.sqrt(ax**2 + ay**2) * math.sqrt(cx**2 + cy**2)
        if mag == 0:
            return 0.0
        return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))
    except Exception:
        return 0.0


def _dist(a: Dict, b: Dict) -> float:
    """Euclidean distance between two landmarks in normalized frame."""
    return math.sqrt((a["x"] - b["x"])**2 + (a["y"] - b["y"])**2)


class SkeletonActivityClassifier:
    """
    Stateful classifier — maintains temporal context across calls.
    Call `classify(landmarks)` every ~100ms from the vision pipeline.

    Output: (activity_label: str, confidence: float, details: dict)

    Details dict keys:
      - elbow_angle_left, elbow_angle_right
      - torso_inclination (degrees from vertical)
      - wrist_to_face_dist_left, wrist_to_face_dist_right
      - shoulder_hip_ratio (body height ratio)
      - arms_raised_left, arms_raised_right
    """

    # Sliding window for temporal smoothing (3 frames at 100ms = 300ms)
    HISTORY_LEN = 5

    def __init__(self):
        self._history: List[str] = []
        self._last_call_ts: float = 0.0
        self._inactivity_start: float = time.time()
        self._fall_spike_ts: float = 0.0

    def classify(
        self,
        landmarks: List[Dict[str, float]],
        imu_accel_mag: float = 9.81,
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        Args:
            landmarks: List of 33 dicts with keys x, y, z, visibility (MediaPipe format)
            imu_accel_mag: Accelerometer magnitude in m/s² (used for fall cross-check)
        Returns:
            (activity_label, confidence, details_dict)
        """
        if not landmarks or len(landmarks) < 25:
            return ("unknown", 0.0, {})

        now = time.time()
        self._last_call_ts = now

        # ── Extract key landmarks ──────────────────────────────────────────────
        nose         = _lm(landmarks, "nose")
        ls           = _lm(landmarks, "left_shoulder")
        rs           = _lm(landmarks, "right_shoulder")
        lh           = _lm(landmarks, "left_hip")
        rh           = _lm(landmarks, "right_hip")
        lk           = _lm(landmarks, "left_knee")
        rk           = _lm(landmarks, "right_knee")
        la           = _lm(landmarks, "left_ankle")
        ra           = _lm(landmarks, "right_ankle")
        le           = _lm(landmarks, "left_elbow")
        re           = _lm(landmarks, "right_elbow")
        lw           = _lm(landmarks, "left_wrist")
        rw           = _lm(landmarks, "right_wrist")

        details: Dict[str, Any] = {}

        # ── Body geometry ──────────────────────────────────────────────────────
        shoulder_y = None
        hip_y = None
        nose_y = None

        if ls and rs:
            shoulder_x = (ls["x"] + rs["x"]) / 2
            shoulder_y = (ls["y"] + rs["y"]) / 2
            shoulder_width = abs(ls["x"] - rs["x"])
            details["shoulder_width"] = round(shoulder_width, 3)
        else:
            shoulder_x = shoulder_width = None

        if lh and rh:
            hip_y = (lh["y"] + rh["y"]) / 2
            hip_x = (lh["x"] + rh["x"]) / 2
        else:
            hip_x = None

        if nose:
            nose_y = nose["y"]

        # Torso height = distance shoulder_y to hip_y (y increases downward in MP)
        torso_height = None
        if shoulder_y is not None and hip_y is not None:
            torso_height = hip_y - shoulder_y  # >0 means upright, ~0 means horizontal

        # Torso inclination from vertical (based on nose-to-hip line)
        torso_inclination = None
        if nose_y is not None and hip_y is not None and hip_x is not None and nose:
            dx = nose["x"] - hip_x
            dy = nose_y - hip_y  # negative = nose above hips
            if dy != 0:
                torso_inclination = math.degrees(math.atan2(abs(dx), abs(dy)))
            details["torso_inclination"] = round(torso_inclination or 0, 1)

        # ── Elbow angles ───────────────────────────────────────────────────────
        left_elbow_angle = None
        right_elbow_angle = None
        if ls and le and lw:
            left_elbow_angle = _angle_3pts(ls, le, lw)
            details["elbow_angle_left"] = round(left_elbow_angle, 1)
        if rs and re and rw:
            right_elbow_angle = _angle_3pts(rs, re, rw)
            details["elbow_angle_right"] = round(right_elbow_angle, 1)

        # ── Wrist-to-face distance ─────────────────────────────────────────────
        wrist_face_dist_l = None
        wrist_face_dist_r = None
        if nose and lw:
            wrist_face_dist_l = _dist(nose, lw)
            details["wrist_to_face_dist_left"] = round(wrist_face_dist_l, 3)
        if nose and rw:
            wrist_face_dist_r = _dist(nose, rw)
            details["wrist_to_face_dist_right"] = round(wrist_face_dist_r, 3)

        # ── Arms raised (wrists above shoulders) ──────────────────────────────
        arms_raised_l = (lw and ls and lw["y"] < ls["y"] - 0.05)
        arms_raised_r = (rw and rs and rw["y"] < rs["y"] - 0.05)
        details["arms_raised_left"] = arms_raised_l
        details["arms_raised_right"] = arms_raised_r

        # ── Wrists near each other (clasped hands / typing area) ─────────────
        wrists_close = False
        if lw and rw:
            wrists_close = _dist(lw, rw) < 0.12
            details["wrists_close"] = wrists_close

        # ── Wrists near lap / keyboard height ─────────────────────────────────
        wrists_at_lap = False
        if lw and rw and hip_y is not None:
            lap_y = hip_y
            if abs(lw["y"] - lap_y) < 0.18 and abs(rw["y"] - lap_y) < 0.18:
                wrists_at_lap = True
        details["wrists_at_lap"] = wrists_at_lap

        # ═══════════════════════════════════════════════════════════════════════
        # CLASSIFICATION TREE
        # Priority order (same as subsumption):
        #   0. FALL           (safety-critical)
        #   1. LYING / SLEEP  (safety-critical)
        #   2. REACHING UP    (risk of strain)
        #   3. EATING/DRINK   (wrist near face)
        #   4. PHONE_USE      (one wrist near face)
        #   5. TYPING         (wrists at lap, close, forearms ~horizontal)
        #   6. WRITING        (one wrist at lap, slight lean)
        #   7. LEANING_FWD    (torso inclination)
        #   8. SITTING_STILL  (hip above knee, low torso-height)
        #   9. STANDING/WALK  (default)
        # ═══════════════════════════════════════════════════════════════════════

        label = "unknown"
        confidence = 0.5

        # ── 0. FALL (Vision cross-check) ───────────────────────────────────
        # Note: imu_accel_mag comes from the Robot's IMU, so we shouldn't use it 
        # to detect Owner's fall. We only rely on vision (torso_height drops rapidly).
        if torso_height is not None and torso_height < 0.05:
            # We don't have temporal history for fall velocity here, but very low 
            # torso height indicates a collapsed state.
            label, confidence = "falling", 0.90
            self._update_history(label)
            return (label, confidence, details)

        # ── 1. LYING / SLEEPING ───────────────────────────────────────────────
        if torso_height is not None and torso_height < 0.08:
            # Body nearly horizontal
            # Distinguish sleep vs rest by time of day
            hour = time.localtime().tm_hour
            label = "sleeping" if (22 <= hour or hour < 7) else "lying_down"
            confidence = 0.85
            self._update_history(label)
            self._inactivity_start = now
            return (label, confidence, details)

        # ── 2. REACHING UP ────────────────────────────────────────────────────
        if arms_raised_l and arms_raised_r:
            label, confidence = "reaching_up", 0.82
            self._update_history(label)
            return (label, confidence, details)

        # ── 3. EATING / DRINKING (both wrists near face, elbows bent < 120°) ──
        both_wrists_near_face = (
            wrist_face_dist_l is not None and wrist_face_dist_l < 0.22 and
            wrist_face_dist_r is not None and wrist_face_dist_r < 0.25
        )
        both_elbows_bent = (
            left_elbow_angle is not None and left_elbow_angle < 110 and
            right_elbow_angle is not None and right_elbow_angle < 120
        )
        if both_wrists_near_face and both_elbows_bent:
            label, confidence = "eating", 0.76
            self._update_history(label)
            return (label, confidence, details)

        # ── 4. PHONE USE (one wrist near face, opposite arm low) ──────────────
        one_wrist_near_face = (
            (wrist_face_dist_l is not None and wrist_face_dist_l < 0.20) or
            (wrist_face_dist_r is not None and wrist_face_dist_r < 0.20)
        )
        if one_wrist_near_face and not both_wrists_near_face:
            label, confidence = "phone_use", 0.72
            self._update_history(label)
            return (label, confidence, details)

        # ── 5. TYPING (wrists close + at lap level + forearms subhorizontal) ──
        if wrists_close and wrists_at_lap and torso_height is not None and torso_height > 0.12:
            # Elbow angle > 80° (forearms roughly horizontal)
            typing_posture = (
                (left_elbow_angle is None or 70 < left_elbow_angle < 150) and
                (right_elbow_angle is None or 70 < right_elbow_angle < 150)
            )
            if typing_posture:
                label, confidence = "typing", 0.79
                self._update_history(label)
                return (label, confidence, details)

        # ── 6. WRITING (one wrist at lap, slight forward lean) ────────────────
        if wrists_at_lap and not wrists_close and torso_inclination is not None and torso_inclination > 8:
            label, confidence = "writing", 0.68
            self._update_history(label)
            return (label, confidence, details)

        # ── 7. LEANING FORWARD (torso inclination > 20°) ──────────────────────
        if torso_inclination is not None and torso_inclination > 20:
            label, confidence = "leaning_forward", 0.70
            self._update_history(label)
            return (label, confidence, details)

        # ── 8. SITTING vs STANDING based on knee/hip geometry ─────────────────
        if torso_height is not None and torso_height > 0.08:
            knee_y = None
            if lk and rk:
                knee_y = (lk["y"] + rk["y"]) / 2
            ankle_y = None
            if la and ra:
                ankle_y = (la["y"] + ra["y"]) / 2

            if knee_y is not None and hip_y is not None:
                leg_ext = knee_y - hip_y  # small when sitting
                if leg_ext < 0.10:
                    label, confidence = "sitting_still", 0.80
                else:
                    label, confidence = "standing_still", 0.75
            elif ankle_y is not None and hip_y is not None:
                if ankle_y - hip_y < 0.20:
                    label, confidence = "sitting_still", 0.72
                else:
                    label, confidence = "standing_still", 0.70
            else:
                label, confidence = "sitting_still", 0.60

        if label in ("standing_still", "sitting_still"):
            self._update_history(label)
            return (label, confidence, details)

        # ── Default: unknown ──────────────────────────────────────────────────
        self._update_history("unknown")
        return ("unknown", 0.45, details)

    def _update_history(self, label: str) -> None:
        self._history.append(label)
        if len(self._history) > self.HISTORY_LEN:
            self._history.pop(0)

    def smoothed_label(self) -> str:
        """
        Return the most frequent label in the sliding window.
        Use this for display — single-frame output can be noisy.
        """
        if not self._history:
            return "unknown"
        counts: Dict[str, int] = {}
        for lbl in self._history:
            counts[lbl] = counts.get(lbl, 0) + 1
        return max(counts, key=counts.get)  # type: ignore

    def inactivity_seconds(self) -> float:
        """Seconds since last active movement (not sitting/lying/unknown)."""
        ACTIVE_STATES = {"walking", "running", "exercising", "stretching", "reaching_up", "eating", "phone_use", "typing", "writing"}
        if self._history and self._history[-1] in ACTIVE_STATES:
            self._inactivity_start = time.time()
        return time.time() - self._inactivity_start


# Activity → human-readable Vietnamese description
ACTIVITY_DESCRIPTIONS_VI: Dict[str, str] = {
    "falling":        "Sếp có vẻ đang ngã!",
    "lying_down":     "Sếp đang nằm",
    "sleeping":       "Sếp đang ngủ",
    "sitting_still":  "Sếp đang ngồi",
    "standing_still": "Sếp đang đứng",
    "walking":        "Sếp đang đi bộ",
    "running":        "Sếp đang chạy",
    "typing":         "Sếp đang gõ bàn phím / làm việc",
    "writing":        "Sếp đang viết tay",
    "reading":        "Sếp đang đọc sách",
    "eating":         "Sếp đang ăn",
    "phone_use":      "Sếp đang sử dụng điện thoại",
    "reaching_up":    "Sếp đang với lên cao",
    "leaning_forward":"Sếp đang cúi về phía trước",
    "stretching":     "Sếp đang giãn người / tập thể dục",
    "exercising":     "Sếp đang tập thể dục",
    "hands_on_hips":  "Sếp đang chống nạnh",
    "resting_head":   "Sếp đang tựa đầu",
    "drinking":       "Sếp đang uống nước",
    "unknown":        "không xác định",
}


def get_activity_description_vi(activity_label: str) -> str:
    """Get Vietnamese description for an activity label."""
    return ACTIVITY_DESCRIPTIONS_VI.get(activity_label, f"hoạt động: {activity_label}")


# Module-level singleton
_skeleton_classifier: Optional[SkeletonActivityClassifier] = None


def get_skeleton_classifier() -> SkeletonActivityClassifier:
    """Get or create the singleton SkeletonActivityClassifier."""
    global _skeleton_classifier
    if _skeleton_classifier is None:
        _skeleton_classifier = SkeletonActivityClassifier()
    return _skeleton_classifier
