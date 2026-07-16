from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Response
import asyncio
import json
from typing import Optional, List
from pydantic import BaseModel
from services.blackboard_service import get_blackboard
from services.sensor_fusion_buffer import get_fusion_buffer, VitalsSample, CameraFrame
from services.hardware_mqtt_service import HardwareMqttService
from core.shared import _device_config, _sensor_cache, _cache_lock
import logging
from core.state import perception_agent

log = logging.getLogger("hk07.api.sensors")

router = APIRouter(tags=["sensors"])

def sanitize_nan(data):
    """Recursively replace float('nan') with None to prevent JSON serialization errors."""
    import math
    if isinstance(data, dict):
        return {k: sanitize_nan(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_nan(x) for x in data]
    elif isinstance(data, float) and math.isnan(data):
        return None
    return data

@router.get("/api/v1/sensor-cache/latest")
async def sensor_cache_latest():
    """
    Returns the latest sensor state from the centralized in-memory cache
    hydrated by run_headless_sensor_daemon.

    The /companion frontend page MUST poll this endpoint instead of mounting
    its own ingestion hooks. Polling interval recommended: 500–1000ms.

    Response schema:
      vitals:        { hr, spo2, temp, alert_level } or null
      frame_b64:     base64 JPEG string or null
      frame_ts:      Unix timestamp of last captured frame
      fall_detected: bool
      fever_alert:   bool
      imu:           latest IMU dict or null
      daemon_status: str (OK | CAMERA_UNRESOLVED | CAMERA_ERROR | RUNNING | STOPPED)
      last_update:   Unix timestamp of last daemon cycle
    """
    import time
    if _cache_lock.locked():
        vitals = _sensor_cache.get("vitals")
        daemon_status = _sensor_cache.get("daemon_status", "UNKNOWN")
        last_update = _sensor_cache.get("last_update")
        fall_detected = _sensor_cache.get("fall_detected", False)
        fever_alert = _sensor_cache.get("fever_alert", False)
        imu = _sensor_cache.get("imu")
        environment = _sensor_cache.get("environment")
        location = _sensor_cache.get("location")
        activity = _sensor_cache.get("activity")
        frame_bytes = _sensor_cache.get("frame_bytes")
        frame_ts = _sensor_cache.get("frame_ts")
    else:
        async with _cache_lock:
            vitals = _sensor_cache.get("vitals")
            daemon_status = _sensor_cache.get("daemon_status", "UNKNOWN")
            last_update = _sensor_cache.get("last_update")
            fall_detected = _sensor_cache.get("fall_detected", False)
            fever_alert = _sensor_cache.get("fever_alert", False)
            imu = _sensor_cache.get("imu")
            environment = _sensor_cache.get("environment")
            location = _sensor_cache.get("location")
            activity = _sensor_cache.get("activity")
            frame_bytes = _sensor_cache.get("frame_bytes")
            frame_ts = _sensor_cache.get("frame_ts")

    # Build LocalOfflineFallback vitals_context for downstream use
    vitals_context = None
    if vitals:
        hr   = vitals.get("hr")
        temp = vitals.get("temp")
        import math
        hr_val = hr if (hr is not None and not (isinstance(hr, float) and math.isnan(hr))) else 0
        temp_val = temp if (temp is not None and not (isinstance(temp, float) and math.isnan(temp))) else 0
        vitals_context = {
            "hr":            hr_val if hr_val > 0 else float('nan'),
            "temp":          temp_val if temp_val > 0 else float('nan'),
            "spo2":          vitals.get("spo2"),
            "fever":         temp_val >= 38.0,
            "tachycardia":   hr_val >= 100,
            "fall_detected": fall_detected,
        }
    return sanitize_nan({
        "status":        "ok",
        "daemon_status": daemon_status,
        "last_update":   last_update,
        "vitals":        vitals,
        "vitals_context": vitals_context,
        "fall_detected": fall_detected,
        "fever_alert":   fever_alert,
        "imu":           imu,
        "environment":   environment,
        "location":      location,
        "activity":      activity,
        # frame_b64 excluded from this endpoint by default (size) —
        # use /api/v1/sensor-cache/frame for raw frame access
        "frame_available": frame_bytes is not None,
        "frame_ts":      frame_ts,
    })

@router.websocket("/api/v1/spatial/stream")
async def websocket_spatial_stream(websocket: WebSocket):
    await websocket.accept()
    from utils.spatial_tracker import SpatialTrackerThread
    SpatialTrackerThread._connections.add(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        SpatialTrackerThread._connections.discard(websocket)

@router.get("/api/v1/sensor-cache/frame")
async def sensor_cache_frame():
    """
    Returns the latest raw binary JPEG frame from the headless sensor daemon cache.
    Aligns with Spring Boot SensorCacheController proxy contract.
    """
    if _cache_lock.locked():
        frame_bytes = _sensor_cache.get("frame_bytes")
    else:
        async with _cache_lock:
            frame_bytes = _sensor_cache.get("frame_bytes")

    if not frame_bytes:
        return Response(status_code=404, content="No frame cached")
    
    return Response(content=frame_bytes, media_type="image/jpeg")

@router.post("/api/v1/sensors/vitals/push")
async def push_vitals(body: dict):
    """
    Lightweight endpoint for SensorFusionBuffer: push a vitals sample.
    (Spring Boot / wristband simulator can call this to feed the fusion buffer)
    Body: { heart_rate, spo2, systolic, diastolic, body_temperature, step_count, alert_level }
    """
    try:
        fusion_buf = get_fusion_buffer()
        sample = VitalsSample(
            heart_rate=body.get("heart_rate") or body.get("heartRate"),
            spo2=body.get("spo2"),
            systolic=body.get("systolic"),
            diastolic=body.get("diastolic"),
            body_temperature=body.get("body_temperature") or body.get("bodyTemperature"),
            step_count=body.get("step_count") or body.get("stepCount"),
            alert_level=body.get("alert_level", "NORMAL"),
        )
        await fusion_buf.push_vitals(sample)
        return {"status": "ok", "buffered_samples": (await fusion_buf.stats())["vitals_samples"]}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

@router.post("/api/v1/config/device-ip")
async def update_device_ip(body: dict):
    """
    Hot-reload device IP configuration for the camera daemon and PerceptionAgent.
    Called by frontend DeviceIpConfigModal on IP confirm — no daemon restart needed.
    Body: { "ip": str, "port": str (optional, default "8080") }
    """
    import time
    new_ip   = (body.get("ip") or body.get("phone_ip") or "").strip()
    new_port = (body.get("port") or body.get("camera_port") or "8080").strip()

    if not new_ip:
        return {"status": "error", "message": "ip field is required"}

    # Update global hot-reload config
    _device_config["phone_ip"]    = new_ip
    _device_config["camera_port"] = new_port
    _device_config["updated_at"]  = int(time.time() * 1000)

    # Also sync to environment for PerceptionAgent IP discovery
    os.environ["PHONE_IP"]    = new_ip
    os.environ["CAMERA_PORT"] = new_port

    # Write to Blackboard for PerceptionAgent to consume
    try:
        bb = get_blackboard()
        await bb.write_value("PHONE_IP", new_ip)
    except Exception as e:
        log.warning("[CONFIG] Blackboard write skipped: %s", e)

    log.info("[CONFIG] \U0001f4f1 Device IP hot-reloaded: %s:%s", new_ip, new_port)
    return {
        "status": "ok",
        "phone_ip": new_ip,
        "camera_port": new_port,
        "message": f"Camera daemon will use {new_ip}:{new_port} on next poll cycle"
    }

@router.get("/api/v1/sensor-cache/vision")
async def sensor_cache_vision():
    """
    Vision status endpoint — returns latest perception scan + camera daemon state.
    Designed for efficient frontend polling (combines perception + camera in one call).
    Poll interval recommendation: 5s (perception scans run at 15s intervals).
    """
    import time
    from datetime import datetime
    try:
        scan = await perception_agent.read_latest_scan()
        if scan and not scan.is_expired():
            async with _cache_lock:
                _sensor_cache["latest_perception_scan"] = scan.to_dict()
                _sensor_cache["latest_perception_ts"] = float(datetime.fromisoformat(scan.timestamp.replace('Z', '+00:00')).timestamp())
    except Exception as e:
        log.warning("[API_VISION] Failed to sync latest scan from Blackboard: %s", e)
    if _cache_lock and not _cache_lock.locked():
        async with _cache_lock:
            latest_scan    = _sensor_cache.get("latest_perception_scan")
            latest_scan_ts = _sensor_cache.get("latest_perception_ts")
            daemon_status  = _sensor_cache.get("daemon_status", "UNKNOWN")
            frame_ts       = _sensor_cache.get("frame_ts")
            frame_avail    = _sensor_cache.get("frame_bytes") is not None
    else:
        latest_scan    = _sensor_cache.get("latest_perception_scan")
        latest_scan_ts = _sensor_cache.get("latest_perception_ts")
        daemon_status  = _sensor_cache.get("daemon_status", "UNKNOWN")
        frame_ts       = _sensor_cache.get("frame_ts")
        frame_avail    = _sensor_cache.get("frame_bytes") is not None

    now = time.time()
    frame_age_s    = round(now - frame_ts,    1) if frame_ts else None
    scan_age_s     = round(now - latest_scan_ts, 1) if latest_scan_ts else None
    camera_fresh   = frame_age_s is not None and frame_age_s < 10.0

    return sanitize_nan({
        "status":          "ok",
        "daemon_status":   daemon_status,
        "camera_fresh":    camera_fresh,
        "frame_available": frame_avail,
        "frame_age_s":     frame_age_s,
        "frame_ts":        frame_ts,
        "phone_ip":        _device_config.get("phone_ip", ""),
        "camera_port":     _device_config.get("camera_port", "8080"),
        "latest_scan":     latest_scan,
        "scan_age_s":      scan_age_s,
    })

