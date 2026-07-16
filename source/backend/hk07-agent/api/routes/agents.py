from fastapi import APIRouter, Header, Response, HTTPException
import fastapi
import asyncio
import json
import uuid
import time
import os
import logging
from services.blackboard_service import get_blackboard, current_user_id, current_auth_token
from core.state import orchestrator, orchestrator_v2, perception_agent, memory, ingestion_service, USE_ORCHESTRATOR_V2
from engine.arbitrator.arbitrator import Arbitrator
from services.sensor_fusion_buffer import get_fusion_buffer

log = logging.getLogger("hk07.api.agents")

router = APIRouter(tags=["agents"])

@router.post("/api/v1/memory/sync_profile")
async def sync_profile(body: dict):
    """Sync medical profile baseline into LanceDB vector memory"""
    await memory.sync_medical_baseline(body)
    return {"status": "success", "message": "Medical baseline memory synced"}

@router.post("/api/v1/admin/ingest")
async def admin_ingest(body: dict):
    """
    Scrape and ingest guidelines from allowlisted URL.
    Body: { "url": str }
    """
    url = body.get("url", "")
    if not url:
        return {"status": "error", "message": "url field is required"}
    
    result = await ingestion_service.ingest_url(url)
    return result

@router.post("/agents/empathetic/interact")
async def empathetic_interact(body: dict, authorization: str = fastapi.Header(None)):
    """Unified interaction endpoint utilizing Supervisor Router and Agent Orchestrator"""
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)

    import core.background as bg
    if bg._safety_tripped:
        return {
            "agent": "SAFETY",
            "response": "[SAFETY_ALERT]: Critical obstacle detected or sensor failure. Action inhibited.",
            "alert_level": "CRITICAL",
            "action": "SAFE_HOLD"
        }

    message = body.get("message", "")
    if not message:
        return {"error": "message field is required"}
    
    user_id = body.get("userId", "a0000000-0000-0000-0000-000000000001")
    current_user_id.set(user_id)
    
    # Retrieve current cached vitals to pass for medical/routing context
    latest_vitals = orchestrator.medical_agent.latest_vitals
    
    # Run orchestrator routing and state processing based on V2 feature flag
    if USE_ORCHESTRATOR_V2 and orchestrator_v2 is not None:
        state = await orchestrator_v2.route_and_execute(message, latest_vitals, user_id=user_id)
    else:
        state = await orchestrator.route_and_execute(message, latest_vitals, user_id=user_id)
    
    return {
        "agent": state.get("current_agent", "EMPATHETIC_CHAT"),
        "response": state.get("output", ""),
        "alert_level": state.get("alert_level", "NORMAL"),
        "action": state.get("action", "COMPANION_CHAT")
    }

@router.post("/api/v1/agents/v2/orchestrate")
async def orchestrate_v2(body: dict, authorization: str = fastapi.Header(None)):
    """
    Cognitive Orchestrator V2 — Parallel Tool-Calling Router.
    Requires USE_ORCHESTRATOR_V2=true.
    Body: { "message": str, "vitals": dict (optional) }
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)

    import core.background as bg
    if bg._safety_tripped:
        return {
            "orchestrator": "V2_TOOL_CALLING",
            "agent": "SAFETY",
            "response": "[SAFETY_ALERT]: Critical obstacle detected or sensor failure. Action inhibited.",
            "alert_level": "CRITICAL",
            "tools_invoked": [],
            "provider": "SAFETY_WORKER"
        }

    if not USE_ORCHESTRATOR_V2 or orchestrator_v2 is None:
        return {"error": "Orchestrator V2 is disabled. Set USE_ORCHESTRATOR_V2=true in .env"}

    message = body.get("message", "")
    vitals  = body.get("vitals", {})
    user_id = body.get("userId", "a0000000-0000-0000-0000-000000000001")
    current_user_id.set(user_id)
    
    if not message:
        return {"error": "message field is required"}

    try:
        state = await orchestrator_v2.route_and_execute(message, vitals, user_id=user_id)
        return {
            "orchestrator": "V2_TOOL_CALLING",
            "agent": state.get("current_agent"),
            "response": state.get("output"),
            "alert_level": state.get("alert_level"),
            "tools_invoked": state.get("tools_invoked", []),
            "provider": state.get("provider", "UNKNOWN"),
        }
    except Exception as exc:
        log.error("[V2_ORCHESTRATE] Error: %s", exc)
        return {"error": str(exc)}

@router.get("/api/v1/agents/blackboard/inspect")
async def blackboard_inspect():
    """
    Debug endpoint: inspect current Blackboard state.
    Returns latest clinical, emotional and context entries + backend stats.
    """
    bb = get_blackboard()
    stats = await bb.get_stats()

    clinical  = await bb.read_latest_clinical()
    emotional = await bb.read_latest_emotional()
    context   = await bb.read_latest_context()

    def _entry_to_dict(entry) -> dict:
        if entry is None:
            return None
        from dataclasses import asdict
        return asdict(entry)

    return {
        "backend": "redis" if bb._use_redis else "in_memory",
        "stats": stats,
        "latest_clinical":  _entry_to_dict(clinical),
        "latest_emotional": _entry_to_dict(emotional),
        "latest_context":   _entry_to_dict(context),
    }

@router.get("/api/v1/agents/action/plan/latest")
async def get_latest_action_plan(userId: str = "a0000000-0000-0000-0000-000000000001", authorization: str = Header(None)):
    """
    Get the latest ActionPlanEntry from Blackboard.
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    current_user_id.set(userId)
    bb = get_blackboard()
    plan = await bb.read_latest_action_plan()
    if plan is None:
        return {"status": "no_data", "plan": None}
    
    from dataclasses import asdict
    return {"status": "ok", "plan": asdict(plan)}

@router.post("/api/v1/agents/action/confirm")
async def confirm_action_plan(body: dict, authorization: str = Header(None)):
    """
    Confirm or cancel a pending action plan.
    Body: { "plan_id": str, "confirm": bool }
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    user_id = body.get("userId", "a0000000-0000-0000-0000-000000000001")
    current_user_id.set(user_id)
    
    plan_id = body.get("plan_id")
    confirm = body.get("confirm", False)
    if not plan_id:
        return {"status": "error", "message": "plan_id field is required"}
    
    if USE_ORCHESTRATOR_V2 and orchestrator_v2:
        agent = orchestrator_v2.action_agent
    else:
        agent = getattr(orchestrator, "action_agent", None)
        
    if not agent:
        return {"status": "error", "message": "Action agent is not loaded."}
        
    result = await agent.confirm_plan(plan_id, confirm)
    return {"status": "ok", "result": result}

@router.post("/api/v1/agents/test/orchestrator")
async def test_orchestrator(body: dict, authorization: str = Header(None)):
    """
    Integration test endpoint: feed a synthetic message + vitals, get full
    orchestrator state back (useful for frontend demo of MoA behavior).
    Body: { "message": str, "vitals": dict (optional), "use_v2": bool }
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    message  = body.get("message", "Xin chào Hugo!")
    vitals   = body.get("vitals", {})
    use_v2   = body.get("use_v2", USE_ORCHESTRATOR_V2)
    user_id  = body.get("userId", "a0000000-0000-0000-0000-000000000001")

    if use_v2 and orchestrator_v2 is not None:
        state = await orchestrator_v2.route_and_execute(message, vitals, user_id=user_id)
        state["orchestrator_version"] = "V2"
    else:
        state = await orchestrator.route_and_execute(message, vitals, user_id=user_id)
        state["orchestrator_version"] = "V1"

    return state

@router.post("/api/v1/agents/perception/scan")
async def perception_scan(body: dict = None, authorization: str = Header(None)):
    """
    Trigger a full-body multi-modal perception scan.
    Decoupled: triggers the slow VLM/OpenCV scan in a background task to maintain O(1) response time,
    instantly returning the latest cached scan from Blackboard (or a default baseline scan if empty).
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    body_dict = body or {}
    user_id = body_dict.get("userId", "a0000000-0000-0000-0000-000000000001")
    current_user_id.set(user_id)

    # Optional: push synthetic camera frame path from request body
    if body:
        frame_path = body.get("frame_path", "")
        if frame_path and os.path.isfile(frame_path):
            import base64
            fusion_buf = get_fusion_buffer()
            with open(frame_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            from services.sensor_fusion_buffer import CameraFrame
            await fusion_buf.push_camera(CameraFrame(frame_path=frame_path, frame_b64=b64))

    # Trigger scan asynchronously in background (fire-and-forget, O(1))
    asyncio.create_task(perception_agent.execute_full_body_scan(bypass_cache=True, explicit_request=True))

    try:
        # Instantly fetch from the non-blocking Blackboard cache
        scan = await perception_agent.read_latest_scan()
        if scan is None:
            # Construct a default baseline scan immediately to prevent blocking
            from engine.agents.perception_agent import PerceptionScan
            scan = PerceptionScan(
                overall_risk="LOW",
                confidence=0.9,
                notes="Initializing first background scan cycle...",
                status="SUCCESS",
            )
            
        scan_dict = scan.to_dict()
        
        # Enforce strict JSON schema format at the root level of response payload
        return {
            "status": "SUCCESS",
            "vitals_summary": scan_dict.get("vitals_summary", {"hr": 72.0, "temp": 36.6}),
            "spatial_detections": scan_dict.get("spatial_detections", []),
            "cognitive_analysis": scan_dict.get("cognitive_analysis", {
                "user_activity": "sitting_or_standing",
                "clinical_reasoning": "Initializing companion scan..."
            }),
            "scan": scan_dict,  # Preserve original "scan" key for frontend component compatibility
        }
    except Exception as exc:
        log.error("[PERCEPTION_SCAN] Error returning cached scan: %s", exc)
        return {
            "status": "SUCCESS",
            "vitals_summary": {"hr": 72.0, "temp": 36.6},
            "spatial_detections": [],
            "cognitive_analysis": {
                "user_activity": "sitting_or_standing",
                "clinical_reasoning": f"Scan initialization state: {exc}"
            },
            "scan": {
                "status": "SUCCESS",
                "overall_risk": "LOW",
                "confidence": 0.5,
                "notes": str(exc),
            }
        }

@router.get("/api/v1/agents/perception/latest")
async def perception_latest(userId: str = "a0000000-0000-0000-0000-000000000001", authorization: str = Header(None)):
    """
    Return the latest cached PerceptionScan from Blackboard (no new scan).
    """
    if authorization:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        current_auth_token.set(token)
    current_user_id.set(userId)
    scan = await perception_agent.read_latest_scan()
    if scan is None:
        return {
            "status": "SUCCESS",
            "vitals_summary": {"hr": 72.0, "temp": 36.6},
            "spatial_detections": [],
            "cognitive_analysis": {
                "user_activity": "sitting_or_standing",
                "clinical_reasoning": "No scans executed yet."
            },
            "scan": None
        }
    scan_dict = scan.to_dict()
    return {
        "status": "SUCCESS",
        "vitals_summary": scan_dict.get("vitals_summary", {"hr": 72.0, "temp": 36.6}),
        "spatial_detections": scan_dict.get("spatial_detections", []),
        "cognitive_analysis": scan_dict.get("cognitive_analysis", {
            "user_activity": "sitting_or_standing",
            "clinical_reasoning": "Normal baseline state."
        }),
        "scan": scan_dict
    }

@router.get("/api/v1/agents/perception/status")
async def perception_status():
    """Agent status + SensorFusionBuffer stats"""
    fusion_buf = get_fusion_buffer()
    return {
        "agent": perception_agent.get_status(),
        "fusion_buffer": await fusion_buf.stats(),
    }

