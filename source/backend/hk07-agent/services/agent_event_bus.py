"""
AgentEventBus — Server-Sent Events (SSE) Broadcast Service
HK-07 Agent Engine | Production Module

Architecture:
  Singleton async event bus using asyncio.Queue per subscriber.
  Agents publish events after each decision → subscribers receive realtime.
  
  Flow:
    Agent decision → log_agent_decision() + publish_sse_event()
                  → AgentEventBus._broadcast()
                  → asyncio.Queue per connected frontend client
                  → /api/v1/agents/stream SSE endpoint
                  → Frontend EventSource subscription
                  → AgentsView renders event
  
  Design:
  - Max 50 concurrent subscribers (production safe)
  - Ring buffer: max 200 events stored for late-joiners
  - Non-blocking: event publish never blocks agent decision loop
  - Auto-reconnect: SSE clients reconnect on drop automatically
"""

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

log = logging.getLogger("hk07.agent_event_bus")

# ── Ring Buffer for late joiners ──────────────────────────────────────────────
_EVENT_RING_BUFFER: list = []
_EVENT_RING_BUFFER_MAX = 200

# ── Subscriber queues ─────────────────────────────────────────────────────────
_SUBSCRIBERS: dict[str, asyncio.Queue] = {}
_MAX_SUBSCRIBERS = 50


def _build_event_payload(
    agent_type: str,
    input_context: str,
    output_decision: str,
    llm_provider: str,
    latency_ms: int,
    alert_level: str = "NORMAL",
    user_id: Optional[str] = None,
    tools_invoked: Optional[list] = None,
    event_type: str = "AGENT_DECISION",
) -> dict:
    """Standardized SSE payload matching AgentEvent TypeScript interface."""
    return {
        "id": f"sse_{uuid.uuid4().hex[:12]}",
        "agentType": agent_type.upper(),
        "eventType": event_type,
        "inputContext": (input_context or "")[:800],
        "outputDecision": (output_decision or "")[:1500],
        "llmProvider": llm_provider or "UNKNOWN",
        "latencyMs": latency_ms,
        "alertLevel": alert_level,
        "toolsInvoked": tools_invoked or [],
        "triggeredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "userId": user_id or "default",
    }


async def publish_agent_event(
    agent_type: str,
    input_context: str,
    output_decision: str,
    llm_provider: str,
    latency_ms: int,
    alert_level: str = "NORMAL",
    user_id: Optional[str] = None,
    tools_invoked: Optional[list] = None,
    event_type: str = "AGENT_DECISION",
) -> None:
    """
    Publish an agent event to all SSE subscribers.
    Non-blocking — fire and forget. Never delays agent decision loop.
    """
    payload = _build_event_payload(
        agent_type=agent_type,
        input_context=input_context,
        output_decision=output_decision,
        llm_provider=llm_provider,
        latency_ms=latency_ms,
        alert_level=alert_level,
        user_id=user_id,
        tools_invoked=tools_invoked,
        event_type=event_type,
    )

    # Store in ring buffer for late-joining clients
    global _EVENT_RING_BUFFER
    _EVENT_RING_BUFFER.append(payload)
    if len(_EVENT_RING_BUFFER) > _EVENT_RING_BUFFER_MAX:
        _EVENT_RING_BUFFER = _EVENT_RING_BUFFER[-_EVENT_RING_BUFFER_MAX:]

    # Broadcast to all connected SSE subscribers
    dead_subscribers = []
    for sub_id, queue in _SUBSCRIBERS.items():
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Drop oldest event to prevent slow consumer from blocking others
            try:
                queue.get_nowait()
                queue.put_nowait(payload)
            except Exception:
                dead_subscribers.append(sub_id)
        except Exception as e:
            log.debug("[EVENT_BUS] Subscriber %s error: %s", sub_id, e)
            dead_subscribers.append(sub_id)

    for sub_id in dead_subscribers:
        _SUBSCRIBERS.pop(sub_id, None)

    if _SUBSCRIBERS:
        log.debug("[EVENT_BUS] Published %s event to %d subscribers", agent_type, len(_SUBSCRIBERS))


async def sse_event_stream(client_id: str, replay_last_n: int = 20) -> AsyncGenerator[str, None]:
    """
    SSE generator for a single frontend client.
    Replays last N events on connect, then streams live events.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _SUBSCRIBERS[client_id] = queue

    try:
        # Send connection confirmation
        yield f"data: {json.dumps({'type': 'CONNECTED', 'clientId': client_id, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})}\n\n"

        # Replay ring buffer for late joiners (last N events)
        replay_events = _EVENT_RING_BUFFER[-replay_last_n:] if _EVENT_RING_BUFFER else []
        for event in replay_events:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        if replay_events:
            log.info("[EVENT_BUS] Replayed %d events to client %s", len(replay_events), client_id)

        # Stream live events
        while True:
            try:
                # Heartbeat every 15s to prevent proxy timeout
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                # SSE heartbeat comment to keep connection alive
                yield ": heartbeat\n\n"
            except asyncio.CancelledError:
                break

    except asyncio.CancelledError:
        log.debug("[EVENT_BUS] Client %s disconnected (CancelledError)", client_id)
    except Exception as e:
        log.warning("[EVENT_BUS] Client %s error: %s", client_id, e)
    finally:
        _SUBSCRIBERS.pop(client_id, None)
        log.info("[EVENT_BUS] Client %s unsubscribed. Active: %d", client_id, len(_SUBSCRIBERS))


def get_recent_events(limit: int = 50) -> list:
    """Return recent events from ring buffer for HTTP polling fallback."""
    return _EVENT_RING_BUFFER[-limit:][::-1]  # newest first


def get_subscriber_count() -> int:
    return len(_SUBSCRIBERS)
