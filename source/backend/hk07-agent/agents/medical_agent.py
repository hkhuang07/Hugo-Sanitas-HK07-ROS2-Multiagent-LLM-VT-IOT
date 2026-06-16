"""
MedicalAgent — Tầng 1 trong Subsumption Architecture

Phân tích dữ liệu sinh tồn từ vòng tay, nhắc nhở uống thuốc, cảnh báo đột quỵ.
Sử dụng LLM logic cao:
- Primary: Groq API (Llama-3)
- Fallback: OpenRouter API (Mistral:free)
- Cuối cùng: Local Rule-based
System Prompt đóng vai bác sĩ, kết quả trả về bắt buộc định dạng JSON nghiêm ngặt.
"""

import asyncio
import json
import logging
import os
import re
import time
import collections
import httpx
import math
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from services.agent_log_client import log_agent_decision
from utils.enums import LLMProvider
from services.blackboard_service import get_blackboard, ClinicalEntry, current_user_id
from typing import Optional

# Load env variables
load_dotenv()

log = logging.getLogger("hk07.medical_agent")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MEDICAL_SYSTEM_PROMPT = (
    "Bạn là một bác sĩ chẩn đoán chuyên nghiệp tích hợp trong robot HK-07.\n"
    "Nhiệm vụ của bạn là phân tích các chỉ số sinh tồn (nhịp tim, SpO2, nhiệt độ, huyết áp) và câu hỏi của người bệnh.\n"
    "BẮT BUỘC TRẢ VỀ KẾT QUẢ DƯỚI ĐỊNH DẠNG JSON NGHIÊM NGẶT (Không chứa thêm bất kỳ đoạn text hội thoại nào bên ngoài JSON).\n"
    "Cấu trúc JSON như sau:\n"
    "{\n"
    '  "alert_level": "NORMAL" | "WARNING" | "CRITICAL" | "STROKE",\n'
    '  "summary": "Tóm tắt tình trạng bằng tiếng Việt ngắn gọn, tối đa 2 câu.",\n'
    '  "action": "Lời khuyên y tế bằng tiếng Việt hành động ngay lập tức, tối đa 2 câu."\n'
    "}\n"
    "LƯU Ý QUAN TRỌNG: TUYỆT ĐỐI KHÔNG thêm từ 'Chẩn đoán:', 'Kế hoạch hành động:', 'Tóm tắt:', 'Lời khuyên:' vào đầu các giá trị JSON trả về. Hãy viết trực tiếp nội dung một cách tự nhiên nhất.\n"
)

MEDICAL_ADVICE_SYSTEM_PROMPT = (
    "Bạn là trợ lý y tế thông minh tích hợp trong robot HK-07 theo chuẩn Baymax.\n"
    "Nhiệm vụ của bạn là kết hợp các chỉ số sinh tồn (nhịp tim, SpO2, nhiệt độ, huyết áp) và triệu chứng để chẩn đoán sơ bộ và hướng dẫn sơ cứu/kế hoạch hành động thực tế.\n"
    "Các câu trả lời phải được viết theo giọng văn an ủi, ấm áp, ngắn gọn chuẩn Baymax.\n"
    "BẮT BUỘC TRẢ VỀ KẾT QUẢ DƯỚI ĐỊNH DẠNG JSON NGHIÊM NGẶT (Không chứa thêm bất kỳ đoạn text hội thoại nào bên ngoài JSON).\n"
    "Cấu trúc JSON như sau:\n"
    "{\n"
    '  "diagnosis": "Mô tả tình trạng sức khỏe ngắn gọn và ấm áp bằng tiếng Việt, ví dụ: bạn bị trầy xước nhẹ ngoài da",\n'
    '  "action_plan": "Lời khuyên sơ cứu/hành động thiết thực, ấm áp bằng tiếng Việt, ví dụ: hãy rửa sạch vết thương bằng nước muối để tránh nhiễm trùng nhé",\n'
    '  "alert_level": "NORMAL" | "WARNING" | "CRITICAL"\n'
    "}\n"
    "LƯU Ý QUAN TRỌNG: TUYỆT ĐỐI KHÔNG thêm từ 'Chẩn đoán:' hay 'Kế hoạch hành động:' vào đầu các giá trị JSON trả về. Hãy viết trực tiếp nội dung một cách tự nhiên nhất.\n"
)


class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_time=30.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.last_state_change = time.time()

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
        log.info("[CIRCUIT_BREAKER] State is CLOSED.")

    def record_failure(self):
        self.failure_count += 1
        log.warning(f"[CIRCUIT_BREAKER] Recorded failure. Failure count: {self.failure_count}/{self.failure_threshold}")
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.last_state_change = time.time()
            log.error(f"[CIRCUIT_BREAKER] State tripped to OPEN. API requests will be blocked for {self.recovery_time}s.")

    def allow_request(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_state_change >= self.recovery_time:
                self.state = "HALF_OPEN"
                self.last_state_change = now
                log.warning("[CIRCUIT_BREAKER] State transitioned to HALF_OPEN. Probing API...")
                return True
            return False
        return True


def safe_extract_json(text: str) -> dict:
    fallback = {
        "alert_level": "WARNING",
        "summary": "Phát hiện chỉ số sinh tồn bất thường nhưng chẩn đoán tự động gặp lỗi định dạng.",
        "action": "Vui lòng theo dõi sát sức khỏe của bản thân hoặc đo lại chỉ số sinh tồn.",
        "diagnosis": "Đang theo dõi sức khỏe và kiểm tra triệu chứng.",
        "action_plan": "Vui lòng theo dõi sát sức khỏe của bản thân hoặc đo lại chỉ số sinh tồn."
    }
    if not text or not isinstance(text, str):
        return fallback
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting markdown json codeblock
    match_cb = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match_cb:
        try:
            return json.loads(match_cb.group(1))
        except json.JSONDecodeError:
            pass

    # Find first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass

    return fallback


class MedicalAgent:
    def __init__(self, memory, arbitrator):
        self.memory = memory
        self.arbitrator = arbitrator
        self._status = "INITIALIZING"
        self._last_analysis = None
        self._buffer = collections.deque(maxlen=50)
        self._buffers = {}  # Per-device vitals buffers
        self._circuit_breaker = CircuitBreaker()
        self._last_state = "NORMAL"
        self._last_analyzed_hr = 0.0
        self._groq_api_key = os.getenv("GROQ_API_KEY", "")
        self._openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        self._client = None
        self._volatile_context = {}
        self._thresholds_cache = {}
        self._last_thresholds_fetch_time = 0.0
        self.latest_vitals = {
            "heartRate": 72,
            "spo2": 98.0,
            "bodyTemperature": 36.6,
            "systolic": 120,
            "diastolic": 80
        }

        # MQTT for sensor background logging (bypassed but initialized safely if broker is up)
        try:
            broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
            broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
            self._mqtt = mqtt.Client(client_id="medical-agent", protocol=mqtt.MQTTv311)
            mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
            mqtt_pass = os.getenv("MQTT_PASSWORD", "")
            if mqtt_user:
                self._mqtt.username_pw_set(mqtt_user, mqtt_pass)
            self._mqtt.connect_async(broker_host, broker_port, keepalive=30)
            self._mqtt.loop_start()
        except Exception as e:
            log.warning(f"[MEDICAL_AGENT] MQTT broker offline, bypassing: {e}")
            self._mqtt = None

    def _on_mqtt_message(self, msg):
        payload = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(payload)
            
            # Extract deviceId from topic: hk07/sensors/wristband/<device_id>/vitals
            device_id = "default"
            parts = msg.topic.split('/')
            if len(parts) >= 4:
                device_id = parts[3]
                self._volatile_context["device_id"] = device_id
            
            # Sliding window median filter (size = 5) for Heart Rate and SpO2
            if not hasattr(self, "_raw_hr_windows"):
                self._raw_hr_windows = {}
            if not hasattr(self, "_raw_spo2_windows"):
                self._raw_spo2_windows = {}
                
            if device_id not in self._raw_hr_windows:
                self._raw_hr_windows[device_id] = collections.deque(maxlen=5)
            if device_id not in self._raw_spo2_windows:
                self._raw_spo2_windows[device_id] = collections.deque(maxlen=5)
                
            if "heartRate" in data:
                self._raw_hr_windows[device_id].append(data["heartRate"])
            elif "heart_rate" in data:
                self._raw_hr_windows[device_id].append(data["heart_rate"])
                
            if "spo2" in data:
                self._raw_spo2_windows[device_id].append(data["spo2"])
                
            if self._raw_hr_windows[device_id]:
                hr_list = sorted(list(self._raw_hr_windows[device_id]))
                median_hr = hr_list[len(hr_list) // 2]
                if "heartRate" in data:
                    data["heartRate"] = median_hr
                if "heart_rate" in data:
                    data["heart_rate"] = median_hr
                    
            if self._raw_spo2_windows[device_id]:
                spo2_list = sorted(list(self._raw_spo2_windows[device_id]))
                median_spo2 = spo2_list[len(spo2_list) // 2]
                data["spo2"] = median_spo2

            self._buffer.append(data)
            # Instantly update latest_vitals for live dashboard
            self.latest_vitals.update(data)
            
            if len(parts) >= 4:
                if not hasattr(self, "_buffers"):
                    self._buffers = {}
                if device_id not in self._buffers:
                    self._buffers[device_id] = collections.deque(maxlen=50)
                self._buffers[device_id].append(data)
        except Exception:
            pass

    def _aggregate_vitals(self, buf=None) -> dict:
        buffer_to_use = buf if buf is not None else self._buffer
        if not buffer_to_use:
            return {}

        total_hr = 0.0
        total_spo2 = 0.0
        total_temp = 0.0
        total_sys = 0.0
        total_dia = 0.0
        count = len(buffer_to_use)

        for item in buffer_to_use:
            total_hr += item.get("heartRate", 72)
            total_spo2 += item.get("spo2", 98.0)
            total_temp += item.get("bodyTemperature", 36.6)
            total_sys += item.get("systolic", 120.0)
            total_dia += item.get("diastolic", 80.0)

        return {
            "heartRate": total_hr / count,
            "spo2": total_spo2 / count,
            "bodyTemperature": total_temp / count,
            "systolic": total_sys / count,
            "diastolic": total_dia / count
        }

    async def _fetch_dynamic_thresholds(self, device_id: str) -> dict:
        """
        Fetches dynamic clinical thresholds from the Spring Boot configuration gateway.
        Falls back to factory default constants if backend is offline or unauthenticated.
        """
        from services.agent_log_client import _client as log_client
        from services.blackboard_service import current_auth_token
        
        defaults = {
            "hrMin": 50, "hrMax": 120,
            "spo2Min": 92.0, "tempMax": 38.5,
            "systolicMax": 140, "diastolicMax": 90
        }
        
        if not log_client or not log_client._http:
            return defaults
            
        token = current_auth_token.get() or log_client._token
        headers = {}
        if token:
            headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
            
        internal_key = os.getenv("INTERNAL_API_KEY", "hk07-internal-api-key-bypass")
        if internal_key:
            headers["X-Internal-API-Key"] = internal_key
            
        if not token and not internal_key:
            return defaults
            
        try:
            resp = await log_client._http.get(
                f"/api/thresholds/{device_id}",
                headers=headers
            )
            if resp.status_code == 200:
                body = resp.json()
                if body.get("success") and "data" in body:
                    data = body["data"]
                    log.info(f"[DYNAMIC_THRESHOLDS] Loaded for {device_id}: HR=[{data.get('hrMin')},{data.get('hrMax')}], SpO2_min={data.get('spo2Min')}%")
                    return data
            elif resp.status_code in (401, 403, 404):
                log.warning(f"[DYNAMIC_THRESHOLDS] [WARN] Auth error or threshold endpoint not found for {device_id}: HTTP {resp.status_code}. Falling back to default thresholds.")
            else:
                log.warning(f"[DYNAMIC_THRESHOLDS] Fetch failed for {device_id}: HTTP {resp.status_code}")
        except Exception as e:
            log.warning(f"[DYNAMIC_THRESHOLDS] [WARN] Error fetching thresholds from backend: {e}. Falling back to default thresholds.")
            
        return defaults

    def compute_stress_index(self, buf=None) -> dict:
        """
        Calculate clinical StressIndex approximated via Heart Rate Variability (HRV SDNN)
        over the sliding buffer of physiological telemetry.
        """
        buffer_to_use = buf if buf is not None else self._buffer
        hr_samples = [item.get("heartRate") for item in buffer_to_use if item.get("heartRate")]
        
        if len(hr_samples) < 5:
            return {
                "score": 15,
                "label": "CALM",
                "disclaimer": (
                    "Stress index is approximated via Heart Rate Variability (SDNN) calculated "
                    "over the sliding window of physiological data. Insufficient samples (<5) "
                    "for high-fidelity calculation. Not a direct chemical neurotransmitter measurement."
                )
            }
            
        # Convert HR (bpm) to RR intervals (ms)
        rr_intervals = [60000.0 / hr for hr in hr_samples]
        mean_rr = sum(rr_intervals) / len(rr_intervals)
        variance = sum((rr - mean_rr) ** 2 for rr in rr_intervals) / len(rr_intervals)
        sdnn = math.sqrt(variance)
        
        if sdnn > 50.0:
            score = int(max(5, min(25, 25 - (sdnn - 50.0) * 0.5)))
            label = "CALM"
        elif sdnn >= 30.0:
            score = int(max(26, min(59, 60 - (sdnn - 30.0) * 1.5)))
            label = "ELEVATED"
        else:
            score = int(max(60, min(95, 95 - sdnn * 1.0)))
            label = "ANXIOUS"
            
        return {
            "score": score,
            "label": label,
            "sdnn_ms": round(sdnn, 2),
            "disclaimer": (
                "Stress index is approximated via Heart Rate Variability (SDNN) calculated "
                "over the sliding window of physiological data. It is not direct neurotransmitter measurement."
            )
        }

    async def _process_latest_buffer(self):
        if not hasattr(self, "_buffers") or not self._buffers:
            if self._buffer:
                await self._process_device_buffer("default", self._buffer)
            return

        for device_id, buf in list(self._buffers.items()):
            if not buf:
                continue
            await self._process_device_buffer(device_id, buf)

    async def _process_device_buffer(self, device_id: str, buf):
        # 1. Compute sliding window average (Edge Computing)
        agg = self._aggregate_vitals(buf)
        if not agg:
            return

        # Compute HRV Stress Index and track in Blackboard history
        stress_info = self.compute_stress_index(buf)
        score = stress_info.get("score", 15)
        bb = get_blackboard()
        
        # Resolve thresholds
        now_time = time.time()
        if device_id not in self._thresholds_cache or (now_time - self._last_thresholds_fetch_time) > 5.0:
            self._thresholds_cache[device_id] = await self._fetch_dynamic_thresholds(device_id)
            self._last_thresholds_fetch_time = now_time
            
        thresholds = self._thresholds_cache[device_id]
        
        # Get target userId from thresholds
        user_id = thresholds.get("userId") or "a0000000-0000-0000-0000-000000000001"
        
        try:
            stress_history_key = f"blackboard:clinical:stress_history:{user_id}"
            history = await bb.read_value(stress_history_key)
            if not history:
                history = []
            if not history or history[-1] != score:
                history.append(score)
                if len(history) > 3:
                    history.pop(0)
                await bb.write_value(stress_history_key, history, ttl_seconds=300)
                log.debug("[STRESS_HISTORY_TRACK] Updated stress history on Blackboard for %s: %s", user_id, history)
        except Exception as e:
            log.error("[STRESS_HISTORY_ERROR] Error updating stress history for %s: %s", user_id, e)

        hr = agg["heartRate"]
        spo2 = agg["spo2"]
        temp = agg["bodyTemperature"]

        hr_min = thresholds.get("hrMin", 50)
        hr_max = thresholds.get("hrMax", 120)
        spo2_min = thresholds.get("spo2Min", 92.0)
        temp_max = thresholds.get("tempMax", 38.5)

        # Check if the aggregated vitals are critical using dynamic thresholds
        is_falling = any(item.get("is_falling") in (True, 1, 1.0, "true", "True") for item in buf)
        emergency_pressed = any(item.get("emergency_button_pressed") in (True, 1, 1.0, "true", "True") for item in buf)

        # Consistency check over sliding window (size = 5)
        hr_window = list(self._raw_hr_windows.get(device_id, []))
        spo2_window = list(self._raw_spo2_windows.get(device_id, []))
        
        hr_consistent_violation = False
        if len(hr_window) >= 5:
            hr_consistent_violation = all(x < hr_min or x > hr_max for x in hr_window)
            
        spo2_consistent_violation = False
        if len(spo2_window) >= 5:
            spo2_consistent_violation = all(x < spo2_min for x in spo2_window)

        is_critical = (
            hr_consistent_violation or
            spo2_consistent_violation or
            temp > temp_max or
            is_falling or emergency_pressed
        )

        # Cross-Modal Consensus Matrix validation gate
        is_vital_drop = hr_consistent_violation or spo2_consistent_violation
        consensus_suppressed = False
        if is_critical and is_vital_drop and not is_falling and not emergency_pressed:
            clinical = await bb.read_value("sensor:perception:clinical")
            imu_data = await bb.read_value("sensor:imu:latest")
            
            vision_normal = False
            if clinical:
                fd = clinical.get("facial_distress", {}).get("detected", False)
                vi = clinical.get("visible_injuries", {}).get("detected", False)
                if not fd and not vi:
                    vision_normal = True
            
            accel_normal = False
            if imu_data:
                g_mag = imu_data.get("g_magnitude", 1.0)
                if 0.85 <= g_mag <= 1.15:
                    accel_normal = True
                    
            if vision_normal and accel_normal:
                log.info("[MEDICAL_CONSENSUS] Vital drop detected, but Vision is normal and IMU is at resting baseline. Suppressing AI_EMERGENCY_WAKEUP, lowering weight to WARNING.")
                is_critical = False
                consensus_suppressed = True

        current_state = "CRITICAL" if is_critical else "NORMAL"
        
        # We need a state tracking dict per device!
        if not hasattr(self, "_last_device_states"):
            self._last_device_states = {}
        if not hasattr(self, "_last_device_analyzed_hr"):
            self._last_device_analyzed_hr = {}
            
        # Support test backward compatibility for single-device attributes
        if device_id == "default":
            if "default" not in self._last_device_states:
                self._last_device_states["default"] = self._last_state
            if "default" not in self._last_device_analyzed_hr:
                self._last_device_analyzed_hr["default"] = self._last_analyzed_hr

        last_state = self._last_device_states.get(device_id, "NORMAL")
        last_analyzed_hr = self._last_device_analyzed_hr.get(device_id, 0.0)
        
        state_changed = (current_state != last_state)
        
        if consensus_suppressed:
            triggered_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            trigger_reasons = []
            if hr < hr_min or hr > hr_max:
                trigger_reasons.append(f"nhịp tim ({hr:.1f} bpm) ngoài ngưỡng")
            if spo2 < spo2_min:
                trigger_reasons.append(f"nồng độ oxy SpO2 ({spo2:.1f}%) tụt thấp")
            reasons_desc = " và ".join(trigger_reasons) if trigger_reasons else "chỉ số sinh hiệu vượt ngưỡng nguy hiểm"
            
            payload = {
                "id": f"evt-{int(time.time())}",
                "eventType": "AGENT_DECISION",
                "agentType": "MEDICAL",
                "alertLevel": "WARNING",
                "inputContext": f"Vitals: HR={hr:.1f}bpm SpO2={spo2:.1f}% Temp={temp:.1f}°C Fall={is_falling} SOS={emergency_pressed}",
                "outputDecision": f"[CẢNH BÁO] Phát hiện {reasons_desc}. Tuy nhiên, kết quả phân tích hình ảnh và gia tốc bình thường. Vui lòng kiểm tra lại thiết bị hoặc nghỉ ngơi.",
                "llmProvider": "LOCAL_RULE",
                "latencyMs": 0,
                "triggeredAt": triggered_at,
                "userId": user_id
            }
            try:
                self._mqtt.publish("hk07/agents/medical/output", json.dumps(payload), qos=1)
                log.info("[MEDICAL_CONSENSUS] Published WARNING alert instead of emergency wakeup.")
            except Exception as e:
                log.error("[MEDICAL_CONSENSUS_ERROR] Failed to publish warning: %s", e)
        
        if current_state == "CRITICAL" and last_state != "CRITICAL":
            # State transitioned to CRITICAL - publish immediate WAKEUP event to MQTT
            triggered_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            trigger_reasons = []
            if hr < hr_min or hr > hr_max:
                trigger_reasons.append(f"nhịp tim ({hr:.1f} bpm) ngoài ngưỡng")
            if spo2 < spo2_min:
                trigger_reasons.append(f"nồng độ oxy SpO2 ({spo2:.1f}%) tụt thấp")
            if temp > temp_max:
                trigger_reasons.append(f"nhiệt độ cơ thể ({temp:.1f}°C) sốt cao")
            if is_falling:
                trigger_reasons.append("phát hiện ngã/chấn thương")
            if emergency_pressed:
                trigger_reasons.append("nút SOS khẩn cấp được nhấn")
            
            reasons_desc = " và ".join(trigger_reasons) if trigger_reasons else "chỉ số sinh hiệu vượt ngưỡng nguy hiểm"
            
            payload = {
                "id": f"evt-{int(time.time())}",
                "eventType": "AI_EMERGENCY_WAKEUP",
                "agentType": "MEDICAL",
                "alertLevel": "CRITICAL",
                "inputContext": f"Vitals: HR={hr:.1f}bpm SpO2={spo2:.1f}% Temp={temp:.1f}°C Fall={is_falling} SOS={emergency_pressed}",
                "outputDecision": f"[CẢNH BÁO NGUY HIỂM] Phát hiện {reasons_desc}. Tôi đang kích hoạt quy trình cứu hộ SOS khẩn cấp. Vui lòng giữ bình tĩnh, trợ giúp đang đến.",
                "llmProvider": "LOCAL_RULE",
                "latencyMs": 0,
                "triggeredAt": triggered_at,
                "userId": user_id
            }
            try:
                self._mqtt.publish("hk07/agents/medical/output", json.dumps(payload), qos=1)
                log.info("[MEDICAL_PROACTIVE_WAKEUP] Instantly published AI_EMERGENCY_WAKEUP to MQTT due to: %s", reasons_desc)
            except Exception as e:
                log.error("[MEDICAL_PROACTIVE_WAKEUP_ERROR] Failed to publish wakeup event: %s", e)

        delta_hr = 0.0
        if last_analyzed_hr > 0.0:
            delta_hr = abs(hr - last_analyzed_hr) / last_analyzed_hr
            
        should_trigger_llm = state_changed or (current_state == "CRITICAL" and delta_hr >= 0.15)

        if should_trigger_llm:
            summary = f"Aggregated Vitals: HR={hr:.1f}bpm SpO2={spo2:.1f}% Temp={temp:.1f}°C"
            log.info("[MEDICAL_TRIGGER] Triggering LLM analysis for %s: StateChanged=%s | DeltaHR=%.2f%%", user_id, state_changed, delta_hr * 100)
            
            # Save new states
            self._last_device_states[device_id] = current_state
            if device_id == "default":
                self._last_state = current_state
            if is_critical:
                self._last_device_analyzed_hr[device_id] = hr
                if device_id == "default":
                    self._last_analyzed_hr = hr
            else:
                self._last_device_analyzed_hr[device_id] = 0.0
                if device_id == "default":
                    self._last_analyzed_hr = 0.0

            # Trigger LLM in background task (Non-blocking)
            async def run_bg_analysis(vitals_data, vitals_summary, target_user_id, is_suppressed):
                try:
                    start_time = time.time()
                    analysis = await self._call_llm_with_fallback(vitals_data, user_id=target_user_id)
                    
                    if is_suppressed:
                        analysis["alert_level"] = "WARNING"
                        analysis["summary"] = f"[Consensus Downgraded] {analysis.get('summary', '')}"
                        
                    self._last_analysis = analysis
                    latency = int((time.time() - start_time) * 1000)

                    # Build compliant payload
                    triggered_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    is_emergency = analysis.get("alert_level") == "CRITICAL"
                    
                    payload = {
                        "id": f"evt-{int(time.time())}",
                        "eventType": "AI_EMERGENCY_WAKEUP" if is_emergency else "AGENT_DECISION",
                        "agentType": "MEDICAL",
                        "alertLevel": analysis.get("alert_level", "NORMAL"),
                        "inputContext": vitals_summary,
                        "outputDecision": f"{analysis.get('summary', '')} LỜI KHUYÊN: {analysis.get('action', '')}",
                        "llmProvider": "GROQ_PROACTIVE" if is_emergency else "GROQ_ANALYSIS",
                        "latencyMs": latency,
                        "triggeredAt": triggered_at,
                        "userId": target_user_id
                      }

                    self._mqtt.publish("hk07/agents/medical/output", json.dumps(payload), qos=1)

                    await log_agent_decision(
                        agent_type="MEDICAL",
                        input_context=vitals_summary,
                        output_decision=json.dumps(payload),
                        llm_provider=LLMProvider.GROQ_OR_FALLBACK.value if self._circuit_breaker.state != "OPEN" else LLMProvider.LOCAL_RULE.value,
                        latency_ms=latency
                    )
                    
                    # Also write the clinical entry to Blackboard for proactive sync
                    bb = get_blackboard()
                    entry = ClinicalEntry(
                        agent_type="MEDICAL",
                        alert_level=analysis.get("alert_level", "NORMAL"),
                        vitals=vitals_data,
                        diagnosis=analysis.get("summary", "Mô tả sức khỏe"),
                        action_recommended=analysis.get("action", "Lời khuyên sơ cứu"),
                        confidence_score=0.9
                    )
                    await bb.write_clinical(entry, user_id=target_user_id)
                except Exception as ex:
                    log.error("[MEDICAL_BG_ANALYSIS_ERROR] Exception: %s", ex)

            asyncio.create_task(run_bg_analysis(agg, summary, user_id, consensus_suppressed))

    async def run_loop(self):
        self._status = "ACTIVE"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        log.info("[MEDICAL_AGENT] Tầng 1 ACTIVE — Chẩn đoán y tế (Direct Buffer Fetch)")

        try:
            import collections
            while True:
                # Direct Buffer Ingestion
                from services.sensor_fusion_buffer import get_fusion_buffer
                fusion_buf = get_fusion_buffer()
                vitals = await fusion_buf.latest_vitals()
                if vitals:
                    # check fall and emergency state from blackboard
                    from services.blackboard_service import get_blackboard
                    bb = get_blackboard()
                    is_falling = await bb.read_value("sensor:vitals:is_falling") or False
                    emergency_pressed = await bb.read_value("sensor:vitals:emergency") or False
                    
                    data = {
                        "heartRate": vitals.heart_rate or 72,
                        "spo2": vitals.spo2 or 98.0,
                        "bodyTemperature": vitals.body_temperature or 36.6,
                        "systolic": vitals.systolic or 120,
                        "diastolic": vitals.diastolic or 80,
                        "is_falling": is_falling,
                        "emergency_button_pressed": emergency_pressed
                    }
                    self._buffer.append(data)
                    self.latest_vitals.update(data)
                    
                    device_id = "default"
                    if not hasattr(self, "_buffers"):
                        self._buffers = {}
                    if device_id not in self._buffers:
                        self._buffers[device_id] = collections.deque(maxlen=50)
                    self._buffers[device_id].append(data)

                await asyncio.sleep(1.0)  # 1Hz check
                await self._process_latest_buffer()
        except asyncio.CancelledError:
            log.info("[MEDICAL_AGENT] Shutdown")
        finally:
            if hasattr(self, "_mqtt") and self._mqtt:
                try:
                    self._mqtt.loop_stop()
                except Exception:
                    pass
            if self._client:
                await self._client.aclose()

    async def process_text_interaction(self, user_message: str, current_vitals: dict, mode: str = "MEDICAL_ANALYSIS", user_id: Optional[str] = None) -> str:
        if user_id is None:
            user_id = current_user_id.get()
        """Called by the supervisor orchestrator to analyze medical query & vitals"""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))

        start_time = time.time()
        
        # Fetch latest perception scan from Blackboard (Multimodal)
        perception_scan = None
        try:
            from agents.perception_agent import PerceptionAgent
            pa = PerceptionAgent(self.arbitrator)
            perception_scan = await pa.read_latest_scan()
        except Exception as e:
            log.error("[MEDICAL_AGENT] Failed to read perception scan: %s", e)
            
        perception_info = "Không có thông tin hình ảnh."
        if perception_scan:
            perception_info = (
                f"Kết quả quét cơ thể hình ảnh (Visual Scan):\n"
                f"- Sắc tố da: {perception_scan.skin_tone_note}\n"
                f"- Mức độ đau đớn/biểu cảm khuôn mặt: {perception_scan.facial_distress} (0.0-1.0)\n"
                f"- Chấn thương bên ngoài: {', '.join(perception_scan.visible_injuries) if perception_scan.visible_injuries else 'Không có'}\n"
                f"- Rủi ro tư thế: {perception_scan.posture_risk}\n"
                f"- Khoảng cách vật cản gần nhất: {perception_scan.nearest_obstacle_m}m\n"
                f"- Mức độ rủi ro LiDAR: {perception_scan.threat_level}\n"
                f"- Mức độ rủi ro tổng hợp trực quan: {perception_scan.overall_risk}\n"
            )
            
        # Compute HRV Stress Index
        stress_index = self.compute_stress_index()
        
        prompt = self._build_chat_prompt(user_message, current_vitals, stress_index, perception_info, mode)
        system_prompt = MEDICAL_ADVICE_SYSTEM_PROMPT if mode == "MEDICAL_ADVICE" else MEDICAL_SYSTEM_PROMPT

        # Inject medical baseline profile (Super Context) if available
        baseline = await self.memory.recall_medical_baseline(user_id=user_id)
        if baseline:
            system_prompt = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_prompt}"

        # Use unified LLMClient
        res_str = ""
        provider_used = LLMProvider.LOCAL_RULE.value

        try:
            from services.llm_client import LLMClient, MEDICAL_TIERS
            res_content, provider_label = await LLMClient.generate_completion(
                prompt=prompt,
                tiers=MEDICAL_TIERS,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=1024,
                timeout=12,
                patient_id=user_id
            )
            if provider_label != "LOCAL_FALLBACK" and res_content:
                extracted = safe_extract_json(res_content)
                res_str = json.dumps(extracted, ensure_ascii=False)
                if "GROQ" in provider_label:
                    provider_used = LLMProvider.GROQ_PRIMARY.value
                elif "OPENROUTER" in provider_label:
                    provider_used = LLMProvider.OPENROUTER_FALLBACK.value
                else:
                    provider_used = provider_label
        except Exception as e:
            log.error("[MEDICAL_AGENT] LLMClient process_text_interaction failed: %s", e)

        # 3. Local rules fallback (returns JSON string)
        if not res_str:
            if mode == "MEDICAL_ADVICE":
                local_diag = {
                    "diagnosis": f"Phát hiện triệu chứng tự báo cáo: {user_message}",
                    "action_plan": self._generate_local_first_aid_plan(user_message),
                    "alert_level": "WARNING"
                }
            else:
                local_diag = self._generate_rule_based_diagnosis(current_vitals)
                local_diag["summary"] = f"[Local Mode] {local_diag['summary']} {self._generate_local_text_fallback_reason(user_message)}"
            res_str = json.dumps(local_diag, ensure_ascii=False)
            provider_used = LLMProvider.LOCAL_RULE.value

        latency = int((time.time() - start_time) * 1000)
        await log_agent_decision("MEDICAL", user_message, res_str, provider_used, latency)
        
        # Write ClinicalEntry back to Blackboard (EHR synchronization)
        try:
            extracted = safe_extract_json(res_str)
            bb = get_blackboard()
            entry = ClinicalEntry(
                agent_type="MEDICAL",
                alert_level=extracted.get("alert_level", "NORMAL"),
                vitals=current_vitals,
                diagnosis=extracted.get("summary") or extracted.get("diagnosis") or "Chẩn đoán y tế",
                action_recommended=extracted.get("action") or extracted.get("action_plan") or "Nghỉ ngơi",
                confidence_score=0.85 if provider_used != LLMProvider.LOCAL_RULE.value else 0.5
            )
            await bb.write_clinical(entry)
        except Exception as e:
            log.error("[MEDICAL_AGENT] Failed to write ClinicalEntry to Blackboard: %s", e)

        return res_str

    async def _call_groq_text(self, prompt: str, system_prompt: str) -> tuple[str, bool]:
        combined_prompt = f"System: {system_prompt}\n\nUser request: {prompt}"
        try:
            resp = await self._client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self._groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": combined_prompt}],
                    "temperature": 0.1
                }
            )
            if resp.status_code != 200:
                log.error(f"[MEDICAL_GROQ_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return "", False
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            extracted = safe_extract_json(content)
            return json.dumps(extracted, ensure_ascii=False), True
        except Exception as e:
            log.error("[MEDICAL_GROQ_ERROR] Exception: %s", e)
            return "", False

    async def _call_openrouter_text(self, prompt: str, system_prompt: str) -> tuple[str, bool]:
        combined_prompt = f"System: {system_prompt}\n\nUser request: {prompt}"
        try:
            resp = await self._client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {self._openrouter_api_key}",
                    "HTTP-Referer": "http://localhost",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openrouter/free",
                    "messages": [{"role": "user", "content": combined_prompt}]
                }
            )
            if resp.status_code != 200:
                log.error(f"[MEDICAL_OPENROUTER_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return "", False
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            extracted = safe_extract_json(content)
            return json.dumps(extracted, ensure_ascii=False), True
        except Exception as e:
            log.error("[MEDICAL_OPENROUTER_ERROR] Exception: %s", e)
            return "", False

    async def _call_llm_with_fallback(self, vitals: dict, user_id: Optional[str] = None) -> dict:
        if user_id is None:
            user_id = current_user_id.get()
        if not self._circuit_breaker.allow_request():
            log.warning("[CIRCUIT_BREAKER] Request blocked (circuit is OPEN). Triggering local rule-based diagnosis.")
            return self._generate_rule_based_diagnosis(vitals)

        prompt_str = self._build_prompt(vitals)
        system_prompt = MEDICAL_SYSTEM_PROMPT
        baseline = await self.memory.recall_medical_baseline(user_id=user_id)
        if baseline:
            system_prompt = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_prompt}"

        try:
            from services.llm_client import LLMClient, MEDICAL_TIERS
            res_content, provider_label = await LLMClient.generate_completion(
                prompt=prompt_str,
                tiers=MEDICAL_TIERS,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=512,
                timeout=12,
                patient_id=user_id
            )
            if provider_label != "LOCAL_FALLBACK" and res_content:
                extracted = safe_extract_json(res_content)
                if extracted and isinstance(extracted, dict) and "alert_level" in extracted:
                    self._circuit_breaker.record_success()
                    return extracted
        except Exception as e:
            log.error("[MEDICAL_AGENT] LLMClient _call_llm_with_fallback failed: %s", e)

        self._circuit_breaker.record_failure()
        return self._generate_rule_based_diagnosis(vitals)



    async def _call_groq(self, vitals: dict, user_id: Optional[str] = None) -> tuple[dict, bool]:
        if user_id is None:
            user_id = current_user_id.get()
        prompt_str = self._build_prompt(vitals)
        system_prompt = MEDICAL_SYSTEM_PROMPT
        baseline = await self.memory.recall_medical_baseline(user_id=user_id)
        if baseline:
            system_prompt = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_prompt}"
        combined_prompt = f"System: {system_prompt}\n\nUser request: {prompt_str}"
        try:
            resp = await self._client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self._groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": combined_prompt}],
                    "temperature": 0.1
                }
            )
            if resp.status_code != 200:
                log.error(f"[MEDICAL_GROQ_BG_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return {}, False
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            extracted = safe_extract_json(content)
            return extracted, True
        except Exception as e:
            log.error("[MEDICAL_GROQ_BG_ERROR] Exception: %s", e)
            return {}, False

    async def _call_openrouter(self, vitals: dict, user_id: Optional[str] = None) -> tuple[dict, bool]:
        if user_id is None:
            user_id = current_user_id.get()
        prompt_str = self._build_prompt(vitals)
        system_prompt = MEDICAL_SYSTEM_PROMPT
        baseline = await self.memory.recall_medical_baseline(user_id=user_id)
        if baseline:
            system_prompt = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_prompt}"
        combined_prompt = f"System: {system_prompt}\n\nUser request: {prompt_str}"
        try:
            resp = await self._client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {self._openrouter_api_key}",
                    "HTTP-Referer": "http://localhost",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openrouter/free",
                    "messages": [{"role": "user", "content": combined_prompt}]
                }
            )
            if resp.status_code != 200:
                log.error(f"[MEDICAL_OPENROUTER_BG_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return {}, False
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            extracted = safe_extract_json(content)
            return extracted, True
        except Exception as e:
            log.error("[MEDICAL_OPENROUTER_BG_ERROR] Exception: %s", e)
            return {}, False

    def _build_prompt(self, vitals: dict) -> str:
        return (
            f"Vital signs: HeartRate={vitals.get('heartRate')}bpm, "
            f"SpO2={vitals.get('spo2')}%, Temp={vitals.get('bodyTemperature')}°C, "
            f"BP={vitals.get('systolic')}/{vitals.get('diastolic')}mmHg. "
            "Analyze and return JSON only."
        )

    def _build_chat_prompt(self, message: str, vitals: dict, stress_index: dict, perception_info: str, mode: str = "MEDICAL_ANALYSIS") -> str:
        vitals_summary = (
            f"Nhịp tim: {vitals.get('heartRate', 72)} bpm, "
            f"SpO2: {vitals.get('spo2', 98)}%, "
            f"Nhiệt độ: {vitals.get('bodyTemperature', 36.6)} °C, "
            f"Huyết áp: {vitals.get('systolic', 120)}/{vitals.get('diastolic', 80)} mmHg."
        )
        stress_summary = f"Chỉ số căng thẳng (HRV Stress): {stress_index.get('score')}/100 ({stress_index.get('label')})."
        
        if mode == "MEDICAL_ADVICE":
            return (
                f"Triệu chứng người dùng khai báo: '{message}'\n"
                f"Chỉ số sinh tồn hiện tại: {vitals_summary}\n"
                f"{stress_summary}\n"
                f"{perception_info}\n"
                "Hãy phân tích triệu chứng kết hợp sinh hiệu và hình ảnh trực quan trên để đưa ra chẩn đoán cùng kế hoạch hành động/sơ cứu thực tế dưới cấu trúc JSON của MEDICAL_ADVICE."
            )
        else:
            return (
                f"Câu hỏi/Yêu cầu phân tích: '{message}'\n"
                f"Chỉ số sinh tồn hiện tại: {vitals_summary}\n"
                f"{stress_summary}\n"
                f"{perception_info}\n"
                "Hãy phân tích các chỉ số trên và đưa ra tóm tắt cùng lời khuyên y tế phù hợp dưới cấu trúc JSON của MEDICAL_ANALYSIS."
            )

    def _generate_rule_based_diagnosis(self, vitals: dict) -> dict:
        hr = vitals.get("heartRate", 72)
        spo2 = vitals.get("spo2", 98.0)
        temp = vitals.get("bodyTemperature", 36.6)
        systolic = vitals.get("systolic", 120.0)

        if hr > 130 or systolic > 150:
            return {
                "alert_level": "CRITICAL",
                "summary": f"Nhịp tim rất cao ({hr} bpm) kèm huyết áp cao. Nguy cơ quá tải tim mạch.",
                "action": "Hãy ngồi nghỉ ngơi ngay lập tức, hít thở sâu và liên hệ người thân hoặc bác sĩ."
            }
        elif spo2 < 92.0:
            return {
                "alert_level": "CRITICAL",
                "summary": f"Nồng độ oxy trong máu (SpO2) thấp ({spo2}%). Thiếu oxy mô.",
                "action": "Hãy mở rộng cửa sổ thông thoáng, ngồi thẳng lưng và chuẩn bị thiết bị thở nếu cần."
            }
        elif temp > 38.5:
            return {
                "alert_level": "WARNING",
                "summary": f"Sốt cao ({temp}°C). Cơ thể đang có dấu hiệu viêm hoặc nhiễm trùng.",
                "action": "Uống nhiều nước ấm, lau mát cơ thể và sử dụng thuốc hạ sốt theo chỉ định."
            }
        else:
            return {
                "alert_level": "NORMAL",
                "summary": f"Chỉ số sinh tồn bình thường (HR={hr}, SpO2={spo2}%, Temp={temp}°C).",
                "action": "Tiếp tục duy trì lối sống lành mạnh."
            }

    def _generate_local_text_fallback_reason(self, user_message: str) -> str:
        msg = user_message.lower()
        if "nhịp tim" in msg or "tim mạch" in msg or "tim" in msg:
            return "Về tim mạch, hãy duy trì lối sống lành mạnh, ăn ít muối và tập thể dục đều đặn."
        elif "sốt" in msg or "nhiệt độ" in msg:
            return "Về nhiệt độ cơ thể, sốt cao có thể do viêm nhiễm. Hãy bù nước đầy đủ."
        elif "spo2" in msg or "oxy" in msg:
            return "Nồng độ oxy SpO2 cần duy trì trên 95% để đảm bảo hô hấp ổn định."
        return "Để an toàn, bạn nên tham khảo ý kiến bác sĩ chuyên khoa hoặc kiểm tra chỉ số sinh tồn trực tiếp."

    def _generate_local_first_aid_plan(self, user_message: str) -> str:
        msg = user_message.lower()
        if "đau tay" in msg or "dau tay" in msg or "gãy" in msg or "gay" in msg:
            return "Tránh vận động tay bị đau. Cố định tạm thời tay bằng nẹp hoặc khăn. Áp đá lạnh chườm giảm sưng và đến ngay cơ sở y tế gần nhất."
        elif "đau đầu" in msg or "nhức đầu" in msg or "dau dau" in msg:
            return "Nằm nghỉ ngơi ở phòng tối và yên tĩnh. Uống một cốc nước ấm. Nếu đau kéo dài, có thể sử dụng paracetamol theo chỉ dẫn và theo dõi thêm."
        elif "bỏng" in msg or "bong" in msg:
            return "Ngâm ngay vùng bị bỏng vào nước mát sạch trong 15-20 phút. Tuyệt đối không bôi kem đánh răng hay dầu mỡ lên vết bỏng. Băng nhẹ bằng gạc sạch."
        elif "chảy máu" in msg or "chay mau" in msg:
            return "Dùng một miếng gạc sạch hoặc khăn sạch ấn chặt trực tiếp lên vết thương để cầm máu. Giữ nguyên áp lực trong ít nhất 5-10 phút."
        return "Hãy nghỉ ngơi tại chỗ, hít thở đều, tránh vận động mạnh. Theo dõi sát các biểu hiện và tìm kiếm sự trợ giúp y tế từ người thân hoặc bác sĩ."

    def get_status(self) -> dict:
        return {"status": self._status, "last_analysis": self._last_analysis}

    def clear_volatile_context(self):
        self._volatile_context.clear()
        self._last_analysis = None
        log.info("[VOLATILE_WIPE] MedicalAgent cleared")

    async def close(self):
        try:
            self._mqtt.loop_stop()
            self._mqtt.disconnect()
        except Exception:
            pass
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()
