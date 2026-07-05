"""
LocalVisionEvaluator — Offline Edge Vision-LLM via Ollama (Moondream2 / llava)

Replaces the failed cloud fallback chain (LiteLLM OpenRouter / HuggingFace) with a
strict local offline evaluation path when internet latency exceeds 2.0s.

Architecture:
  - Primary:  Ollama HTTP API (http://localhost:11434) running moondream2 or llava
  - Fallback: Rule-based vitals-only assessment (zero-dependency, always executes)

Latency budget: 2.0s probe → if exceeded, immediately activate this evaluator.
"""

import asyncio
import base64
import json
import logging
import os
import time
from typing import Optional, Dict, Any

import httpx

log = logging.getLogger("hk07.local_vision")

# ── Ollama Configuration ──────────────────────────────────────────────────────
OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_VISION_MODEL", "moondream")  # moondream | llava
OLLAMA_TIMEOUT   = float(os.getenv("OLLAMA_VISION_TIMEOUT_S", "8.0"))
LATENCY_GATE_S   = 2.0   # If cloud LLM latency > 2.0s → local evaluator kicks in

# ── Shared Availability Flag (module-level) ───────────────────────────────────
_ollama_available: Optional[bool] = None   # None = not probed yet
_ollama_probe_ts: float = 0.0
_OLLAMA_PROBE_TTL = 30.0                   # re-probe every 30s max
_resolved_vision_model: str = OLLAMA_MODEL


async def _pull_ollama_model(model_name: str):
    log.warning("[LOCAL_VISION] Dynamic pull initiated for model '%s'...", model_name)
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/pull", json={"name": model_name, "stream": False})
            if resp.status_code == 200:
                log.info("[LOCAL_VISION] Model '%s' pulled successfully!", model_name)
                global _ollama_available
                _ollama_available = True
            else:
                log.error("[LOCAL_VISION] Failed to pull model '%s': status=%d", model_name, resp.status_code)
    except Exception as e:
        log.error("[LOCAL_VISION] Error pulling model '%s': %s", model_name, e)

async def _probe_ollama() -> bool:
    """Probe Ollama /api/tags endpoint to confirm service is live."""
    global _ollama_available, _ollama_probe_ts, _resolved_vision_model
    now = time.monotonic()
    if _ollama_available is not None and (now - _ollama_probe_ts) < _OLLAMA_PROBE_TTL:
        return _ollama_available

    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                # Accept any moondream or llava variant
                matched_model = None
                if OLLAMA_MODEL in models:
                    matched_model = OLLAMA_MODEL
                else:
                    for m in models:
                        if OLLAMA_MODEL in m:
                            matched_model = m
                            break
                            
                if matched_model:
                    _resolved_vision_model = matched_model
                    log.info("[LOCAL_VISION] Ollama available. Model '%s' resolved to '%s'.", OLLAMA_MODEL, _resolved_vision_model)
                    _ollama_available = True
                else:
                    log.warning(
                        "[LOCAL_VISION] Ollama running but model '%s' not found. Available: %s",
                        OLLAMA_MODEL, models
                    )
                    # Trigger background dynamic pull
                    asyncio.create_task(_pull_ollama_model(OLLAMA_MODEL))
                    _ollama_available = False
            else:
                _ollama_available = False
    except Exception as exc:
        log.debug("[LOCAL_VISION] Ollama probe failed: %s", exc)
        _ollama_available = False

    _ollama_probe_ts = now
    return _ollama_available  # type: ignore


# ── Core Ollama Vision Call ───────────────────────────────────────────────────

async def _call_ollama_vision(
    image_bytes: bytes,
    vitals_str: str,
) -> Optional[str]:
    """
    POST to Ollama /api/generate with a base64 image payload.
    Returns raw text response or None on failure.
    Uses a strict OLLAMA_TIMEOUT budget — never blocks main loop.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "You are a medical-support AI vision system for robot Hugo (Sanitas HK-07). "
        "Analyze the provided image and the vitals context below.\n"
        f"Vitals: {vitals_str}\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "skin_tone_note": "string",\n'
        '  "facial_distress": 0.0,\n'
        '  "visible_injuries": [],\n'
        '  "posture_risk": "LOW|MED|HIGH",\n'
        '  "confidence": 0.0,\n'
        '  "notes": "brief clinical observation",\n'
        '  "overall_risk": "LOW|MED|HIGH|CRITICAL"\n'
        "}\n"
        "Rules: facial_distress 0-1. DO NOT diagnose. Return ONLY JSON."
    )

    payload = {
        "model": _resolved_vision_model,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 256}
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
    except Exception as exc:
        log.error("[LOCAL_VISION] Ollama API call failed: %s", exc)
    return None


# ── JSON Parser ───────────────────────────────────────────────────────────────

def _parse_vision_json(raw: str) -> Optional[Dict[str, Any]]:
    """Extract and parse the first JSON object from Ollama raw output."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(raw[start:end + 1])
        # Enforce schema defaults
        data.setdefault("skin_tone_note", "")
        data.setdefault("facial_distress", 0.0)
        data.setdefault("visible_injuries", [])
        data.setdefault("posture_risk", "LOW")
        data.setdefault("overall_risk", "LOW")
        data.setdefault("confidence", 0.65)
        data.setdefault("notes", f"Local vision analysis via Ollama/{OLLAMA_MODEL}")
        data.setdefault("status", "LOCAL_OLLAMA")
        data.setdefault("alertLevel", "NORMAL")
        return data
    except json.JSONDecodeError:
        return None


# ── Vitals-Only Fallback ──────────────────────────────────────────────────────

def _vitals_only_fallback(vitals_str: str) -> Dict[str, Any]:
    """
    Zero-dependency rule-based fallback when Ollama is also unavailable.
    Uses the vitals string to derive risk level without any I/O.
    Optimized to dynamically import and check `_sensor_cache` in-memory.
    """
    risk = "LOW"
    posture_risk = "LOW"
    
    # Try fetching real-time status from main._sensor_cache
    try:
        from main import _sensor_cache
        vitals = _sensor_cache.get("vitals") or {}
        fall = _sensor_cache.get("fall_detected", False)
        fever = _sensor_cache.get("fever_alert", False)
        
        # In-memory validation
        hr = vitals.get("hr", 0.0)
        temp = vitals.get("temp", 0.0)
        spo2 = vitals.get("spo2", 100.0)
        
        if fall or fever or hr > 140 or hr < 40 or temp > 38.5 or spo2 < 88:
            risk = "CRITICAL"
        elif hr > 100 or temp > 37.5 or spo2 < 95:
            risk = "HIGH"
            
        if fall:
            posture_risk = "HIGH"
            
        notes = f"[DEGRADED MODE] Mất kết nối Cloud Vision. Chế độ offline cục bộ. Chỉ số: HR={hr:.0f} bpm, Temp={temp:.1f} C, SpO2={spo2:.0f}%, Fall={fall}"
    except Exception as exc:
        log.warning("[LOCAL_VISION] Error querying _sensor_cache, fallback to parsing vitals_str: %s", exc)
        # Fallback to string heuristic if main._sensor_cache import fails or key is missing
        vs_lower = vitals_str.lower()
        if any(k in vs_lower for k in ["critical", "emergency", ">140", "<40", "spo2<88", "fall"]):
            risk = "CRITICAL"
        elif any(k in vs_lower for k in ["high", "fever", "tachycardia", "bradycardia"]):
            risk = "HIGH"
        notes = f"[DEGRADED MODE] Mất kết nối Cloud Vision. Không có dữ liệu VLM. Chỉ số: {vitals_str}"

    return {
        "skin_tone_note": "",
        "facial_distress": 0.0,
        "visible_injuries": [],
        "posture_risk": posture_risk,
        "overall_risk": risk,
        "confidence": 0.3,
        "notes": notes,
        "status": "DEGRADED_LOCAL_OFFLINE",
        "alertLevel": "NORMAL" if risk == "LOW" else "WARNING",
        "nearest_obstacle_m": 1.5,
    }


# ── Main Public Interface ─────────────────────────────────────────────────────

class LocalVisionEvaluator:
    """
    Drop-in replacement for cloud vision LLM.
    Called by PerceptionAgent when internet latency > LATENCY_GATE_S or
    when all cloud tiers are circuit-broken.

    Usage:
        evaluator = LocalVisionEvaluator()
        result = await evaluator.evaluate(image_bytes=frame_bytes, vitals_str=vitals)
    """

    def __init__(self):
        self._latency_gate = LATENCY_GATE_S

    async def is_available(self) -> bool:
        """Non-blocking availability check (cached 30s TTL)."""
        return await _probe_ollama()

    async def evaluate(
        self,
        image_bytes: Optional[bytes],
        vitals_str: str,
    ) -> Dict[str, Any]:
        """
        Main evaluation entry point.
        Tries Ollama → falls back to rule-based.
        Enforces strict async timeout — never blocks > OLLAMA_TIMEOUT.

        Args:
            image_bytes: Raw JPEG bytes from IPWebcam / latest_frame.jpg
            vitals_str:  Human-readable vitals string from SensorFusionBuffer

        Returns:
            Dict matching PerceptionScan field schema.
        """
        t_start = time.perf_counter()
        ollama_ok = await _probe_ollama()

        if ollama_ok and image_bytes:
            try:
                raw_text = await asyncio.wait_for(
                    _call_ollama_vision(image_bytes, vitals_str),
                    timeout=OLLAMA_TIMEOUT
                )
                if raw_text:
                    parsed = _parse_vision_json(raw_text)
                    if parsed:
                        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
                        log.info(
                            "[LOCAL_VISION] Ollama/%s completed in %.0fms — risk=%s",
                            OLLAMA_MODEL, elapsed_ms, parsed.get("overall_risk")
                        )
                        return parsed
                    log.warning("[LOCAL_VISION] Ollama returned unparseable JSON: %s", raw_text[:120])
            except asyncio.TimeoutError:
                log.error("[LOCAL_VISION] Ollama hard timeout (%.1fs). Routing to rule-based.", OLLAMA_TIMEOUT)
            except Exception as exc:
                log.error("[LOCAL_VISION] Unexpected Ollama error: %s", exc)

        # Final safety net — always succeeds, zero-dependency
        log.warning("[LOCAL_VISION] Activating zero-dependency rule-based vitals assessment.")
        return _vitals_only_fallback(vitals_str)

    @staticmethod
    def get_status() -> Dict[str, Any]:
        return {
            "ollama_url": OLLAMA_BASE_URL,
            "model": OLLAMA_MODEL,
            "available": _ollama_available,
            "latency_gate_s": LATENCY_GATE_S,
        }
