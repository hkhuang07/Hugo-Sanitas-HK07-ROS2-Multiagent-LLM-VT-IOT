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
    def __init__(self, recovery_time=30.0):
        self.recovery_time = float(recovery_time)
        self.state = "CLOSED"  # CLOSED, OPEN
        self.last_trip_time = 0.0

    def trip(self):
        self.state = "OPEN"
        self.last_trip_time = float(time.time())
        log.error(f"[LLM_CLIENT_CB] Circuit Breaker tripped to OPEN. Routing to LocalOfflineFallback for {self.recovery_time}s.")

    def allow_request(self) -> bool:
        if self.state == "OPEN":
            if float(time.time()) - self.last_trip_time >= self.recovery_time:
                self.state = "CLOSED"
                log.warning("[LLM_CLIENT_CB] Circuit Breaker closed. Restoring API requests.")
                return True
            return False
        return True

_circuit_breaker = LLMClientCircuitBreaker()
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

# Import llama-cpp-python for local quantized SLM support
try:
    import llama_cpp
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    log.warning("[LLM_CLIENT] llama-cpp-python not installed — local SLM offline fallback will be rule-based!")

# ─── API keys from environment ────────────────────────────────────────────────
_GROQ_KEY        = os.getenv("GROQ_API_KEY", "")
_OPENAI_KEY      = os.getenv("OPENAI_API_KEY", "")
_GEMINI_KEY      = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_GENERATIVEAI_API_KEY", ""))
_MISTRAL_KEY     = os.getenv("MISTRAL_API_KEY", "")
_COHERE_KEY      = os.getenv("COHERE_API_KEY", "")
_OPENROUTER_KEY  = os.getenv("OPENROUTER_API_KEY", "")
_HF_KEY          = os.getenv("HUGGINGFACE_API_KEY", "")

class ProviderCircuitBreaker:
    def __init__(self, recovery_time=30.0):
        self.recovery_time = float(recovery_time)
        self._tripped_providers = {}

    def trip(self, provider: str):
        p = provider.lower()
        self._tripped_providers[p] = time.time()
        log.error(f"[PROVIDER_CB] Tripped {p.upper()} due to 429/401/503. Offline for {self.recovery_time}s.")

    def is_tripped(self, provider: str) -> bool:
        p = provider.lower()
        if p in self._tripped_providers:
            if time.time() - self._tripped_providers[p] >= self.recovery_time:
                del self._tripped_providers[p]
                log.warning(f"[PROVIDER_CB] Restored connection to {p.upper()}.")
                return False
            return True
        return False

_provider_breaker = ProviderCircuitBreaker()
_rolling_start_index = 0

def _increment_rolling_index():
    global _rolling_start_index
    _rolling_start_index += 1

def _get_execution_chain(is_vision=False) -> List[Dict[str, Any]]:
    # Load all keys dynamically to allow hot-reloading if env changes
    groq_key = os.getenv("GROQ_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_GENERATIVEAI_API_KEY", ""))
    mistral_key = os.getenv("MISTRAL_API_KEY", "")
    cohere_key = os.getenv("COHERE_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    hf_key = os.getenv("HUGGINGFACE_API_KEY", "")

    # Define the 7 Tiers Failover & Specialization Graph
    chain = [
        {
            "provider": "groq",
            "model": "groq/llama-3.3-70b-versatile",
            "api_key": groq_key,
            "label": "GROQ_TIER_1",
            "enabled": bool(groq_key) and not is_vision,
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
        {
            "provider": "mistral",
            "model": "mistral/mistral-large-latest",
            "api_key": mistral_key,
            "label": "MISTRAL_TIER_4",
            "enabled": bool(mistral_key) and not is_vision,
        },
        {
            "provider": "cohere",
            "model": "cohere/command-r-plus",
            "api_key": cohere_key,
            "label": "COHERE_TIER_5",
            "enabled": bool(cohere_key) and not is_vision,
        },
        {
            "provider": "openrouter",
            "model": "openrouter/google/gemini-flash-1.5:free",
            "api_key": openrouter_key,
            "label": "OPENROUTER_TIER_6",
            "enabled": bool(openrouter_key),
            "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 Core"},
        },
        {
            "provider": "openrouter",
            "model": "openrouter/google/gemini-flash-1.5:free",
            "api_key": openrouter_key,
            "label": "OPENROUTER_TIER_6_ALT",
            "enabled": bool(openrouter_key),
            "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 Core"},
        },
        {
            "provider": "huggingface",
            "model": "huggingface/Qwen/Qwen2-VL-7B-Instruct" if is_vision else "huggingface/meta-llama/Meta-Llama-3-8B-Instruct",
            "api_key": hf_key,
            "label": "HUGGINGFACE_TIER_7",
            "enabled": bool(hf_key),
        }
    ]

    active_chain = []
    for tier in chain:
        if tier["enabled"] and not _provider_breaker.is_tripped(tier["provider"]):
            active_chain.append(tier)

    # Roll/rotate active chain based on the centralized rolling tracking index
    if active_chain:
        global _rolling_start_index
        shift = _rolling_start_index % len(active_chain)
        active_chain = active_chain[shift:] + active_chain[:shift]

    return active_chain

# ─── Standard Provider Tiers ──────────────────────────────────────────────────
ROUTER_TIERS: List[Dict[str, Any]] = []
MEDICAL_TIERS: List[Dict[str, Any]] = []
EMPATHY_TIERS: List[Dict[str, Any]] = []
VISION_TIERS: List[Dict[str, Any]] = []
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
            log.warning(f"[LOCAL_SLM] Quantized model file not found at: {model_path}. Please download the GGUF model. Falling back to rule-based fallback.")
            return None
            
        try:
            log.info(f"[LOCAL_SLM] Loading quantized SLM model from: {model_path}")
            import llama_cpp
            cls._model_instance = llama_cpp.Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=4,
                verbose=False
            )
            log.info("[LOCAL_SLM] Quantized SLM model loaded successfully.")
            return cls._model_instance
        except Exception as e:
            log.error(f"[LOCAL_SLM] Failed to load local SLM model: {e}")
            return None

    @classmethod
    def get_completion_fallback(cls, prompt: str, system_prompt: Optional[str] = None) -> str:
        model = cls.get_model()
        if model is None:
            return cls._rule_based_completion(prompt, system_prompt)

        model_path = os.getenv("LOCAL_SLM_MODEL_PATH", "models/phi-3-mini-4k-instruct-q4.gguf").lower()
        system = system_prompt or "You are Baymax, your personal healthcare companion. Operating in local offline mode."
        
        if "phi" in model_path:
            formatted_prompt = f"<|system|>\n{system}<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>\n"
        elif "llama" in model_path:
            formatted_prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        else:
            formatted_prompt = f"System: {system}\nUser: {prompt}\nAssistant: "

        try:
            log.info("[LOCAL_SLM] Generating text completion via local GGUF SLM...")
            response = model(
                formatted_prompt,
                max_tokens=256,
                temperature=0.3,
                stop=["<|end|>", "<|eot_id|>", "User:", "System:"],
                echo=False
            )
            text = response["choices"][0]["text"].strip()
            log.info("[LOCAL_SLM] Text generation succeeded.")
            return text
        except Exception as e:
            log.error(f"[LOCAL_SLM] Local SLM generation failed: {e}. Falling back to rule-based completion.")
            return cls._rule_based_completion(prompt, system_prompt)

    @classmethod
    def _rule_based_completion(cls, prompt: str, system_prompt: Optional[str] = None) -> str:
        prompt_lower = prompt.lower()
        
        # Check greetings
        if any(w in prompt_lower for w in ["hello", "hi", "chào", "xin chào", "hey"]):
            return (
                "Hello, I am Baymax, your personal healthcare companion. "
                "I am currently operating in offline fallback mode. "
                "How can I assist you with your health today?"
            )
            
        # Check emergency / SOS
        if any(w in prompt_lower for w in ["emergency", "sos", "stroke", "đột quỵ", "cấp cứu", "nguy kịch", "tai nạn"]):
            return (
                "[EMERGENCY ALERT] I have detected a potentially life-threatening situation. "
                "Although my primary cloud connection is offline, I am triggering the local emergency protocol. "
                "Please stay calm, rest immediately, and contact emergency medical services if you can."
            )
            
        # Check clinical symptoms / chest pain
        if any(w in prompt_lower for w in ["pain", "hurt", "chest", "headache", "fever", "đau", "sốt", "mệt", "ho"]):
            return (
                "I am currently offline, but based on your description, I advise you to rest and monitor your vitals. "
                "If you experience chest pressure, difficulty breathing, or severe pain, please seek immediate medical attention."
            )
            
        # Check connection / status
        if any(w in prompt_lower for w in ["status", "device", "sensor", "connection", "kết nối", "thiết bị"]):
            return (
                "System Status: ONLINE (Local Offline Fallback Mode). "
                "Primary LLM Cloud Service is currently unreachable. "
                "Local controllers and safety nodes are operational."
            )

        # Default fallback
        return (
            "I am Baymax, your personal healthcare companion. "
            "I am currently operating in offline mode due to a connection timeout. "
            "My local health monitors are active and tracking your vitals. Please let me know how I can help."
        )

    @classmethod
    def get_tool_call_fallback(cls, prompt: str, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        fallback_data = {
            "visible_injuries": {"detected": False, "details": "Offline vision fallback active"},
            "facial_distress": {"detected": False, "details": "Offline vision fallback active"},
            "environmental_hazards": {"detected": False, "details": "Offline vision fallback active"}
        }
        return json.dumps(fallback_data)


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
        Production-grade async LLM dispatch with explicit task lifecycle management.
        Prevents orphaned coroutine leaks by creating an explicit asyncio.Task
        and properly cancelling + awaiting it on timeout.
        """
        task = asyncio.ensure_future(
            litellm.acompletion(model=tier_config["model"], messages=payload, timeout=timeout_limit, **kwargs)
        )
        try:
            response = await asyncio.wait_for(task, timeout=timeout_limit)
            return response
        except asyncio.TimeoutError:
            # Explicitly cancel the task and await it to drain any internal coroutines
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            log.error(f"Tier {tier_config['label']} hit hard budget timeout. Rotating...")
            raise asyncio.TimeoutError(f"Tier {tier_config['label']} timed out.") from None
        except Exception:
            # On non-timeout errors, ensure task is cleaned up if still running
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
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
        timeout: int = 12,
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
                log.warning(f"[LLM_CLIENT_LIMITER] Patient {patient_id} LLM query debounced (last was {elapsed:.2f}s ago). Routing immediately to LocalOfflineFallback.")
                return LocalOfflineFallback.get_completion_fallback(prompt, system_prompt), "LOCAL_FALLBACK"

        if not _circuit_breaker.allow_request():
            log.warning("[LLM_CLIENT] Circuit is OPEN. Direct routing to LocalOfflineFallback.")
            return LocalOfflineFallback.get_completion_fallback(prompt, system_prompt), "LOCAL_FALLBACK"

        if not LITELLM_AVAILABLE:
            log.warning("[LLM_CLIENT] litellm not available. Activating LocalOfflineFallback.")
            return LocalOfflineFallback.get_completion_fallback(prompt, system_prompt), "LOCAL_FALLBACK"

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
            remaining = 5.0 - elapsed
            if remaining <= 0.2:
                log.warning("[LLM_CLIENT] Global 5.0s timeout reached. Aborting completion fallback chain.")
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

                response = await cls.safe_execute_7_tier_chain(
                    tier_config=tier,
                    payload=messages,
                    timeout_limit=min(1.5, remaining),
                    **kwargs
                )
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    if content:
                        log.info("[LLM_CLIENT] ✅ Text completion succeeded via %s", tier["label"])
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

                if is_auth_error or is_provider_down or is_credit_issue or is_timeout:
                    _provider_breaker.trip(tier["provider"])
                _increment_rolling_index()

                if is_credit_issue or is_rate_limit or is_timeout or is_auth_error or is_provider_down:
                    log.warning("[LLM_CLIENT] ⚠️ Error on %s (%s) — instantly rotating in chain. Err: %s", tier["label"], tier["model"], err_str[:80])
                else:
                    log.warning("[LLM_CLIENT] ❌ %s execution failed: %s. Rotating in chain.", tier["label"], str(e)[:120])
                continue

        log.warning("[LLM_CLIENT] All LLM tiers failed for text completion. Activating LocalOfflineFallback.")
        return LocalOfflineFallback.get_completion_fallback(prompt, system_prompt), "LOCAL_FALLBACK"

    @classmethod
    async def generate_tool_call(
        cls,
        prompt: str,
        tiers: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
        timeout: int = 10
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
            log.warning("[LLM_CLIENT] Circuit is OPEN. Direct routing to LocalOfflineFallback.")
            return LocalOfflineFallback.get_tool_call_fallback(prompt, tools), "LOCAL_FALLBACK"

        if not LITELLM_AVAILABLE:
            log.warning("[LLM_CLIENT] litellm not available for tool call. Activating LocalOfflineFallback.")
            return LocalOfflineFallback.get_tool_call_fallback(prompt, tools), "LOCAL_FALLBACK"

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
            remaining = 5.0 - elapsed
            if remaining <= 0.2:
                log.warning("[LLM_CLIENT] Global 5.0s timeout reached. Aborting tool call fallback chain.")
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

                response = await cls.safe_execute_7_tier_chain(
                    tier_config=tier,
                    payload=messages,
                    timeout_limit=min(1.2, remaining),
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
                    log.info("[LLM_CLIENT] ✅ Tool calling succeeded via %s — %d tools", tier["label"], len(tool_calls))
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
                    log.info("[LLM_CLIENT] ✅ completion returned text instead of tool call via %s", tier["label"])
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

                if is_auth_error or is_provider_down or is_credit_issue or is_timeout:
                    _provider_breaker.trip(tier["provider"])
                _increment_rolling_index()

                if is_credit_issue or is_rate_limit or is_timeout or is_auth_error or is_provider_down:
                    log.warning("[LLM_CLIENT] ⚠️ Error on %s (%s) — instantly rotating in chain. Err: %s", tier["label"], tier["model"], err_str[:80])
                else:
                    log.warning("[LLM_CLIENT] ❌ %s tool call failed: %s. Rotating in chain.", tier["label"], str(e)[:120])
                continue

        log.warning("[LLM_CLIENT] All LLM tiers failed for tool calling. Activating LocalOfflineFallback.")
        return LocalOfflineFallback.get_tool_call_fallback(prompt, tools), "LOCAL_FALLBACK"

    @classmethod
    async def generate_vision_completion(
        cls,
        prompt: str,
        tiers: List[Dict[str, Any]],
        image_base64: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.4,
        timeout: int = 15
    ) -> Tuple[Optional[str], str]:
        """
        Vision / Multimodal image processing completion with fallback.
        Returns: (response_text, provider_label)
        """
        if not _circuit_breaker.allow_request():
            log.warning("[LLM_CLIENT] Circuit is OPEN. Direct routing to LocalOfflineFallback.")
            return LocalOfflineFallback.get_vision_completion_fallback(prompt, system_prompt), "LOCAL_FALLBACK"

        if not LITELLM_AVAILABLE:
            log.warning("[LLM_CLIENT] litellm not available for vision. Activating LocalOfflineFallback.")
            return LocalOfflineFallback.get_vision_completion_fallback(prompt, system_prompt), "LOCAL_FALLBACK"

        global_start = time.time()
        execution_chain = _get_execution_chain(is_vision=True)
        for tier in execution_chain:
            if not tier.get("enabled", False):
                continue

            elapsed = time.time() - global_start
            remaining = 5.0 - elapsed
            if remaining <= 0.2:
                log.warning("[LLM_CLIENT] Global 5.0s timeout reached. Aborting vision fallback chain.")
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

                response = await cls.safe_execute_7_tier_chain(
                    tier_config=tier,
                    payload=tier_messages,
                    timeout_limit=min(1.5, remaining),
                    **kwargs
                )
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    if content:
                        log.info("[LLM_CLIENT] ✅ Vision completion succeeded via %s", tier["label"])
                        return content.strip(), tier["label"]

            except Exception as e:
                err_str = str(e).lower()
                is_credit_issue = "insufficient credits" in err_str or "402" in err_str or "insufficient_quota" in err_str or "exceeded your current quota" in err_str
                is_rate_limit = cls._is_rate_limit(e) or "429" in err_str or "ratelimit" in err_str
                is_timeout = isinstance(e, asyncio.TimeoutError) or "timeout" in err_str
                is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str or "forbidden" in err_str or "403" in err_str
                is_provider_down = "503" in err_str or "502" in err_str or "504" in err_str or "unavailable" in err_str

                if is_auth_error or is_provider_down or is_credit_issue or is_timeout:
                    _provider_breaker.trip(tier["provider"])
                _increment_rolling_index()

                if is_credit_issue or is_rate_limit or is_timeout or is_auth_error or is_provider_down:
                    log.warning("[LLM_CLIENT] ⚠️ Error on %s (%s) — instantly rotating in chain. Err: %s", tier["label"], tier["model"], err_str[:80])
                else:
                    log.warning("[LLM_CLIENT] ❌ %s vision completion failed: %s. Rotating in chain.", tier["label"], str(e)[:120])
                continue

        log.warning("[LLM_CLIENT] All LLM tiers failed for vision completion. Activating LocalOfflineFallback.")
        return LocalOfflineFallback.get_vision_completion_fallback(prompt, system_prompt), "LOCAL_FALLBACK"
