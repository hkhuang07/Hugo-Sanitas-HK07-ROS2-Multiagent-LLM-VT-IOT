"""
MedicalAgent — Tầng 1 trong Subsumption Architecture

Phân tích dữ liệu sinh tồn từ vòng tay, nhắc nhở uống thuốc, cảnh báo đột quỵ.
Sử dụng Groq API (Llama 3.1 70B) cho suy luận y tế chính xác hơn.
"""

import asyncio
import json
import logging
import os
import time

import httpx
import paho.mqtt.client as mqtt

from services.agent_log_client import log_agent_decision

log = logging.getLogger("hk07.medical_agent")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MEDICAL_SYSTEM_PROMPT = (
    "Bạn là Medical Agent của robot HK-07. Phân tích các chỉ số sinh tồn "
    "và đưa ra khuyến nghị ngắn gọn bằng JSON: "
    '{"alert_level": "NORMAL|WARNING|CRITICAL|STROKE", "summary": "...", "action": "..."}'
)

# Thresholds for rule-based pre-screening (no LLM latency for obvious cases)
HR_MIN, HR_MAX = 50, 120
SPO2_MIN = 92.0
TEMP_MAX = 38.5


class MedicalAgent:
    def __init__(self, memory, arbitrator):
        self.memory = memory
        self.arbitrator = arbitrator
        self._status = "INITIALIZING"
        self._last_analysis = None
        self._groq_api_key = os.getenv("GROQ_API_KEY", "")
        self._client = None
        self._volatile_context = {}

        broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self._mqtt = mqtt.Client(client_id="medical-agent", protocol=mqtt.MQTTv311)
        self._mqtt.connect_async(broker_host, broker_port, keepalive=30)
        self._mqtt.loop_start()

    async def run_loop(self):
        self._status = "ACTIVE"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        log.info("[MEDICAL_AGENT] Tầng 1 ACTIVE — Monitoring vitals")

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        self._mqtt.on_message = lambda c, u, msg: loop.call_soon_threadsafe(
            queue.put_nowait, msg.payload.decode("utf-8", errors="replace")
        )
        self._mqtt.subscribe("hk07/sensors/wristband/+/vitals", qos=0)

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=2.0)
                    await self._analyze_vitals(payload)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            log.info("[MEDICAL_AGENT] Shutdown")
        finally:
            if self._client:
                await self._client.aclose()

    async def _analyze_vitals(self, payload: str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        hr = data.get("heartRate", 0)
        spo2 = data.get("spo2", 100.0)
        temp = data.get("bodyTemperature", 37.0)

        # Fast rule-based screening (no LLM)
        obvious_critical = (
            hr < HR_MIN or hr > HR_MAX or
            spo2 < SPO2_MIN or temp > TEMP_MAX
        )

        if obvious_critical:
            summary = f"HR={hr}bpm SpO2={spo2}% Temp={temp}°C"
            log.warning("[MEDICAL_ALERT] Abnormal vitals: %s", summary)
            
            start_time = time.time()
            analysis = await self._call_groq_analysis(data)
            self._last_analysis = analysis

            # Publish Medical Agent output to MQTT
            self._mqtt.publish("hk07/agents/medical/output",
                               json.dumps(analysis), qos=1)
                               
            # Log to Spring Boot via REST
            latency = int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
            await log_agent_decision(
                agent_type="MEDICAL",
                input_context=summary,
                output_decision=json.dumps(analysis),
                llm_provider="GROQ-70B",
                latency_ms=latency
            )

    async def _call_groq_analysis(self, vitals: dict) -> dict:
        if not self._groq_api_key:
            return {"alert_level": "WARNING", "summary": "Mock analysis", "action": "Configure GROQ_API_KEY"}

        prompt = (
            f"Chỉ số sinh tồn: Nhịp tim={vitals.get('heartRate')}bpm, "
            f"SpO2={vitals.get('spo2')}%, Nhiệt độ={vitals.get('bodyTemperature')}°C, "
            f"Huyết áp={vitals.get('systolic')}/{vitals.get('diastolic')}mmHg. "
            "Phân tích và trả về JSON."
        )

        try:
            resp = await self._client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {self._groq_api_key}"},
                json={
                    "model": "llama-3.1-70b-versatile",
                    "messages": [
                        {"role": "system", "content": MEDICAL_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 256,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log.error("[MEDICAL_GROQ_ERROR] %s", e)
            return {"alert_level": "WARNING", "summary": "Analysis failed", "action": "Manual check"}

    def get_status(self) -> dict:
        return {"status": self._status, "last_analysis": self._last_analysis}

    def clear_volatile_context(self):
        self._volatile_context.clear()
        self._last_analysis = None
        log.info("[VOLATILE_WIPE] MedicalAgent cleared")
