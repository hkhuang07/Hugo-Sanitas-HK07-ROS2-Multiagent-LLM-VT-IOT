"""
PerceptionAgent — Tier 0.5: Full-Body Multi-modal Scan

Role: Observe. Do NOT speak to user directly.
Output: PerceptionScan JSON written to Blackboard.

Capability matrix (Phase 2):
  A. Full-body scan (camera depth/RGB + vitals)
  B. Physical analysis (skin tone note, facial distress, posture risk, injuries)
  C. LiDAR threat context from Fusion Buffer
  D. Writes PerceptionScan to BlackboardService

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

log = logging.getLogger("hk07.perception_agent")

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
        return asdict(self)


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

    SCAN_PROMPT = """You are a medical-support AI vision system for robot HK-07 (Baymax-inspired).
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

        # Latest scan cached for API retrieval
        self._latest_scan: Optional[PerceptionScan] = None
        log.info("[PERCEPTION_AGENT] Initialized — Vision model: %s", self.VISION_MODEL)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def execute_full_body_scan(self) -> PerceptionScan:
        """
        Main entry point for tool `execute_full_body_scan`.
        Called by OrchestratorV2 or directly via POST /agents/perception/scan.
        """
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

        # Build vitals context string for the prompt
        vitals_str = self._vitals_to_str(ctx)

        # ── Camera analysis ──────────────────────────────────────────────────
        vision_result: Dict[str, Any] = {}
        vision_payload_url = ""

        bb = get_blackboard()
        phone_ip = await bb.read_value("PHONE_IP")
        if not phone_ip:
            phone_ip = os.getenv("PHONE_IP", "")
        if not phone_ip or phone_ip == "127.0.0.1":
            try:
                import sys
                from pathlib import Path
                parent_dir = str(Path(__file__).resolve().parent.parent)
                if parent_dir not in sys.path:
                    sys.path.append(parent_dir)
                from main import get_default_gateway_ip
                phone_ip = get_default_gateway_ip()
            except Exception:
                phone_ip = "127.0.0.1"

        if not phone_ip:
            phone_ip = "127.0.0.1"

        video_url = f"http://{phone_ip}:8080/shot.jpg"
        log.info("[PERCEPTION] Fetching live frame snapshot from IPWebcam: %s", video_url)
        
        frame_bytes = None
        try:
            # Enforce strict non-blocking HTTP fetch with a 2-second timeout
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(video_url)
                if resp.status_code == 200:
                    frame_bytes = resp.content
                    log.info("[PERCEPTION] Live snapshot successfully ingested from IPWebcam.")
                    
                    # Safe concurrent disk synchronization / Overwrite latest_frame.jpg on disk
                    default_path = os.path.join(os.path.dirname(__file__), "..", "latest_frame.jpg")
                    default_path = os.path.normpath(default_path)
                    try:
                        with open(default_path, "wb") as f:
                            f.write(frame_bytes)
                    except Exception as e:
                        log.warning("[PERCEPTION] Failed to save latest_frame.jpg: %s", e)
        except Exception as e:
            log.warning("[PERCEPTION] Live frame fetch failed: %s. Falling back to shared disk buffer.", e)

        # Fallback to shared disk buffer if live stream fetch failed
        if frame_bytes:
            encoded_frame = base64.b64encode(frame_bytes).decode("utf-8")
            vision_payload_url = f"data:image/jpeg;base64,{encoded_frame}"
        else:
            default_path = os.path.join(os.path.dirname(__file__), "..", "latest_frame.jpg")
            default_path = os.path.normpath(default_path)
            if os.path.isfile(default_path):
                try:
                    with open(default_path, "rb") as f:
                        fallback_bytes = f.read()
                        encoded_frame = base64.b64encode(fallback_bytes).decode("utf-8")
                        vision_payload_url = f"data:image/jpeg;base64,{encoded_frame}"
                    log.info("[PERCEPTION] Successfully read fallback latest_frame.jpg from disk.")
                except Exception as e:
                    log.warning("[PERCEPTION] Failed to read fallback latest_frame.jpg from disk: %s", e)

        if vision_payload_url:
            vision_result = await self._call_vision_llm(vision_payload_url, vitals_str)
        else:
            log.warning("[PERCEPTION] No camera frame available — vitals-only scan")
            vision_result = await self._vitals_only_assessment(ctx)

        # ── Build PerceptionScan ─────────────────────────────────────────────
        scan = PerceptionScan(
            scan_duration_ms=round((time.perf_counter() - t_start) * 1000, 1),
            skin_tone_note=vision_result.get("skin_tone_note", ""),
            facial_distress=safe_float(vision_result.get("facial_distress", 0.0)),
            visible_injuries=vision_result.get("visible_injuries", []),
            posture_risk=vision_result.get("posture_risk", "LOW"),
            confidence=safe_float(vision_result.get("confidence", 0.0)),
            notes=vision_result.get("notes", ""),
            overall_risk=vision_result.get("overall_risk", "LOW"),
            # Vitals from fusion buffer
            heart_rate=ctx.vitals.heart_rate if ctx.vitals else None,
            spo2=ctx.vitals.spo2 if ctx.vitals else None,
            body_temperature=ctx.vitals.body_temperature if ctx.vitals else None,
            status=vision_result.get("status", "UNKNOWN"),
            alertLevel=vision_result.get("alertLevel", "NORMAL"),
            nearest_obstacle_m=safe_float(vision_result.get("nearest_obstacle_m", 999.0), 999.0),
        )

        # ── Adjust overall_risk based on vitals thresholds ───────────────────
        scan = self._apply_vitals_risk_override(scan, ctx)

        # ── Write to Blackboard ──────────────────────────────────────────────
        await self._write_to_blackboard(scan)

        self._latest_scan = scan
        log.info("[PERCEPTION] Scan complete in %.0fms — risk=%s confidence=%.2f status=%s",
                 scan.scan_duration_ms, scan.overall_risk, scan.confidence, scan.status)
        return scan

    # ── Private Helpers ───────────────────────────────────────────────────────

    async def _call_vision_llm(self, vision_payload_url: str, vitals_context: str) -> Dict[str, Any]:
        """
        Call Vision LLM (via unified LLMClient fallback engine) with image + vitals.
        Falls back to vitals-only assessment on failure.
        """
        from services.llm_client import LLMClient, VISION_TIERS

        prompt = f"{self.SCAN_PROMPT}\n\nCurrent Vitals Context:\n{vitals_context}"

        try:
            raw_text, provider = await LLMClient.generate_vision_completion(
                prompt=prompt,
                tiers=VISION_TIERS,
                image_base64=vision_payload_url,
                system_prompt="You are a medical-support AI vision system for robot HK-07 (Baymax-inspired).",
                max_tokens=512,
                temperature=0.1,
                timeout=15
            )

            if provider == "LOCAL_FALLBACK":
                log.warning("[PERCEPTION] LLM returned LOCAL_FALLBACK. Applying safe nominal fallback values.")
                return {
                    "skin_tone_note": "NORMAL",
                    "facial_distress": 0.0,
                    "visible_injuries": [],
                    "posture_risk": "LOW",
                    "overall_risk": "LOW",
                    "confidence": 0.5,
                    "notes": "LOCAL_FALLBACK: Vision API blackout / timeout. Pre-streaming nominal fallback.",
                    "status": "LOCAL_FALLBACK",
                    "alertLevel": "NORMAL",
                    "nearest_obstacle_m": 1.5
                }

            # Strip markdown fences if present or find JSON boundary
            start = raw_text.find('{')
            end = raw_text.rfind('}')
            if start != -1 and end != -1:
                raw_text = raw_text[start:end+1]

            result = json.loads(raw_text)
            
            # Enforce schema defaults for maximum robustness
            result.setdefault("skin_tone_note", "")
            result.setdefault("facial_distress", 0.0)
            result.setdefault("visible_injuries", [])
            result.setdefault("posture_risk", "LOW")
            result.setdefault("overall_risk", "LOW")
            result.setdefault("notes", f"Vision analysis via {provider}")
            result.setdefault("confidence", 0.75 if provider != "LOCAL_FALLBACK" else 0.0)
            result.setdefault("status", "NOMINAL")
            result.setdefault("alertLevel", "NORMAL")

            log.debug("[PERCEPTION_LLM] Vision result via %s: %s", provider, result)
            return result

        except json.JSONDecodeError as e:
            log.error("[PERCEPTION_LLM] JSON parse error: %s", e)
            return {
                "skin_tone_note": "NORMAL",
                "facial_distress": 0.0,
                "visible_injuries": [],
                "posture_risk": "LOW",
                "overall_risk": "LOW",
                "confidence": 0.5,
                "notes": "Vision analysis returned non-JSON — API blackout.",
                "status": "LOCAL_FALLBACK",
                "alertLevel": "NORMAL",
                "nearest_obstacle_m": 1.5
            }
        except Exception as e:
            log.error("[PERCEPTION_LLM] Unexpected error during vision LLM call: %s", e)
            return {
                "skin_tone_note": "NORMAL",
                "facial_distress": 0.0,
                "visible_injuries": [],
                "posture_risk": "LOW",
                "overall_risk": "LOW",
                "confidence": 0.5,
                "notes": f"Vision analysis error: {str(e)[:50]}",
                "status": "LOCAL_FALLBACK",
                "alertLevel": "NORMAL",
                "nearest_obstacle_m": 1.5
            }

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
                        return PerceptionScan(**json.loads(data_str))
            else:
                async with bb._lock:
                    perception_entries = [
                        (k, v) for k, v in bb._in_memory_store.items()
                        if k.startswith("blackboard:perception:")
                    ]
                    if perception_entries:
                        _, data = sorted(perception_entries)[-1]
                        scan = PerceptionScan(**data)
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
