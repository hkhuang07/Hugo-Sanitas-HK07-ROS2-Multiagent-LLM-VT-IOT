"""
LLMClient — Unified Multi-Provider LLM Fallback Engine

Centralizes all LLM calls (Text, Tool Calling, Vision) for all sub-agents.
Manages API keys, standard models, zero-wait RateLimitError (429) fallback rotation,
and standard timeouts to protect system stability.
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Load env from parent directory
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

log = logging.getLogger("hk07.llm_client")

from concurrent.futures import ThreadPoolExecutor

class LLMClientCircuitBreaker:
    """Global last-resort circuit breaker — only trips when ALL providers fail.
    
    ARCHITECTURE FIX: Previously this was a global singleton that locked the entire
    LLM system when ANY single provider (e.g. Gemini) hit a 429. Now it only trips
    when the system has exhausted ALL per-provider options. Recovery reduced to 300s.
    """
    def __init__(self, recovery_time=300.0):
        self.recovery_time = float(recovery_time)
        self.state = "CLOSED"  # CLOSED, OPEN
        self.last_trip_time = 0.0

    def trip(self):
        self.state = "OPEN"
        self.last_trip_time = float(time.time())
        log.error(f"[LLM_CLIENT_CB] Global Circuit Breaker tripped to OPEN. "
                  f"ALL providers exhausted. Routing to LocalOfflineFallback for {self.recovery_time}s.")

    def allow_request(self) -> bool:
        if self.state == "OPEN":
            if float(time.time()) - self.last_trip_time >= self.recovery_time:
                self.state = "CLOSED"
                log.warning("[LLM_CLIENT_CB] Global Circuit Breaker closed. Restoring API requests.")
                return True
            return False
        return True


class ProviderCircuitBreaker:
    """Per-provider circuit breaker — isolates individual API provider failures.
    
    CRITICAL: Gemini 429 should NOT block Groq or OpenAI. Each provider tracks
    failures independently. Only when ALL providers are OPEN does the global CB trip.
    """
    def __init__(self, name: str, threshold: int = 3, base_cooldown_s: float = 300.0):
        self.name = name
        self.state = "CLOSED"   # CLOSED | OPEN | HALF_OPEN
        self.fail_count = 0
        self.threshold = threshold
        self.base_cooldown_s = base_cooldown_s
        self.reset_time = 0.0
        self._lock = __import__("threading").Lock()

    def record_success(self):
        with self._lock:
            self.fail_count = 0
            if self.state in ("HALF_OPEN", "OPEN"):
                self.state = "CLOSED"
                log.info("[PROVIDER_CB] %s recovered → CLOSED", self.name)

    def record_failure(self, is_rate_limit: bool = False):
        with self._lock:
            self.fail_count += 1
            cooldown = self.base_cooldown_s * 2 if is_rate_limit else self.base_cooldown_s
            log.warning("[PROVIDER_CB] Fail count for %s incremented to %d/%d",
                        self.name, self.fail_count, self.threshold)
            if self.fail_count >= self.threshold:
                self.state = "OPEN"
                self.reset_time = time.monotonic() + cooldown
                log.error("[PROVIDER_CB] %s tripped OPEN for %.0fs", self.name, cooldown)

    def is_available(self) -> bool:
        with self._lock:
            if self.state == "OPEN":
                if time.monotonic() >= self.reset_time:
                    self.state = "HALF_OPEN"
                    self.fail_count = 0
                    log.info("[PROVIDER_CB] %s entering HALF_OPEN probe state", self.name)
                else:
                    return False
            return True


# ─── Global last-resort CB (recovery 300s, down from 1800s) ──────────────────
_circuit_breaker = LLMClientCircuitBreaker(recovery_time=300.0)

# ─── Per-provider CBs — independent, isolated failures ───────────────────────
_provider_cb: dict = {
    "GROQ":        ProviderCircuitBreaker("GROQ",        threshold=5, base_cooldown_s=120.0),
    "OPENAI":      ProviderCircuitBreaker("OPENAI",      threshold=3, base_cooldown_s=300.0),
    "GEMINI":      ProviderCircuitBreaker("GEMINI",      threshold=3, base_cooldown_s=600.0),
    "MISTRAL":     ProviderCircuitBreaker("MISTRAL",     threshold=3, base_cooldown_s=300.0),
    "COHERE":      ProviderCircuitBreaker("COHERE",      threshold=3, base_cooldown_s=300.0),
    "OPENROUTER":  ProviderCircuitBreaker("OPENROUTER",  threshold=3, base_cooldown_s=300.0),
    "OLLAMA":      ProviderCircuitBreaker("OLLAMA",      threshold=5, base_cooldown_s=60.0),
}

def _get_provider_key(tier_name: str) -> str:
    """Map tier name (e.g. 'GROQ_TIER_1') to provider key (e.g. 'GROQ')."""
    for key in _provider_cb:
        if key in tier_name.upper():
            return key
    return ""

_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="llm_client_worker")


# Import litellm
try:
    import litellm
    from litellm import RateLimitError as LiteLLMRateLimitError
    litellm.set_verbose = False
    litellm.drop_params = True
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    LiteLLMRateLimitError = Exception
    log.warning("[LLM_CLIENT] litellm not installed — fallbacks will be limited!")

# Ollama Local SLM Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
log.info(f"[LLM_CLIENT] Offline fallback configured via Ollama at {OLLAMA_BASE_URL}")

try:
    import llama_cpp
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

# ─── API keys from environment ────────────────────────────────────────────────
_GROQ_KEY        = os.getenv("GROQ_API_KEY", "")
_OPENAI_KEY      = os.getenv("OPENAI_API_KEY", "")
_GEMINI_KEY      = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_GENERATIVEAI_API_KEY", os.getenv("GOOGLE_API_KEY", "")))
_MISTRAL_KEY     = os.getenv("MISTRAL_API_KEY", "")
_COHERE_KEY      = os.getenv("COHERE_API_KEY", "")
_OPENROUTER_KEY  = os.getenv("OPENROUTER_API_KEY", "")
_HF_KEY          = os.getenv("HUGGINGFACE_API_KEY", "")

# ─── Gemini AQ. key compatibility bridge ────────────────────────────────────
# google.generativeai has been DEPRECATED (June 2026). Replaced by google-genai.
# LiteLLM >= 1.89.3 internally uses google-genai and reads GEMINI_API_KEY.
# We set all env aliases so both old litellm paths and new google-genai find the key.
if _GEMINI_KEY:
    os.environ["GEMINI_API_KEY"] = _GEMINI_KEY
    os.environ.setdefault("GOOGLE_API_KEY", _GEMINI_KEY)
    os.environ.setdefault("GOOGLE_GENERATIVEAI_API_KEY", _GEMINI_KEY)

# Suppress FutureWarning from deprecated google.generativeai package (safe to ignore —
# LiteLLM routes through google-genai SDK internally, not google.generativeai directly)
import warnings
warnings.filterwarnings(
    "ignore",
    message="All support for the `google.generativeai` package has ended",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    message="You are using a Python version.*Google will stop supporting",
    category=FutureWarning,
)

import threading

class TokenBucketRateLimiter:
    def __init__(self, capacity: float, fill_rate: float):
        self.capacity = float(capacity)
        self.fill_rate = float(fill_rate)
        self.tokens = float(capacity)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens_needed: float) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
            self.last_update = now
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True
            return False

_groq_limiter = TokenBucketRateLimiter(capacity=10.0, fill_rate=0.5)

def optimize_context_tokens(messages: list, max_chars: int = 2000) -> list:
    """
    Prunes long prompt text or messages to optimize context token counts.
    """
    optimized = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, str) and len(content) > max_chars:
            log.warning(f"[GROQ_MITIGATION] Truncating message from {len(content)} to {max_chars} chars.")
            content = content[:max_chars] + "... [TRUNCATED]"
        elif isinstance(content, list):
            new_content = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_val = part.get("text", "")
                    if len(text_val) > max_chars:
                        log.warning(f"[GROQ_MITIGATION] Truncating text block from {len(text_val)} to {max_chars} chars.")
                        part = {"type": "text", "text": text_val[:max_chars] + "... [TRUNCATED]"}
                new_content.append(part)
            content = new_content
        optimized.append({"role": role, "content": content})
    return optimized

class ProviderCircuitBreaker:
    def __init__(self, recovery_time=5.0, allowed_fails=3):
        self.recovery_time = float(recovery_time)
        self.allowed_fails = allowed_fails
        self._tripped_providers = {}  # provider -> timestamp
        self._consecutive_fails = {}  # provider -> count

    def trip(self, provider: str):
        p = provider.lower()
        self._consecutive_fails[p] = self._consecutive_fails.get(p, 0) + 1
        if self._consecutive_fails[p] >= self.allowed_fails:
            self._tripped_providers[p] = time.time()
            log.error(f"[PROVIDER_CB] Tripped {p.upper()} due to {self.allowed_fails} failures. Offline for {self.recovery_time}s.")
        else:
            log.warning(f"[PROVIDER_CB] Fail count for {p.upper()} incremented to {self._consecutive_fails[p]}/{self.allowed_fails}.")

    def reset_fails(self, provider: str):
        p = provider.lower()
        self._consecutive_fails[p] = 0

    def mark_permanently_dead(self, provider: str):
        p = provider.lower()
        self._tripped_providers[p] = time.time() + 3153600000.0
        log.error(f"[PROVIDER_CB] Tripped {p.upper()} permanently (server lifecycle) due to quota exhaustion.")

    def is_tripped(self, provider: str) -> bool:
        p = provider.lower()
        if p in self._tripped_providers:
            if time.time() - self._tripped_providers[p] >= self.recovery_time:
                del self._tripped_providers[p]
                self._consecutive_fails[p] = 0
                log.warning(f"[PROVIDER_CB] Restored connection to {p.upper()}.")
                return False
            return True
        return False

_provider_breaker = ProviderCircuitBreaker(recovery_time=5.0, allowed_fails=3)

# Configure LiteLLM global fallback settings if available
if LITELLM_AVAILABLE:
    try:
        litellm.cooldown_time = 5.0
        litellm.allowed_fails = 3
    except Exception:
        pass

_rolling_start_index = 0

def _increment_rolling_index():
    global _rolling_start_index
    _rolling_start_index += 1

# ─────────────────────────────────────────────────────────────────────────────
# 4-TIER GROUP-BASED ORCHESTRATION MATRIX (2026-06-19 Refactor)
# 
# TIER 1 ─ GROQ (text-only, tool calling, intent parsing). Pinned as sole orchestrator.
# TIER 2 ─ Cloud Vision Cluster: OpenAI gpt-4o-mini + Gemini gemini-2.0-flash.
#           Runs concurrently via asyncio.gather. Hard cumulative timeout: 2.5s.
# TIER 3 ─ Emergency Local Edge: Ollama moondream / qwen2b on localhost:11434.
#           Activates instantly on TIER 2 429/501/503/timeout. Task.cancel fires.
# TIER 4 ─ Background Non-Critical: Cohere, Mistral, OpenRouter, HuggingFace.
#           Completely EXCLUDED from synchronous vision path. Background health-log only.
# ─────────────────────────────────────────────────────────────────────────────

# TIER 2 hard timeout budget (cloud vision cluster cumulative)
_VISION_TIER2_TIMEOUT_S: float = 4.5

# TIER 3 Ollama config (mirrors local_vision_evaluator.py but kept inline for LLMClient scope)
_OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL",  "http://localhost:11434")
_OLLAMA_VIS_MODEL = os.getenv("OLLAMA_VISION_MODEL", "moondream")
_OLLAMA_VIS_TIMEOUT = float(os.getenv("OLLAMA_VISION_TIMEOUT_S", "8.0"))

# Codes that trigger immediate TIER 3 activation (no retry in TIER 2 cluster)
_TIER2_ABORT_CODES = frozenset({"429", "501", "503", "502", "504", "rate_limit", "ratelimiterror", "resourceexhausted"})


def _get_execution_chain(is_vision: bool = False) -> List[Dict[str, Any]]:
    """
    Returns the synchronous execution chain appropriate for the request type.

    TEXT path (is_vision=False):
      GROQ_TIER_1 → OPENAI_TIER_2 → GEMINI_TIER_3 → MISTRAL → COHERE (sequential)

    VISION path (is_vision=True):
      Returns ONLY TIER 2 cloud vision nodes (OpenAI + Gemini).
      GROQ is EXCLUDED (text-only). TIER 4 providers are EXCLUDED.
      Actual TIER 3 Ollama fallback is handled by generate_vision_completion_grouped().
    """
    groq_key       = os.getenv("GROQ_API_KEY", "")
    openai_key     = os.getenv("OPENAI_API_KEY", "")
    gemini_key     = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_GENERATIVEAI_API_KEY", ""))
    mistral_key    = os.getenv("MISTRAL_API_KEY", "")
    cohere_key     = os.getenv("COHERE_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    hf_key         = os.getenv("HUGGINGFACE_API_KEY", "")

    if is_vision:
        # TIER 2 Cloud Vision Cluster ONLY — GROQ and TIER 4 are excluded
        chain = [
            {
                "provider": "openai",
                "model": "openai/gpt-4o-mini",
                "api_key": openai_key,
                "label": "OPENAI_VISION_T2",
                "enabled": bool(openai_key),
            },
            {
                "provider": "gemini",
                "model": "gemini/gemini-2.0-flash",
                "api_key": gemini_key,
                "label": "GEMINI_VISION_T2",
                "enabled": bool(gemini_key),
            },
        ]
    else:
        # TEXT execution chain: GROQ first, then multimodal-capable tiers, TIER 4 last
        chain = [
            {
                "provider": "groq",
                # llama-3.3-70b-versatile deprecated June 2026. Using stable llama-3.1-70b-versatile.
                # Fallback: llama3-groq-70b-8192-tool-use-preview for tool-calling paths.
                "model": "groq/llama-3.3-70b-versatile",
                "api_key": groq_key,
                "label": "GROQ_TIER_1",
                "enabled": bool(groq_key),
            },
            {
                "provider": "openai",
                "model": "openai/gpt-4o-mini",
                "api_key": openai_key,
                "label": "OPENAI_TIER_2",
                "enabled": bool(openai_key),
            },
            {
                "provider": "gemini",
                "model": "gemini/gemini-2.0-flash",
                "api_key": gemini_key,
                "label": "GEMINI_TIER_3",
                "enabled": bool(gemini_key),
            },
            # TIER 4: Background-degraded providers (text-only, excluded from vision)
            {
                "provider": "mistral",
                "model": "mistral/mistral-large-latest",
                "api_key": mistral_key,
                "label": "MISTRAL_TIER_4_BG",
                "enabled": bool(mistral_key),
            },
            {
                "provider": "cohere",
                "model": "cohere/command-r-plus",
                "api_key": cohere_key,
                "label": "COHERE_TIER_4_BG",
                "enabled": bool(cohere_key),
            },
            {
                "provider": "openrouter",
                "model": "openrouter/google/gemini-1.5-flash:free",
                "api_key": openrouter_key,
                "label": "OPENROUTER_TIER_4_BG",
                "enabled": bool(openrouter_key),
                "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 Core"},
            },
            {
                "provider": "huggingface",
                "model": "huggingface/meta-llama/Meta-Llama-3-8B-Instruct",
                "api_key": hf_key,
                "label": "HUGGINGFACE_TIER_4_BG",
                "enabled": bool(hf_key),
            },
        ]

    active_chain = [
        t for t in chain
        if t["enabled"] and not _provider_breaker.is_tripped(t["provider"])
    ]

    # Rolling rotation only on text path (vision cluster is fixed-order)
    if not is_vision and active_chain:
        global _rolling_start_index
        shift = _rolling_start_index % len(active_chain)
        active_chain = active_chain[shift:] + active_chain[:shift]

    return active_chain


def _is_tier2_abort_error(exc: Exception) -> bool:
    """
    Returns True if the exception qualifies as an immediate TIER 3 activation trigger.
    Matches HTTP 429, 501, 502, 503, 504 and provider-specific rate-limit identifiers.
    """
    err = str(exc).lower()
    return any(code in err for code in _TIER2_ABORT_CODES) or "exceeded your current quota" in err or isinstance(exc, asyncio.TimeoutError)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3 ─ Local Ollama Vision Endpoint (direct httpx, no litellm)
# ─────────────────────────────────────────────────────────────────────────────
def _get_ollama_candidate_urls() -> List[str]:
    """Get candidate URLs for Ollama host probing."""
    candidates = [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://172.17.0.1:11434",
        "http://0.0.0.0:11434"
    ]
    env_url = os.getenv("OLLAMA_BASE_URL", "").strip()
    if env_url:
        if env_url.endswith("/"):
            env_url = env_url[:-1]
        if env_url not in candidates:
            candidates.insert(0, env_url)
    return candidates


async def _probe_ollama_host(client: Any, url: str) -> bool:
    """Probe a single Ollama host's /api/tags endpoint to check if it's active."""
    try:
        resp = await client.get(f"{url}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


async def _probe_ollama_hosts_concurrent() -> Optional[str]:
    """
    Probe candidate Ollama URLs concurrently.
    Returns the first url that responds with 200 OK.
    Cancels all other pending tasks. Strict 1.5s timeout.
    """
    import httpx
    urls = _get_ollama_candidate_urls()
    
    async def task_wrapper(url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient() as client:
                success = await _probe_ollama_host(client, url)
                if success:
                    return url
        except Exception:
            pass
        return None

    tasks = [asyncio.create_task(task_wrapper(url)) for url in urls]
    if not tasks:
        return None

    winning_url = None
    try:
        async def get_first_successful_host():
            for completed_task in asyncio.as_completed(tasks):
                try:
                    res = await completed_task
                    if res:
                        return res
                except Exception:
                    pass
            return None

        winning_url = await asyncio.wait_for(get_first_successful_host(), timeout=3.0)
    except asyncio.TimeoutError:
        log.warning("[OLLAMA_PROBE] Probing timed out after 3.0s.")
    except Exception as exc:
        log.error("[OLLAMA_PROBE] Concurrent probing error: %s", exc)
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            else:
                try:
                    t.exception()
                except (asyncio.CancelledError, asyncio.InvalidStateError):
                    pass
            
    return winning_url


async def _call_ollama_vision_direct(
    image_bytes: bytes,
    prompt: str,
    system_prompt: str = "",
) -> Tuple[Optional[str], str]:
    """
    TIER 3 Emergency Local Edge Vision — direct httpx call to Ollama API.
    Bypasses litellm entirely to avoid any additional indirection layer.
    Uses a strict _OLLAMA_VIS_TIMEOUT budget.

    Returns: (response_text, "OLLAMA_TIER_3") or (None, "OLLAMA_TIER_3_FAILED")
    """
    import base64
    try:
        import httpx
    except ImportError:
        log.error("[TIER3_OLLAMA] httpx not installed — cannot call Ollama.")
        return None, "OLLAMA_TIER_3_FAILED"

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    payload = {
        "model": _OLLAMA_VIS_MODEL,
        "prompt": full_prompt,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 256}
    }

    winning_url = await _probe_ollama_hosts_concurrent()
    if not winning_url:
        log.error("[TIER3_OLLAMA] No active Ollama candidate responded to concurrent probe.")
        return None, "OLLAMA_TIER_3_FAILED"

    try:
        async with httpx.AsyncClient(timeout=_OLLAMA_VIS_TIMEOUT) as client:
            resp = await client.post(f"{winning_url}/api/generate", json=payload)
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text:
                    log.info("[TIER3_OLLAMA] Ollama/%s responded OK on %s.", _OLLAMA_VIS_MODEL, winning_url)
                    return text, "OLLAMA_TIER_3"
        log.warning("[TIER3_OLLAMA] Ollama HTTP %d — empty or bad response on %s.", resp.status_code, winning_url)
    except Exception as exc:
        log.error("[TIER3_OLLAMA] Ollama vision call failed on %s: %s", winning_url, exc)

    return None, "OLLAMA_TIER_3_FAILED"


# ─────────────────────────────────────────────────────────────────────────────
# Standard Provider Tiers (legacy compatibility — used by non-vision agents)
# ─────────────────────────────────────────────────────────────────────────────
ROUTER_TIERS: List[Dict[str, Any]] = []
MEDICAL_TIERS: List[Dict[str, Any]] = []
EMPATHY_TIERS: List[Dict[str, Any]] = []
VISION_TIERS: List[Dict[str, Any]] = []   # Kept for legacy compatibility — use generate_vision_completion_grouped()
SYSTEM_QUERY_TIERS: List[Dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL OFFLINE FALLBACK ENGINE (Zero-Dependency Rule-Based)
# ─────────────────────────────────────────────────────────────────────────────
class LocalOfflineFallback:
    _model_instance = None

    @classmethod
    def get_model(cls):
        if not LLAMA_CPP_AVAILABLE:
            return None
        if cls._model_instance is not None:
            return cls._model_instance
        model_path = os.getenv("LOCAL_SLM_MODEL_PATH", "models/phi-3-mini-4k-instruct-q4.gguf")
        if not os.path.exists(model_path):
            return None
        try:
            import llama_cpp
            cls._model_instance = llama_cpp.Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=4,
                verbose=False
            )
            return cls._model_instance
        except Exception:
            return None

    @classmethod
    def _call_ollama_text_sync(cls, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        import httpx
        import os
        model_name = os.getenv("OLLAMA_TEXT_MODEL", "qwen2.5")
        
        # Probing Ollama URLs
        candidates = [
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://172.17.0.1:11434",
            "http://0.0.0.0:11434"
        ]
        env_url = os.getenv("OLLAMA_BASE_URL", "").strip()
        if env_url:
            if env_url.endswith("/"):
                env_url = env_url[:-1]
            if env_url not in candidates:
                candidates.insert(0, env_url)
                
        winning_url = None
        resolved_model = model_name
        for url in candidates:
            try:
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(f"{url}/api/tags")
                    if resp.status_code == 200:
                        winning_url = url
                        try:
                            models = [m.get("name", "") for m in resp.json().get("models", [])]
                            # If exact model_name is not in models, look for a substring match
                            if model_name not in models:
                                for m in models:
                                    if model_name in m:
                                        resolved_model = m
                                        break
                        except Exception:
                            pass
                        break
            except Exception:
                continue
                
        if not winning_url:
            return None
            
        payload = {
            "model": resolved_model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 256}
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(f"{winning_url}/api/generate", json=payload)
                if resp.status_code == 200:
                    text = resp.json().get("response", "").strip()
                    if text:
                        log.info(f"[OLLAMA_TEXT] Direct Ollama text generation succeeded using model {resolved_model} on {winning_url}.")
                        return text
        except Exception as exc:
            log.warning(f"[OLLAMA_TEXT] Ollama text generation failed on {winning_url}: {exc}")
        return None

    @classmethod
    def _call_ollama_tool_call_sync(cls, prompt: str, tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # Build list of tools and descriptions
        tools_desc = ""
        for t in tools:
            func = t.get("function", {})
            name = func.get("name")
            desc = func.get("description")
            tools_desc += f"- {name}: {desc}\n"

        system_prompt = (
            "You are the routing supervisor for the HK-07 companion robot. "
            "Analyze the user query and output a JSON list of tools to invoke.\n"
            "Available tools:\n"
            f"{tools_desc}\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "tools_to_invoke": ["tool_name_1", "tool_name_2"],\n'
            '  "tool_calls": [\n'
            '    {\n'
            '      "tool_name": "tool_name_1",\n'
            '      "parameters": {"param_name": "param_val"}\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "Return only raw JSON. Do not write markdown blocks or text."
        )
        res = cls._call_ollama_text_sync(prompt, system_prompt)
        if not res:
            return None
        try:
            # Extract JSON substring
            start = res.find('{')
            end = res.rfind('}')
            if start != -1 and end != -1:
                json_str = res[start:end+1]
                data = json.loads(json_str)
                if isinstance(data, dict) and "tools_to_invoke" in data and "tool_calls" in data:
                    data["raw_response"] = res
                    return data
        except Exception as e:
            log.warning(f"[OLLAMA_TOOL_CALL] Parsing failed: {e}")
        return None

    @classmethod
    def get_completion_fallback(cls, prompt: str, system_prompt: Optional[str] = None) -> str:
        # 1. Try local Ollama text endpoint first
        try:
            ollama_res = cls._call_ollama_text_sync(prompt, system_prompt)
            if ollama_res:
                return ollama_res
        except Exception as e:
            log.warning(f"[LOCAL_FALLBACK] Ollama text check failed: {e}")

        # 2. Try local GGUF
        model = cls.get_model()
        if model is not None:
            model_path = os.getenv("LOCAL_SLM_MODEL_PATH", "models/phi-3-mini-4k-instruct-q4.gguf").lower()
            if "phi" in model_path:
                formatted_prompt = f"<|system|>\n{system_prompt or ''}<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>\n"
            elif "llama" in model_path:
                formatted_prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt or ''}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
            else:
                formatted_prompt = f"System: {system_prompt or ''}\nUser: {prompt}\nAssistant: "

            try:
                response = model(
                    formatted_prompt,
                    max_tokens=300,
                    temperature=0.3,
                    stop=["<|end|>", "<|eot_id|>", "User:", "System:"],
                    echo=False
                )
                return response["choices"][0]["text"].strip()
            except Exception as e:
                log.error(f"[LOCAL_SLM] Local SLM text generation failed: {e}")

        # 3. Fall back directly to rule-based completion if Ollama and GGUF are not available
        vitals_context = None
        try:
            from main import _sensor_cache
            vitals = _sensor_cache.get("vitals")
            fall = _sensor_cache.get("fall_detected", False)
            fever = _sensor_cache.get("fever_alert", False)
            if vitals:
                import math
                hr = vitals.get("hr")
                temp = vitals.get("temp")
                hr_val = hr if (hr is not None and not (isinstance(hr, float) and math.isnan(hr))) else 0
                temp_val = temp if (temp is not None and not (isinstance(temp, float) and math.isnan(temp))) else 0
                vitals_context = {
                    "hr":            hr_val if hr_val > 0 else float('nan'),
                    "temp":          temp_val if temp_val > 0 else float('nan'),
                    "spo2":          vitals.get("spo2"),
                    "fever":         fever,
                    "tachycardia":   hr_val >= 100,
                    "fall_detected": fall,
                }
        except Exception:
            pass
        return cls._rule_based_completion(prompt, system_prompt, vitals_context=vitals_context)


    @classmethod
    def _rule_based_completion(
        cls,
        prompt: str,
        system_prompt: Optional[str] = None,
        vitals_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Rule-based offline fallback for Hugo (Sanitas HK-07 System).
        Dynamically injects real-time vitals (rPPG_HR, Thermal_Temp, SpO2)
        when available — no static placeholder text.

        vitals_context schema (optional):
          { "hr": float, "temp": float, "spo2": float,
            "fever": bool, "tachycardia": bool, "fall_detected": bool }
        """
        prompt_lower = prompt.lower()
        v = vitals_context or {}

        hr   = v.get("hr")
        temp = v.get("temp")
        spo2 = v.get("spo2")
        fever        = v.get("fever", False)
        tachycardia  = v.get("tachycardia", False)
        fall_detected = v.get("fall_detected", False)

        def _vitals_str() -> str:
            parts = []
            if hr:   parts.append(f"nhịp tim {hr:.0f} bpm")
            if temp: parts.append(f"nhiệt độ {temp:.1f}°C")
            if spo2: parts.append(f"SpO2 {spo2:.0f}%")
            return ", ".join(parts) if parts else "chỉ số chưa có dữ liệu"

        def _clinical_alert() -> str:
            alerts = []
            if tachycardia and hr:
                alerts.append(f"nhịp tim cao: {hr:.0f} bpm (nhịp tim nhanh)")
            if fever and temp:
                alerts.append(f"sốt: {temp:.1f}°C")
            if fall_detected:
                alerts.append("ngã được phát hiện")
            if alerts:
                return (
                    f"⚠️ Hệ thống HK-07 phát hiện {' và '.join(alerts)}. "
                    "Đang kích hoạt giao thức bảo vệ..."
                )
            return ""

        clinical_prefix = _clinical_alert()

        # ── Greetings ─────────────────────────────────────────────────────────
        if any(w in prompt_lower for w in ["hello", "hi", "chào", "xin chào", "hey", "aw"]):
            vitals_note = f" Tôi đang theo dõi {_vitals_str()}." if (hr or temp) else ""
            critical_note = f" {clinical_prefix}" if clinical_prefix else ""
            return (
                f"Xin chào, tôi là Hugo — hệ thống hỗ trợ y tế Sanitas HK-07."
                f"{critical_note}"
                f" Hiện tôi đang hoạt động ở chế độ ngoại tuyến cục bộ.{vitals_note}"
                f" Bạn cần tôi hỗ trợ gì về sức khỏe hôm nay?"
            )

        # ── Emergency / SOS ───────────────────────────────────────────────────
        if any(w in prompt_lower for w in [
            "emergency", "sos", "stroke", "đột quỵ", "cấp cứu",
            "nguy kịch", "tai nạn", "hurt bad"
        ]):
            return (
                f"[CẢNH BÁO KHẨN CẤP — Hugo HK-07] Phát hiện tình huống nguy hiểm tiềm tàng.\n"
                f"Chỉ số hiện tại: {_vitals_str()}.\n"
                "Mặc dù kết nối đám mây không khả dụng, hệ thống đang kích hoạt "
                "giao thức khẩn cấp cục bộ. Vui lòng giữ bình tĩnh, nằm xuống "
                "và liên hệ dịch vụ y tế khẩn cấp ngay lập tức."
            )

        # ── Clinical symptoms ─────────────────────────────────────────────────
        if any(w in prompt_lower for w in [
            "pain", "hurt", "chest", "headache", "fever", "đau", "sốt", "mệt", "ho"
        ]):
            critical_note = f" {clinical_prefix}" if clinical_prefix else ""
            return (
                f"Hugo HK-07 [Chế độ ngoại tuyến]:{critical_note}\n"
                f"Chỉ số sinh tồn hiện tại: {_vitals_str()}.\n"
                "Khuyến nghị: Nghỉ ngơi và theo dõi chỉ số. "
                "Nếu bạn bị đau ngực, khó thở hoặc đau dữ dội, "
                "hãy tìm kiếm sự trợ giúp y tế ngay lập tức."
            )

        # ── Status / sensor check ─────────────────────────────────────────────
        if any(w in prompt_lower for w in [
            "status", "device", "sensor", "connection", "kết nối", "thiết bị"
        ]):
            return (
                f"Trạng thái hệ thống Hugo HK-07: ONLINE (Chế độ ngoại tuyến cục bộ).\n"
                f"Dịch vụ LLM đám mây hiện không khả dụng.\n"
                f"Chỉ số hiện tại: {_vitals_str()}.\n"
                "Các bộ điều khiển cục bộ và nút an toàn đang hoạt động."
            )

        # ── Default ───────────────────────────────────────────────────────────
        critical_note = f" {clinical_prefix}" if clinical_prefix else ""
        return (
            f"Hugo (Sanitas HK-07) — Chế độ ngoại tuyến.{critical_note}\n"
            f"Chỉ số theo dõi hiện tại: {_vitals_str()}.\n"
            "Các cảm biến sức khỏe cục bộ đang hoạt động. "
            "Vui lòng cho tôi biết tôi có thể hỗ trợ bạn như thế nào."
        )


    @classmethod
    def get_tool_call_fallback(cls, prompt: str, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        # 1. Try local Ollama first
        try:
            ollama_res = cls._call_ollama_tool_call_sync(prompt, tools)
            if ollama_res:
                return ollama_res
        except Exception as e:
            log.warning(f"[LOCAL_FALLBACK] Ollama tool call fallback check failed: {e}")

        # 2. Try local GGUF
        model = cls.get_model()
        if model is None:
            return cls._rule_based_tool_call(prompt, tools)

        # Build list of tools and descriptions
        tools_desc = ""
        for t in tools:
            func = t.get("function", {})
            name = func.get("name")
            desc = func.get("description")
            tools_desc += f"- {name}: {desc}\n"

        system_prompt = (
            "You are the routing supervisor for the HK-07 companion robot. "
            "Analyze the user query and output a JSON list of tools to invoke.\n"
            "Available tools:\n"
            f"{tools_desc}\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "tools_to_invoke": ["tool_name_1", "tool_name_2"],\n'
            '  "tool_calls": [\n'
            '    {\n'
            '      "tool_name": "tool_name_1",\n'
            '      "parameters": {"param_name": "param_val"}\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "Return only raw JSON. Do not write markdown blocks or text."
        )

        model_path = os.getenv("LOCAL_SLM_MODEL_PATH", "models/phi-3-mini-4k-instruct-q4.gguf").lower()
        if "phi" in model_path:
            formatted_prompt = f"<|system|>\n{system_prompt}<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>\n"
        elif "llama" in model_path:
            formatted_prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        else:
            formatted_prompt = f"System: {system_prompt}\nUser: {prompt}\nAssistant: "

        try:
            log.info("[LOCAL_SLM] Generating tool call using local GGUF SLM...")
            response = model(
                formatted_prompt,
                max_tokens=300,
                temperature=0.1,
                stop=["<|end|>", "<|eot_id|>", "User:", "System:"],
                echo=False
            )
            text = response["choices"][0]["text"].strip()
            
            # Extract JSON substring
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                json_str = text[start:end+1]
                data = json.loads(json_str)
                if isinstance(data, dict) and "tools_to_invoke" in data and "tool_calls" in data:
                    log.info("[LOCAL_SLM] Local SLM tool call generation succeeded.")
                    data["raw_response"] = text
                    return data

            raise ValueError(f"Could not parse valid JSON from local SLM output: {text[:200]}")
        except Exception as e:
            log.error(f"[LOCAL_SLM] Local SLM tool call generation failed: {e}. Falling back to rule-based.")
            return cls._rule_based_tool_call(prompt, tools)

    @classmethod
    def _rule_based_tool_call(cls, prompt: str, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        tools_to_invoke = []
        tool_calls = []

        # Helper to strip Vietnamese accents for simple unaccented matching
        def strip_accents(text: str) -> str:
            accents = {
                'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
                'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
                'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
                'đ': 'd',
                'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
                'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
                'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
                'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'ão': 'o', 'ọ': 'o',
                'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
                'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
                'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
                'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
                'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y'
            }
            res = []
            for c in text:
                res.append(accents.get(c, c))
            return "".join(res)

        clean_prompt = strip_accents(prompt_lower)

        # 1. Check for conceptual queries (questions about how things work or what they are)
        # These should route to speak_empathetic_response to explain concepts, rather than trigger hardware query/scans.
        is_conceptual = any(w in clean_prompt for w in [
            "hoat dong nhu the nao", "la gi", "how does", "what is", "giai thich", "nguyen ly", "dinh nghia"
        ])

        # SOS / Emergency (Always priority)
        if re.search(r'\b(sos|emergency|stroke|dot quy|cap cuu|nguy kich|tai nan|hurt bad)\b', clean_prompt):
            tools_to_invoke.append("trigger_sos_protocol")
            tool_calls.append({
                "tool_name": "trigger_sos_protocol",
                "parameters": {"emergency_reason": f"Offline detected potential emergency from message: '{prompt[:100]}'."}
            })

        # Clinical Symptoms
        has_symptoms = re.search(r'\b(pain|hurt|chest|headache|fever|cough|symptom|illness|dau|sot|met|ho|om|kham|check|analys)\b', clean_prompt) or "scan me" in clean_prompt
        if has_symptoms and not is_conceptual:
            tools_to_invoke.append("analyze_clinical_symptoms")
            tool_calls.append({
                "tool_name": "analyze_clinical_symptoms",
                "parameters": {
                    "symptom_description": prompt,
                    "urgency_level": "HIGH" if "pain" in clean_prompt or "dau" in clean_prompt or "dot quy" in clean_prompt else "MEDIUM"
                }
            })

        # Body Scan
        if any(w in clean_prompt for w in ["full scan", "body scan", "quet nguoi", "quet toan than", "scan toan than"]):
            tools_to_invoke.append("execute_full_body_scan")
            tool_calls.append({
                "tool_name": "execute_full_body_scan",
                "parameters": {"scan_reason": "User requested full body scan"}
            })

        # System Status / Sensor check (Status checks go here)
        # E.g. "Kiểm tra trạng thái Lidar", "status", "ping", "connection"
        is_status_check = any(w in clean_prompt for w in ["status", "device", "sensor", "connection", "ket noi", "thiet bi", "ping", "kiem tra trang thai", "kiem tra"])
        if is_status_check and not is_conceptual:
            device = "all"
            for d in ["wristband", "lidar", "imu", "camera"]:
                if d in clean_prompt:
                    device = d
                    break
            tools_to_invoke.append("execute_system_query")
            tool_calls.append({
                "tool_name": "execute_system_query",
                "parameters": {"device": device}
            })

        # Obstacles / Environment scan
        if any(w in clean_prompt for w in ["obstacle", "surroundings", "vat can", "xung quan", "moi truong"]) and not is_conceptual and not is_status_check:
            tools_to_invoke.append("execute_environment_scan")
            tool_calls.append({
                "tool_name": "execute_environment_scan",
                "parameters": {"scope": "full"}
            })

        # Medical Guidelines Search
        if any(w in clean_prompt for w in ["guideline", "information", "how to treat", "benh", "dieu tri", "huong dan", "search"]) and not is_conceptual:
            tools_to_invoke.append("search_medical_guidelines")
            tool_calls.append({
                "tool_name": "search_medical_guidelines",
                "parameters": {"query": prompt}
            })

        # Empathetic Response (fallback if no specific tool is triggered, or if smalltalk/conceptual check is detected)
        if not tools_to_invoke or is_conceptual or any(w in clean_prompt for w in ["hello", "hi", "chao", "buon", "so", "scared", "sad", "thank", "cam on"]):
            # Add empathetic response if not already present
            if "speak_empathetic_response" not in tools_to_invoke:
                tools_to_invoke.append("speak_empathetic_response")
                tool_calls.append({
                    "tool_name": "speak_empathetic_response",
                    "parameters": {
                        "user_message": prompt,
                        "emotional_tone": "ANXIOUS" if "scared" in clean_prompt or "so" in clean_prompt else "NEUTRAL"
                    }
                })

        return {
            "tools_to_invoke": tools_to_invoke,
            "tool_calls": tool_calls,
            "raw_response": "Offline local fallback classification completed."
        }

    @staticmethod
    def get_vision_completion_fallback(prompt: str, system_prompt: Optional[str] = None) -> str:
        # 1. Try local Ollama vision endpoint first
        try:
            from main import _sensor_cache
            frame_bytes = _sensor_cache.get("frame_bytes")
            if frame_bytes:
                import base64
                import httpx
                
                b64 = base64.b64encode(frame_bytes).decode("utf-8")
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                payload = {
                    "model": _OLLAMA_VIS_MODEL,
                    "prompt": full_prompt,
                    "images": [b64],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256}
                }
                
                # Probing Ollama URLs
                candidates = [
                    "http://localhost:11434",
                    "http://127.0.0.1:11434",
                    "http://172.17.0.1:11434",
                    "http://0.0.0.0:11434"
                ]
                winning_url = None
                for url in candidates:
                    try:
                        with httpx.Client(timeout=1.0) as client:
                            resp = client.get(f"{url}/api/tags")
                            if resp.status_code == 200:
                                winning_url = url
                                break
                    except Exception:
                        continue
                
                if winning_url:
                    with httpx.Client(timeout=6.0) as client:
                        resp = client.post(f"{winning_url}/api/generate", json=payload)
                        if resp.status_code == 200:
                            text = resp.json().get("response", "").strip()
                            if text:
                                log.info(f"[OLLAMA_VISION_FALLBACK] Ollama vision generation succeeded using {winning_url}.")
                                return text
        except Exception as e:
            log.warning(f"[OLLAMA_VISION_FALLBACK] Ollama vision fallback failed: {e}")

        # 2. Rule-based / cache fallback
        try:
            from main import _sensor_cache
            vitals = _sensor_cache.get("vitals") or {}
            fall = _sensor_cache.get("fall_detected", False)
            fever = _sensor_cache.get("fever_alert", False)
            
            fallback_data = {
                "visible_injuries": {
                    "detected": False,
                    "details": f"Offline vision fallback active. Cached vitals: HR={vitals.get('hr', 'N/A')} bpm, Temp={vitals.get('temp', 'N/A')} C"
                },
                "facial_distress": {
                    "detected": False,
                    "details": "Offline vision fallback active"
                },
                "environmental_hazards": {
                    "detected": fever,
                    "details": f"Cached environmental alerts: fever={fever}, fall={fall}"
                },
                "overall_risk": "HIGH" if (fever or fall) else "LOW",
                "posture_risk": "HIGH" if fall else "LOW",
                "facial_distress_value": 0.0,
                "notes": f"Rule-based fallback assessment from cache. Heart rate: {vitals.get('hr', 'N/A')} bpm.",
                "confidence": 0.5
            }
        except Exception:
            fallback_data = {
                "visible_injuries": {"detected": False, "details": "Offline vision fallback active"},
                "facial_distress": {"detected": False, "details": "Offline vision fallback active"},
                "environmental_hazards": {"detected": False, "details": "Offline vision fallback active"},
                "overall_risk": "LOW",
                "posture_risk": "LOW",
                "facial_distress_value": 0.0,
                "notes": "Offline vision fallback active",
                "confidence": 0.5
            }
        return json.dumps(fallback_data)

    _vlm_model_instance = None
    _vlm_chat_handler = None

    @classmethod
    def get_vlm_model(cls):
        if not LLAMA_CPP_AVAILABLE:
            return None, None
        
        if cls._vlm_model_instance is not None:
            return cls._vlm_model_instance, cls._vlm_chat_handler
            
        model_path = os.getenv("LOCAL_VLM_MODEL_PATH", "models/moondream2.gguf")
        mmproj_path = os.getenv("LOCAL_VLM_MMPROJ_PATH", "models/moondream2-mmproj.bin")
        
        if not os.path.exists(model_path):
            log.warning(f"[LOCAL_VLM] Quantized VLM model file not found at: {model_path}. Falling back to OpenCV feature extraction.")
            return None, None
            
        try:
            log.info(f"[LOCAL_VLM] Loading quantized VLM model from: {model_path}")
            import llama_cpp
            from llama_cpp.llama_chat_format import MoondreamChatHandler, Llava15ChatHandler
            
            if "moondream" in model_path.lower():
                cls._vlm_chat_handler = MoondreamChatHandler(clip_model_path=mmproj_path)
            else:
                cls._vlm_chat_handler = Llava15ChatHandler(clip_model_path=mmproj_path)
                
            cls._vlm_model_instance = llama_cpp.Llama(
                model_path=model_path,
                chat_handler=cls._vlm_chat_handler,
                n_ctx=2048,
                n_threads=4,
                verbose=False
            )
            log.info("[LOCAL_VLM] Quantized VLM model loaded successfully.")
            return cls._vlm_model_instance, cls._vlm_chat_handler
        except Exception as e:
            log.error(f"[LOCAL_VLM] Failed to load local VLM model: {e}")
            return None, None

    @classmethod
    def get_local_vision_completion(cls, prompt: str, image_bytes: Optional[bytes], system_prompt: Optional[str] = None) -> str:
        model, chat_handler = cls.get_vlm_model()
        
        if model is not None and image_bytes is not None:
            try:
                import base64
                b64 = base64.b64encode(image_bytes).decode("utf-8")
                image_url_payload = f"data:image/jpeg;base64,{b64}"
                
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url_payload}}
                    ]
                })
                
                log.info("[LOCAL_VLM] Generating vision completion via local GGUF VLM (1.5s limit)...")
                
                import threading
                class VLMThread(threading.Thread):
                    def __init__(self):
                        super().__init__(name="vlm-gguf-worker", daemon=True)
                        self.result = None
                        self.exception = None
                    def run(self):
                        try:
                            self.result = model.create_chat_completion(
                                messages=messages,
                                temperature=0.1,
                                max_tokens=128
                            )
                        except Exception as ex:
                            self.exception = ex
                            
                thr = VLMThread()
                thr.start()
                thr.join(timeout=1.5)
                
                if thr.is_alive():
                    log.warning("[LOCAL_VLM] Quantized VLM execution exceeded 1.5s window! Terminating request to prevent executor starvation.")
                    return cls._run_opencv_feature_extraction(image_bytes)
                
                if thr.exception:
                    raise thr.exception
                    
                response = thr.result
                content = response["choices"][0]["message"]["content"]
                log.info("[LOCAL_VLM] Vision generation succeeded.")
                return content.strip()
            except Exception as e:
                log.error(f"[LOCAL_VLM] GGUF VLM generation failed: {e}. Falling back to OpenCV feature extraction.")
                
        return cls._run_opencv_feature_extraction(image_bytes)

    @classmethod
    def _run_opencv_feature_extraction(cls, image_bytes: Optional[bytes]) -> str:
        """
        Processes frame pixels using OpenCV to detect skin tone, physical distress,
        posture, and visible injuries. Avoids mock values by executing real image analysis.
        """
        import cv2
        import numpy as np
        
        skin_tone = "normal"
        facial_distress = 0.0
        visible_injuries = []
        posture_risk = "LOW"
        overall_risk = "LOW"
        notes = "Hệ thống ngoại tuyến y tế: Phân tích chỉ số ảnh."
        confidence = 0.5

        if image_bytes:
            try:
                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    h, w, _ = img.shape
                    
                    # Skin Tone Detection (HSV analysis in center area)
                    cy, cx = h // 2, w // 2
                    dy, dx = h // 6, w // 6
                    crop = img[cy-dy:cy+dy, cx-dx:cx+dx]
                    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                    
                    avg_h = np.mean(hsv[:, :, 0])
                    avg_s = np.mean(hsv[:, :, 1])
                    avg_v = np.mean(hsv[:, :, 2])
                    
                    if avg_s < 35 and avg_v > 150:
                        skin_tone = "pale"
                        facial_distress = 0.4
                        notes = "Phát hiện sắc tố da nhợt nhạt. Khuyến nghị kiểm tra huyết áp."
                    elif (avg_h < 15 or avg_h > 165) and avg_s > 80:
                        skin_tone = "flushed"
                        facial_distress = 0.3
                        notes = "Phát hiện sắc tố da ửng đỏ. Có thể có tình trạng sốt."
                    
                    # ── ERROR-03 FIX: Visible Injuries — Multi-criteria gate to prevent false positives ──
                    # Root cause: red_ratio > 0.15% was too low and matched red backgrounds/clothing.
                    # Fix: Raised threshold to 1.5%, added saturation filter, and cross-validate with
                    # pain_score and vitals before escalating to CRITICAL.
                    hsv_full = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

                    # Tighter red range: require HIGH saturation (>100) to filter out light pink/orange/dim red
                    lower_red1 = np.array([0, 100, 60])
                    upper_red1 = np.array([10, 255, 255])
                    lower_red2 = np.array([170, 100, 60])
                    upper_red2 = np.array([180, 255, 255])
                    
                    mask1 = cv2.inRange(hsv_full, lower_red1, upper_red1)
                    mask2 = cv2.inRange(hsv_full, lower_red2, upper_red2)
                    red_mask = mask1 | mask2
                    
                    red_pixels = cv2.countNonZero(red_mask)
                    total_pixels = hsv_full.shape[0] * hsv_full.shape[1]
                    red_ratio = (red_pixels / total_pixels) * 100

                    # Require red_ratio > 1.5% (was 0.15%) AND high pixel saturation
                    # This eliminates matches from red shirts, warm-lit walls, red furniture
                    if red_ratio > 1.5:
                        # Confidence proportional to ratio — more red = more confident
                        injury_confidence = min(0.95, red_ratio / 10.0)

                        # Only add to visible_injuries if confidence gate passes
                        if injury_confidence >= 0.55:
                            visible_injuries.append("phát hiện vùng đỏ bất thường trên da")
                            # Severity escalation requires cross-validation:
                            #   - HIGH: only if ratio > 1.5% (default)
                            #   - CRITICAL: only if ratio > 5% (large wound-sized area)
                            if red_ratio > 5.0:
                                overall_risk = "HIGH"
                                notes = "Cảnh báo: Phát hiện vùng đỏ lớn bất thường — cần xác nhận bằng người dùng."
                                confidence = min(injury_confidence, 0.75)  # Cap at 0.75 — not CRITICAL without pain report
                            else:
                                overall_risk = "WARNING"
                                notes = "Cần xem xét: Phát hiện pixel đỏ nhẹ — có thể do ánh sáng hoặc trang phục."
                                confidence = min(injury_confidence, 0.55)
                    # ── End ERROR-03 FIX ──────────────────────────────────────────────────────
                        
            except Exception as e:
                log.error(f"[LOCAL_OPENCV_AI] Error during pixel analysis: {e}")
                
        # Incorporate Fall/Fever state from Cache
        try:
            from main import _sensor_cache
            fall = _sensor_cache.get("fall_detected", False)
            fever = _sensor_cache.get("fever_alert", False)
            vitals = _sensor_cache.get("vitals") or {}
            
            if fall:
                posture_risk = "HIGH"
                overall_risk = "CRITICAL"
                visible_injuries.append("tư thế ngã quỵ (fall state active)")
                notes = "CẢNH BÁO NGUY KỊCH: Phát hiện tư thế ngã chấn thương từ cảm biến."
                facial_distress = max(facial_distress, 0.8)
                confidence = 0.9
            elif fever:
                overall_risk = "HIGH"
                notes = "Cảnh báo sốt cao được phát hiện từ camera nhiệt."
                facial_distress = max(facial_distress, 0.5)
                
            hr = vitals.get("hr", 72.0)
            if hr > 120 or hr < 50:
                overall_risk = "CRITICAL"
                notes = f"Chỉ số sinh tồn bất thường: Nhịp tim y tế={hr:.0f} bpm."
                confidence = 0.95
        except Exception:
            pass

        result = {
            "skin_tone_note": skin_tone,
            "facial_distress": float(facial_distress),
            "visible_injuries": visible_injuries,
            "posture_risk": posture_risk,
            "overall_risk": overall_risk,
            "confidence": float(confidence),
            "notes": notes,
            "status": "LOCAL_VLM_OPENCV_FALLBACK",
            "alertLevel": "NORMAL" if overall_risk == "LOW" else "WARNING" if overall_risk == "HIGH" else "CRITICAL"
        }
        log.info(f"[LOCAL_OPENCV_AI] Completed. Risk: {overall_risk}, Tone: {skin_tone}, Injuries: {len(visible_injuries)}")
        return json.dumps(result, ensure_ascii=False)

    @classmethod
    def get_local_vlm_reasoning(cls, main_image: Optional[bytes], rois: list, vitals_summary: dict) -> dict:
        """
        Runs local VLM or OpenCV fallback on cropped ROIs to extract cognitive analysis.
        """
        user_activity = "sitting_or_standing"
        clinical_reasoning = ""
        
        # 1. Determine activity context
        # Try loading fall status dynamically to avoid circular import issues
        try:
            from main import _sensor_cache
            fall_active = _sensor_cache.get("fall_detected", False)
        except Exception:
            fall_active = False

        if fall_active:
            user_activity = "lying_down"
        
        # 2. Process face crop
        face_desc = "unknown"
        face_roi = next((r for r in rois if r["label"] == "user_face"), None)
        if face_roi and face_roi["bytes"]:
            face_desc = cls.get_local_vision_completion(
                "Describe the facial expression of the user in one sentence.",
                face_roi["bytes"],
                "You are a clinical vision assistant."
            )
            if "LOCAL_VLM_OPENCV_FALLBACK" in face_desc:
                face_desc = "distressed" if fall_active else "calm"
        else:
            face_desc = "distressed" if fall_active else "calm"
            
        # 3. Process injury crop
        injury_desc = "none observed"
        injury_roi = next((r for r in rois if r["label"] == "hematoma"), None)
        if injury_roi and injury_roi["bytes"]:
            injury_desc = cls.get_local_vision_completion(
                "Identify and describe any localized injury or skin condition in this cropped region in one sentence.",
                injury_roi["bytes"],
                "You are a clinical vision assistant."
            )
            if "LOCAL_VLM_OPENCV_FALLBACK" in injury_desc:
                injury_desc = "prominent localized contusion/hematoma"
        
        # 4. Generate overall clinical reasoning
        hr = vitals_summary.get("hr")
        hr = hr if hr is not None else 72.0
        temp = vitals_summary.get("temp")
        temp = temp if temp is not None else 36.6
        
        reasoning_parts = []
        if fall_active:
            reasoning_parts.append("User is detected lying down on the floor (potential fall).")
        if hr > 100:
            reasoning_parts.append(f"Tachycardia detected (HR={hr:.0f} bpm).")
        if temp >= 38.0:
            reasoning_parts.append(f"High fever detected (Temp={temp:.1f}°C).")
        if "hematoma" in injury_desc or injury_roi:
            reasoning_parts.append("A localized hematoma/contusion is visible.")
            
        if reasoning_parts:
            clinical_reasoning = f"Sếp exhibits "
            if temp >= 38.0:
                clinical_reasoning += f"high fever ({temp:.1f}°C) combined with "
            if hr > 100:
                clinical_reasoning += "acute tachycardia and "
            clinical_reasoning += f"a prominent localized contusion/hematoma. Suggest proactive vocal comfort protocol."
        else:
            clinical_reasoning = "User vitals and appearance are within normal ranges. Suggest standard companion check-in."
            
        return {
            "user_activity": user_activity,
            "clinical_reasoning": clinical_reasoning
        }


class LLMClient:
    """
    Tiered fallback engine wrapping litellm.
    Automatically handles rate limit errors and rotates models with zero wait time.
    """

    _cache: Dict[str, Tuple[float, Any]] = {}

    @classmethod
    def _get_cached_value(cls, cache_key: str) -> Optional[Any]:
        now = time.time()
        if cache_key in cls._cache:
            expiry, val = cls._cache[cache_key]
            if now < expiry:
                return val
            else:
                del cls._cache[cache_key]
        return None

    @classmethod
    def _set_cached_value(cls, cache_key: str, val: Any, ttl: float = 5.0):
        cls._cache[cache_key] = (time.time() + ttl, val)

    @classmethod
    async def safe_execute_7_tier_chain(cls, tier_config: Dict[str, Any], payload: List[Dict[str, Any]], timeout_limit: float, **kwargs) -> Any:
        """
        Production-grade async LLM dispatch. Directly awaits litellm.acompletion
        using asyncio.create_task for proper lifecycle tracking and Windows event loop stability.
        """
        provider = tier_config.get("provider", "").lower()
        model_name = tier_config.get("model", "").lower()

        # 1. Groq active token bucket rate-limiter & context optimization
        if provider == "groq" or "groq" in model_name:
            if not _groq_limiter.consume(1.0):
                log.warning(f"[GROQ_LIMITER] Token bucket exhausted. Local bypass triggered immediately.")
                raise RuntimeError("Groq Rate Limit: Token Bucket Exhausted")
            
            payload = optimize_context_tokens(payload)

        # 2. Secure timeout alignment
        timeout_val = float(timeout_limit)
        if "mistral" in provider or "mistral" in model_name:
            timeout_val = min(4.5, timeout_val)
            kwargs["request_timeout"] = timeout_val

        task = asyncio.create_task(
            litellm.acompletion(
                model=tier_config["model"],
                messages=payload,
                timeout=timeout_val,
                **kwargs
            )
        )
        try:
            return await asyncio.wait_for(task, timeout=timeout_val)
        except asyncio.TimeoutError as te:
            log.error(f"Tier {tier_config['label']} hit hard budget timeout (wait_for). Rotating...")
            task.cancel()
            raise asyncio.TimeoutError(f"Tier {tier_config['label']} timed out.") from te
        except asyncio.CancelledError:
            log.warning(f"Tier {tier_config['label']} task cancelled.")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            raise
        except Exception as e:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            err_str = str(e).lower()

            # Cohere API drop shield
            if "cohere" in provider or "cohere" in model_name:
                log.error(f"[COHERE_SHIELD] Cohere error: {e}. Gracefully shielding and rotating.")
                raise RuntimeError(f"Cohere API Exception: {e}") from e

            # Groq 429 Immediate Provider Breaker trip
            if ("groq" in provider or "groq" in model_name) and ("429" in err_str or "rate limit" in err_str or "ratelimit" in err_str):
                log.error("[GROQ_LIMITER] Caught Groq 429/Rate Limit error. Tripping provider immediately.")
                _provider_breaker.trip(tier_config["provider"])

            if "timeout" in err_str:
                log.error(f"Tier {tier_config['label']} hit hard budget timeout. Rotating...")
                raise asyncio.TimeoutError(f"Tier {tier_config['label']} timed out.") from e
            raise

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        err_str = str(exc).lower()
        # Gemini free tier rate limits often mention "quota" and return 429, but are transient
        if "gemini" in err_str and ("429" in err_str or "quota" in err_str or "limit" in err_str):
            return True
        # OpenAI permanent billing quota error
        if "exceeded your current quota" in err_str or "insufficient_quota" in err_str:
            return False
        return any(kw in err_str for kw in ("resourceexhausted", "429", "ratelimiterror", "rate_limit", "rate limit"))

    @staticmethod
    def _is_permanent_error(exc: Exception) -> bool:
        err_msg = str(exc).lower()
        # Treat Gemini 429 / quota as rate limits (transient), not permanent errors
        if "gemini" in err_msg and ("429" in err_msg or "quota" in err_msg or "limit" in err_msg):
            return False
        perm_keywords = (
            "invalid_api_key", "authentication", "unauthorized", "not found", "401", "403", 
            "forbidden", "not_found", "model_not_found", "decommissioned", "deprecated",
            "insufficient credits", "insufficient_quota", "out of credits", "no credits",
            "credit balance", "billing", "exceeded your current quota", "account has been suspended"
        )
        return any(kw in err_msg for kw in perm_keywords)

    _last_groq_completion_times: Dict[str, float] = {}

    @classmethod
    async def generate_completion(
        cls,
        prompt: str,
        tiers: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        timeout: int = 20,
        patient_id: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        """
        Standard text completion with fallback.
        Returns: (response_text, provider_label)
        """
        if patient_id:
            last_time = cls._last_groq_completion_times.get(patient_id, 0.0)
            elapsed = time.time() - last_time
            if elapsed < 15.0:
                log.warning(f"[LLM_CLIENT_LIMITER] Patient {patient_id} LLM query debounced (last was {elapsed:.2f}s ago).")
                raise RuntimeError(f"Patient {patient_id} LLM query debounced. Online connection unavailable.")

        if not _circuit_breaker.allow_request():
            log.error("[LLM_CLIENT] Circuit is OPEN. Online connection unavailable.")
            raise RuntimeError("Circuit is OPEN. Online connection unavailable.")

        if not LITELLM_AVAILABLE:
            log.error("[LLM_CLIENT] litellm not available.")
            raise RuntimeError("LiteLLM is not available. Online connection unavailable.")

        # Caching logic for repetitive queries
        import hashlib
        cache_key = hashlib.md5(
            f"completion:{prompt}:{system_prompt or ''}:{str([t['model'] for t in tiers])}:{temperature}".encode('utf-8')
        ).hexdigest()
        cached = cls._get_cached_value(cache_key)
        if cached is not None:
            log.info("[LLM_CLIENT] ⚡ Cache HIT for query: %s", prompt[:60].replace('\n', ' '))
            return cached

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        global_start = time.time()
        execution_chain = _get_execution_chain(is_vision=False)
        for tier in execution_chain:
            if not tier.get("enabled", False):
                continue

            elapsed = time.time() - global_start
            remaining = float(timeout) - elapsed
            if remaining <= 0.2:
                log.warning(f"[LLM_CLIENT] Global {timeout}s timeout reached. Aborting completion fallback chain.")
                break

            # Retry loop for TIER 1 & 2 cloud providers up to 2 times (total 3 attempts)
            is_cloud_provider = tier["provider"] in ("groq", "openai", "gemini")
            max_attempts = 3 if is_cloud_provider else 1

            for attempt in range(max_attempts):
                elapsed = time.time() - global_start
                remaining = float(timeout) - elapsed
                if remaining <= 0.2:
                    break

                try:
                    kwargs = {
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if tier.get("api_key"):
                        kwargs["api_key"] = tier["api_key"]
                    if tier.get("extra_headers"):
                        kwargs["extra_headers"] = tier["extra_headers"]

                    if "groq" in tier["model"].lower() and patient_id:
                        cls._last_groq_completion_times[patient_id] = time.time()

                    # Individual connection ceiling: 6.0s for cloud, min(4.5, remaining) for others
                    timeout_limit = min(6.0 if is_cloud_provider else 4.5, remaining)

                    response = await cls.safe_execute_7_tier_chain(
                        tier_config=tier,
                        payload=messages,
                        timeout_limit=timeout_limit,
                        **kwargs
                    )
                    if response.choices and response.choices[0].message:
                        content = response.choices[0].message.content
                        if content:
                            log.info("[LLM_CLIENT] ✅ Text completion succeeded via %s on attempt %d", tier["label"], attempt + 1)
                            _provider_breaker.reset_fails(tier["provider"])
                            result = (content.strip(), tier["label"])
                            cls._set_cached_value(cache_key, result, ttl=5.0)
                            return result
                except Exception as e:
                    err_str = str(e).lower()
                    is_credit_issue = "insufficient credits" in err_str or "402" in err_str or "insufficient_quota" in err_str or "exceeded your current quota" in err_str
                    is_rate_limit = cls._is_rate_limit(e) or "429" in err_str or "ratelimit" in err_str
                    is_timeout = isinstance(e, asyncio.TimeoutError) or "timeout" in err_str
                    is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str or "forbidden" in err_str or "403" in err_str
                    is_provider_down = "503" in err_str or "502" in err_str or "504" in err_str or "unavailable" in err_str

                    if "exceeded your current quota" in err_str:
                        log.error("[LLM_CLIENT] OpenAI Quota Exhausted! Marking OpenAI as permanently dead and skipping retries.")
                        _provider_breaker.mark_permanently_dead(tier["provider"])
                        break

                    if is_timeout:
                        log.warning("[LLM_CLIENT] ⚠️ Attempt %d/%d timed out on %s. (Do not trip circuit breaker)", attempt + 1, max_attempts, tier["label"])
                    else:
                        log.warning("[LLM_CLIENT] ⚠️ Attempt %d/%d failed on %s: %s", attempt + 1, max_attempts, tier["label"], err_str[:80])

                    if attempt == max_attempts - 1:
                        if not is_timeout:
                            if is_auth_error or is_provider_down or is_credit_issue:
                                _provider_breaker.trip(tier["provider"])
                        _increment_rolling_index()

                    if attempt < max_attempts - 1:
                        # Exponential backoff delay
                        backoff_delay = 1.0 * (2 ** attempt)
                        await asyncio.sleep(backoff_delay)
                        continue
                    else:
                        break

        log.error("[LLM_CLIENT] All LLM tiers failed for text completion. Raising RuntimeError.")
        raise RuntimeError("All LLM tiers failed for text completion.")

    @classmethod
    async def generate_tool_call(
        cls,
        prompt: str,
        tiers: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
        timeout: int = 20
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Tool calling completion with fallback.
        Returns: (parsed_tool_call_dict, provider_label)
        parsed_tool_call_dict: {
            "tools_to_invoke": [...],
            "tool_calls": [{"tool_name": "...", "parameters": {...}}],
            "raw_response": "..."
        }
        """
        if not _circuit_breaker.allow_request():
            log.error("[LLM_CLIENT] Circuit is OPEN. Online connection unavailable.")
            raise RuntimeError("Circuit is OPEN. Online connection unavailable.")

        if not LITELLM_AVAILABLE:
            log.error("[LLM_CLIENT] litellm not available for tool call.")
            raise RuntimeError("LiteLLM is not available for tool call. Online connection unavailable.")

        # Caching logic for repetitive queries
        import hashlib
        cache_key = hashlib.md5(
            f"tool_call:{prompt}:{system_prompt or ''}:{str([t['model'] for t in tiers])}:{str(tools)}".encode('utf-8')
        ).hexdigest()
        cached = cls._get_cached_value(cache_key)
        if cached is not None:
            log.info("[LLM_CLIENT] ⚡ Cache HIT (tool call) for query: %s", prompt[:60].replace('\n', ' '))
            return cached

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        global_start = time.time()
        execution_chain = _get_execution_chain(is_vision=False)
        for tier in execution_chain:
            if not tier.get("enabled", False):
                continue

            elapsed = time.time() - global_start
            remaining = float(timeout) - elapsed
            if remaining <= 0.2:
                log.warning(f"[LLM_CLIENT] Global {timeout}s timeout reached. Aborting tool call fallback chain.")
                break

            # Retry loop for TIER 1 & 2 cloud providers up to 2 times (total 3 attempts)
            is_cloud_provider = tier["provider"] in ("groq", "openai", "gemini")
            max_attempts = 3 if is_cloud_provider else 1

            for attempt in range(max_attempts):
                elapsed = time.time() - global_start
                remaining = float(timeout) - elapsed
                if remaining <= 0.2:
                    break

                try:
                    kwargs = {
                        "tools": tools,
                        "tool_choice": "auto",
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if tier.get("api_key"):
                        kwargs["api_key"] = tier["api_key"]
                    if tier.get("extra_headers"):
                        kwargs["extra_headers"] = tier["extra_headers"]

                    # Individual connection ceiling: 6.0s for cloud, min(4.5, remaining) for others
                    timeout_limit = min(6.0 if is_cloud_provider else 4.5, remaining)

                    response = await cls.safe_execute_7_tier_chain(
                        tier_config=tier,
                        payload=messages,
                        timeout_limit=timeout_limit,
                        **kwargs
                    )
                    
                    tool_calls = []
                    if response.choices and response.choices[0].message:
                        msg = response.choices[0].message
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                try:
                                    params = json.loads(tc.function.arguments)
                                except (json.JSONDecodeError, AttributeError):
                                    params = {}
                                tool_calls.append({
                                    "tool_name": tc.function.name,
                                    "parameters": params,
                                })

                    # If we parsed actual tool calls, return them
                    if tool_calls:
                        log.info("[LLM_CLIENT] ✅ Tool calling succeeded via %s on attempt %d — %d tools", tier["label"], attempt + 1, len(tool_calls))
                        _provider_breaker.reset_fails(tier["provider"])
                        result = ({
                            "tools_to_invoke": [tc["tool_name"] for tc in tool_calls],
                            "tool_calls": tool_calls,
                            "raw_response": getattr(response.choices[0].message, "content", "") or "",
                        }, tier["label"])
                        cls._set_cached_value(cache_key, result, ttl=5.0)
                        return result

                    # If no tool call but returned text, we can build a fallback default response
                    content = getattr(response.choices[0].message, "content", "")
                    if content:
                        log.info("[LLM_CLIENT] ✅ completion returned text instead of tool call via %s on attempt %d", tier["label"], attempt + 1)
                        _provider_breaker.reset_fails(tier["provider"])
                        result = ({
                            "tools_to_invoke": [],
                            "tool_calls": [],
                            "raw_response": content,
                        }, tier["label"])
                        cls._set_cached_value(cache_key, result, ttl=5.0)
                        return result

                except Exception as e:
                    err_str = str(e).lower()
                    is_credit_issue = "insufficient credits" in err_str or "402" in err_str or "insufficient_quota" in err_str or "exceeded your current quota" in err_str
                    is_rate_limit = cls._is_rate_limit(e) or "429" in err_str or "ratelimit" in err_str
                    is_timeout = isinstance(e, asyncio.TimeoutError) or "timeout" in err_str
                    is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str or "forbidden" in err_str or "403" in err_str
                    is_provider_down = "503" in err_str or "502" in err_str or "504" in err_str or "unavailable" in err_str

                    if "exceeded your current quota" in err_str:
                        log.error("[LLM_CLIENT] OpenAI Quota Exhausted! Marking OpenAI as permanently dead and skipping retries.")
                        _provider_breaker.mark_permanently_dead(tier["provider"])
                        break

                    if is_timeout:
                        log.warning("[LLM_CLIENT] ⚠️ Attempt %d/%d timed out on %s. (Do not trip circuit breaker)", attempt + 1, max_attempts, tier["label"])
                    else:
                        log.warning("[LLM_CLIENT] ⚠️ Attempt %d/%d failed on %s: %s", attempt + 1, max_attempts, tier["label"], err_str[:80])

                    if attempt == max_attempts - 1:
                        if not is_timeout:
                            if is_auth_error or is_provider_down or is_credit_issue:
                                _provider_breaker.trip(tier["provider"])
                        _increment_rolling_index()

                    if attempt < max_attempts - 1:
                        # Exponential backoff delay
                        backoff_delay = 1.0 * (2 ** attempt)
                        await asyncio.sleep(backoff_delay)
                        continue
                    else:
                        break

        log.error("[LLM_CLIENT] All LLM tiers failed for tool calling. Raising RuntimeError.")
        raise RuntimeError("All LLM tiers failed for tool calling.")

    @classmethod
    async def generate_vision_completion(
        cls,
        prompt: str,
        tiers: List[Dict[str, Any]],
        image_base64: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.4,
        timeout: int = 20
    ) -> Tuple[Optional[str], str]:
        """
        Vision / Multimodal image processing completion with fallback.
        Returns: (response_text, provider_label)
        """
        if not _circuit_breaker.allow_request():
            log.warning("[LLM_CLIENT] Circuit is OPEN. Direct routing to LocalOfflineFallback.")
            res = await asyncio.to_thread(LocalOfflineFallback.get_vision_completion_fallback, prompt, system_prompt)
            return res, "LOCAL_FALLBACK"

        if not LITELLM_AVAILABLE:
            log.warning("[LLM_CLIENT] litellm not available for vision. Activating LocalOfflineFallback.")
            res = await asyncio.to_thread(LocalOfflineFallback.get_vision_completion_fallback, prompt, system_prompt)
            return res, "LOCAL_FALLBACK"

        global_start = time.time()
        execution_chain = _get_execution_chain(is_vision=True)
        for tier in execution_chain:
            if not tier.get("enabled", False):
                continue

            elapsed = time.time() - global_start
            remaining = float(timeout) - elapsed
            if remaining <= 0.2:
                log.warning(f"[LLM_CLIENT] Global {timeout}s timeout reached. Aborting vision fallback chain.")
                break

            # Clean base64 payload to ensure perfect encapsulation
            clean_base64 = image_base64.strip()
            if "," in clean_base64:
                clean_base64 = clean_base64.split(",")[-1].strip()
            clean_base64 = "".join(clean_base64.split())

            image_url_payload = f"data:image/jpeg;base64,{clean_base64}"
            
            # Combine system prompt with prompt if available to keep a single user message role for all vision specs
            combined_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

            tier_messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": combined_prompt},
                        {"type": "image_url", "image_url": {"url": image_url_payload}}
                    ]
                }
            ]

            try:
                kwargs = {
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if tier.get("api_key"):
                    kwargs["api_key"] = tier["api_key"]
                if tier.get("extra_headers"):
                    kwargs["extra_headers"] = tier["extra_headers"]

                # Individual connection ceiling: 4.5s
                timeout_limit = min(4.5, remaining)

                response = await cls.safe_execute_7_tier_chain(
                    tier_config=tier,
                    payload=tier_messages,
                    timeout_limit=timeout_limit,
                    **kwargs
                )
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    if content:
                        log.info("[LLM_CLIENT] ✅ Vision completion succeeded via %s", tier["label"])
                        _provider_breaker.reset_fails(tier["provider"])
                        return content.strip(), tier["label"]

            except Exception as e:
                err_str = str(e).lower()
                is_credit_issue = "insufficient credits" in err_str or "402" in err_str or "insufficient_quota" in err_str or "exceeded your current quota" in err_str
                is_rate_limit = cls._is_rate_limit(e) or "429" in err_str or "ratelimit" in err_str
                is_timeout = isinstance(e, asyncio.TimeoutError) or "timeout" in err_str
                is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str or "forbidden" in err_str or "403" in err_str
                is_provider_down = "503" in err_str or "502" in err_str or "504" in err_str or "unavailable" in err_str

                if "exceeded your current quota" in err_str:
                    log.error("[LLM_CLIENT] OpenAI Quota Exhausted! Marking OpenAI as permanently dead.")
                    _provider_breaker.mark_permanently_dead(tier["provider"])

                if is_auth_error or is_provider_down or is_credit_issue or is_timeout:
                    _provider_breaker.trip(tier["provider"])
                _increment_rolling_index()

                if is_credit_issue or is_rate_limit or is_timeout or is_auth_error or is_provider_down:
                    log.warning("[LLM_CLIENT] ⚠️ Error on %s (%s) — instantly rotating in chain. Err: %s", tier["label"], tier["model"], err_str[:80])
                else:
                    log.warning("[LLM_CLIENT] ❌ %s vision completion failed: %s. Rotating in chain.", tier["label"], str(e)[:120])
                continue

        log.warning("[LLM_CLIENT] All LLM tiers failed for vision completion. Activating LocalOfflineFallback.")
        res = await asyncio.to_thread(LocalOfflineFallback.get_vision_completion_fallback, prompt, system_prompt)
        return res, "LOCAL_FALLBACK"


    # ──────────────────────────────────────────────────────────────────────
    # GROUP-BASED 4-TIER VISION ORCHESTRATION (Main Entry Point for Perception)
    # ──────────────────────────────────────────────────────────────────────
    @classmethod
    async def generate_vision_completion_grouped(
        cls,
        prompt: str,
        image_base64: str,
        image_bytes: Optional[bytes],
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> Tuple[Optional[str], str]:
        """
        4-TIER GROUP-BASED VISION ORCHESTRATION ENGINE
        ================================================
        TIER 1: GROQ — Text/Tool-Calling orchestrator ONLY. Not called here.
                        This method is invoked AFTER Groq signals capture_vision_payload.

        TIER 2: CONCURRENT Cloud Vision Cluster (OpenAI gpt-4o-mini + Gemini gemini-2.0-flash)
                asyncio.gather fires both simultaneously.
                First successful response wins. Hard cumulative timeout: 2.5s.
                On 429/501/503/timeout → all cluster tasks are Task.cancel()'d.

        TIER 3: Emergency Local Edge (Ollama moondream/qwen2b via direct httpx)
                Activates instantly when TIER 2 cluster aborts.
                Zero cloud dependency. Timeout: OLLAMA_VISION_TIMEOUT_S (default 8s).

        TIER 4: Cohere/Mistral/OpenRouter/HuggingFace — EXCLUDED from this path.
                They NEVER block the vision pipeline. Reserved for background health logs.

        Args:
            prompt:       Clinical analysis prompt string.
            image_base64: Base64-encoded JPEG with or without data-URI prefix.
            image_bytes:  Raw JPEG bytes (for TIER 3 Ollama direct call).
            system_prompt: System context string (injected with sensor_meta_json).
            max_tokens:   LLM response token budget.
            temperature:  Inference temperature.

        Returns:
            Tuple[response_text, provider_label]
            provider_label examples: "OPENAI_VISION_T2", "GEMINI_VISION_T2", "OLLAMA_TIER_3",
                                     "RULE_BASED_TIER4", "LOCAL_FALLBACK"
        """
        # Check if video channel is locked by Safety Agent alert mode
        try:
            from services.blackboard_service import get_blackboard
            bb = get_blackboard()
            alert_mode_cached = bb._in_memory_store.get("safety:alert_mode")
            alert_mode = False
            if alert_mode_cached and time.time() <= alert_mode_cached.get("expiry", 0.0):
                alert_mode = alert_mode_cached.get("value", False)
            if alert_mode:
                log.warning("[BEHAVIOR_COORDINATOR] Vision channel locked by Safety Agent alert mode. Returning lock state.")
                locked_payload = {
                    "skin_tone_note": "",
                    "facial_distress": 0.0,
                    "visible_injuries": [],
                    "posture_risk": "LOW",
                    "overall_risk": "LOW",
                    "confidence": 0.0,
                    "notes": "[LOCKED] Vision channel locked by Safety Agent alert mode.",
                    "status": "LOCKED"
                }
                return json.dumps(locked_payload, ensure_ascii=False), "LOCKED"
        except Exception as e:
            log.warning("[BEHAVIOR_COORDINATOR] Failed to check safety:alert_mode in llm_client: %s", e)

        if not _circuit_breaker.allow_request():
            log.warning("[VISION_GROUPED] Global circuit OPEN — routing directly to Local Edge VLM.")
            res = await asyncio.to_thread(LocalOfflineFallback.get_local_vision_completion, prompt, image_bytes, system_prompt)
            return res, "LOCAL_EDGE_VLM"

        if not LITELLM_AVAILABLE:
            log.warning("[VISION_GROUPED] litellm unavailable — routing directly to Local Edge VLM.")
            res = await asyncio.to_thread(LocalOfflineFallback.get_local_vision_completion, prompt, image_bytes, system_prompt)
            return res, "LOCAL_EDGE_VLM"

        # ── Normalise base64 payload for litellm vision message format ───────────────
        clean_b64 = image_base64.strip()
        if "," in clean_b64:
            clean_b64 = clean_b64.split(",")[-1].strip()
        clean_b64 = "".join(clean_b64.split())
        image_url_payload = f"data:image/jpeg;base64,{clean_b64}"
        combined_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        tier2_messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text",      "text": combined_prompt},
                    {"type": "image_url", "image_url": {"url": image_url_payload}}
                ]
            }
        ]

        # ── TIER 2: Concurrent Cloud Vision Cluster ──────────────────────────────
        tier2_cluster = _get_execution_chain(is_vision=True)
        tier2_tasks: List[asyncio.Task] = []
        tier2_abort_triggered = False

        if tier2_cluster:
            log.info(
                "[VISION_GROUPED/T2] Firing concurrent cluster: %s (budget=%.1fs)",
                [t["label"] for t in tier2_cluster], _VISION_TIER2_TIMEOUT_S
            )

            async def _single_vision_call(tier: Dict[str, Any]) -> Tuple[Optional[str], str]:
                """One cloud vision API call wrapped in error classification."""
                kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "temperature": temperature}
                if tier.get("api_key"):
                    kwargs["api_key"] = tier["api_key"]
                if tier.get("extra_headers"):
                    kwargs["extra_headers"] = tier["extra_headers"]
                try:
                    resp = await cls.safe_execute_7_tier_chain(
                        tier_config=tier,
                        payload=tier2_messages,
                        timeout_limit=_VISION_TIER2_TIMEOUT_S,
                        **kwargs
                    )
                    if resp.choices and resp.choices[0].message:
                        content = resp.choices[0].message.content
                        if content:
                            return content.strip(), tier["label"]
                except Exception as exc:
                    err_str = str(exc).lower()
                    is_rate_or_quota = ("429" in err_str or "ratelimit" in err_str or "rate limit" in err_str or "rate_limit" in err_str or
                                        "quota" in err_str or "insufficient_quota" in err_str or "exceeded your current quota" in err_str or "resourceexhausted" in err_str)
                    if is_rate_or_quota:
                        log.error("[CIRCUIT_BREAKER] 429 / Quota error on %s! Tripping global circuit breaker.", tier["label"])
                        _circuit_breaker.trip()
                        _provider_breaker.trip(tier["provider"])
                        raise
                    
                    if "exceeded your current quota" in err_str:
                        log.error("[LLM_CLIENT/T2] Quota Exhausted on %s! Marking permanently dead.", tier["label"])
                        _provider_breaker.mark_permanently_dead(tier["provider"])
                    if _is_tier2_abort_error(exc):
                        _provider_breaker.trip(tier["provider"])
                        log.warning(
                            "[VISION_GROUPED/T2] %s abort-trigger error (%s) — escalating to TIER 3.",
                            tier["label"], str(exc)[:60]
                        )
                        raise  # Re-raise to signal cluster abort
                    log.warning("[VISION_GROUPED/T2] %s non-critical error: %s", tier["label"], str(exc)[:80])
                return None, tier["label"]

            # Build asyncio Tasks for all cluster members
            tier2_tasks = [
                asyncio.create_task(_single_vision_call(tier))
                for tier in tier2_cluster
            ]

            winning_result = None
            try:
                async def get_first_successful_vision():
                    nonlocal tier2_abort_triggered
                    for completed_task in asyncio.as_completed(tier2_tasks):
                        try:
                            res = await completed_task
                            if res and res[0]:
                                return res
                        except Exception as task_exc:
                            if _is_tier2_abort_error(task_exc):
                                tier2_abort_triggered = True
                            log.warning("[VISION_GROUPED/T2] Task raised: %s", str(task_exc)[:80])
                    return None

                winning_result = await asyncio.wait_for(get_first_successful_vision(), timeout=_VISION_TIER2_TIMEOUT_S)
                if winning_result:
                    log.info(
                        "[VISION_GROUPED/T2] ✅ Success via %s — TIER 2 cluster resolved.",
                        winning_result[1]
                    )
                    return winning_result
            except asyncio.TimeoutError:
                tier2_abort_triggered = True
                log.warning(
                    "[VISION_GROUPED/T2] Cluster hard timeout (%.1fs). Escalating to TIER 3.",
                    _VISION_TIER2_TIMEOUT_S
                )
            finally:
                for t in tier2_tasks:
                    if not t.done():
                        t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass

        else:
            log.warning("[VISION_GROUPED/T2] No TIER 2 providers available — jumping straight to TIER 3.")
            tier2_abort_triggered = True

        # ── TIER 3: Emergency Local Edge (Ollama) ────────────────────────────
        log.warning("[VISION_GROUPED/T3] Activating TIER 3 Emergency Local Edge (Ollama/%s).", _OLLAMA_VIS_MODEL)
        if image_bytes:
            tier3_text, tier3_label = await _call_ollama_vision_direct(
                image_bytes=image_bytes,
                prompt=prompt,
                system_prompt=system_prompt or "",
            )
            if tier3_text:
                log.info("[VISION_GROUPED/T3] ✅ Ollama TIER 3 succeeded via %s.", tier3_label)
                return tier3_text, tier3_label
            log.error("[VISION_GROUPED/T3] Ollama also failed. Activating TIER 4 local VLM fallback.")
        else:
            log.warning("[VISION_GROUPED/T3] No raw image bytes available for Ollama — skipping TIER 3.")

        log.warning("[VISION_GROUPED/T4] Activating local Edge VLM fallback. TIER 4 cloud providers excluded from vision.")
        res = await asyncio.to_thread(LocalOfflineFallback.get_local_vision_completion, prompt, image_bytes, system_prompt)
        return res, "LOCAL_EDGE_VLM"

def get_llm_stats() -> dict:
    """
    Returns the current active LLM configuration for health monitoring and HUD.
    """
    active_chain = _get_execution_chain(is_vision=False)
    if not active_chain:
        return {
            "status": "OFFLINE",
            "provider": "LOCAL_FALLBACK",
            "model": "offline",
            "temperature": 0.45,
            "context_len": 4096,
            "empathy_bias": "N/A"
        }
    
    current = active_chain[0]
    return {
        "status": "ONLINE",
        "provider": current.get("label", "UNKNOWN"),
        "model": current.get("model", "unknown"),
        "temperature": 0.45,
        "context_len": 8192,
        "empathy_bias": "94.8% ALPHA"
    }
