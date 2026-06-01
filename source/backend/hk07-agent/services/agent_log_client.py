"""
Agent Log Client — HTTP Bridge: Python hk07-agent → Spring Boot hk07-core

Sends agent decision logs to the Spring Boot backend REST API.
The backend persists them to PostgreSQL and broadcasts via WebSocket.

Usage: Import and call in MedicalAgent, EmpathyAgent after each decision.

Design:
- Async HTTP POST using httpx (non-blocking)
- Fire-and-forget: logs dropped if backend is unreachable (never blocks agent decision loop)
- Batching: buffers up to 10 logs, flushes every 5 seconds (saves network overhead)
- Auth: authenticates once at startup using owner credentials, caches JWT token
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

log = logging.getLogger("hk07.agent_log_client")

CORE_API_URL = os.getenv("CORE_API_URL") or os.getenv("HK07_CORE_URL") or "http://localhost:8888"
AUTH_EMAIL = os.getenv("AGENT_AUTH_EMAIL", "owner@hk07.local")
AUTH_PASSWORD = os.getenv("AGENT_AUTH_PASSWORD", "HK07-Admin-Change-Me!")

BATCH_SIZE = 10
FLUSH_INTERVAL_S = 5.0


@dataclass
class AgentLogEntry:
    agent_type: str          # EMPATHETIC | MEDICAL | SAFETY
    input_context: str
    output_decision: str
    llm_provider: str        # GROQ | GEMINI | THRESHOLD | MOCK
    latency_ms: int
    queued_at: float = field(default_factory=time.time)


class AgentLogClient:
    """
    Async batch-log client.
    Sends agent decisions to Spring Boot /api/v1/agents/log endpoint.
    """

    def __init__(self):
        self._buffer: list[AgentLogEntry] = []
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._http: Optional[httpx.AsyncClient] = None
        self._flush_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Call once at startup to initialize HTTP client and start flush loop"""
        self._http = httpx.AsyncClient(
            base_url=CORE_API_URL,
            timeout=httpx.Timeout(5.0),
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=1)
        )
        await self._authenticate()
        self._flush_task = asyncio.create_task(self._flush_loop())
        log.info("[AGENT_LOG_CLIENT] Started — flushing every %ss", FLUSH_INTERVAL_S)

    async def stop(self):
        """Flush remaining buffer on shutdown"""
        if self._flush_task:
            self._flush_task.cancel()
        await self._flush_buffer()  # Final flush
        if self._http:
            await self._http.aclose()

    async def log_decision(self, agent_type: str, input_context: str,
                           output_decision: str, llm_provider: str, latency_ms: int):
        """
        Queue a decision log entry. Non-blocking — returns immediately.
        Buffer is flushed in background every FLUSH_INTERVAL_S seconds or when BATCH_SIZE is reached.
        """
        entry = AgentLogEntry(
            agent_type=agent_type,
            input_context=input_context[:800] if input_context else "",
            output_decision=output_decision[:1500] if output_decision else "",
            llm_provider=llm_provider,
            latency_ms=latency_ms
        )

        async with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= BATCH_SIZE:
                # Don't await — fire flush in background, don't block the caller
                asyncio.create_task(self._flush_buffer())

    # ─── Internal ────────────────────────────────────────────────────────────
    async def _flush_loop(self):
        """Background coroutine: flush every FLUSH_INTERVAL_S"""
        while True:
            await asyncio.sleep(FLUSH_INTERVAL_S)
            await self._flush_buffer()

    async def _flush_buffer(self):
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer.copy()
            self._buffer.clear()

        if not self._token or time.time() > self._token_expires_at:
            await self._authenticate()

        if not self._token:
            log.warning("[AGENT_LOG_CLIENT] No auth token — %d logs dropped", len(batch))
            return

        # Use asyncio.gather to prevent blocking the async loop sequentially
        async def _post_log(entry):
            try:
                resp = await self._http.post(
                    "/api/v1/agents/log",
                    json={
                        "agentType": entry.agent_type,
                        "inputContext": entry.input_context,
                        "outputDecision": entry.output_decision,
                        "llmProvider": entry.llm_provider,
                        "latencyMs": entry.latency_ms,
                    },
                    headers={"Authorization": f"Bearer {self._token}"}
                )
                if resp.status_code not in (200, 202):
                    log.warning("[AGENT_LOG_CLIENT] POST failed: %s", resp.text[:100])
            except (httpx.TimeoutException, httpx.ConnectError):
                log.warning("[AGENT_LOG_CLIENT] Backend unreachable — log dropped")

        tasks = [_post_log(entry) for entry in batch]
        await asyncio.gather(*tasks, return_exceptions=True)

        log.debug("[AGENT_LOG_CLIENT] Flushed %d logs concurrently", len(batch))

    async def _authenticate(self):
        """Get JWT token from Spring Boot auth endpoint"""
        try:
            resp = await self._http.post(
                "/api/v1/auth/login",
                json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD}
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data["data"]["accessToken"]
                self._token_expires_at = time.time() + 800  # Refresh before 15min expiry
                log.info("[AGENT_LOG_CLIENT] Authenticated as %s", AUTH_EMAIL)
            else:
                log.error("[AGENT_LOG_CLIENT] Auth failed: %s", resp.text[:100])
        except Exception as e:
            log.error("[AGENT_LOG_CLIENT] Auth error: %s", e)


# ─── Singleton instance ───────────────────────────────────────────────────────
_client = AgentLogClient()


async def start_log_client():
    """Call from FastAPI lifespan startup"""
    await _client.start()


async def stop_log_client():
    """Call from FastAPI lifespan shutdown"""
    await _client.stop()


async def log_agent_decision(agent_type: str, input_context: str,
                              output_decision: str, llm_provider: str, latency_ms: int):
    """Convenience function for agents — import and call this directly"""
    await _client.log_decision(agent_type, input_context, output_decision, llm_provider, latency_ms)
