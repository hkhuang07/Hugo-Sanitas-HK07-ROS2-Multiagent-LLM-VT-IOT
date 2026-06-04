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
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Load env from parent directory
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

log = logging.getLogger("hk07.llm_client")

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

# ─── API keys from environment ────────────────────────────────────────────────
_GROQ_KEY        = os.getenv("GROQ_API_KEY", "")
_OPENAI_KEY      = os.getenv("OPENAI_API_KEY", "")
_OPENROUTER_KEY  = os.getenv("OPENROUTER_API_KEY", "")
_COHERE_KEY      = os.getenv("COHERE_API_KEY", "")
_MISTRAL_KEY     = os.getenv("MISTRAL_API_KEY", "")
_GEMINI_KEY      = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_GENERATIVEAI_API_KEY", ""))

# ─── Standard Provider Tiers ──────────────────────────────────────────────────
ROUTER_TIERS: List[Dict[str, Any]] = [
    {
        "model": "groq/llama-3.3-70b-versatile",
        "api_key": _GROQ_KEY,
        "label": "GROQ_LLAMA_70B",
        "enabled": bool(_GROQ_KEY),
    },
    {
        "model": "openrouter/openai/gpt-4o-mini",
        "api_key": _OPENROUTER_KEY,
        "label": "OPENROUTER_GPT4O_MINI",
        "enabled": bool(_OPENROUTER_KEY),
        "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 Router"},
    },
]

MEDICAL_TIERS: List[Dict[str, Any]] = [
    {
        "model": "groq/llama-3.3-70b-versatile",
        "api_key": _GROQ_KEY,
        "label": "GROQ_LLAMA_70B",
        "enabled": bool(_GROQ_KEY),
    },
    {
        "model": "openrouter/openai/gpt-4o-mini",
        "api_key": _OPENROUTER_KEY,
        "label": "OPENROUTER_GPT4O_MINI",
        "enabled": bool(_OPENROUTER_KEY),
        "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 Medical"},
    },
    {
        "model": "openai/gpt-4o",
        "api_key": _OPENAI_KEY,
        "label": "OPENAI_GPT4O",
        "enabled": bool(_OPENAI_KEY),
    },
    {
        "model": "openrouter/anthropic/claude-3-haiku",
        "api_key": _OPENROUTER_KEY,
        "label": "OPENROUTER_CLAUDE_HAIKU",
        "enabled": bool(_OPENROUTER_KEY),
        "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 Medical"},
    },
]

EMPATHY_TIERS: List[Dict[str, Any]] = [
    {
        "model": "groq/llama-3.3-70b-versatile",
        "api_key": _GROQ_KEY,
        "label": "GROQ_LLAMA_70B",
        "enabled": bool(_GROQ_KEY),
    },
    {
        "model": "openrouter/openai/gpt-4o-mini",
        "api_key": _OPENROUTER_KEY,
        "label": "OPENROUTER_GPT4O_MINI",
        "enabled": bool(_OPENROUTER_KEY),
        "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 Empathy"},
    },
    {
        "model": "openai/gpt-4o-mini",
        "api_key": _OPENAI_KEY,
        "label": "OPENAI_GPT4O_MINI",
        "enabled": bool(_OPENAI_KEY),
    },
    {
        "model": "cohere/command-r",
        "api_key": _COHERE_KEY,
        "label": "COHERE_COMMAND_R",
        "enabled": bool(_COHERE_KEY),
    },
]

# Centralized Vision & Multimodal Tiers (Groq is primary, Gemini/OpenAI are fallbacks)
VISION_TIERS: List[Dict[str, Any]] = [
    {
        "model": "groq/llama-3.2-90b-vision-preview",
        "api_key": _GROQ_KEY,
        "label": "GROQ_LLAMA_90B_VISION",
        "enabled": bool(_GROQ_KEY),
    },
    {
        "model": "openrouter/openai/gpt-4o-mini",
        "api_key": _OPENROUTER_KEY,
        "label": "OPENROUTER_VISION_MINI",
        "enabled": bool(_OPENROUTER_KEY),
        "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 Vision"},
    },
    {
        "model": "openai/gpt-4o-mini",
        "api_key": _OPENAI_KEY,
        "label": "OPENAI_VISION_MINI",
        "enabled": bool(_OPENAI_KEY),
    },
    {
        "model": "gemini/gemini-1.5-flash",
        "api_key": _GEMINI_KEY,
        "label": "GEMINI_FLASH_VISION",
        "enabled": bool(_GEMINI_KEY),
    },
]

# Centralized System Queries Tiers (Tool Calling enabled)
SYSTEM_QUERY_TIERS: List[Dict[str, Any]] = [
    {
        "model": "groq/llama-3.3-70b-versatile",
        "api_key": _GROQ_KEY,
        "label": "GROQ_LLAMA_70B",
        "enabled": bool(_GROQ_KEY),
    },
    {
        "model": "openrouter/openai/gpt-4o-mini",
        "api_key": _OPENROUTER_KEY,
        "label": "OPENROUTER_GPT4O_MINI",
        "enabled": bool(_OPENROUTER_KEY),
        "extra_headers": {"HTTP-Referer": "https://hk07-hugobot.local", "X-Title": "HK-07 System Query"},
    },
    {
        "model": "openai/gpt-4o-mini",
        "api_key": _OPENAI_KEY,
        "label": "OPENAI_GPT4O_MINI",
        "enabled": bool(_OPENAI_KEY),
    },
    {
        "model": "gemini/gemini-2.0-flash",
        "api_key": _GEMINI_KEY,
        "label": "GEMINI_2_0_FLASH",
        "enabled": bool(_GEMINI_KEY),
    },
]


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

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        err_str = str(exc)
        return any(kw in err_str for kw in ("ResourceExhausted", "429", "quota", "RateLimitError", "rate_limit"))

    @classmethod
    async def generate_completion(
        cls,
        prompt: str,
        tiers: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        timeout: int = 12
    ) -> Tuple[Optional[str], str]:
        """
        Standard text completion with fallback.
        Returns: (response_text, provider_label)
        """
        if not LITELLM_AVAILABLE:
            return None, "LITELLM_NOT_AVAILABLE"

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

        for tier in tiers:
            if not tier.get("enabled", False):
                continue

            try:
                kwargs = {
                    "model": tier["model"],
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "timeout": timeout,
                }
                if tier.get("api_key"):
                    kwargs["api_key"] = tier["api_key"]
                if tier.get("extra_headers"):
                    kwargs["extra_headers"] = tier["extra_headers"]

                response = await asyncio.to_thread(litellm.completion, **kwargs)
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    if content:
                        log.info("[LLM_CLIENT] ✅ Text completion succeeded via %s", tier["label"])
                        result = (content.strip(), tier["label"])
                        cls._set_cached_value(cache_key, result, ttl=5.0)
                        return result

            except LiteLLMRateLimitError:
                log.warning("[LLM_CLIENT] ⚠️ 429 RateLimit on %s — rotating tier", tier["label"])
                continue
            except Exception as e:
                if cls._is_rate_limit(e):
                    log.warning("[LLM_CLIENT] ⚠️ 429 RateLimit (detected via string) on %s — rotating tier", tier["label"])
                    continue
                
                # Check for permanent errors (Auth / Model Not Found / Invalid Key)
                err_msg = str(e).lower()
                is_perm_err = any(kw in err_msg for kw in ("invalid_api_key", "authentication", "unauthorized", "not found", "401", "403", "forbidden", "not_found", "model_not_found"))
                if is_perm_err:
                    log.error("[LLM_CLIENT] ❌ Permanent error on %s: %s. Disabling tier.", tier["label"], str(e)[:120])
                    tier["enabled"] = False
                else:
                    log.warning("[LLM_CLIENT] ❌ %s text completion failed: %s", tier["label"], str(e)[:120])
                continue

        return None, "FAILED"

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
        if not LITELLM_AVAILABLE:
            return None, "LITELLM_NOT_AVAILABLE"

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

        for tier in tiers:
            if not tier.get("enabled", False):
                continue

            try:
                kwargs = {
                    "model": tier["model"],
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "timeout": timeout,
                }
                if tier.get("api_key"):
                    kwargs["api_key"] = tier["api_key"]
                if tier.get("extra_headers"):
                    kwargs["extra_headers"] = tier["extra_headers"]

                response = await asyncio.to_thread(litellm.completion, **kwargs)
                
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

            except LiteLLMRateLimitError:
                log.warning("[LLM_CLIENT] ⚠️ 429 RateLimit on %s — rotating tier", tier["label"])
                continue
            except Exception as e:
                if cls._is_rate_limit(e):
                    log.warning("[LLM_CLIENT] ⚠️ 429 RateLimit (detected via string) on %s — rotating tier", tier["label"])
                    continue
                
                # Check for permanent errors (Auth / Model Not Found / Invalid Key)
                err_msg = str(e).lower()
                is_perm_err = any(kw in err_msg for kw in ("invalid_api_key", "authentication", "unauthorized", "not found", "401", "403", "forbidden", "not_found", "model_not_found"))
                if is_perm_err:
                    log.error("[LLM_CLIENT] ❌ Permanent error on %s: %s. Disabling tier.", tier["label"], str(e)[:120])
                    tier["enabled"] = False
                else:
                    log.warning("[LLM_CLIENT] ❌ %s tool call failed: %s", tier["label"], str(e)[:120])
                continue

        return None, "FAILED"

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
        if not LITELLM_AVAILABLE:
            return None, "LITELLM_NOT_AVAILABLE"

        # Build multimodal messages
        user_content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})

        for tier in tiers:
            if not tier.get("enabled", False):
                continue

            try:
                kwargs = {
                    "model": tier["model"],
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "timeout": timeout,
                }
                if tier.get("api_key"):
                    kwargs["api_key"] = tier["api_key"]
                if tier.get("extra_headers"):
                    kwargs["extra_headers"] = tier["extra_headers"]

                response = await asyncio.to_thread(litellm.completion, **kwargs)
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    if content:
                        log.info("[LLM_CLIENT] ✅ Vision completion succeeded via %s", tier["label"])
                        return content.strip(), tier["label"]

            except LiteLLMRateLimitError:
                log.warning("[LLM_CLIENT] ⚠️ 429 RateLimit on %s — rotating vision tier", tier["label"])
                continue
            except Exception as e:
                if cls._is_rate_limit(e):
                    log.warning("[LLM_CLIENT] ⚠️ 429 RateLimit (detected via string) on %s — rotating vision tier", tier["label"])
                    continue
                
                # Check for permanent errors (Auth / Model Not Found / Invalid Key)
                err_msg = str(e).lower()
                is_perm_err = any(kw in err_msg for kw in ("invalid_api_key", "authentication", "unauthorized", "not found", "401", "403", "forbidden", "not_found", "model_not_found"))
                if is_perm_err:
                    log.error("[LLM_CLIENT] ❌ Permanent error on %s: %s. Disabling tier.", tier["label"], str(e)[:120])
                    tier["enabled"] = False
                else:
                    log.warning("[LLM_CLIENT] ❌ %s vision completion failed: %s", tier["label"], str(e)[:120])
                continue

        return None, "FAILED"
