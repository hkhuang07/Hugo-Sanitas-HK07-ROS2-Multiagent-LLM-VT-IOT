"""
RouterAgent v2 — LLM-Driven Tool Calling Architecture with Tiered Fallback

Thay vì phân loại ý định vào 1 category, Router dùng Tool Calling để:
1. Quyết định ĐỒNG THỜI gọi nhiều tools
2. Cho phép Mixture of Agents (ví dụ: gọi cả Medical & Empathetic cùng lúc)

Tools định nghĩa:
- analyze_clinical_symptoms: Medical Agent analyzes vitals + symptoms
- speak_empathetic_response: Empathetic Agent generates compassionate reply
- search_medical_guidelines: Search medical knowledge base
- trigger_sos_protocol: Activate emergency response (Safety Agent)

Tiered Fallback (Zero-wait on 429):
  [ROUTER_ENGINE]   Tier-1: groq/llama-3.1-70b-versatile
                    Tier-2: openrouter/openai/gpt-4o-mini
                    Tier-3: local rule-based
  [MEDICAL_ENGINE]  Tier-1: openai/gpt-4o
                    Tier-2: openrouter/anthropic/claude-3-haiku
                    Tier-3: mistral/mistral-medium
  [EMPATHY_ENGINE]  Tier-1: cohere/command-r-plus
                    Tier-2: openai/gpt-4o-mini
                    Tier-3: local rule-based

Gemini đẩy ra khỏi luồng ưu tiên (fallback cuối / disabled) do lỗi HTTP 429.
"""

import asyncio
import json
import logging
import os
import time
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("hk07.router_agent_v2")

# ─── Centralized LLMClient Tiers ──────────────────────────────────────────────
from services.llm_client import LLMClient, ROUTER_TIERS, MEDICAL_TIERS, EMPATHY_TIERS

# ─── Tool Definitions (JSON Schema) ───────────────────────────────────────────
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "fetch_sensor_telemetry",
            "description": (
                "Query simulated hardware gateway to fetch active sensor payloads (live heart rate and IMU metrics). "
                "Use this whenever the user asks about their health, heart, vitals, or physical status."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_vision_payload",
            "description": (
                "Query simulated vision gateway to retrieve structured object logs or trigger visual frame evaluation. "
                "Use this whenever the user asks what the camera sees, what is in front of the robot, or about surroundings visual state."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_clinical_symptoms",
            "description": (
                "Invoke Medical Agent to analyze vital signs, scan body health, and clinical symptoms. "
                "Use this when user reports health issues, asks about vitals, or requests a health/body scan (e.g. 'Scan me', 'Scan my body', 'Analyze my vitals')."
            ),
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
            "description": (
                "Invoke Empathetic Agent to generate a compassionate, supportive response. "
                "Use this for emotional support, greetings, small talk, or any non-medical conversation."
            ),
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
    },
    {
        "type": "function",
        "function": {
            "name": "execute_full_body_scan",
            "description": (
                "Trigger Perception Agent to perform a full multi-modal body scan "
                "(camera vision + vitals + LiDAR). Use when user explicitly requests "
                "a body scan (e.g. 'Quét người tôi', 'Full scan', 'Scan toàn thân'). "
                "Silent — writes results to Blackboard, does not reply to user directly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scan_reason": {
                        "type": "string",
                        "description": "Brief reason for triggering the scan"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_environment_scan",
            "description": (
                "Read latest LiDAR environment scan from sensor buffer. "
                "Use when user asks about nearby obstacles, surroundings, or environment safety."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "Scan scope: 'full' (all sectors) or 'front' (forward only)",
                        "enum": ["full", "front"]
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_system_query",
            "description": "Ping hardware devices or check status of sensors (e.g. wristband, lidar, imu, camera, connection). Use when user asks to check device status, connection, or ping sensors. Do NOT use for user health scans or clinical assessments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Name of the sensor or device to check (e.g. wristband, lidar, imu, camera)"
                    }
                },
                "required": ["device"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_action_plan",
            "description": (
                "Propose and execute a structured plan to control robot movements, trigger SOS, "
                "send medication reminders, speak custom TTS messages, or navigate waypoint locations. "
                "Use when user requests physical control, waypoints navigation, reminders, or emergency actions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Unique plan ID (e.g. plan-12345)"
                    },
                    "steps": {
                        "type": "array",
                        "description": "List of sequential steps to execute",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["SAFE_HOLD", "RESUME", "SOS_DISPATCH", "REMINDER_MEDICATION", "NAVIGATE_TO", "SPEAK_MESSAGE"]
                                },
                                "mqtt_topic": {
                                    "type": "string",
                                    "description": "MQTT topic to target (e.g. 'hk07/control/subsumption/inhibit', 'hk07/control/navigation/waypoint', 'hk07/agents/action/reminder', 'hk07/agents/action/tts')"
                                },
                                "payload": {
                                    "type": "object",
                                    "description": "Dictionary of payload data to send"
                                },
                                "requires_confirm": {
                                    "type": "boolean",
                                    "description": "True if action is safety-critical (like SOS dispatch) and needs user confirmation"
                                }
                            },
                            "required": ["type", "mqtt_topic", "payload"]
                        }
                    }
                },
                "required": ["plan_id", "steps"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_care_action",
            "description": (
                "[BAYMAX] Propose a proactive care action based on what the owner is currently doing and feeling. "
                "Use this when vision/perception data indicates the owner needs attention: sad, stressed, tired, in pain, "
                "eating, typing for long periods, inactive, or happy and needs positive engagement. "
                "Examples: owner appears sad → EMOTIONAL_SUPPORT; typing 2+ hours → INACTIVITY_NUDGE; "
                "facial grimace detected → MEDICAL_FIRST_AID; owner is happy → COMPANION_CHAT."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "observed_activity": {
                        "type": "string",
                        "enum": [
                            "sitting_still", "typing", "writing", "eating", "drinking", "phone_use",
                            "sleeping", "lying_down", "walking", "running", "falling",
                            "reaching_up", "leaning_forward", "standing_still", "unknown"
                        ],
                        "description": "Owner's observed activity from vision pipeline"
                    },
                    "observed_expression": {
                        "type": "string",
                        "enum": ["calm", "happy", "sad", "stressed", "fearful", "angry", "pain", "tired", "unknown"],
                        "description": "Owner's detected facial expression/mood from FacialExpressionAnalyzer"
                    },
                    "care_action_type": {
                        "type": "string",
                        "enum": [
                            "COMPANION_CHAT", "EMOTIONAL_SUPPORT", "STRESS_RELIEF",
                            "MEDICAL_FIRST_AID", "HUG_GESTURE", "TREATMENT_PROMPT",
                            "INACTIVITY_NUDGE", "SLEEP_MONITORING", "TASK_ASSISTANCE",
                            "FALL_RESPONSE", "DRINKING_REMINDER"
                        ],
                        "description": "Proposed Baymax care action type"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for proposing this care action"
                    }
                },
                "required": ["observed_activity", "observed_expression", "care_action_type", "reason"]
            }
        }
    }
]


ORCHESTRATOR_SYSTEM_PROMPT = (
    "Bạn là Router Agent v2 của robot đồng hành HK-07 (Hugo / Sanitas HK-07) — hoạt động như Baymax trong Big Hero 6.\n"
    "Nhiệm vụ: Phân tích message từ user và quyết định gọi ĐỒNG THỜI các Tool phù hợp.\n"
    "Tư duy Mixture of Agents: 1 message có thể trigger 2-3 tools cùng lúc.\n"
    "Quy tắc bắt buộc:\n"
    "- Nếu người dùng hỏi về sức khỏe, tim mạch, nhịp tim, sinh hiệu (ví dụ: 'Nhịp tim tôi thế nào?', 'Sức khỏe tôi ra sao?'): BẮT BUỘC phải gọi tool fetch_sensor_telemetry đầu tiên. TUYỆT ĐỐI KHÔNG tự bịa ra câu trả lời hoặc sử dụng câu trả lời văn bản cứng.\n"
    "- Nếu người dùng hỏi về camera, thị giác, những gì robot nhìn thấy (ví dụ: 'Camera thấy gì?', 'Bạn nhìn thấy gì?'): BẮT BUỘC phải gọi tool capture_vision_payload đầu tiên. TUYỆT ĐỐI KHÔNG tự bịa ra hoặc đoán.\n"
    "- Nếu người dùng yêu cầu quét toàn thân hoặc phân tích triệu chứng chi tiết, có thể kết hợp cả hai hoặc các tool chuyên sâu như analyze_clinical_symptoms.\n"
    "Ví dụ:\n"
    "- User: 'Tôi ho ra máu và rất sợ' → gọi analyze_clinical_symptoms + speak_empathetic_response\n"
    "- User: 'Xin chào Hugo' → gọi speak_empathetic_response\n"
    "- User: 'Tôi bị đột quỵ' → gọi trigger_sos_protocol + speak_empathetic_response\n"
    "- User: 'Quét toàn thân tôi' → gọi execute_full_body_scan\n"
    "- User: 'Xung quanh tôi có vật cản không?' → gọi execute_environment_scan\n"
    "- User: '[CARE_CONTEXT] activity=typing expression=stressed' → gọi propose_care_action + speak_empathetic_response\n"
    "\n"
    "Nguyên tắc (Subsumption):\n"
    "1. Luôn ưu tiên Safety (Emergency) trước — TIER 0 (Ví dụ: đột quỵ, nhồi máu cơ tim, bất tỉnh → gọi trigger_sos_protocol)\n"
    "2. Nếu có triệu chứng y tế hoặc yêu cầu quét cơ thể chi tiết (analyze_clinical_symptoms) — TIER 1\n"
    "3. Nếu user yêu cầu quét toàn thân hình ảnh (camera), gọi execute_full_body_scan — TIER 0.5\n"
    "4. Nếu hỏi về vật cản / môi trường xung quanh, gọi execute_environment_scan\n"
    "5. Nếu có yếu tố cảm xúc, gọi speak_empathetic_response — TIER 2\n"
    "6. Nếu hỏi về kiến thức y tế, gọi search_medical_guidelines\n"
    "7. Nếu muốn kiểm tra trạng thái phần cứng, kết nối hoặc ping cảm biến, gọi execute_system_query\n"
    "8. [BAYMAX] Nếu context cho thấy chủ nhân đang buồn/căng thẳng/mệt/đau mà không hỏi gì cụ thể → gọi propose_care_action + speak_empathetic_response\n"
    "LƯU Ý QUAN TRỌNG VỀ PHÂN BIỆT Ý ĐỊNH:\n"
    "- Nếu yêu cầu là quét cơ thể/sức khỏe hoặc phân tích sinh tồn (ví dụ: 'Scan me', 'Quét cơ thể tôi', 'Analyze my vitals', 'Scan my body', 'Scan my vitals'), bạn BẮT BUỘC phải gọi analyze_clinical_symptoms (Medical Analysis). TUYỆT ĐỐI KHÔNG gọi execute_system_query.\n"
    "- Nếu câu hỏi là về lý thuyết/kiến thức khái niệm (ví dụ: 'Cảm biến Lidar hoạt động như thế nào?', 'Lidar là gì?', 'How does Lidar work?'), bạn BẮT BUỘC phải gọi speak_empathetic_response (để an ủi/giải thích khái niệm) hoặc search_medical_guidelines (nếu y tế). TUYỆT ĐỐI KHÔNG gọi execute_system_query.\n"
    "- Chỉ khi người dùng thực sự muốn kiểm tra trạng thái hoạt động hiện tại của phần cứng (ví dụ: 'Kiểm tra trạng thái Lidar', 'Ping cảm biến đeo tay', 'Check wristband status'), bạn mới gọi execute_system_query.\n"
    "Trả lời bằng tool_calls, không giải thích thêm.\n"
)




# ─── RouterAgentV2 ────────────────────────────────────────────────────────────
class RouterAgentV2:
    """
    Tool-calling Router with Zero-wait Tiered Fallback.
    Provider priority: Groq → OpenRouter → [Gemini last resort]
    On RateLimitError (HTTP 429): immediately switch tier, no sleep.
    """

    def __init__(self):
        # Expose active tier label for observability
        self.last_provider_used: str = "LOCAL_RULES"

    # ── Public API ──────────────────────────────────────────────────────────
    async def orchestrate_with_tools(self, user_message: str) -> Dict[str, Any]:
        """
        Main orchestration entry point.
        """
        # 1. Try centralized LLM client for tool calling fallback
        try:
            from services.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            plugin_tools = pm.get_all_tools()
            combined_tools = TOOLS_SCHEMA + plugin_tools
        except Exception as pm_err:
            log.warning("[ROUTER_V2] Failed to load plugin tools: %s", pm_err)
            combined_tools = TOOLS_SCHEMA

        try:
            result, provider = await LLMClient.generate_tool_call(
                prompt=user_message,
                tiers=ROUTER_TIERS,
                tools=combined_tools,
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=512,
                timeout=8
            )
            if result:
                self.last_provider_used = provider
                result["provider"] = provider
                return result
        except Exception as e:
            log.warning("[ROUTER_V2] LLM client tool call failed (%s). Activating local rules fallback.", e)

        # 2. Rule-based local fallback (zero-dependency, deterministic)
        result = self._local_classify_and_route(user_message)
        result["provider"] = "LOCAL_RULES"
        self.last_provider_used = "LOCAL_RULES"
        log.info("[ROUTER_V2] Routed via Local Rule-Based fallback: %d tools", len(result["tool_calls"]))
        return result

    async def get_medical_response(self, prompt: str) -> Optional[str]:
        """
        Dedicated medical engine call — returns free-text LLM response.
        """
        content, _ = await LLMClient.generate_completion(
            prompt=prompt,
            tiers=MEDICAL_TIERS,
            temperature=0.3,
            max_tokens=1024,
            timeout=12
        )
        return content

    async def get_empathy_response(self, prompt: str) -> Optional[str]:
        """
        Dedicated empathy engine call — returns free-text LLM response.
        """
        content, _ = await LLMClient.generate_completion(
            prompt=prompt,
            tiers=EMPATHY_TIERS,
            temperature=0.3,
            max_tokens=1024,
            timeout=12
        )
        return content

    # ── Local Rule-Based Fallback ───────────────────────────────────────────
    def _local_classify_and_route(self, user_message: str) -> Dict[str, Any]:
        """
        Deterministic keyword classifier — zero-dependency, always succeeds.
        Subsumption: SAFETY > MEDICAL > EMPATHETIC
        """
        msg = user_message.lower()
        tool_calls = []

        # Tier 0 — Safety / Emergency
        emergency_kw = [
            "đột quỵ", "dot quy", "suy tim", "hôn mê", "hon me",
            "co giật", "co giat", "ngạt thở", "ngat tho", "choking",
            "heart attack", "unconscious", "stop breathing",
        ]
        if any(w in msg for w in emergency_kw):
            return {
                "tools_to_invoke": ["trigger_sos_protocol"],
                "tool_calls": [
                    {
                        "tool_name": "trigger_sos_protocol",
                        "parameters": {"emergency_reason": user_message},
                    }
                ],
                "raw_response": "[EMERGENCY ACTIVATED — LOCAL RULE]",
            }

        # Tier 1 — Medical symptoms & health queries
        medical_kw = [
            "đau", "dau", "sốt", "sot", "ho", "mệt", "met",
            "bệnh", "benh", "chấn thương", "chan thuong",
            "buồn nôn", "buon non", "nôn", "non",
            "khó thở", "kho tho", "chest pain", "headache", "fever",
            "scan me", "scan my", "quét cơ thể", "quet co the", "quét sức khỏe", "quet suc khoe",
            "vitals", "sinh tồn", "sinh ton", "tim", "heart", "nhịp tim", "nhip tim"
        ]
        if any(w in msg for w in medical_kw):
            tool_calls.append({
                "tool_name": "fetch_sensor_telemetry",
                "parameters": {},
            })
            urgent = any(w in msg for w in ["cấp", "cap", "khẩn", "khan", "urgent", "severe"])
            tool_calls.append({
                "tool_name": "analyze_clinical_symptoms",
                "parameters": {
                    "symptom_description": user_message,
                    "urgency_level": "HIGH" if urgent else "MEDIUM",
                },
            })

        # Tier 0.5 — Full body scan (camera + perception)
        body_scan_kw = [
            "quét toàn thân", "quet toan than", "full scan", "full body scan",
            "scan toàn thân", "scan toan than", "quét người", "quet nguoi",
            "full body", "perception scan", "body scan"
        ]
        if any(w in msg for w in body_scan_kw):
            tool_calls.append({
                "tool_name": "execute_full_body_scan",
                "parameters": {"scan_reason": user_message},
            })

        # Vision / Camera
        vision_kw = [
            "camera", "nhìn thấy", "nhin thay", "thấy gì", "thay gi", "webcam", "mắt", "mat", "clip", "stream", "vision"
        ]
        if any(w in msg for w in vision_kw):
            tool_calls.append({
                "tool_name": "capture_vision_payload",
                "parameters": {},
            })

        # Environment / obstacle scan
        env_scan_kw = [
            "vật cản", "vat can", "obstacle", "xung quanh", "surroundings",
            "môi trường", "moi truong", "environment scan", "lidar scan"
        ]
        if any(w in msg for w in env_scan_kw):
            tool_calls.append({
                "tool_name": "execute_environment_scan",
                "parameters": {"scope": "full"},
            })

        # Tier 3 — System / Hardware Queries
        system_kw = [
            "ping", "sensor", "cảm biến", "cam bien", "kết nối", "ket noi",
            "thiết bị", "thiet bi", "hardware", "phần cứng", "status", "trạng thái"
        ]
        conceptual_kws = [
            "như thế nào", "nhu the nao", "hoạt động thế nào", "hoat dong the nao",
            "là gì", "la gi", "what is", "how does", "tại sao", "tai sao", "why",
            "hoạt động ra sao", "hoat dong ra sao", "giải thích", "giai thich",
            "tác dụng", "tac dung", "như nào", "nhu nao", "để làm gì", "de lam gi",
            "thế nào", "the nao", "work", "explain", "about", "về", "info", "thông tin"
        ]
        is_concept = any(w in msg for w in conceptual_kws) or (
            any(w in msg for w in ["lidar", "imu", "wristband", "camera"]) and
            not any(w in msg for w in ["ping", "status", "check", "kiểm tra", "kiem tra", "kết nối", "ket noi", "trạng thái", "trang thai"])
        )
        if any(w in msg for w in system_kw) and not is_concept:
            device = "wristband"
            for d in ["lidar", "imu", "camera", "wristband"]:
                if d in msg:
                    device = d
            tool_calls.append({
                "tool_name": "execute_system_query",
                "parameters": {"device": device}
            })

        # Tier 2.5 — Action Agent Commands Fallback
        action_steps = []
        
        # 1. SAFE_HOLD
        hold_kws = ["dừng lại", "dung lai", "dừng di chuyển", "dung di chuyen", "safe hold", "hold"]
        if any(w in msg for w in hold_kws):
            action_steps.append({
                "type": "SAFE_HOLD",
                "mqtt_topic": "hk07/control/subsumption/inhibit",
                "payload": {"trigger": "SAFE_HOLD", "agent": "ACTION_AGENT", "message": "Manual hold via local command"},
                "requires_confirm": False
            })
            
        # 2. RESUME
        resume_kws = ["đi tiếp", "di tiep", "tiếp tục", "tiep tuc", "resume"]
        if any(w in msg for w in resume_kws):
            action_steps.append({
                "type": "RESUME",
                "mqtt_topic": "hk07/control/subsumption/inhibit",
                "payload": {"trigger": "CLEAR", "agent": "ACTION_AGENT", "message": "Manual resume via local command"},
                "requires_confirm": False
            })

        # 3. SOS_DISPATCH
        sos_kws = ["gửi cứu hộ", "gui cuu ho", "cứu tôi", "cuu toi", "gửi cấp cứu", "gui cap cuu", "sos"]
        if any(w in msg for w in sos_kws):
            action_steps.append({
                "type": "SOS_DISPATCH",
                "mqtt_topic": "hk07/control/subsumption/inhibit",
                "payload": {"trigger": "OWNER_EMERGENCY", "agent": "ACTION_AGENT", "message": "SOS triggered via local command"},
                "requires_confirm": True
            })

        # 4. REMINDER_MEDICATION
        reminder_kws = ["uống thuốc", "uong thuoc", "nhắc nhở", "nhac nho", "reminder", "nhắc tôi"]
        if any(w in msg for w in reminder_kws):
            action_steps.append({
                "type": "REMINDER_MEDICATION",
                "mqtt_topic": "hk07/agents/action/reminder",
                "payload": {"message": "Nhắc nhở uống thuốc huyết áp/y tế"},
                "requires_confirm": False
            })

        # 5. NAVIGATE_TO
        nav_kws = ["di chuyển đến", "di chuyen den", "đi ra", "di ra", "navigate to", "go to", "đến phòng", "den phong"]
        if any(w in msg for w in nav_kws):
            action_steps.append({
                "type": "NAVIGATE_TO",
                "mqtt_topic": "hk07/control/navigation/waypoint",
                "payload": {"x": 2.0, "y": 0.0, "z": 0.0, "label": "phòng khách"},
                "requires_confirm": False
            })

        # 6. SPEAK_MESSAGE
        speak_kws = ["hãy nói", "hay noi", "nói rằng", "noi rang", "say that", "speak message"]
        if any(w in msg for w in speak_kws):
            action_steps.append({
                "type": "SPEAK_MESSAGE",
                "mqtt_topic": "hk07/agents/action/tts",
                "payload": {"message": user_message},
                "requires_confirm": False
            })

        if action_steps:
            tool_calls.append({
                "tool_name": "execute_action_plan",
                "parameters": {
                    "plan_id": f"plan-{int(time.time())}",
                    "steps": action_steps
                }
            })

        # Tier 2 — Empathetic / Conversational
        empathy_kw = [
            "xin", "vui", "buồn", "buon", "sợ", "so", "lo",
            "chào", "chao", "hello", "hi", "cảm ơn", "cam on",
            "thank", "help", "giúp", "giup",
        ]
        if any(w in msg for w in empathy_kw) or len(msg.split()) < 8 or is_concept:

            tool_calls.append({
                "tool_name": "speak_empathetic_response",
                "parameters": {
                    "user_message": user_message,
                    "emotional_tone": self._detect_emotional_tone(msg),
                },
            })

        # Default: always reply empathetically if nothing matched
        if not tool_calls:
            tool_calls.append({
                "tool_name": "speak_empathetic_response",
                "parameters": {
                    "user_message": user_message,
                    "emotional_tone": "NEUTRAL",
                },
            })

        return {
            "tools_to_invoke": [tc["tool_name"] for tc in tool_calls],
            "tool_calls": tool_calls,
            "raw_response": "[LOCAL_RULE_ROUTED]",
        }

    def _detect_emotional_tone(self, text: str) -> str:
        """Simple heuristic for emotional tone detection"""
        t = text.lower()
        if any(w in t for w in ["vui", "tốt", "tot", "happy", "yêu", "yeu", "great"]):
            return "HAPPY"
        if any(w in t for w in ["buồn", "buon", "tệ", "te", "sad", "khóc", "khoc"]):
            return "SAD"
        if any(w in t for w in ["sợ", "so", "danger", "cảnh báo"]):
            return "FEARFUL"
        if any(w in t for w in ["lo", "anxious", "lo lắng", "lo lang", "worried"]):
            return "ANXIOUS"
        return "NEUTRAL"

    async def close(self):
        log.info("[ROUTER_V2] Closing RouterAgentV2 resources.")

