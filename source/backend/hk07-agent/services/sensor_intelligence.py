"""
SensorIntelligence — Behavioral Stress Proxy & Sensor Fusion Analyzer
HK-07 Agent Engine | Production Module

ARCH-1 CRITICAL FIX:
  The previous design used inferred "Dopamine/Cortisol/Serotonin" labels —
  these are scientifically invalid without blood/biochemical sensors.
  This module replaces that with a rigorous BehavioralStressProxy:
    - Uses ONLY observable behavioral signals (HR, motion, activity, light, posture)
    - Named "stress_proxy" not "cortisol" — never presented as medical diagnosis
    - Outputs ONLY to EmpatheticAgent for conversational decisions
    - STRICTLY FORBIDDEN from feeding MedicalAgent diagnostic pipeline

ARCH-2:
  ActivityClassifier: Pure local numpy/threshold logic on IMU data.
  No ML model required. Sub-millisecond latency.
  MediaPipe Pose keypoints → activity state (sitting/standing/walking/falling).
"""

import math
import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict, field

log = logging.getLogger("hk07.sensor_intelligence")


# ─────────────────────────────────────────────────────────────────────────────
# BEHAVIORAL STRESS PROXY
# Converts multi-sensor observable signals → behavioral stress estimate.
#
# CRITICAL DISCLAIMER:
#   This module does NOT measure actual neurotransmitters.
#   Output is a heuristic proxy for observable behavioral distress patterns.
#   It MUST ONLY be consumed by EmpatheticAgent to guide conversation tone.
#   It MUST NEVER be used by MedicalAgent for clinical diagnosis.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BehavioralStressProxy:
    """
    Observable behavioral stress estimate from sensor fusion.
    NOT a medical measurement. NOT neurotransmitter levels.
    USE: EmpatheticAgent conversation tone adjustment ONLY.
    FORBIDDEN: MedicalAgent diagnostic input.
    """
    # Stress score 0.0 (calm) → 1.0 (high behavioral distress indicators)
    stress_score: float = 0.0

    # Contributing signal weights (for explainability / debugging)
    hr_contribution: float = 0.0        # Elevated HR beyond resting baseline
    motion_contribution: float = 0.0    # High-frequency tremor or frantic movement
    inactivity_contribution: float = 0.0  # Prolonged stillness (depression proxy)
    light_contribution: float = 0.0     # Very low light (night / isolation proxy)

    # Human-readable label for EmpatheticAgent prompt injection
    stress_label: str = "NOMINAL"       # NOMINAL | MILD_DISTRESS | MODERATE_DISTRESS | HIGH_DISTRESS

    # Behavioral context for EmpatheticAgent
    behavioral_context: str = ""        # e.g. "Owner appears physically active but heart rate is elevated"

    # Timestamp
    timestamp: float = field(default_factory=time.time)

    # MANDATORY disclaimer — always injected into any prompt using this data
    disclaimer: str = (
        "⚠️ BehavioralStressProxy: This is a heuristic behavioral estimate from "
        "observable sensor signals only. It is NOT a medical measurement, "
        "NOT a neurotransmitter reading, and MUST NOT be used for clinical diagnosis. "
        "Use only to guide empathetic conversation tone."
    )

    def to_empathy_context(self) -> str:
        """
        Serializes to a compact string safe for EmpatheticAgent system prompt injection.
        Intentionally omits clinical language.
        """
        return (
            f"[BEHAVIORAL_CONTEXT] stress_label={self.stress_label} | "
            f"stress_score={self.stress_score:.2f} | "
            f"context='{self.behavioral_context}' | "
            f"[NOTE: heuristic proxy only — not a medical measurement]"
        )


def compute_behavioral_stress_proxy(
    heart_rate: Optional[float],
    activity_state: str,
    wrist_motion_magnitude: float,
    ambient_light_lux: Optional[float],
    step_count_delta: Optional[float],
    posture_risk: str,
    inactivity_seconds: float = 0.0,
) -> BehavioralStressProxy:
    """
    Compute BehavioralStressProxy from observable sensor signals.

    Algorithm: Weighted sum of normalized behavioral indicators.
    No neurotransmitter terminology. No medical claims.

    Args:
        heart_rate: BPM from wristband/rPPG. None if sensor offline.
        activity_state: From ActivityClassifier ('sitting','walking','running','falling','lying')
        wrist_motion_magnitude: Accelerometer magnitude from wristband
        ambient_light_lux: Light sensor reading in lux. None if offline.
        step_count_delta: Steps in last 60s from pedometer. None if offline.
        posture_risk: 'LOW'|'MED'|'HIGH' from MediaPipe Pose or PerceptionScan
        inactivity_seconds: Seconds since last significant movement
    """
    # All contributions normalized to [0.0, 1.0]
    hr_contrib = 0.0
    motion_contrib = 0.0
    inactivity_contrib = 0.0
    light_contrib = 0.0

    # ── Heart Rate Contribution ─────────────────────────────────────────────
    # Elevated HR beyond resting baseline (60-100 BPM) is a behavioral signal.
    # NOT a cortisol proxy — just elevated HR is observable.
    if heart_rate is not None and not math.isnan(heart_rate) and heart_rate > 0:
        if heart_rate > 100:
            # Above normal resting: scale 100→180 BPM → 0→1 contribution
            hr_contrib = min(1.0, (heart_rate - 100) / 80.0)
        elif heart_rate < 45:
            # Bradycardia range — may indicate severe exhaustion or medical issue
            hr_contrib = 0.4
    # If HR sensor is offline: contribute 0 (unknown ≠ elevated)

    # ── Motion / Tremor Contribution ────────────────────────────────────────
    # High wrist motion magnitude in a "resting" state may indicate tremor or anxiety
    if wrist_motion_magnitude > 0:
        if activity_state in ("sitting", "lying", "standing") and wrist_motion_magnitude > 1.5:
            # High motion while supposedly still → possible tremor/fidgeting
            motion_contrib = min(1.0, (wrist_motion_magnitude - 1.5) / 5.0)

    # ── Inactivity Contribution ─────────────────────────────────────────────
    # Prolonged stillness (>2h) may correlate with low energy / low mood
    if inactivity_seconds > 0:
        if inactivity_seconds > 7200:   # > 2 hours
            inactivity_contrib = min(1.0, (inactivity_seconds - 7200) / 7200.0)
        elif inactivity_seconds > 3600:  # 1-2h
            inactivity_contrib = 0.2

    # ── Ambient Light Contribution ──────────────────────────────────────────
    # Very dark environment (< 30 lux) after peak hours may indicate withdrawal
    if ambient_light_lux is not None and not math.isnan(ambient_light_lux):
        current_hour = time.localtime().tm_hour
        # Only meaningful signal between 8:00-22:00
        if 8 <= current_hour <= 22 and ambient_light_lux < 30:
            light_contrib = min(1.0, (30 - ambient_light_lux) / 30.0) * 0.3

    # ── Posture Override ────────────────────────────────────────────────────
    # HIGH posture risk boosts stress score directly
    posture_boost = 0.0
    if posture_risk == "HIGH":
        posture_boost = 0.35
    elif posture_risk == "MED":
        posture_boost = 0.15

    # ── Weighted Composite ──────────────────────────────────────────────────
    # Weights: HR is most important behavioral signal, then posture, motion, inactivity, light
    score = (
        hr_contrib * 0.40
        + motion_contrib * 0.20
        + inactivity_contrib * 0.15
        + light_contrib * 0.10
        + posture_boost
    )
    score = max(0.0, min(1.0, score))

    # ── Label Mapping ───────────────────────────────────────────────────────
    if score < 0.2:
        label = "NOMINAL"
        context = "Observable behavioral indicators within normal range."
    elif score < 0.45:
        label = "MILD_DISTRESS"
        context = _build_context(hr_contrib, motion_contrib, inactivity_contrib, light_contrib, activity_state)
    elif score < 0.70:
        label = "MODERATE_DISTRESS"
        context = _build_context(hr_contrib, motion_contrib, inactivity_contrib, light_contrib, activity_state)
    else:
        label = "HIGH_DISTRESS"
        context = _build_context(hr_contrib, motion_contrib, inactivity_contrib, light_contrib, activity_state)

    return BehavioralStressProxy(
        stress_score=round(score, 3),
        hr_contribution=round(hr_contrib, 3),
        motion_contribution=round(motion_contrib, 3),
        inactivity_contribution=round(inactivity_contrib, 3),
        light_contribution=round(light_contrib, 3),
        stress_label=label,
        behavioral_context=context,
    )


def _build_context(hr: float, motion: float, inactivity: float, light: float, activity: str) -> str:
    """Build human-readable behavioral context string for EmpatheticAgent."""
    factors = []
    if hr > 0.3:
        factors.append("elevated heart rate")
    if motion > 0.3:
        factors.append("unusual wrist movement while at rest")
    if inactivity > 0.2:
        factors.append("prolonged physical inactivity")
    if light > 0.2:
        factors.append("low ambient light environment")
    if activity == "falling":
        factors.append("fall or sudden drop detected")
    if not factors:
        factors.append("multiple mild signals")
    return f"Behavioral distress indicators observed: {', '.join(factors)}."


# ─────────────────────────────────────────────────────────────────────────────
# ACTIVITY CLASSIFIER
# Pure threshold/rule-based classification from IMU sensor data.
# Local only — zero API calls, sub-millisecond latency.
# ─────────────────────────────────────────────────────────────────────────────

class ActivityClassifier:
    """
    Classifies user activity state from accelerometer + gyroscope signals.
    Uses MediaPipe Pose keypoints when available, falls back to IMU thresholds.

    Output states:
      - 'still'    : Very low motion, sensor magnitude ≈ gravity (9.81 m/s²)
      - 'sitting'  : Low accel, low gyro, upright-ish orientation
      - 'standing' : Low motion but upright (from pose if available)
      - 'walking'  : Periodic accel oscillation ~1-3 Hz
      - 'running'  : High accel, high gyro, high step rate
      - 'falling'  : Sudden large accel spike followed by near-zero (free fall pattern)
      - 'lying'    : Very low accel overall, body roughly horizontal
      - 'unknown'  : Insufficient data
    """

    # Thresholds (m/s² and rad/s)
    FALL_SPIKE_THRESHOLD = 25.0     # Very large acceleration spike
    FALL_FLOOR_THRESHOLD = 3.0      # Near free-fall after spike
    WALK_ACCEL_MIN = 10.5           # Above normal gravity
    WALK_ACCEL_MAX = 20.0
    RUN_ACCEL_MIN = 18.0
    GYRO_WALK_MIN = 0.3             # Some rotation while walking
    STILL_THRESHOLD = 1.0           # Accel magnitude deviation from 9.81

    def __init__(self):
        self._prev_accel_mag: float = 9.81
        self._prev_state: str = "unknown"
        self._fall_spike_ts: float = 0.0
        self._inactivity_start: float = time.time()
        self._step_buffer: List[float] = []  # timestamps of motion peaks for step detection

    def classify(
        self,
        accel_x: float,
        accel_y: float,
        accel_z: float,
        gyro_x: float = 0.0,
        gyro_y: float = 0.0,
        gyro_z: float = 0.0,
        pose_keypoints: Optional[Dict] = None,
    ) -> Tuple[str, float]:
        """
        Classify activity from IMU readings.

        Returns:
            (activity_state: str, confidence: float)
        """
        accel_mag = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
        gyro_mag = math.sqrt(gyro_x**2 + gyro_y**2 + gyro_z**2)
        accel_delta = abs(accel_mag - self._prev_accel_mag)
        now = time.time()

        # ── Fall Detection (Priority 1) ──────────────────────────────────────
        # Pattern: large spike (> 25 m/s²) followed within 0.5s by near-zero (< 3 m/s²)
        if accel_mag > self.FALL_SPIKE_THRESHOLD:
            self._fall_spike_ts = now
            log.debug("[ACTIVITY] Fall spike detected: accel_mag=%.2f", accel_mag)

        if self._fall_spike_ts > 0 and (now - self._fall_spike_ts) < 0.5:
            if accel_mag < self.FALL_FLOOR_THRESHOLD:
                self._prev_accel_mag = accel_mag
                self._prev_state = "falling"
                return ("falling", 0.95)

        # ── Lying Down (Priority 2) ─────────────────────────────────────────
        # Very low total accel (gravity dominates one axis, very little else)
        deviation_from_gravity = abs(accel_mag - 9.81)
        if deviation_from_gravity < self.STILL_THRESHOLD and gyro_mag < 0.2:
            # Differentiate lying vs still-sitting by orientation
            # If Z-axis is near 0 and X or Y near 9.81 → horizontal = lying
            if abs(accel_z) < 3.0 and (abs(accel_x) > 7.0 or abs(accel_y) > 7.0):
                state = "lying"
                conf = 0.80
                self._inactivity_start = now  # lying = inactivity
            else:
                state = "still"
                conf = 0.85
                self._inactivity_start = self._inactivity_start  # unchanged

            self._prev_accel_mag = accel_mag
            self._prev_state = state
            return (state, conf)

        # ── Pose keypoint override (if MediaPipe available) ─────────────────
        if pose_keypoints:
            pose_state = self._classify_from_pose(pose_keypoints)
            if pose_state != "unknown":
                self._prev_accel_mag = accel_mag
                self._prev_state = pose_state
                return (pose_state, 0.88)

        # ── Walking / Running from accel magnitude ──────────────────────────
        if accel_mag >= self.RUN_ACCEL_MIN and gyro_mag > 0.5:
            state, conf = "running", 0.75
        elif self.WALK_ACCEL_MIN <= accel_mag < self.WALK_ACCEL_MAX and gyro_mag >= self.GYRO_WALK_MIN:
            state, conf = "walking", 0.70
        elif accel_delta > 2.0:
            state, conf = "moving", 0.60
        else:
            state, conf = "standing", 0.65

        if state in ("walking", "running", "moving"):
            self._inactivity_start = now

        self._prev_accel_mag = accel_mag
        self._prev_state = state
        return (state, conf)

    def _classify_from_pose(self, keypoints: Dict) -> str:
        """
        Classify from MediaPipe Pose 33-landmark output.
        Uses hip-shoulder angle and knee angles to determine posture.
        keypoints: dict of landmark index → {x, y, z, visibility}
        """
        try:
            # Landmark indices (MediaPipe Pose)
            # 11=left_shoulder, 12=right_shoulder, 23=left_hip, 24=right_hip
            # 25=left_knee, 26=right_knee, 27=left_ankle, 28=right_ankle
            ls = keypoints.get(11, {})
            rs = keypoints.get(12, {})
            lh = keypoints.get(23, {})
            rh = keypoints.get(24, {})
            lk = keypoints.get(25, {})
            rk = keypoints.get(26, {})

            if not all([ls.get("visibility", 0) > 0.5, lh.get("visibility", 0) > 0.5]):
                return "unknown"

            # Shoulder midpoint Y, Hip midpoint Y
            shoulder_y = (ls.get("y", 0.5) + rs.get("y", 0.5)) / 2
            hip_y = (lh.get("y", 0.5) + rh.get("y", 0.5)) / 2
            knee_y = (lk.get("y", 0.5) + rk.get("y", 0.5)) / 2

            # Y axis in MediaPipe: 0=top, 1=bottom
            torso_height = hip_y - shoulder_y    # positive = upright
            leg_extension = knee_y - hip_y        # positive = legs below hips

            if torso_height < 0.05:
                # Body appears horizontal → lying
                return "lying"
            elif leg_extension < 0.08:
                # Short leg extension → sitting
                return "sitting"
            else:
                # Upright with extended legs → standing
                return "standing"
        except Exception:
            return "unknown"

    def inactivity_seconds(self) -> float:
        """Returns seconds since last significant movement."""
        return time.time() - self._inactivity_start


# ─────────────────────────────────────────────────────────────────────────────
# SENSOR FUSION ANALYZER
# Combines all sensor streams into a unified semantic context snapshot.
# ─────────────────────────────────────────────────────────────────────────────

class SensorFusionAnalyzer:
    """
    Combines IMU, vitals, environment, and vision signals into a semantic context.
    Designed for O(1) per-cycle compute — no blocking I/O.

    Outputs:
      - activity_state: str
      - behavioral_stress_proxy: BehavioralStressProxy
      - sensor_availability: dict (which sensors are live vs offline)

    CRITICAL: All offline sensors must emit 'SENSOR_OFFLINE' sentinel,
    never a default numeric fallback.
    """

    def __init__(self):
        self._activity_classifier = ActivityClassifier()

    def analyze(
        self,
        imu_data: Optional[Dict[str, Any]],
        vitals_data: Optional[Dict[str, Any]],
        env_data: Optional[Dict[str, Any]],
        posture_risk: str = "LOW",
        pose_keypoints: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Single unified analysis cycle. All parameters are Optional —
        SENSOR_OFFLINE sentinel returned for any missing data.

        Args:
            imu_data: dict with accel_x/y/z, gyro_x/y/z etc from blackboard
            vitals_data: dict with heart_rate, spo2, etc
            env_data: dict with light_lux, barometer_hpa, etc
            posture_risk: from PerceptionScan ('LOW'|'MED'|'HIGH')
            pose_keypoints: MediaPipe Pose landmark dict (optional)
        """
        availability = {}

        # ── IMU ─────────────────────────────────────────────────────────────
        if imu_data:
            ax = float(imu_data.get("accel_x", 0.0) or 0.0)
            ay = float(imu_data.get("accel_y", 0.0) or 0.0)
            az = float(imu_data.get("accel_z", 9.81) or 9.81)
            gx = float(imu_data.get("gyro_x", 0.0) or 0.0)
            gy = float(imu_data.get("gyro_y", 0.0) or 0.0)
            gz = float(imu_data.get("gyro_z", 0.0) or 0.0)
            wrist_mag = float(imu_data.get("wrist_motion_magnitude", 0.0) or 0.0)
            availability["imu"] = "ONLINE"
        else:
            ax = ay = 0.0
            az = 9.81
            gx = gy = gz = 0.0
            wrist_mag = 0.0
            availability["imu"] = "SENSOR_OFFLINE"

        # ── Activity Classification ─────────────────────────────────────────
        activity_state, activity_confidence = self._activity_classifier.classify(
            ax, ay, az, gx, gy, gz, pose_keypoints
        )
        inactivity_secs = self._activity_classifier.inactivity_seconds()

        # ── Vitals ──────────────────────────────────────────────────────────
        hr = None
        if vitals_data:
            hr_raw = vitals_data.get("heart_rate") or vitals_data.get("hr")
            if hr_raw is not None:
                try:
                    hr = float(hr_raw)
                    if math.isnan(hr) or hr <= 0:
                        hr = None
                except (TypeError, ValueError):
                    hr = None
            availability["vitals"] = "ONLINE" if hr is not None else "SENSOR_OFFLINE"
        else:
            availability["vitals"] = "SENSOR_OFFLINE"

        # ── Environment ─────────────────────────────────────────────────────
        light_lux = None
        if env_data:
            lux_raw = env_data.get("light_lux") or env_data.get("light")
            if lux_raw is not None:
                try:
                    light_lux = float(lux_raw)
                except (TypeError, ValueError):
                    light_lux = None
            availability["environment"] = "ONLINE"
        else:
            availability["environment"] = "SENSOR_OFFLINE"

        # ── Behavioral Stress Proxy ─────────────────────────────────────────
        stress_proxy = compute_behavioral_stress_proxy(
            heart_rate=hr,
            activity_state=activity_state,
            wrist_motion_magnitude=wrist_mag,
            ambient_light_lux=light_lux,
            step_count_delta=None,  # TODO: wire pedometer when available
            posture_risk=posture_risk,
            inactivity_seconds=inactivity_secs,
        )

        return {
            "activity_state": activity_state,
            "activity_confidence": round(activity_confidence, 2),
            "inactivity_seconds": round(inactivity_secs, 1),
            "behavioral_stress_proxy": asdict(stress_proxy),
            # EmpatheticAgent injects this — never MedicalAgent
            "empathy_context": stress_proxy.to_empathy_context(),
            "sensor_availability": availability,
            "analyzed_at": time.time(),
        }


# Module-level singleton for agent imports
_sensor_fusion_analyzer: Optional[SensorFusionAnalyzer] = None


def get_sensor_fusion_analyzer() -> SensorFusionAnalyzer:
    """Get or create the singleton SensorFusionAnalyzer."""
    global _sensor_fusion_analyzer
    if _sensor_fusion_analyzer is None:
        _sensor_fusion_analyzer = SensorFusionAnalyzer()
    return _sensor_fusion_analyzer
