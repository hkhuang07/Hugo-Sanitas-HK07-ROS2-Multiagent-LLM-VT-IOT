"""
Agent Log Client — HTTP Bridge: Python hk07-agent → Spring Boot hk07-core

Sends agent decision logs to the Spring Boot backend REST API.
The backend persists them to MySQL and broadcasts via WebSocket.

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

from pathlib import Path
import httpx
from dotenv import load_dotenv

# Robust .env loading
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

log = logging.getLogger("hk07.agent_log_client")


# Use 127.0.0.1 instead of localhost to bypass IPv6 loopback issues on Windows/WSL2
CORE_API_URL = os.getenv("CORE_API_URL") or os.getenv("HK07_CORE_URL") or "http://127.0.0.1:8888"
AUTH_EMAIL = os.getenv("AGENT_AUTH_EMAIL", "owner@hk07.local")
AUTH_PASSWORD = os.getenv("AGENT_AUTH_PASSWORD", "HK07-Admin-Change-Me!")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "hk07-internal-api-key-bypass")

BATCH_SIZE = 10
FLUSH_INTERVAL_S = 5.0


@dataclass
class AgentLogEntry:
    agent_type: str          # EMPATHETIC | MEDICAL | SAFETY
    input_context: str
    output_decision: str
    llm_provider: str        # GROQ | GEMINI | THRESHOLD | MOCK
    latency_ms: int
    user_id: Optional[str] = None
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
        self._retry_auth_after: float = 0.0
        self._backoff_delay: float = 5.0  # Start with 5 seconds backoff

    async def start(self):
        """Call once at startup to initialize HTTP client and start flush loop"""
        self._http = httpx.AsyncClient(
            base_url=CORE_API_URL,
            timeout=httpx.Timeout(5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
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
                           output_decision: str, llm_provider: str, latency_ms: int,
                           user_id: Optional[str] = None):
        """
        Queue a decision log entry. Non-blocking — returns immediately.
        Buffer is flushed in background every FLUSH_INTERVAL_S seconds or when BATCH_SIZE is reached.
        """
        # Standardize agent type to match Spring Boot enum
        agent_type_upper = agent_type.upper() if agent_type else ""
        if "MEDICAL" in agent_type_upper:
            sanitized_type = "MEDICAL"
        elif "SAFETY" in agent_type_upper:
            sanitized_type = "SAFETY"
        elif "EMPATHETIC" in agent_type_upper or "EMPATHY" in agent_type_upper:
            sanitized_type = "EMPATHETIC"
        elif "CARE" in agent_type_upper:
            sanitized_type = "CARE"
        elif "PERCEPTION" in agent_type_upper:
            sanitized_type = "PERCEPTION"
        elif "ACTION" in agent_type_upper:
            sanitized_type = "ACTION"
        elif "ROUTER" in agent_type_upper or "ORCHESTRATOR" in agent_type_upper:
            sanitized_type = "ROUTER"
        else:
            sanitized_type = "EMPATHETIC"  # Default fallback

        entry = AgentLogEntry(
            agent_type=sanitized_type,
            input_context=input_context[:800] if input_context else "",
            output_decision=output_decision[:1500] if output_decision else "",
            llm_provider=llm_provider,
            latency_ms=latency_ms,
            user_id=user_id
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
            if time.time() > self._retry_auth_after:
                await self._authenticate()

        if not self._token:
            log.debug("[AGENT_LOG_CLIENT] No auth token available — falling back to MQTT for %d logs", len(batch))
            for entry in batch:
                self._fallback_publish_mqtt_sync(entry)
            return

        # Use asyncio.gather to prevent blocking the async loop sequentially
        async def _post_log(entry):
            try:
                headers = {}
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"
                if INTERNAL_API_KEY:
                    headers["X-Internal-API-Key"] = INTERNAL_API_KEY
                resp = await self._http.post(
                    "/api/v1/agents/log",
                    json={
                        "agentType": entry.agent_type,
                        "inputContext": entry.input_context,
                        "outputDecision": entry.output_decision,
                        "llmProvider": entry.llm_provider,
                        "latencyMs": entry.latency_ms,
                        "userId": entry.user_id,
                    },
                    headers=headers
                )
                if resp.status_code not in (200, 202):
                    log.warning("[AGENT_LOG_CLIENT] POST failed: %s. Falling back to MQTT.", resp.text[:100])
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self._fallback_publish_mqtt_sync, entry)
            except Exception as exc:
                log.warning("[AGENT_LOG_CLIENT] Backend HTTP unreachable (%s) — falling back to MQTT", exc)
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self._fallback_publish_mqtt_sync, entry)
                except RuntimeError:
                    # If loop is not running, execute synchronously
                    self._fallback_publish_mqtt_sync(entry)

        tasks = [_post_log(entry) for entry in batch]
        await asyncio.gather(*tasks, return_exceptions=True)

        log.debug("[AGENT_LOG_CLIENT] Flushed %d logs concurrently", len(batch))

    def _fallback_publish_mqtt_sync(self, entry: AgentLogEntry):
        try:
            import paho.mqtt.publish as publish
            import json
            import uuid
            from datetime import datetime

            broker_host = os.getenv("MQTT_BROKER_HOST") or "127.0.0.1"
            broker_port = int(os.getenv("MQTT_BROKER_PORT") or 1883)
            mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
            mqtt_pass = os.getenv("MQTT_PASSWORD", "hk07_mqtt_dev_pwd")

            client_id = f"agent-log-fallback-{uuid.uuid4().hex[:8]}"
            
            # Prepare standardized JSON payload matching handleAgentOutput expectations
            payload = {
                "id": f"mqtt_fallback_{uuid.uuid4()}",
                "agentType": entry.agent_type.upper(),
                "inputContext": entry.input_context,
                "outputDecision": entry.output_decision,
                "llmProvider": entry.llm_provider,
                "latencyMs": entry.latency_ms,
                "triggeredAt": datetime.now().isoformat()
            }
            
            topic = f"hk07/agents/{entry.agent_type.lower()}/decision"
            
            auth_dict = None
            if mqtt_user:
                auth_dict = {'username': mqtt_user, 'password': mqtt_pass}
                
            publish.single(
                topic,
                payload=json.dumps(payload),
                hostname=broker_host,
                port=broker_port,
                auth=auth_dict,
                client_id=client_id,
                qos=1
            )
            log.info("[AGENT_LOG_CLIENT] Successfully published log fallback to MQTT topic: %s", topic)
        except Exception as e:
            log.error("[AGENT_LOG_CLIENT] MQTT fallback publish failed: %s", e)

    async def _authenticate(self):
        """Get JWT token from environment variable or Spring Boot auth endpoint"""
        # Re-load .env to get the latest token if changed
        load_dotenv(dotenv_path=env_path, override=True)
        env_token = os.getenv("BACKEND_API_TOKEN")
        if env_token:
            if env_token.startswith("Bearer "):
                env_token = env_token[7:]
            self._token = env_token
            self._token_expires_at = time.time() + 3600  # Cache for 1 hour, check env again later
            if self._http:
                self._http.headers["Authorization"] = f"Bearer {self._token}"
            log.info("[AGENT_LOG_CLIENT] Authenticated via BACKEND_API_TOKEN environment variable")
            return

        try:
            resp = await self._http.post(
                "/api/v1/auth/login",
                json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD}
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data["data"]["accessToken"]
                self._token_expires_at = time.time() + 800  # Refresh before 15min expiry
                self._retry_auth_after = 0.0
                self._backoff_delay = 5.0  # Reset backoff on success
                if self._http:
                    self._http.headers["Authorization"] = f"Bearer {self._token}"
                log.info("[AGENT_LOG_CLIENT] Authenticated successfully as %s", AUTH_EMAIL)
            else:
                # Server is online but credentials are wrong or DB is not seeded
                log.error(
                    "[AGENT_LOG_CLIENT] Auth failed: Invalid credentials or database not seeded. "
                    "Status Code: %d, Response: %s",
                    resp.status_code,
                    resp.text[:100]
                )
                # Keep a fixed retry backoff for credential failures to avoid spamming the database
                self._retry_auth_after = time.time() + 60.0
        except httpx.RequestError as exc:
            err_msg = str(exc) or exc.__class__.__name__
            log.warning(
                "[AGENT_LOG_CLIENT] Backend core is offline or booting up. Reconnecting in %.1fs... (Detail: %s)",
                self._backoff_delay,
                err_msg
            )
            self._retry_auth_after = time.time() + self._backoff_delay
            self._backoff_delay = min(self._backoff_delay * 2, 60.0)  # Exponential backoff
        except Exception as e:
            err_msg = str(e) or e.__class__.__name__
            log.error("[AGENT_LOG_CLIENT] Auth error: %s", err_msg, exc_info=True)
            self._retry_auth_after = time.time() + 60.0


# ─── Singleton instance ───────────────────────────────────────────────────────
_client = AgentLogClient()


async def start_log_client():
    """Call from FastAPI lifespan startup"""
    await _client.start()


async def stop_log_client():
    """Call from FastAPI lifespan shutdown"""
    await _client.stop()


async def log_agent_decision(agent_type: str, input_context: str,
                              output_decision: str, llm_provider: str, latency_ms: int,
                              user_id: Optional[str] = None):
    """Convenience function for agents — import and call this directly"""
    await _client.log_decision(agent_type, input_context, output_decision, llm_provider, latency_ms, user_id=user_id)
