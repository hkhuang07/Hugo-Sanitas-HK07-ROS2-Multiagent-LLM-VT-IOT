"""
EmpathyAgent — Tầng 2 trong Subsumption Architecture

Phân tích cảm xúc và giao tiếp với chủ nhân. Sử dụng Groq API (Llama 3 8B).
Volatile Memory: lịch sử hội thoại chỉ lưu trên RAM (< 10 turns).
"""

import asyncio
import logging
import os
from collections import deque
import time

import httpx

from services.agent_log_client import log_agent_decision

log = logging.getLogger("hk07.empathy_agent")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
EMPATHY_SYSTEM_PROMPT = (
    "Bạn là Hugo, trợ lý robot đồng hành ấm áp. Lắng nghe và thấu cảm. "
    "Không đưa lời khuyên y tế. Trả lời tối đa 3 câu ngắn."
)


class EmpathyAgent:
    MAX_TURNS = 10

    def __init__(self, memory, arbitrator):
        self.memory = memory
        self.arbitrator = arbitrator
        self._status = "INITIALIZING"
        self._history: deque = deque(maxlen=self.MAX_TURNS * 2)
        self._groq_api_key = os.getenv("GROQ_API_KEY", "")
        self._client = None

    async def run_loop(self):
        self._status = "ACTIVE"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        log.info("[EMPATHY_AGENT] Active — Tầng 2")
        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            if self._client:
                await self._client.aclose()

    async def process_text_interaction(self, user_message: str) -> str:
        messages = [{"role": "system", "content": EMPATHY_SYSTEM_PROMPT}]
        messages.extend(list(self._history))
        messages.append({"role": "user", "content": user_message})

        if not self._groq_api_key:
            return "[MOCK] Groq key not configured. Set GROQ_API_KEY env."

        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

        start_time = time.time()
        try:
            resp = await self._client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {self._groq_api_key}"},
                json={"model": "llama3-8b-8192", "messages": messages, "max_tokens": 256},
            )
            content = resp.json()["choices"][0]["message"]["content"]
            self._history.append({"role": "user", "content": user_message})
            self._history.append({"role": "assistant", "content": content})
            
            latency = int((time.time() - start_time) * 1000)
            await log_agent_decision(
                agent_type="EMPATHETIC",
                input_context=user_message,
                output_decision=content,
                llm_provider="GROQ-8B",
                latency_ms=latency
            )
            return content
        except Exception as e:
            log.error("[EMPATHY_ERROR] %s", e)
            return "Tôi đang gặp sự cố. Tôi vẫn ở đây bên bạn!"

    def get_status(self) -> dict:
        return {"status": self._status, "turns": len(self._history) // 2}

    def clear_volatile_context(self):
        self._history.clear()
        log.info("[VOLATILE_WIPE] EmpathyAgent cleared")
