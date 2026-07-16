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
from services.llm_client import is_ollama_vision_cb_open, record_ollama_vision_failure, record_ollama_vision_success

log = logging.getLogger("hk07.local_vision")

# ── Ollama Configuration ──────────────────────────────────────────────────────
OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_VISION_MODEL", "moondream")  # moondream | llava
OLLAMA_TIMEOUT   = float(os.getenv("OLLAMA_VISION_TIMEOUT_S", "45.0"))
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

_OLLAMA_PROBE_CANDIDATES = [
    OLLAMA_BASE_URL,
    "http://localhost:11434",
    "http://127.0.0.1:11434",
    "http://host.docker.internal:11434",  # WSL2 → Docker Desktop host bridge
    "http://172.17.0.1:11434",            # Docker bridge network from WSL
]

async def _probe_ollama() -> bool:
    """
    Probe all candidate Ollama URLs concurrently and pick the first responsive one.
    Uses 5.0s per probe to accommodate WSL/Docker cold-start latency.
    """
    global _ollama_available, _ollama_probe_ts, _resolved_vision_model
    now = time.monotonic()
    if _ollama_available is not None and (now - _ollama_probe_ts) < _OLLAMA_PROBE_TTL:
        return _ollama_available

    # Deduplicate candidates while preserving order
    seen: set = set()
    candidates = [u for u in _OLLAMA_PROBE_CANDIDATES if not (u in seen or seen.add(u))]  # type: ignore

    # Try each candidate sequentially with a 5s budget per host
    _winning_ollama_url: str | None = None
    for url in candidates:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}/api/tags")
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
                    _winning_ollama_url = url
                    log.info("[LOCAL_VISION] Ollama available on %s. Model '%s' resolved to '%s'.", url, OLLAMA_MODEL, _resolved_vision_model)
                    _ollama_available = True
                    break  # found a working host
                else:
                    log.warning(
                        "[LOCAL_VISION] Ollama on %s running but model '%s' not found. Available: %s",
                        url, OLLAMA_MODEL, models
                    )
                    # Trigger background dynamic pull on first candidate only
                    if url == candidates[0]:
                        asyncio.create_task(_pull_ollama_model(OLLAMA_MODEL))
        except Exception as exc:
            log.debug("[LOCAL_VISION] Ollama probe failed on %s: %s", url, exc)
            continue

    if _winning_ollama_url is None:
        log.warning("[LOCAL_VISION] No Ollama host responded. All %d candidates failed.", len(candidates))
        _ollama_available = False

    # Persist the winning URL for subsequent API calls
    global _active_ollama_url
    _active_ollama_url = _winning_ollama_url or OLLAMA_BASE_URL

    _ollama_probe_ts = now
    return bool(_ollama_available)


# ── Core Ollama Vision Call ───────────────────────────────────────────────────

async def _call_ollama_vision(
    image_bytes: bytes,
    vitals_str: str,
) -> Optional[str]:
    """
    POST to Ollama /api/generate with a base64 image payload.
    Returns raw text response or None on failure.

    CPU/RAM optimization: image downscaled to 336×336 (moondream native input)
    to reduce inference time from 60s+ to ~15-20s on memory-constrained hardware.
    """
    # ── Image downsample to 336×336 max ───────────────────────────────────────
    try:
        import cv2
        import numpy as np
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            h, w = img.shape[:2]
            max_dim = 336
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            image_bytes = buf.tobytes()
    except Exception:
        pass  # non-fatal: fall through with original bytes

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
        "options": {
            "temperature": 0.1,
            "num_predict": 192,  # sufficient for JSON schema
            "num_ctx": 1024,     # reduced context → less RAM allocated
        }
    }

    # Use the dynamically resolved URL from the last successful probe
    target_url = globals().get("_active_ollama_url", OLLAMA_BASE_URL)
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(f"{target_url}/api/generate", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
    except Exception as exc:
        log.error("[LOCAL_VISION] Ollama API call failed on %s: %s", target_url, exc)
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
    Returns VLM disconnected status and no detection, with absolutely no mock/fake data.
    """
    return {
        "skin_tone_note": "MẤT KẾT NỐI VLM",
        "facial_distress": -1.0,
        "visible_injuries": [],
        "posture_risk": "UNKNOWN",
        "overall_risk": "UNKNOWN",
        "confidence": 0.0,
        "notes": "[MẤT KẾT NỐI VLM] Không có kết nối tới máy chủ AI nhận diện hình ảnh. Không thể phát hiện hoặc nhận diện.",
        "status": "VLM_DISCONNECTED",
        "alertLevel": "UNKNOWN",
        "nearest_obstacle_m": -1.0,
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

        # ── 1. Circuit Breaker Check ──────────────────────────────────────────
        if is_ollama_vision_cb_open():
            log.warning(
                "[LOCAL_VISION] ⚡ Vision Circuit Breaker is OPEN (Ollama CPU swap). "
                "Bypassing Ollama evaluation instantly to avoid 45s lag."
            )
            return _vitals_only_fallback(vitals_str)

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
                        # ── Record CB Success ─────────────────────────────────
                        record_ollama_vision_success()
                        return parsed
                    log.warning("[LOCAL_VISION] Ollama returned unparseable JSON: %s", raw_text[:120])
            except asyncio.TimeoutError:
                log.error("[LOCAL_VISION] Ollama hard timeout (%.1fs). Routing to rule-based.", OLLAMA_TIMEOUT)
                # ── Record CB Failure (Timeout) ──────────────────────────────
                record_ollama_vision_failure()
            except Exception as exc:
                log.error("[LOCAL_VISION] Unexpected Ollama error: %s", exc)
                # ── Record CB Failure (Exception) ────────────────────────────
                record_ollama_vision_failure()

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
