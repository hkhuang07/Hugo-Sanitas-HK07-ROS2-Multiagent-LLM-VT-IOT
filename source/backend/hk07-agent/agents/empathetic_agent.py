"""
EmpatheticAgent — Tầng 2 trong Subsumption Architecture

Giao tiếp thấu cảm và chăm sóc tâm lý với chủ nhân.
Mô hình sử dụng:
- Primary: Cohere API (Lợi thế cực mạnh về RAG) truy vấn từ LanceDB memory
- Fallback: Gemini API (Gemini 1.5 Flash)
- Cuối cùng: Local Rule-based
System Prompt đóng vai Hugo (Trợ lý y tế), giọng điệu ấm áp, ngắn gọn.
"""

import asyncio
import logging
import os
import time
from collections import deque
import httpx
from dotenv import load_dotenv
from services.agent_log_client import log_agent_decision
from utils.enums import LLMProvider

# Load env variables
load_dotenv()

log = logging.getLogger("hk07.empathy_agent")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

EMPATHY_SYSTEM_PROMPT = (
    "Bạn là Hugo, một trợ lý chăm sóc sức khỏe cá nhân và đồng hành ấm áp của bệnh nhân.\n"
    "Hãy lắng nghe, thấu cảm, xoa dịu người dùng (thường xuyên sử dụng các cụm từ ấm áp như 'Có tôi ở đây bên bạn rồi', 'Hãy hít thở sâu cùng tôi nhé').\n"
    "Tuyệt đối không tự xưng là Baymax.\n"
    "Khuyên người dùng hít thở sâu nếu họ lo lắng.\n"
    "Trả lời bằng tiếng Việt, tối đa 3 câu ngắn gọn, ấm áp, giàu tình cảm."
)

class EmpatheticAgent:
    MAX_TURNS = 10

    def __init__(self, memory, arbitrator):
        self.memory = memory
        self.arbitrator = arbitrator
        self._status = "INITIALIZING"
        self._history = deque(maxlen=self.MAX_TURNS * 2)
        self._cohere_api_key = os.getenv("COHERE_API_KEY", "")
        self._gemini_api_key = os.getenv("GEMINI_API_KEY", "")
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
        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

        start_time = time.time()
        
        # 1. Retrieve memory context from LanceDB
        mem_context = []
        if self.memory:
            try:
                mem_context = await self.memory.retrieve_recent_events(limit=5)
            except Exception as e:
                log.warning("[EMPATHY_AGENT] Error recalling memory: %s", e)

        # Map memory context to Cohere documents format
        documents = []
        for i, doc in enumerate(mem_context):
            documents.append({
                "id": doc.get("id", f"doc_{i}"),
                "title": doc.get("type", "past_event"),
                "text": doc.get("content", "")
            })

        # 2. Primary Attempt: Cohere API (RAG)
        if self._cohere_api_key:
            content, success = await self._call_cohere(user_message, documents)
            if success:
                latency = int((time.time() - start_time) * 1000)
                await self._log_interaction(user_message, content, LLMProvider.COHERE_PRIMARY.value, latency)
                return content
            log.warning("[EMPATHY_AGENT] Cohere failed — switching to Gemini fallback")

        # 3. Fallback Attempt: Gemini API
        if self._gemini_api_key:
            content, success = await self._call_gemini(user_message, mem_context)
            if success:
                latency = int((time.time() - start_time) * 1000)
                await self._log_interaction(user_message, content, LLMProvider.GEMINI_FALLBACK.value, latency)
                return content
            log.error("[EMPATHY_AGENT] Both Cohere and Gemini unavailable")

        # 4. Local Rule-Based fallback
        content = self._generate_local_fallback(user_message)
        latency = int((time.time() - start_time) * 1000)
        await self._log_interaction(user_message, content, LLMProvider.LOCAL_RULE.value, latency)
        return content

    async def _call_cohere(self, user_message: str, documents: list) -> tuple[str, bool]:
        history_str = ""
        for h in self._history:
            role = "HK-07" if h["role"] == "assistant" else "User"
            history_str += f"{role}: {h['content']}\n"
        context_str = "\n".join([f"- {d['text']}" for d in documents])
        prompt = (
            f"System Instruction:\n{EMPATHY_SYSTEM_PROMPT}\n"
            f"Ký ức quá khứ của bệnh nhân:\n{context_str}\n\n"
            f"Lịch sử hội thoại:\n{history_str}\n"
            f"User: {user_message}\nHugo:"
        )
        try:
            resp = await self._client.post(
                "https://api.cohere.com/v1/chat",
                headers={
                    "Authorization": f"Bearer {self._cohere_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "command-r-08-2024",
                    "message": prompt
                }
            )
            if resp.status_code != 200:
                log.error(f"[EMPATHY_COHERE_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return "", False
            resp.raise_for_status()
            content = resp.json()["text"]
            return content.strip(), True
        except Exception as e:
            log.error("[EMPATHY_COHERE_ERROR] Exception: %s", e)
            return "", False

    async def _call_gemini(self, user_message: str, mem_context: list) -> tuple[str, bool]:
        history_str = ""
        for h in self._history:
            role = "HK-07" if h["role"] == "assistant" else "User"
            history_str += f"{role}: {h['content']}\n"
        context_str = "\n".join([f"- {d['content']}" for d in mem_context])
        prompt = (
            f"System Instruction:\n{EMPATHY_SYSTEM_PROMPT}\n"
            f"Ký ức quá khứ của bệnh nhân:\n{context_str}\n\n"
            f"Lịch sử hội thoại:\n{history_str}\n"
            f"User: {user_message}\nHugo:"
        )
        try:
            resp = await self._client.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={self._gemini_api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}]
                }
            )
            if resp.status_code != 200:
                log.error(f"[EMPATHY_GEMINI_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return "", False
            resp.raise_for_status()
            content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return content.strip(), True
        except Exception as e:
            log.error("[EMPATHY_GEMINI_ERROR] Exception: %s", e)
            return "", False

    async def _log_interaction(self, user_message: str, content: str, provider: str, latency: int):
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": content})
        
        # Save memory event to LanceDB
        if self.memory:
            try:
                await self.memory.store_emotional_event(user_message, content)
            except Exception as e:
                log.warning("[EMPATHY_AGENT] Memory save failed: %s", e)

        await log_agent_decision(
            agent_type="EMPATHETIC",
            input_context=user_message,
            output_decision=content,
            llm_provider=provider,
            latency_ms=latency
        )

    def _generate_local_fallback(self, user_message: str) -> str:
        msg = user_message.lower()
        if "chào" in msg or "hello" in msg or "hi" in msg:
            return "Xin chào! Tôi là Hugo, trợ lý chăm sóc sức khỏe cá nhân của bạn. Có tôi ở đây bên bạn rồi."
        elif "buồn" in msg or "mệt" in msg or "khóc" in msg or "buon" in msg or "met" in msg or "kho" in msg:
            return "Tôi nghe thấy bạn có vẻ không được vui. Hãy hít thở thật sâu cùng tôi nhé. Có tôi ở đây bên bạn rồi."
        elif "lo" in msg or "sợ" in msg or "anxious" in msg or "fear" in msg:
            return "Đừng lo lắng quá. Nhắm mắt lại và hít một hơi thật sâu. Có tôi ở đây bên bạn rồi."
        return "Tôi hiểu mà. Tôi luôn ở đây để lắng nghe và chăm sóc bạn. Có tôi ở đây bên bạn rồi."

    def get_status(self) -> dict:
        return {"status": self._status, "turns": len(self._history) // 2}

    def clear_volatile_context(self):
        self._history.clear()
        log.info("[VOLATILE_WIPE] EmpathyAgent cleared")
