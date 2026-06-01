"""
RouterAgent — Node 0 (Supervisor Router)
Phân loại ý định của input đầu vào cực nhanh sang các Node:
- SAFETY
- MEDICAL
- EMPATHETIC

API sử dụng:
- HuggingFace Inference API (facebook/bart-large-mnli)
- Groq API (llama3-8b-8192) làm fallback
- Local Rule-based làm fallback cuối cùng
"""

import os
import logging
import httpx
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()

log = logging.getLogger("hk07.router_agent")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"

ROUTER_SYSTEM_PROMPT = (
    "You are the Router Agent of the HK-07 companion robot. "
    "Classify the user query into exactly one category: 'MEDICAL_ANALYSIS', 'MEDICAL_ADVICE', 'SYSTEM_QUERY', or 'EMPATHETIC_CHAT'.\n"
    "Categories:\n"
    "- 'MEDICAL_ANALYSIS': Checking, reading, or analyzing the user's current vitals, heart rate, SpO2, blood pressure, or temperature.\n"
    "- 'MEDICAL_ADVICE': When the user reports symptoms (e.g. pain, fever, cough, sickness) or asks for first-aid/medical/clinical advice.\n"
    "- 'SYSTEM_QUERY': When the user asks to check hardware status, wristband connection, ping devices, or perform vitals/sensor scans.\n"
    "- 'EMPATHETIC_CHAT': Greetings, small talk, general conversation, explanations of concepts, or emotional expressions of feelings (sadness, anxiety, tiredness).\n"
    "Respond with ONLY a single phrase: 'MEDICAL_ANALYSIS', 'MEDICAL_ADVICE', 'SYSTEM_QUERY', or 'EMPATHETIC_CHAT'."
)

class RouterAgent:
    def __init__(self):
        self._hf_api_key = os.getenv("HUGGINGFACE_API_KEY", "")
        self._groq_api_key = os.getenv("GROQ_API_KEY", "")
        self._client = None

    async def classify_intent(self, user_message: str) -> str:
        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(5.0))

        # Attempt 1: HuggingFace Inference API (Zero-Shot Text Classification)
        if self._hf_api_key:
            res, success = await self._call_huggingface(user_message)
            if success:
                log.info("[ROUTER_AGENT] Routed via HuggingFace: %s", res)
                return res
            log.warning("[ROUTER_AGENT] HuggingFace failed, trying Groq fallback")

        # Attempt 2: Groq Fallback
        if self._groq_api_key:
            res, success = await self._call_groq(user_message)
            if success:
                log.info("[ROUTER_AGENT] Routed via Groq: %s", res)
                return res
            log.error("[ROUTER_AGENT] Both HuggingFace and Groq failed")

        # Attempt 3: Local Rule-Based
        res = self._local_classify(user_message)
        log.info("[ROUTER_AGENT] Routed via Local Rule-Based: %s", res)
        return res

    async def _call_huggingface(self, user_message: str) -> tuple[str, bool]:
        try:
            resp = await self._client.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {self._hf_api_key}"},
                json={
                    "inputs": user_message,
                    "parameters": {"candidate_labels": ["MEDICAL_ANALYSIS", "MEDICAL_ADVICE", "SYSTEM_QUERY", "EMPATHETIC_CHAT"]}
                }
            )
            if resp.status_code != 200:
                log.error(f"[ROUTER_HF_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return "", False
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "labels" in data and len(data["labels"]) > 0:
                top_label = data["labels"][0].upper()
                if top_label in ["MEDICAL_ANALYSIS", "MEDICAL_ADVICE", "SYSTEM_QUERY", "EMPATHETIC_CHAT"]:
                    return f"ROUTING_TARGET: {top_label}", True
            return "", False
        except Exception as e:
            log.error("[ROUTER_HF_ERROR] Exception: %s", e)
            return "", False

    async def _call_groq(self, user_message: str) -> tuple[str, bool]:
        prompt = f"System: {ROUTER_SYSTEM_PROMPT}\n\nUser query to classify: {user_message}"
        try:
            resp = await self._client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self._groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1
                }
            )
            if resp.status_code != 200:
                log.error(f"[ROUTER_GROQ_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return "", False
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip().upper()
            for cat in ["MEDICAL_ANALYSIS", "MEDICAL_ADVICE", "SYSTEM_QUERY", "EMPATHETIC_CHAT"]:
                if cat in content:
                    return f"ROUTING_TARGET: {cat}", True
            return "ROUTING_TARGET: EMPATHETIC_CHAT", True
        except Exception as e:
            log.error("[ROUTER_GROQ_ERROR] Exception: %s", e)
            return "", False

    def _local_classify(self, user_message: str) -> str:
        msg = user_message.lower()
        if any(w in msg for w in ["ping", "sensor", "cảm biến", "cam bien", "kết nối", "ket noi", "scan", "thiết bị", "thiet bi", "hardware", "phần cứng"]):
            return "ROUTING_TARGET: SYSTEM_QUERY"
        if any(w in msg for w in ["đau", "sốt", "ho", "mệt", "bệnh", "chấn thương", "bị thương", "first aid", "sơ cứu", "dau", "sot", "benh", "phát ban", "phat ban", "bỏng", "bong"]):
            return "ROUTING_TARGET: MEDICAL_ADVICE"
        if any(w in msg for w in ["chỉ số", "nhịp tim", "spo2", "huyết áp", "nhiệt độ", "sinh hiệu", "vitals", "chi so", "nhip tim", "huyet ap", "nhiep do"]):
            return "ROUTING_TARGET: MEDICAL_ANALYSIS"
        return "ROUTING_TARGET: EMPATHETIC_CHAT"

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
