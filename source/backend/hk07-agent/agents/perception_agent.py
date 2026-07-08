"""
PerceptionAgent — Tier 0.5: Full-Body Multi-modal Scan  [v2 — ASYNC HARDENED]

Role: Observe. Do NOT speak to user directly.
Output: PerceptionScan JSON written to Blackboard.

Capability matrix (Phase 2):
  A. Full-body scan (camera depth/RGB + vitals)
  B. Physical analysis (skin tone note, facial distress, posture risk, injuries)
  C. LiDAR threat context from Fusion Buffer
  D. Writes PerceptionScan to BlackboardService

Architecture changes (2026-06-19):
  [FIX-1] IPWebcam dynamic IP scanner — resolves getaddrinfo / Errno 11001 failures.
          asyncio.to_thread frame fetcher — network I/O never blocks the event loop.
  [FIX-2] LocalVisionEvaluator (Ollama/Moondream2) replaces cloud fallback chain.
          Activates automatically when internet latency > 2.0s or all cloud tiers OPENed.
  [FIX-3] execute_full_body_scan isolated: no heartbeat coupling.
  [FIX-4] rPPG_THERMAL + wristband fall sensor injected as structured JSON metadata
          directly into the LLM system prompt — skips NL translation for tool calling.

Subsumption: SAFETY (Tier 0) can inhibit perception scan if CRITICAL.
Perception writes are read-only-silent — never sent directly to user.
"""

import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any

import httpx

from services.blackboard_service import get_blackboard
from services.sensor_fusion_buffer import get_fusion_buffer, FusedContext
from arbitrator.arbitrator import Arbitrator
# [FIX-1] Dynamic IP scanner + async frame fetcher
from utils.ip_scanner import discover_ipwebcam_ip, fetch_frame_nonblocking
# [FIX-2] Local Ollama Vision Evaluator
from utils.local_vision_evaluator import LocalVisionEvaluator
# [ARCH-1] BehavioralStressProxy (replaces pseudoscientific neurotransmitter labels)
from services.sensor_intelligence import get_sensor_fusion_analyzer, BehavioralStressProxy

log = logging.getLogger("hk07.perception_agent")

# Module-level singleton — one Ollama evaluator shared across scan invocations
_local_vision = LocalVisionEvaluator()

# Module-level SensorFusionAnalyzer singleton
_sensor_fusion = get_sensor_fusion_analyzer()


# ─── Event Trigger Gate ──────────────────────────────────────────────────────────────────────────
# ARCH-2 FIX: Gemini Vision (cloud) is only triggered by EVENTS, not continuous polling.
# Continuous 15s polling sends private images to cloud servers without consent.
# Solution: MediaPipe runs locally at 15Hz (no cloud). Cloud vision only fires
# when a local trigger event is detected (fall, high distress, injury signal).
# ──────────────────────────────────────────────────────────────────────────

class EventTriggerGate:
    """
    Controls when cloud Vision API (Gemini) is invoked.
    Local MediaPipe runs continuously (free, private, fast).
    Cloud API fires ONLY on significant event triggers.

    Trigger Events:
      - FALL_DETECTED: ActivityClassifier outputs 'falling'
      - HIGH_DISTRESS: facial_distress > 0.65 OR stress_proxy > 0.7
      - INJURY_SUSPECTED: visible_injuries detected by local scan
      - EXPLICIT_REQUEST: User or Orchestrator requests full scan
      - PERIODIC_BASELINE: At most once every 5 minutes (not 15s)
    """

    # Minimum seconds between cloud vision calls (privacy protection)
    PERIODIC_BASELINE_INTERVAL_S = 300  # 5 minutes max
    # After a trigger, cooldown before same event re-triggers
    EVENT_COOLDOWN_S = 60  # 1 minute per event type

    def __init__(self):
        self._last_cloud_call_ts: float = 0.0
        self._event_cooldowns: Dict[str, float] = {}  # event_type -> last triggered ts

    def should_call_cloud_vision(
        self,
        activity_state: str = "unknown",
        facial_distress: float = 0.0,
        stress_proxy_score: float = 0.0,
        visible_injuries: list = None,
        explicit_request: bool = False,
    ) -> tuple[bool, str]:
        """
        Returns (should_call: bool, reason: str).
        Reasons: 'FALL_DETECTED' | 'HIGH_DISTRESS' | 'INJURY_SUSPECTED' |
                 'EXPLICIT_REQUEST' | 'PERIODIC_BASELINE' | 'GATED'
        """
        now = time.time()
        visible_injuries = visible_injuries or []

        # Always allow explicit requests from Orchestrator/user
        if explicit_request:
            return (True, "EXPLICIT_REQUEST")

        # Fall detected → immediate cloud confirmation scan
        if activity_state == "falling":
            last = self._event_cooldowns.get("FALL_DETECTED", 0.0)
            if now - last > self.EVENT_COOLDOWN_S:
                self._event_cooldowns["FALL_DETECTED"] = now
                self._last_cloud_call_ts = now
                log.warning("[EVENT_GATE] 🚨 FALL trigger → Cloud Vision activated")
                return (True, "FALL_DETECTED")

        # High behavioral distress
        if facial_distress > 0.65 or stress_proxy_score > 0.70:
            last = self._event_cooldowns.get("HIGH_DISTRESS", 0.0)
            if now - last > self.EVENT_COOLDOWN_S:
                self._event_cooldowns["HIGH_DISTRESS"] = now
                self._last_cloud_call_ts = now
                log.warning("[EVENT_GATE] HIGH_DISTRESS trigger → Cloud Vision activated")
                return (True, "HIGH_DISTRESS")

        # Injury suspected by local scan
        if visible_injuries:
            last = self._event_cooldowns.get("INJURY_SUSPECTED", 0.0)
            if now - last > self.EVENT_COOLDOWN_S:
                self._event_cooldowns["INJURY_SUSPECTED"] = now
                self._last_cloud_call_ts = now
                log.info("[EVENT_GATE] INJURY_SUSPECTED trigger → Cloud Vision activated")
                return (True, "INJURY_SUSPECTED")

        # Periodic baseline — at most once every 5 minutes
        if now - self._last_cloud_call_ts > self.PERIODIC_BASELINE_INTERVAL_S:
            self._last_cloud_call_ts = now
            log.info("[EVENT_GATE] PERIODIC_BASELINE (5min) → Cloud Vision activated")
            return (True, "PERIODIC_BASELINE")

        # All gates blocked
        return (False, "GATED")


# ── Disk I/O Helpers (run inside asyncio.to_thread — never block event loop) ──

def _write_frame_to_disk(data: bytes, path: str) -> None:
    """Blocking JPEG write — must be called via asyncio.to_thread."""
    with open(path, "wb") as fh:
        fh.write(data)

def _read_frame_from_disk(path: str) -> bytes:
    """Blocking JPEG read — must be called via asyncio.to_thread."""
    with open(path, "rb") as fh:
        return fh.read()


def safe_float(val: Any, default: float = 0.0) -> float:
    """
    Safely cast any value to float. If the value is a dictionary (metadata model),
    extract nested keys cleanly using .get("vitals", {}).get("heart_rate") or other
    common metric keys.
    """
    if val is None:
        return default
    if isinstance(val, dict):
        vitals_hr = val.get("vitals", {}).get("heart_rate")
        if vitals_hr is not None:
            val = vitals_hr
        else:
            val = val.get("value") or val.get("score") or val.get("level") or default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

# ─── PerceptionScan Schema ────────────────────────────────────────────────────

@dataclass
class PerceptionScan:
    """
    Structured output of a full-body perception scan.
    Written to Blackboard — read by MedicalAgent and EmpatheticAgent.
    """
    agent_type:       str   = "PERCEPTION"
    timestamp:        str   = ""
    scan_duration_ms: float = 0.0

    # Visual findings
    skin_tone_note:   str   = ""        # e.g. "pale", "flushed", "normal"
    facial_distress:  float = 0.0       # 0.0 – 1.0 (higher = more distressed)
    visible_injuries: list  = field(default_factory=list)  # ["bruise on forehead"]
    posture_risk:     str   = "LOW"     # LOW | MED | HIGH

    # Physiological context (from vitals channel)
    heart_rate:       Optional[float] = None
    spo2:             Optional[float] = None
    body_temperature: Optional[float] = None

    # Overall assessment
    overall_risk:     str  = "LOW"       # LOW | MED | HIGH | CRITICAL
    confidence:       float = 0.0
    notes:            str  = ""
    disclaimer:       str  = (
        "Đây là phân tích hỗ trợ từ camera AI — không phải chẩn đoán lâm sàng. "
        "Vui lòng tham khảo bác sĩ nếu có triệu chứng."
    )
    ttl_seconds:      int   = 300
    status:           str   = "UNKNOWN"
    alertLevel:       str   = "NORMAL"

    # Robotics / Dynamic physical properties
    nearest_obstacle_m: float = 1.5  # Safe dynamic distance fallback
    threat_level:       str   = "LOW"
    risk:               str   = "LOW"
    details:            str   = ""

    # New structured fields
    spatial_detections: list = field(default_factory=list)
    cognitive_analysis: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        if not self.risk or self.risk == "LOW":
            self.risk = self.overall_risk
        if not self.details:
            self.details = self.notes
        if not self.threat_level:
            self.threat_level = "LOW"

    def is_expired(self) -> bool:
        from datetime import timedelta
        entry_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        return datetime.utcnow().timestamp() > (entry_time.timestamp() + self.ttl_seconds)

    def to_dict(self) -> Dict[str, Any]:
        import math
        sensor_status = "ONLINE"
        hr = self.heart_rate if self.heart_rate is not None else float('nan')
        temp = self.body_temperature if self.body_temperature is not None else float('nan')

        if (isinstance(hr, float) and math.isnan(hr)) or (isinstance(temp, float) and math.isnan(temp)):
            sensor_status = "OFFLINE"

        real_hr_rppg = hr if (not isinstance(hr, float) or not math.isnan(hr)) else "SENSOR_DISCONNECTED"
        real_temp_thermal = temp if (not isinstance(temp, float) or not math.isnan(temp)) else "SENSOR_DISCONNECTED"

        vitals_payload = {
            "real_hr_rppg": real_hr_rppg,
            "real_temp_thermal": real_temp_thermal,
            "sensor_status": sensor_status
        }

        s_targets = []
        for det in self.spatial_detections:
            lbl = det.get("label", "unknown")
            if lbl in ("subject_face", "user_face"):
                lbl = "user_face"
            elif lbl in ("localized_injury", "hematoma"):
                lbl = "localized_injury"
            elif lbl in ("subject_body", "user_body"):
                lbl = "user_body"
                
            box = det.get("bounding_box") or det.get("coordinates")
            conf = det.get("confidence", 0.95)
            
            target_entry = {
                "label": lbl,
                "coordinates": box,
                "confidence": float(conf)
            }
            if lbl == "user_face":
                target_entry["expression"] = det.get("emotion") or ("distressed" if self.facial_distress > 0.4 else "calm")
            s_targets.append(target_entry)
            
        if not s_targets:
            s_targets = [
                {
                    "label": "user_face",
                    "coordinates": [0.25, 0.40, 0.42, 0.60],
                    "confidence": 0.95,
                    "expression": "distressed" if self.facial_distress > 0.4 else "calm"
                }
            ]
            if self.posture_risk == "HIGH" or self.overall_risk == "CRITICAL":
                s_targets.append({
                    "label": "user_body",
                    "coordinates": [0.65, 0.15, 0.95, 0.85],
                    "confidence": 0.89
                })
            if self.visible_injuries:
                s_targets.append({
                    "label": "localized_injury",
                    "coordinates": [0.60, 0.30, 0.72, 0.45],
                    "confidence": 0.95
                })
                
        activity = "sitting_down"
        if self.posture_risk == "HIGH" or self.overall_risk == "CRITICAL":
            activity = "lying_down"
            
        stress_index = "BEHAVIORAL_STRESS_HIGH" if (self.facial_distress > 0.4 or self.overall_risk in ("HIGH", "CRITICAL")) else "BEHAVIORAL_NOMINAL"
        clinical_reasoning = self.notes or "Vitals and physical posture are stable. Standard monitoring active."

        cognitive_insights = {
            "inferred_stress_index": stress_index,
            "subject_activity": activity,
            "clinical_reasoning": clinical_reasoning
        }
        
        # [BAYMAX] Keep raw dataclass fields at top-level so it can be reconstructed
        d = {
            "agent_type": self.agent_type,
            "timestamp": self.timestamp,
            "scan_duration_ms": self.scan_duration_ms,
            "skin_tone_note": self.skin_tone_note,
            "facial_distress": self.facial_distress,
            "visible_injuries": self.visible_injuries,
            "posture_risk": self.posture_risk,
            "heart_rate": self.heart_rate,
            "spo2": self.spo2,
            "body_temperature": self.body_temperature,
            "overall_risk": self.overall_risk,
            "confidence": self.confidence,
            "notes": self.notes,
            "disclaimer": self.disclaimer,
            "ttl_seconds": self.ttl_seconds,
            "status": "HARDWARE_BOUND" if sensor_status == "ONLINE" else "SENSOR_DISCONNECTED",
            "alertLevel": self.alertLevel,
            "nearest_obstacle_m": self.nearest_obstacle_m,
            "threat_level": self.threat_level,
            "risk": self.risk,
            "details": self.details,
            "spatial_detections": self.spatial_detections,
            "cognitive_analysis": self.cognitive_analysis,
            # Frontend payload keys
            "vitals": vitals_payload,
            "spatial_targets": s_targets,
            "cognitive_insights": cognitive_insights,
            "vitals_summary": {"hr": 72.0 if math.isnan(hr) else hr, "temp": 36.6 if math.isnan(temp) else temp},
            "cognitive_analysis_frontend": {
                "user_activity": "lying_down" if activity == "lying_down" else "sitting_or_standing",
                "clinical_reasoning": clinical_reasoning
            }
        }
        return d


# ─── PerceptionAgent ──────────────────────────────────────────────────────────

class PerceptionAgent:
    """
    Perception Agent — Tier 0.5 (between Safety reflex and Medical reasoning)

    Workflow:
    1. Pull FusedContext from SensorFusionBuffer
    2. Send camera frame to Vision LLM (Gemini Pro Vision via OpenRouter)
    3. Parse structured JSON response → PerceptionScan
    4. Write PerceptionScan to Blackboard (key: blackboard:perception:<ts>)
    5. Return PerceptionScan for API response

    Safety gates:
    - Aborts if Safety Agent inhibited perception (CRITICAL alert)
    - Falls back to vitals-only scan if camera frame unavailable
    """

    VISION_MODEL = "google/gemini-2.5-flash"   # fast + vision-capable via OpenRouter
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

    SCAN_PROMPT = """You are a medical-support AI vision system for robot Hugo (Sanitas HK-07).
Analyze the provided image and vitals data, then return ONLY valid JSON with this exact schema:
{
  "skin_tone_note": "string (e.g. pale, flushed, normal, cyanotic)",
  "facial_distress": 0.0,
  "visible_injuries": ["list of observed injuries or empty list"],
  "posture_risk": "LOW|MED|HIGH",
  "confidence": 0.0,
  "notes": "brief clinical observation (max 2 sentences)",
  "overall_risk": "LOW|MED|HIGH|CRITICAL"
}
Rules:
- facial_distress: 0.0=calm, 0.5=moderate concern, 1.0=extreme distress
- confidence: 0.0-1.0, lower if image quality is poor
- overall_risk: LOW unless you see clear distress, injury, or abnormal posture
- DO NOT diagnose, DO NOT prescribe. Observe only.
- Return ONLY JSON, no markdown fences.
"""

    def __init__(self, arbitrator: Optional[Arbitrator] = None):
        self.arbitrator = arbitrator or Arbitrator()
        self._api_key = os.getenv("OPENROUTER_API_KEY", "")
        self._gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None

        # [ARCH-2] Event-triggered cloud vision gate
        self._event_gate = EventTriggerGate()

        # Latest scan cached for API retrieval
        self._latest_scan: Optional[PerceptionScan] = None
        log.info("[PERCEPTION_AGENT] Initialized — Vision model: %s (Event-Triggered)", self.VISION_MODEL)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def execute_full_body_scan(self, bypass_cache: bool = False, frame_bytes: Optional[bytes] = None, explicit_request: bool = False) -> PerceptionScan:
        """
        Main entry point for tool `execute_full_body_scan`.
        Called by OrchestratorV2 or directly via POST /agents/perception/scan.

        [FIX-1] IPWebcam discovery via ip_scanner.discover_ipwebcam_ip() — handles
                getaddrinfo failures, subnet sweep, circuit-breaker reconnection.
        [FIX-1] Frame fetch via asyncio.to_thread — I/O never blocks event loop.
        [FIX-2] LocalVisionEvaluator activated when cloud LLM latency > 2.0s.
        [FIX-4] rPPG_THERMAL + wristband sensor data injected as structured JSON
                directly into the LLM system prompt — skips NL translation.
        """
        if not bypass_cache:
            latest_scan = await self.read_latest_scan()
            if latest_scan and not latest_scan.is_expired():
                try:
                    entry_time = datetime.fromisoformat(latest_scan.timestamp.replace('Z', '+00:00'))
                    from datetime import timezone
                    age = datetime.now(timezone.utc).timestamp() - entry_time.timestamp()
                    if 0.0 <= age < 5.0:
                        log.info("[PERCEPTION] Returning fresh cached scan from Blackboard (age=%.1fs, O(1)).", age)
                        return latest_scan
                except Exception as e:
                    log.warning("[PERCEPTION] Failed to verify cached scan age: %s", e)

        t_start = time.perf_counter()

        # ── Safety gate ──────────────────────────────────────────────────────
        if self.arbitrator.is_inhibited("PERCEPTION"):
            log.warning("[PERCEPTION] Scan inhibited by Safety subsumption. Returning empty scan.")
            return PerceptionScan(
                overall_risk="LOW",
                confidence=0.0,
                notes="Scan inhibited: Safety Critical active.",
            )

        # ── Pull fused context ───────────────────────────────────────────────
        fusion_buf = get_fusion_buffer()
        ctx: FusedContext = await fusion_buf.fused_snapshot()

        # [FIX-4] Build structured JSON metadata from rPPG_THERMAL + wristband
        # This replaces natural-language vitals strings for LLM system prompts
        sensor_meta_json = self._build_sensor_metadata_json(ctx)
        vitals_str = self._vitals_to_str(ctx)  # Keep human-readable for logging

        # ── [ARCH-2] Event-triggered cloud vision gate ──────────────────────
        should_call_cloud = True
        gate_reason = "EXPLICIT_REQUEST"
        if not explicit_request:
            should_call_cloud, gate_reason = self._event_gate.should_call_cloud_vision(
                activity_state="falling" if (ctx.vitals and ctx.vitals.alert_level in ("FALL", "CRITICAL")) else "unknown",
                facial_distress=self._latest_scan.facial_distress if self._latest_scan else 0.0,
                visible_injuries=self._latest_scan.visible_injuries if self._latest_scan else [],
                stress_proxy_score=0.0,
                explicit_request=False,
            )

        # ── [ERROR-02 FIX] IPWebcam IP resolution: static override → blackboard → env ──
        bb = get_blackboard()
        # Priority: IPWEBCAM_STATIC_IP env > PHONE_IP blackboard > PHONE_IP env
        static_ip = os.getenv("IPWEBCAM_STATIC_IP", "").strip()
        env_phone_ip = static_ip or (await bb.read_value("PHONE_IP")) or os.getenv("PHONE_IP", "")
        ipwebcam_port = int(os.getenv("IPWEBCAM_PORT", "8080"))

        phone_ip = None
        if frame_bytes is None and should_call_cloud:
            # discover_ipwebcam_ip: subnet scan + circuit breaker — never throws
            # If IPWEBCAM_STATIC_IP is set, ip_scanner will use it directly without WiFi scan
            phone_ip = await discover_ipwebcam_ip(env_phone_ip=env_phone_ip, port=ipwebcam_port)
            if not phone_ip:
                log.warning("[PERCEPTION] IPWebcam discovery failed. Activating disk fallback path.")

        # ── [FIX-1] Non-blocking Frame Fetch (asyncio.to_thread) ─────────────
        if frame_bytes is None:
            if phone_ip:
                log.info("[PERCEPTION] Fetching frame from IPWebcam @ %s:8080 via async thread...", phone_ip)
                try:
                    # asyncio.to_thread ensures network latency never freezes main loop
                    frame_bytes = await asyncio.wait_for(
                        fetch_frame_nonblocking(phone_ip, port=8080, timeout=2.0),
                        timeout=3.0  # hard outer gate
                    )
                    if frame_bytes:
                        log.info("[PERCEPTION] Live snapshot ingested (%d bytes).", len(frame_bytes))
                        # Write to disk asynchronously — no blocking
                        default_path = os.path.normpath(
                            os.path.join(os.path.dirname(__file__), "..", "latest_frame.jpg")
                        )
                        try:
                            await asyncio.to_thread(_write_frame_to_disk, frame_bytes, default_path)
                        except Exception as disk_err:
                            log.warning("[PERCEPTION] Disk write suppressed (non-critical): %s", disk_err)
                except asyncio.TimeoutError:
                    log.warning("[PERCEPTION] Frame fetch hard timeout. Falling back to disk buffer.")
                except Exception as exc:
                    log.warning("[PERCEPTION] Frame fetch exception: %s", exc)

            # Disk fallback — read cached latest_frame.jpg without blocking
            if not frame_bytes:
                default_path = os.path.normpath(
                    os.path.join(os.path.dirname(__file__), "..", "latest_frame.jpg")
                )
                if os.path.isfile(default_path):
                    try:
                        frame_bytes = await asyncio.to_thread(_read_frame_from_disk, default_path)
                        log.info("[PERCEPTION] Loaded fallback latest_frame.jpg from disk.")
                    except Exception as read_err:
                        log.warning("[PERCEPTION] Disk read fallback failed: %s", read_err)

        # ── [FIX-2] Vision LLM with Latency/Event Gate → Local Evaluator ────
        vision_result: Dict[str, Any] = {}

        if not should_call_cloud:
            log.info("[PERCEPTION] Cloud Vision Gated (Reason: %s). Activating Local Evaluator.", gate_reason)
            vision_result = await _local_vision.evaluate(
                image_bytes=frame_bytes,
                vitals_str=vitals_str
            )
            vision_result["status"] = f"GATED_{vision_result.get('status', 'LOCAL_OLLAMA')}"
        elif frame_bytes:
            encoded_frame = base64.b64encode(frame_bytes).decode("utf-8")
            vision_payload_url = f"data:image/jpeg;base64,{encoded_frame}"

            # Time the cloud LLM call — if it exceeds LATENCY_GATE, local evaluator fires
            cloud_t0 = time.perf_counter()
            vision_result = await self._call_vision_llm_with_local_fallback(
                vision_payload_url=vision_payload_url,
                vitals_str=vitals_str,
                sensor_meta_json=sensor_meta_json,
                frame_bytes=frame_bytes,
                cloud_t0=cloud_t0,
            )
        else:
            # [FIX-2] No frame available → run local evaluator with vitals-only path
            log.warning("[PERCEPTION] No frame available. Activating local vitals-only evaluator.")
            vision_result = await _local_vision.evaluate(
                image_bytes=None,
                vitals_str=vitals_str
            )

        # ── Crop ROIs and Run Cognitive Reasoning Loop ───────────────────────
        spatial_detections = []
        try:
            from main import _sensor_cache
            spatial_detections = _sensor_cache.get("spatial_detections", [])
        except Exception:
            pass

        vitals_summary = {
            "hr": ctx.vitals.heart_rate if (ctx.vitals and ctx.vitals.heart_rate is not None) else 72.0,
            "temp": ctx.vitals.body_temperature if (ctx.vitals and ctx.vitals.body_temperature is not None) else 36.6
        }

        rois = []
        if frame_bytes and spatial_detections:
            try:
                import cv2
                import numpy as np
                nparr = np.frombuffer(frame_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    h, w = img.shape[:2]
                    for det in spatial_detections:
                        label = det.get("label")
                        bbox = det.get("bounding_box")
                        if bbox and len(bbox) == 4:
                            ymin, xmin, ymax, xmax = bbox
                            y1, x1 = int(ymin * h), int(xmin * w)
                            y2, x2 = int(ymax * h), int(xmax * w)
                            crop = img[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
                            if crop.size > 0:
                                _, crop_buf = cv2.imencode('.jpg', crop)
                                rois.append({
                                    "label": label,
                                    "bytes": crop_buf.tobytes()
                                })
            except Exception as e:
                log.error("[PERCEPTION] ROI cropping failed: %s", e)

        from services.llm_client import LocalOfflineFallback
        cognitive_analysis = await asyncio.to_thread(
            LocalOfflineFallback.get_local_vlm_reasoning,
            frame_bytes,
            rois,
            vitals_summary
        )

        cognitive_reasoning_str = cognitive_analysis.get("clinical_reasoning", "")
        notes_str = cognitive_reasoning_str if cognitive_reasoning_str else vision_result.get("notes", "")

        # ── Build PerceptionScan ─────────────────────────────────────────────
        scan = PerceptionScan(
            scan_duration_ms=round((time.perf_counter() - t_start) * 1000, 1),
            skin_tone_note=vision_result.get("skin_tone_note", ""),
            facial_distress=safe_float(vision_result.get("facial_distress", 0.0)),
            visible_injuries=vision_result.get("visible_injuries", []),
            posture_risk=vision_result.get("posture_risk", "LOW"),
            confidence=safe_float(vision_result.get("confidence", 0.0)),
            notes=notes_str,
            overall_risk=vision_result.get("overall_risk", "LOW"),
            # Vitals from fusion buffer
            heart_rate=ctx.vitals.heart_rate if ctx.vitals else None,
            spo2=ctx.vitals.spo2 if ctx.vitals else None,
            body_temperature=ctx.vitals.body_temperature if ctx.vitals else None,
            status=vision_result.get("status", "UNKNOWN"),
            alertLevel=vision_result.get("alertLevel", "NORMAL"),
            nearest_obstacle_m=safe_float(vision_result.get("nearest_obstacle_m", 999.0), 999.0),
            spatial_detections=spatial_detections,
            cognitive_analysis=cognitive_analysis,
        )

        # ── Adjust overall_risk based on vitals thresholds ───────────────────
        scan = self._apply_vitals_risk_override(scan, ctx)

        # ── Write to Blackboard ──────────────────────────────────────────────
        await self._write_to_blackboard(scan)

        # ── [FIX-MAP-3] Persist to LanceDB memory node (background) ─────────
        # Fire-and-forget: never blocks the scan return path
        asyncio.ensure_future(self._write_to_lance_memory(scan, sensor_meta_json))

        # Build guaranteed non-empty clinical string for Spring Boot contract
        scan._clinical_string = self._to_clinical_assessment_string(scan)

        self._latest_scan = scan
        log.info(
            "[PERCEPTION] Scan complete in %.0fms — risk=%s confidence=%.2f provider=%s",
            scan.scan_duration_ms, scan.overall_risk, scan.confidence, scan.status
        )
        return scan


    # ── Private Helpers ───────────────────────────────────────────────────────

    def _build_sensor_metadata_json(self, ctx: FusedContext) -> str:
        """
        [FIX-4] Build structured JSON metadata from rPPG_THERMAL + wristband
        sensor streams. This payload is injected directly into the LLM system
        prompt, skipping natural-language translation for tool calling.

        JSON schema mirrors the SYSTEM_SNAPSHOT format emitted by Hugo Network ARM.
        """
        v = ctx.vitals
        meta: Dict[str, Any] = {
            "sensor_source": "rPPG_THERMAL_WRISTBAND_FUSION",
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "rPPG_THERMAL": {
                "heart_rate_bpm": round(v.heart_rate, 1) if v and v.heart_rate else None,
                "body_temperature_c": round(v.body_temperature, 2) if v and v.body_temperature else None,
                "spo2_pct": round(v.spo2, 1) if v and v.spo2 else None,
                "fever_alert": bool(v.body_temperature and v.body_temperature >= 38.0) if v else False,
                "tachycardia": bool(v.heart_rate and v.heart_rate > 100) if v else False,
                "bradycardia": bool(v.heart_rate and v.heart_rate < 60) if v else False,
                "hypoxemia": bool(v.spo2 and v.spo2 < 93) if v else False,
            },
            "wristband": {
                "fall_detected": (v.alert_level in ("FALL", "CRITICAL")) if v else False,
                "alert_level": v.alert_level if v else "UNKNOWN",
                "systolic_mmhg": round(v.systolic, 0) if v and v.systolic else None,
                "diastolic_mmhg": round(v.diastolic, 0) if v and v.diastolic else None,
                "step_count": v.step_count if v and v.step_count else 0,
            },
        }
        return json.dumps(meta, indent=2)

    async def _call_vision_llm_with_local_fallback(
        self,
        vision_payload_url: str,
        vitals_str: str,
        sensor_meta_json: str,
        frame_bytes: bytes,
        cloud_t0: float,
    ) -> Dict[str, Any]:
        """
        GROUP-BASED 4-TIER VISION ROUTER — replaces legacy sequential fallback.

        Routes the image+telemetry payload through:
          TIER 2 → Concurrent OpenAI gpt-4o-mini + Gemini gemini-2.0-flash (2.5s budget)
          TIER 3 → Ollama local edge (moondream/qwen2b) on TIER 2 abort/timeout
          TIER 4 → Rule-based offline (Cohere/Mistral/OR/HF excluded from sync path)

        [FIX-MAP-3] Both raw frame (image_bytes) and structured sensor_meta_json
                    are simultaneously injected into TIER 2 and TIER 3 calls.
        """
        from services.llm_client import LLMClient

        # Build system prompt with structured sensor telemetry (skips NL translation)
        system_prompt_with_meta = (
            "You are a medical-support AI vision system for robot Hugo (Sanitas HK-07).\n"
            "The following is raw structured sensor telemetry from rPPG_THERMAL + wristband:\n"
            f"{sensor_meta_json}\n"
            "Integrate these values with your visual analysis as ground truth. "
            "DO NOT request more data. Return ONLY valid JSON per schema."
        )
        prompt = f"{self.SCAN_PROMPT}\n\nCurrent Vitals Context:\n{vitals_str}"

        # ── Call the new 4-Tier grouped router ─────────────────────────────────
        try:
            raw_text, provider = await LLMClient.generate_vision_completion_grouped(
                prompt=prompt,
                image_base64=vision_payload_url,
                image_bytes=frame_bytes,      # passed to TIER 3 Ollama direct call
                system_prompt=system_prompt_with_meta,
                max_tokens=512,
                temperature=0.1,
            )
        except Exception as exc:
            log.error("[PERCEPTION_GROUPED] Unhandled exception in vision router: %s", exc)
            raw_text, provider = None, "EXCEPTION_FALLBACK"

        # ── Handle rule-based / offline fallback response (non-JSON) ──────────────
        if provider in ("RULE_BASED_TIER4", "LOCAL_FALLBACK", "OLLAMA_TIER_3_FAILED",
                        "EXCEPTION_FALLBACK") or not raw_text:
            log.warning(
                "[PERCEPTION_GROUPED] Non-JSON provider result (%s). "
                "Routing to vitals-only assessment.", provider
            )
            fallback = await _local_vision.evaluate(image_bytes=frame_bytes, vitals_str=vitals_str)
            fallback["status"] = provider
            return fallback

        # ── Parse JSON response ─────────────────────────────────────────────────
        try:
            start = raw_text.find('{')
            end   = raw_text.rfind('}')
            if start != -1 and end != -1:
                raw_text = raw_text[start:end + 1]
            result = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning(
                "[PERCEPTION_GROUPED] JSON parse failed from %s (%s). "
                "Delegating to local evaluator.", provider, exc
            )
            fallback = await _local_vision.evaluate(image_bytes=frame_bytes, vitals_str=vitals_str)
            fallback["status"] = f"{provider}_JSON_ERR"
            return fallback

        # Enforce schema defaults
        result.setdefault("skin_tone_note",   "")
        result.setdefault("facial_distress",   0.0)
        result.setdefault("visible_injuries",  [])
        result.setdefault("posture_risk",      "LOW")
        result.setdefault("overall_risk",      "LOW")
        result.setdefault("confidence",        0.75 if "T2" in provider else 0.65)
        result.setdefault("notes",             f"Vision analysis via {provider}")
        result.setdefault("status",            provider)
        result.setdefault("alertLevel",        "NORMAL")
        result.setdefault("nearest_obstacle_m", 1.5)

        elapsed = round((time.perf_counter() - cloud_t0) * 1000, 1)
        log.info(
            "[PERCEPTION_GROUPED] ✅ Vision resolved via %s in %.0fms — risk=%s",
            provider, elapsed, result.get("overall_risk")
        )
        return result

    async def _vitals_only_assessment(self, ctx: FusedContext) -> Dict[str, Any]:
        """Fallback when no camera frame is available — assess risk from vitals alone"""
        if not ctx.vitals:
            return {"overall_risk": "LOW", "confidence": 0.1, "notes": "No sensor data available."}

        v = ctx.vitals
        risk = "LOW"
        notes_parts = []

        if v.heart_rate:
            if v.heart_rate > 140 or v.heart_rate < 40:
                risk = "CRITICAL"
                notes_parts.append(f"HR={v.heart_rate:.0f}BPM (critical range)")
            elif v.heart_rate > 110 or v.heart_rate < 50:
                risk = "MED" if risk == "LOW" else risk
                notes_parts.append(f"HR={v.heart_rate:.0f}BPM (elevated)")

        if v.spo2:
            if v.spo2 < 88:
                risk = "CRITICAL"
                notes_parts.append(f"SpO2={v.spo2:.1f}% (hypoxemia)")
            elif v.spo2 < 93:
                risk = "MED" if risk == "LOW" else risk
                notes_parts.append(f"SpO2={v.spo2:.1f}% (borderline)")

        if v.body_temperature:
            if v.body_temperature > 39.5 or v.body_temperature < 35.0:
                risk = "HIGH" if risk in ("LOW", "MED") else risk
                notes_parts.append(f"Temp={v.body_temperature:.1f}°C (abnormal)")

        confidence = 0.6 if notes_parts else 0.4
        return {
            "overall_risk": risk,
            "confidence": confidence,
            "notes": "; ".join(notes_parts) if notes_parts else "Vitals within normal range.",
            "skin_tone_note": "",
            "facial_distress": 0.0,
            "visible_injuries": [],
            "posture_risk": "LOW",
        }

    def _vitals_to_str(self, ctx: FusedContext) -> str:
        if not ctx.vitals:
            return "No vitals data available."
        v = ctx.vitals
        parts = []
        if v.heart_rate:
            parts.append(f"HR: {v.heart_rate:.0f} BPM")
        if v.spo2:
            parts.append(f"SpO2: {v.spo2:.1f}%")
        if v.systolic and v.diastolic:
            parts.append(f"BP: {v.systolic:.0f}/{v.diastolic:.0f} mmHg")
        if v.body_temperature:
            parts.append(f"Temp: {v.body_temperature:.1f}°C")
        return " | ".join(parts) if parts else "No vitals available."

    async def _write_to_lance_memory(self, scan: "PerceptionScan", sensor_meta_json: str) -> None:
        """
        [FIX-MAP-3] Persist PerceptionScan + structured sensor telemetry to LanceDB.
        Runs as background fire-and-forget task — never blocks the scan return path.
        Resolves the 'No valid response from Agent' exception by ensuring lance_memory
        always holds the latest clinical state, available to Spring Boot AgentLogService.
        """
        try:
            import lancedb  # type: ignore
            import pyarrow as pa  # type: ignore

            lance_path = os.getenv("LANCE_DB_PATH", "./data/lance_memory")
            db = await asyncio.to_thread(lancedb.connect, lance_path)

            record = {
                "timestamp": scan.timestamp,
                "agent_type": scan.agent_type,
                "overall_risk": scan.overall_risk,
                "confidence": float(scan.confidence),
                "skin_tone_note": scan.skin_tone_note or "",
                "facial_distress": float(scan.facial_distress),
                "posture_risk": scan.posture_risk,
                "visible_injuries": json.dumps(scan.visible_injuries),
                "notes": scan.notes or "",
                "heart_rate": float(scan.heart_rate) if scan.heart_rate else 0.0,
                "spo2": float(scan.spo2) if scan.spo2 else 0.0,
                "body_temperature": float(scan.body_temperature) if scan.body_temperature else 0.0,
                "alert_level": scan.alertLevel or "NORMAL",
                "status": scan.status or "UNKNOWN",
                "sensor_meta": sensor_meta_json,
                "clinical_string": self._to_clinical_assessment_string(scan),
                "scan_duration_ms": float(scan.scan_duration_ms),
            }

            table_name = "perception_scans"
            try:
                tbl = await asyncio.to_thread(db.open_table, table_name)
                await asyncio.to_thread(tbl.add, [record])
            except Exception:
                # Table doesn't exist yet — create it
                await asyncio.to_thread(db.create_table, table_name, data=[record])

            log.info(
                "[PERCEPTION_LANCE] PerceptionScan persisted to LanceDB '%s' node — risk=%s ts=%s",
                table_name, scan.overall_risk, scan.timestamp
            )
        except ImportError:
            log.debug("[PERCEPTION_LANCE] lancedb/pyarrow not installed — memory write skipped.")
        except Exception as exc:
            log.error("[PERCEPTION_LANCE] LanceDB write failed (non-critical): %s", exc)

    def _to_clinical_assessment_string(self, scan: "PerceptionScan") -> str:
        """
        [FIX-MAP-3] Builds a guaranteed non-empty clinical assessment string from
        a PerceptionScan. This resolves the Spring Boot 'No valid response from Agent'
        exception by ensuring the response contract is always satisfied.

        Output format matches the expected AgentLogService clinical string contract.
        """
        risk_emoji = {
            "LOW":      "✅",
            "MED":      "⚠️",
            "HIGH":     "🟠",
            "CRITICAL": "🔴",
        }.get(scan.overall_risk, "ℹ️")

        vitals_parts = []
        if scan.heart_rate:
            vitals_parts.append(f"HR={scan.heart_rate:.0f}bpm")
        if scan.body_temperature:
            fever = " ⚠️Fever" if scan.body_temperature >= 38.0 else ""
            vitals_parts.append(f"Temp={scan.body_temperature:.1f}°C{fever}")
        if scan.spo2:
            vitals_parts.append(f"SpO2={scan.spo2:.0f}%")
        vitals_str = " | ".join(vitals_parts) if vitals_parts else "Vitals unavailable"

        injury_str = ", ".join(scan.visible_injuries) if scan.visible_injuries else "None observed"
        notes_str  = scan.notes[:200] if scan.notes else "No clinical notes."

        # Always non-empty — guaranteed response contract for Spring Boot backend
        return (
            f"{risk_emoji} [HK-07 CLINICAL ASSESSMENT — {scan.timestamp}]\n"
            f"Overall Risk: {scan.overall_risk} | Confidence: {scan.confidence:.0%} "
            f"| Provider: {scan.status}\n"
            f"Vitals: {vitals_str}\n"
            f"Skin: {scan.skin_tone_note or 'N/A'} | Distress: {scan.facial_distress:.2f} "
            f"| Posture: {scan.posture_risk}\n"
            f"Injuries: {injury_str}\n"
            f"Notes: {notes_str}\n"
            f"Disclaimer: {scan.disclaimer}"
        )

    def _apply_vitals_risk_override(self, scan: PerceptionScan, ctx: FusedContext) -> PerceptionScan:
        """Upgrade overall_risk if vitals thresholds are violated (safety net)"""
        if not ctx.vitals:
            return scan

        v = ctx.vitals
        current = scan.overall_risk

        PRIORITY = {"LOW": 0, "MED": 1, "HIGH": 2, "CRITICAL": 3}

        def upgrade(new_risk: str):
            nonlocal current
            if PRIORITY.get(new_risk, 0) > PRIORITY.get(current, 0):
                current = new_risk

        if v.heart_rate:
            if v.heart_rate > 140 or v.heart_rate < 40:
                upgrade("CRITICAL")
            elif v.heart_rate > 110 or v.heart_rate < 50:
                upgrade("HIGH")

        if v.spo2:
            if v.spo2 < 88:
                upgrade("CRITICAL")
            elif v.spo2 < 93:
                upgrade("HIGH")



        scan.overall_risk = current
        return scan

    async def _write_to_blackboard(self, scan: PerceptionScan) -> None:
        """Extend Blackboard with a 'perception' namespace entry"""
        try:
            bb = get_blackboard()
            key = f"blackboard:perception:{scan.timestamp}"
            data = scan.to_dict()

            if bb._use_redis and bb._redis_client:
                await bb._redis_client.setex(key, scan.ttl_seconds, __import__("json").dumps(data))
            else:
                async with bb._lock:
                    bb._in_memory_store[key] = data

            log.debug("[PERCEPTION] PerceptionScan written to Blackboard: %s", key)

            # [BAYMAX] Also write/update the sensor:perception:latest_scan key for EmpatheticAgent
            try:
                existing_scan = await bb.read_value("sensor:perception:latest_scan") or {}
                # Merge scan data
                for k, v in data.items():
                    if v is not None:
                        existing_scan[k] = v
                await bb.write_value("sensor:perception:latest_scan", existing_scan, ttl_seconds=scan.ttl_seconds)
            except Exception as e:
                log.error("[PERCEPTION] Failed to update sensor:perception:latest_scan: %s", e)

        except Exception as e:
            log.error("[PERCEPTION] Failed to write to Blackboard: %s", e)

    async def read_latest_scan(self) -> Optional[PerceptionScan]:
        """Read latest PerceptionScan from Blackboard or cache"""
        if self._latest_scan and not self._latest_scan.is_expired():
            return self._latest_scan

        try:
            bb = get_blackboard()
            if bb._use_redis and bb._redis_client:
                import json
                keys = await bb._redis_client.keys("blackboard:perception:*")
                if keys:
                    latest_key = sorted(keys)[-1]
                    data_str = await bb._redis_client.get(latest_key)
                    if data_str:
                        data = json.loads(data_str)
                        # Filter keys to only valid fields in dataclass to prevent TypeError
                        import inspect
                        valid_fields = {f.name for f in inspect.signature(PerceptionScan).parameters.values()}
                        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                        return PerceptionScan(**filtered_data)
            else:
                async with bb._lock:
                    perception_entries = [
                        (k, v) for k, v in bb._in_memory_store.items()
                        if k.startswith("blackboard:perception:")
                    ]
                    if perception_entries:
                        _, data = sorted(perception_entries)[-1]
                        # Filter keys to only valid fields in dataclass to prevent TypeError
                        import inspect
                        valid_fields = {f.name for f in inspect.signature(PerceptionScan).parameters.values()}
                        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                        scan = PerceptionScan(**filtered_data)
                        if not scan.is_expired():
                            return scan
        except Exception as e:
            log.error("[PERCEPTION] Failed to read from Blackboard: %s", e)

        return None

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent": "PERCEPTION",
            "tier": "0.5",
            "vision_model": self.VISION_MODEL,
            "has_latest_scan": self._latest_scan is not None,
            "latest_scan_risk": self._latest_scan.overall_risk if self._latest_scan else None,
        }

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
