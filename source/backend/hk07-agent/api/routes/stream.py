"""
Agent Stream Routes — SSE endpoint for real-time agent event streaming.
Bypasses Spring Boot dependency. Frontend connects directly to FastAPI.
"""

import asyncio
import logging
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from services.agent_event_bus import sse_event_stream, get_recent_events, get_subscriber_count

log = logging.getLogger("hk07.api.stream")
router = APIRouter(tags=["stream"])


@router.get("/api/v1/agents/stream")
async def agent_event_stream_endpoint(request: Request, replay: int = 20):
    """
    SSE endpoint — real-time agent decision stream.
    
    Frontend connects via EventSource:
      const es = new EventSource('/api/v1/agents/stream')
      es.onmessage = (e) => { const ev = JSON.parse(e.data); store.addEvent(ev) }
    
    Query params:
      replay: number of past events to replay on connect (default: 20, max: 200)
    """
    client_id = f"fe_{uuid.uuid4().hex[:8]}"
    replay_n = min(max(0, replay), 200)

    log.info("[STREAM] New SSE client connected: %s (replay=%d, active=%d)",
             client_id, replay_n, get_subscriber_count() + 1)

    async def event_generator():
        async for chunk in sse_event_stream(client_id, replay_last_n=replay_n):
            # Check if client disconnected
            if await request.is_disconnected():
                log.debug("[STREAM] Client %s disconnected early.", client_id)
                break
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering for SSE
        },
    )


@router.get("/api/v1/agents/stream/history")
async def agent_event_history(limit: int = 50):
    """
    HTTP polling fallback — returns recent events from ring buffer.
    Use this when EventSource is not supported or for initial page load.
    """
    events = get_recent_events(limit=min(limit, 200))
    return {
        "status": "ok",
        "count": len(events),
        "subscribers": get_subscriber_count(),
        "events": events,
    }


@router.get("/api/v1/agents/stream/status")
async def agent_stream_status():
    """Health check for SSE infrastructure."""
    return {
        "status": "ONLINE",
        "active_subscribers": get_subscriber_count(),
        "ring_buffer_size": len(get_recent_events(200)),
    }
