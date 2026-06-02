"""
RouterAgent v2 — LLM-Driven Tool Calling Architecture

Thay vì phân loại ý định vào 1 category, Router giờ dùng Tool Calling để:
1. Quyết định ĐỒNG THỜI gọi nhiều tools
2. Cho phép Mixture of Agents (ví dụ: gọi cả Medical & Empathetic cùng lúc)

Tools định nghĩa:
- analyze_clinical_symptoms: Medical Agent analyzes vitals + symptoms
- speak_empathetic_response: Empathetic Agent generates compassionate reply
- search_medical_guidelines: Search medical knowledge base
- trigger_sos_protocol: Activate emergency response (Safety Agent)

LLM Provider: Gemini 1.5 Pro (native Tool Calling support)
"""

import os
import logging
import json
import httpx
from typing import List, Dict, Any
from dotenv import load_dotenv

# Attempt to import litellm for multi-provider LLM support
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logging.warning("[ROUTER_V2] litellm not available; will use direct API calls")

# Load env variables
load_dotenv()

log = logging.getLogger("hk07.router_agent_v2")

# ─── Tool Definitions (JSON Schema) ───────────────────────────────────────────
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "analyze_clinical_symptoms",
            "description": "Invoke Medical Agent to analyze vital signs and clinical symptoms. Use this when user reports health issues or asks about vitals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptom_description": {
                        "type": "string",
                        "description": "User's reported symptoms (e.g., 'chest pain and shortness of breath')"
                    },
                    "urgency_level": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                        "description": "Estimated clinical urgency based on symptoms"
                    }
                },
                "required": ["symptom_description", "urgency_level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "speak_empathetic_response",
            "description": "Invoke Empathetic Agent to generate a compassionate, supportive response. Use this for emotional support, greetings, small talk, or any non-medical conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_message": {
                        "type": "string",
                        "description": "The original user message to respond to"
                    },
                    "emotional_tone": {
                        "type": "string",
                        "enum": ["HAPPY", "SAD", "ANXIOUS", "NEUTRAL", "FEARFUL"],
                        "description": "Detected emotional tone of the user"
                    }
                },
                "required": ["user_message", "emotional_tone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_medical_guidelines",
            "description": "Search medical knowledge base for guidelines, diagnostics, or treatment information. Use when user asks specific medical questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Medical query (e.g., 'stroke symptoms', 'diabetes management')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_sos_protocol",
            "description": "EMERGENCY ONLY: Activate emergency response when life-threatening situation detected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "emergency_reason": {
                        "type": "string",
                        "description": "Reason for emergency activation (e.g., 'Severe chest pain + lost consciousness')"
                    }
                },
                "required": ["emergency_reason"]
            }
        }
    }
]

ORCHESTRATOR_SYSTEM_PROMPT = (
    "Bạn là Router Agent v2 của robot đồng hành HK-07.\n"
    "Nhiệm vụ: Phân tích message từ user và quyết định gọi ĐỒng THỜI các Tool phù hợp.\n"
    "Tư duy Mixture of Agents: 1 message có thể trigger 2-3 tools cùng lúc.\n"
    "Ví dụ:\n"
    "- User: 'Tôi ho ra máu và rất sợ' → gọi analyze_clinical_symptoms + speak_empathetic_response\n"
    "- User: 'Xin chào Hugo' → gọi speak_empathetic_response\n"
    "- User: 'Tôi bị đột quỵ' → gọi trigger_sos_protocol + analyze_clinical_symptoms\n"
    "\n"
    "Nguyên tắc:\n"
    "1. Luôn ưu tiên Safety (Emergency) trước\n"
    "2. Nếu có triệu chứng y tế, gọi analyze_clinical_symptoms\n"
    "3. Nếu có yếu tố cảm xúc, gọi speak_empathetic_response\n"
    "4. Nếu hỏi về kiến thức y tế, gọi search_medical_guidelines\n"
    "5. Nếu không rõ, gọi speak_empathetic_response để ask for clarification\n"
)

class RouterAgentV2:
    def __init__(self):
        self._gemini_api_key = os.getenv("GOOGLE_GENERATIVEAI_API_KEY", "")
        self._groq_api_key = os.getenv("GROQ_API_KEY", "")
        self._client = None

    async def orchestrate_with_tools(self, user_message: str) -> Dict[str, Any]:
        """
        Main orchestration method using Tool Calling.
        
        Returns:
        {
            "tools_to_invoke": ["analyze_clinical_symptoms", "speak_empathetic_response"],
            "tool_calls": [
                {
                    "tool_name": "analyze_clinical_symptoms",
                    "parameters": {"symptom_description": "...", "urgency_level": "HIGH"}
                },
                ...
            ],
            "raw_response": "..."
        }
        """
        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

        # Attempt 1: Use Gemini with Tool Calling
        if self._gemini_api_key:
            try:
                # Prefer faster flash model for routing with slightly relaxed timeout
                result = await self._call_gemini_with_tools(user_message, model_name="gemini-2.0-flash", timeout_s=2.5)
                if result:
                    log.info("[ROUTER_V2] Orchestrated via Gemini (flash): %d tools", len(result.get("tool_calls", [])))
                    return result
            except Exception as e:
                log.warning("[ROUTER_V2] Gemini flash routing failed: %s", e)

        # Attempt 2: Use litellm (if available) with fallback to multiple providers
        if LITELLM_AVAILABLE:
            try:
                result = await self._call_litellm_with_tools(user_message)
                if result:
                    log.info("[ROUTER_V2] Orchestrated via litellm: %d tools", len(result.get("tool_calls", [])))
                    return result
            except Exception as e:
                log.warning("[ROUTER_V2] litellm failed: %s", e)

        # Attempt 3: Local rule-based fallback
        result = self._local_classify_and_route(user_message)
        log.info("[ROUTER_V2] Orchestrated via Local Rule-Based: %d tools", len(result.get("tool_calls", [])))
        return result

    async def _call_gemini_with_tools(self, user_message: str, model_name: str = "gemini-2.0-flash", timeout_s: float = 2.5) -> Dict[str, Any]:
        """Call Gemini with Tool Calling capability"""
        # New signature supports fast model selection and timeout
        async def _inner(model_name: str = "gemini-2.0-flash", timeout_s: float = 0.9):
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._gemini_api_key)

                model = genai.GenerativeModel(
                    model_name=model_name,
                    tools=[TOOLS_SCHEMA],
                    system_instruction=ORCHESTRATOR_SYSTEM_PROMPT
                )

                # Run model call in thread and bound by timeout to keep routing < 1s
                import asyncio as _asyncio
                def sync_call():
                    return model.generate_content(
                        user_message,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,
                            max_output_tokens=300
                        )
                    )

                response = await _asyncio.wait_for(_asyncio.to_thread(sync_call), timeout=timeout_s)

                # Parse tool calls from response
                tool_calls = []
                if getattr(response, "candidates", None):
                    for cand in response.candidates:
                        for part in getattr(cand, "content", []).parts:
                            if hasattr(part, "function_call"):
                                tool_calls.append({
                                    "tool_name": part.function_call.name,
                                    "parameters": dict(part.function_call.args)
                                })

                if tool_calls:
                    return {
                        "tools_to_invoke": [tc["tool_name"] for tc in tool_calls],
                        "tool_calls": tool_calls,
                        "raw_response": getattr(response, "text", "")
                    }

                # Default fallback
                return {
                    "tools_to_invoke": ["speak_empathetic_response"],
                    "tool_calls": [
                        {"tool_name": "speak_empathetic_response", "parameters": {"user_message": user_message, "emotional_tone": "NEUTRAL"}}
                    ],
                    "raw_response": getattr(response, "text", "")
                }
            except Exception as e:
                log.error("[ROUTER_V2_GEMINI] Error or timeout: %s", e)
                return None

        # Expose inner function with same name for compatibility
        return await _inner()

    async def _call_litellm_with_tools(self, user_message: str) -> Dict[str, Any]:
        """Call LLM via litellm with multi-provider support"""
        try:
            # litellm automatically handles provider fallback
            response = litellm.completion(
                model="gpt-4-turbo",  # Will fallback based on available keys
                messages=[
                    {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parse tool calls
            tool_calls = []
            if hasattr(response, "choices") and len(response.choices) > 0:
                if hasattr(response.choices[0].message, "tool_calls"):
                    for tc in response.choices[0].message.tool_calls:
                        tool_calls.append({
                            "tool_name": tc.function.name,
                            "parameters": json.loads(tc.function.arguments)
                        })
            
            if tool_calls:
                return {
                    "tools_to_invoke": [tc["tool_name"] for tc in tool_calls],
                    "tool_calls": tool_calls,
                    "raw_response": response.choices[0].message.content if hasattr(response.choices[0].message, "content") else ""
                }
            else:
                return None
        except Exception as e:
            log.error("[ROUTER_V2_LITELLM] Error: %s", e)
            return None

    def _local_classify_and_route(self, user_message: str) -> Dict[str, Any]:
        """Local rule-based fallback for tool routing"""
        msg = user_message.lower()
        tool_calls = []

        # Detect emergency keywords
        if any(w in msg for w in ["đột quỵ", "suy tim", "hôn mê", "co giật", "choking", "ngạt thở", "dot quy", "suy tim"]):
            tool_calls.append({
                "tool_name": "trigger_sos_protocol",
                "parameters": {"emergency_reason": user_message}
            })
            return {
                "tools_to_invoke": ["trigger_sos_protocol"],
                "tool_calls": tool_calls,
                "raw_response": "[EMERGENCY ACTIVATED]"
            }

        # Detect medical symptoms (high priority)
        if any(w in msg for w in ["đau", "sốt", "ho", "mệt", "bệnh", "chấn thương", "buồn nôn", "nôn", "dau", "sot", "ho", "met", "benh", "chan thuong"]):
            tool_calls.append({
                "tool_name": "analyze_clinical_symptoms",
                "parameters": {
                    "symptom_description": user_message,
                    "urgency_level": "HIGH" if any(w in msg for w in ["cấp", "cap", "khẩn"]) else "MEDIUM"
                }
            })

        # Detect empathetic/conversational intent
        if any(w in msg for w in ["xin", "vui", "vừa", "được", "không", "khong", "tạm", "tam", "chào", "chao", "lạ", "la"]) or len(msg) < 30:
            # Usually small messages are conversational
            tool_calls.append({
                "tool_name": "speak_empathetic_response",
                "parameters": {
                    "user_message": user_message,
                    "emotional_tone": self._detect_emotional_tone(msg)
                }
            })

        # Default: if no tools matched, speak empathetically
        if not tool_calls:
            tool_calls.append({
                "tool_name": "speak_empathetic_response",
                "parameters": {
                    "user_message": user_message,
                    "emotional_tone": "NEUTRAL"
                }
            })

        return {
            "tools_to_invoke": [tc["tool_name"] for tc in tool_calls],
            "tool_calls": tool_calls,
            "raw_response": "[Routed via Local Rules]"
        }

    def _detect_emotional_tone(self, text: str) -> str:
        """Simple heuristic for emotional tone detection"""
        text_lower = text.lower()
        if any(w in text_lower for w in ["vui", "vừa", "tốt", "tốt lắm", "yêu", "happy", "vui vẻ"]):
            return "HAPPY"
        if any(w in text_lower for w in ["buồn", "gằm", "tệ", "tồi", "khó", "sad", "buon"]):
            return "SAD"
        if any(w in text_lower for w in ["sợ", "lo", "cảnh báo", "danger", "canh bao", "so"]):
            return "FEARFUL"
        if any(w in text_lower for w in ["lo lắng", "endlessly", "anxious", "lo lang"]):
            return "ANXIOUS"
        return "NEUTRAL"

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
