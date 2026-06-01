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
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from services.agent_log_client import log_agent_decision
from utils.enums import LLMProvider

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
)

MEDICAL_ADVICE_SYSTEM_PROMPT = (
    "Bạn là một bác sĩ chẩn đoán và sơ cứu chuyên nghiệp tích hợp trong robot HK-07.\n"
    "Nhiệm vụ của bạn là kết hợp các chỉ số sinh tồn (nhịp tim, SpO2, nhiệt độ, huyết áp) và các triệu chứng người dùng khai báo để đưa ra chẩn đoán sơ bộ và hướng dẫn sơ cứu/kế hoạch hành động thực tế.\n"
    "BẮT BUỘC TRẢ VỀ KẾT QUẢ DƯỚI ĐỊNH DẠNG JSON NGHIÊM NGẶT (Không chứa thêm bất kỳ đoạn text hội thoại nào bên ngoài JSON).\n"
    "Cấu trúc JSON như sau:\n"
    "{\n"
    '  "diagnosis": "Chẩn đoán sơ bộ về tình trạng sức khỏe/triệu chứng của bệnh nhân bằng tiếng Việt, ngắn gọn.",\n'
    '  "action_plan": "Kế hoạch hành động và hướng dẫn sơ cứu chi tiết thực tế bằng tiếng Việt.",\n'
    '  "alert_level": "NORMAL" | "WARNING" | "CRITICAL"\n'
    "}\n"
)

HR_MIN, HR_MAX = 50, 120
SPO2_MIN = 92.0
TEMP_MAX = 38.5

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
        self._circuit_breaker = CircuitBreaker()
        self._last_state = "NORMAL"
        self._last_analyzed_hr = 0.0
        self._groq_api_key = os.getenv("GROQ_API_KEY", "")
        self._openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        self._client = None
        self._volatile_context = {}
        self.latest_vitals = {
            "heartRate": 72,
            "spo2": 98.0,
            "bodyTemperature": 36.6,
            "systolic": 120,
            "diastolic": 80
        }

        # MQTT for sensor background logging
        broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self._mqtt = mqtt.Client(client_id="medical-agent", protocol=mqtt.MQTTv311)
        mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
        mqtt_pass = os.getenv("MQTT_PASSWORD", "hk07mqtt2026")
        if mqtt_user:
            self._mqtt.username_pw_set(mqtt_user, mqtt_pass)
        self._mqtt.connect_async(broker_host, broker_port, keepalive=30)
        self._mqtt.loop_start()

    def _on_mqtt_message(self, msg):
        payload = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(payload)
            self._buffer.append(data)
            # Instantly update latest_vitals for live dashboard
            self.latest_vitals.update(data)
        except Exception:
            pass

    def _aggregate_vitals(self) -> dict:
        if not self._buffer:
            return {}

        total_hr = 0.0
        total_spo2 = 0.0
        total_temp = 0.0
        total_sys = 0.0
        total_dia = 0.0
        count = len(self._buffer)

        for item in self._buffer:
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

    async def _process_latest_buffer(self):
        if not self._buffer:
            return

        # 1. Compute sliding window average (Edge Computing)
        agg = self._aggregate_vitals()
        if not agg:
            return

        hr = agg["heartRate"]
        spo2 = agg["spo2"]
        temp = agg["bodyTemperature"]

        # Check if the aggregated vitals are critical
        is_critical = (
            hr < HR_MIN or hr > HR_MAX or
            spo2 < SPO2_MIN or temp > TEMP_MAX
        )

        current_state = "CRITICAL" if is_critical else "NORMAL"
        
        # 2. State-Transition Filtering & Delta calculation
        state_changed = (current_state != self._last_state)
        
        delta_hr = 0.0
        if self._last_analyzed_hr > 0.0:
            delta_hr = abs(hr - self._last_analyzed_hr) / self._last_analyzed_hr
            
        should_trigger_llm = state_changed or (current_state == "CRITICAL" and delta_hr >= 0.15)

        if should_trigger_llm:
            summary = f"Aggregated Vitals: HR={hr:.1f}bpm SpO2={spo2:.1f}% Temp={temp:.1f}°C"
            log.info("[MEDICAL_TRIGGER] Triggering LLM analysis: StateChanged=%s | DeltaHR=%.2f%%", state_changed, delta_hr * 100)
            
            # Save new states
            self._last_state = current_state
            if is_critical:
                self._last_analyzed_hr = hr
            else:
                self._last_analyzed_hr = 0.0 # Reset last analyzed HR when normal

            # Trigger LLM in background task (Non-blocking)
            async def run_bg_analysis(vitals_data, vitals_summary):
                try:
                    start_time = time.time()
                    analysis = await self._call_llm_with_fallback(vitals_data)
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
                        "triggeredAt": triggered_at
                    }

                    self._mqtt.publish("hk07/agents/medical/output", json.dumps(payload), qos=1)

                    await log_agent_decision(
                        agent_type="MEDICAL",
                        input_context=vitals_summary,
                        output_decision=json.dumps(payload),
                        llm_provider=LLMProvider.GROQ_OR_FALLBACK.value if self._circuit_breaker.state != "OPEN" else LLMProvider.LOCAL_RULE.value,
                        latency_ms=latency
                    )
                except Exception as ex:
                    log.error("[MEDICAL_BG_ANALYSIS_ERROR] Exception: %s", ex)

            asyncio.create_task(run_bg_analysis(agg, summary))

    async def run_loop(self):
        self._status = "ACTIVE"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        log.info("[MEDICAL_AGENT] Tầng 1 ACTIVE — Chẩn đoán y tế")

        # Subscribing and updating deque via callback
        self._mqtt.on_message = lambda c, u, msg: self._on_mqtt_message(msg)
        self._mqtt.subscribe("hk07/sensors/wristband/+/vitals", qos=0)

        try:
            while True:
                await asyncio.sleep(0.1)  # 10Hz check
                await self._process_latest_buffer()
        except asyncio.CancelledError:
            log.info("[MEDICAL_AGENT] Shutdown")
        finally:
            self._mqtt.loop_stop()
            if self._client:
                await self._client.aclose()

    async def process_text_interaction(self, user_message: str, current_vitals: dict, mode: str = "MEDICAL_ANALYSIS") -> str:
        """Called by the supervisor orchestrator to analyze medical query & vitals"""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))

        start_time = time.time()
        prompt = self._build_chat_prompt(user_message, current_vitals, mode)
        system_prompt = MEDICAL_ADVICE_SYSTEM_PROMPT if mode == "MEDICAL_ADVICE" else MEDICAL_SYSTEM_PROMPT

        # Inject medical baseline profile (Super Context) if available
        baseline = await self.memory.recall_medical_baseline()
        if baseline:
            system_prompt = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_prompt}"

        # 1. Primary: Groq API
        if self._groq_api_key:
            res_str, success = await self._call_groq_text(prompt, system_prompt)
            if success:
                latency = int((time.time() - start_time) * 1000)
                await log_agent_decision(mode, user_message, res_str, LLMProvider.GROQ_PRIMARY.value, latency)
                return res_str
            log.warning("[MEDICAL_AGENT] Groq failed, switching to OpenRouter fallback")

        # 2. Fallback: OpenRouter API
        if self._openrouter_api_key:
            res_str, success = await self._call_openrouter_text(prompt, system_prompt)
            if success:
                latency = int((time.time() - start_time) * 1000)
                await log_agent_decision(mode, user_message, res_str, LLMProvider.OPENROUTER_FALLBACK.value, latency)
                return res_str
            log.error("[MEDICAL_AGENT] Both Groq and OpenRouter failed")

        # 3. Local rules fallback (returns JSON string)
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
        latency = int((time.time() - start_time) * 1000)
        await log_agent_decision(mode, user_message, res_str, LLMProvider.LOCAL_RULE.value, latency)
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

    async def _call_llm_with_fallback(self, vitals: dict) -> dict:
        if not self._circuit_breaker.allow_request():
            log.warning("[CIRCUIT_BREAKER] Request blocked (circuit is OPEN). Triggering local rule-based diagnosis.")
            return self._generate_rule_based_diagnosis(vitals)

        if self._groq_api_key:
            result, success = await self._call_groq(vitals)
            if success:
                self._circuit_breaker.record_success()
                return result
            log.warning("[MEDICAL_AGENT] Groq failed — switching to OpenRouter fallback")

        if self._openrouter_api_key:
            result, success = await self._call_openrouter(vitals)
            if success:
                self._circuit_breaker.record_success()
                return result
            log.error("[MEDICAL_AGENT] Both Groq and OpenRouter unavailable")

        self._circuit_breaker.record_failure()
        return self._generate_rule_based_diagnosis(vitals)


    async def _call_groq(self, vitals: dict) -> tuple[dict, bool]:
        prompt_str = self._build_prompt(vitals)
        system_prompt = MEDICAL_SYSTEM_PROMPT
        baseline = await self.memory.recall_medical_baseline()
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

    async def _call_openrouter(self, vitals: dict) -> tuple[dict, bool]:
        prompt_str = self._build_prompt(vitals)
        system_prompt = MEDICAL_SYSTEM_PROMPT
        baseline = await self.memory.recall_medical_baseline()
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

    def _build_chat_prompt(self, message: str, vitals: dict, mode: str = "MEDICAL_ANALYSIS") -> str:
        vitals_summary = (
            f"Nhịp tim: {vitals.get('heartRate', 72)} bpm, "
            f"SpO2: {vitals.get('spo2', 98)}%, "
            f"Nhiệt độ: {vitals.get('bodyTemperature', 36.6)} °C, "
            f"Huyết áp: {vitals.get('systolic', 120)}/{vitals.get('diastolic', 80)} mmHg."
        )
        if mode == "MEDICAL_ADVICE":
            return (
                f"Triệu chứng người dùng khai báo: '{message}'\n"
                f"Chỉ số sinh tồn hiện tại của họ: {vitals_summary}\n"
                "Hãy phân tích triệu chứng kết hợp sinh hiệu và đưa ra chẩn đoán cùng kế hoạch hành động/sơ cứu thực tế dưới cấu trúc JSON của MEDICAL_ADVICE."
            )
        else:
            return (
                f"Câu hỏi/Yêu cầu phân tích: '{message}'\n"
                f"Chỉ số sinh tồn hiện tại của họ: {vitals_summary}\n"
                "Hãy phân tích chỉ số sinh tồn và đưa ra tóm tắt cùng lời khuyên y tế phù hợp dưới cấu trúc JSON của MEDICAL_ANALYSIS."
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
