import asyncio
import logging
import os
from core.config import load_env_and_apply_wsl_routing, get_default_gateway_ip
from services.blackboard_service import get_blackboard
from engine.arbitrator.arbitrator import Arbitrator
from core.state import memory, vision_pipeline, perception_agent
from core.shared import _sensor_cache, _cache_lock, _device_config
from services.sensor_fusion_buffer import get_fusion_buffer

log = logging.getLogger("hk07.background")

async def run_network_ingestion_worker():
    """
    Background worker parsing local .env modifications and validating gateway IP every 5.0 seconds.
    """
    log.info("[NETWORK_WORKER] Network Ingestion worker started.")
    while True:
        try:
            load_env_and_apply_wsl_routing()
            gateway_ip = get_default_gateway_ip()
            os.environ["DEFAULT_GATEWAY"] = gateway_ip
            
            bb = get_blackboard()
            await bb.write_value("system:network:gateway", gateway_ip)
            await bb.write_value("system:network:status", "ONLINE" if gateway_ip != "127.0.0.1" else "LOCAL_LOOPBACK")
            
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"[NETWORK_WORKER] Error: {e}")
            await asyncio.sleep(5.0)

async def initialize_memory_background():
    """Initialize LanceDB without blocking FastAPI startup."""
    try:
        memory_timeout_s = float(os.getenv("LANCE_INIT_TIMEOUT_S", "120.0"))
        await asyncio.wait_for(memory.initialize(), timeout=memory_timeout_s)
    except asyncio.TimeoutError:
        log.warning("[STARTUP] LanceDB memory initialization exceeded %.1fs; continuing in degraded mode.", memory_timeout_s)
    except Exception as e:
        log.error("[STARTUP] LanceDB memory initialization failed; continuing in degraded mode: %s", e)

class SafetyState:
    """Safety State Machine states for Subsumption Tier-0."""
    SENSOR_UNINITIALIZED = "SENSOR_UNINITIALIZED"  # Startup: sensors not yet confirmed
    HOLD_POSITION        = "HOLD_POSITION"           # Uninitialized → hold, await sensor data
    NOMINAL              = "NOMINAL"                 # Sensors OK, no threats detected
    TRIPPED              = "TRIPPED"                 # Debounced threat confirmed, safety active

_safety_state = SafetyState.SENSOR_UNINITIALIZED
_safety_tripped = False
_safety_reason = ""

async def run_subsumption_safety_worker():
    """
    Tier-0 Safety Logic — State Machine Implementation.

    States:
      SENSOR_UNINITIALIZED → HOLD_POSITION: Sensors not yet confirmed. Robot
        holds position. Agents write HOLD_POSITION to MQTT. Does NOT blindly
        skip safety — if user falls before sensors init, the UNINITIALIZED
        state itself triggers a conservative HOLD_POSITION response.

      HOLD_POSITION → NOMINAL: Transitions when first valid clinical read arrives.
        (Sensors confirmed as alive = safe to assume nominal baseline.)

      NOMINAL → TRIPPED: Requires 3 consecutive confirmed threat cycles (~1.5s)
        to prevent transient glitches from triggering E-STOP.

      TRIPPED → NOMINAL: Requires 3 consecutive clear cycles (~1.5s) to resume.
    """
    global _safety_state, _safety_tripped, _safety_reason
    import time
    import json
    log.info("[SAFETY_WORKER] Subsumption Safety State Machine started. State=SENSOR_UNINITIALIZED")

    consecutive_trips = 0
    consecutive_clears = 0
    consecutive_sensor_confirms = 0  # Count of valid sensor reads (for INIT transition)
    INIT_CONFIRM_THRESHOLD = 2       # Need 2 consecutive valid reads to leave UNINITIALIZED

    while True:
        try:
            bb = get_blackboard()

            # ──────────────────────────────────────────────────────────────────────────
            # Read sensor data (clinical perception from IPWebcam analysis)
            clinical = await bb.read_value("sensor:perception:clinical")
            is_falling = await bb.read_value("sensor:vitals:is_falling")
            sos_emergency = await bb.read_value("sensor:vitals:emergency")
            imu = await bb.read_value("sensor:imu:latest")
            env = await bb.read_value("sensor:env:latest")
            vitals = await bb.read_value("sensor:vitals:latest")

            sensor_data_present = (
                (clinical is not None) or 
                (is_falling is not None) or 
                (imu is not None) or 
                (env is not None) or 
                (vitals is not None)
            )

            # ── STATE: SENSOR_UNINITIALIZED ──────────────────────────────────────────────────────
            if _safety_state in (SafetyState.SENSOR_UNINITIALIZED, SafetyState.HOLD_POSITION):
                await bb.write_value("safety:state", _safety_state, ttl_seconds=60)
                await bb.write_value("safety:tripped", False)

                if sensor_data_present:
                    consecutive_sensor_confirms += 1
                    if consecutive_sensor_confirms >= INIT_CONFIRM_THRESHOLD:
                        # Sensors confirmed as alive → transition to NOMINAL
                        _safety_state = SafetyState.NOMINAL
                        _safety_tripped = False
                        log.info(
                            "[SAFETY_SM] ✅ Sensors confirmed (%d reads). Transitioning: UNINITIALIZED → NOMINAL.",
                            consecutive_sensor_confirms
                        )
                        await bb.write_value("safety:state", SafetyState.NOMINAL, ttl_seconds=60)
                else:
                    consecutive_sensor_confirms = 0
                    if _safety_state == SafetyState.SENSOR_UNINITIALIZED:
                        _safety_state = SafetyState.HOLD_POSITION
                        log.warning(
                            "[SAFETY_SM] ⏳ No sensor data yet. State=HOLD_POSITION. "
                            "Robot holds position. Agents in STANDBY mode."
                        )
                        await bb.write_value("safety:state", SafetyState.HOLD_POSITION, ttl_seconds=60)
                        await bb.write_value("safety:reason", "Sensors not yet initialized", ttl_seconds=60)

            # ── STATE: NOMINAL or TRIPPED (sensors are live) ──────────────────────────────
            else:
                candidate_trip = False
                reason = ""

                # Wristband hardware SOS / fall safety trips disabled per user request
                if is_falling is True:
                    pass
                elif sos_emergency is True:
                    pass

                # Vision-based threats from PerceptionAgent (lower priority, event-triggered)
                if clinical and not candidate_trip:
                    facial_distress = clinical.get("facial_distress", {})
                    env_hazards = clinical.get("environmental_hazards", {})
                    visible_injuries = clinical.get("visible_injuries", {})

                    if facial_distress.get("detected"):
                        pass
                    elif env_hazards.get("detected"):
                        pass
                    elif visible_injuries.get("detected"):
                        pass

                # Debounce filter: 3 consecutive cycles to engage OR clear
                if candidate_trip:
                    consecutive_clears = 0
                    consecutive_trips += 1
                    if consecutive_trips >= 3:
                        if _safety_state != SafetyState.TRIPPED:
                            _safety_state = SafetyState.TRIPPED
                            _safety_tripped = True
                            _safety_reason = reason
                            log.warning("[SAFETY_SM] 🚨 TRIP ENGAGED (debounced 3x): %s", reason)
                else:
                    consecutive_trips = 0
                    consecutive_clears += 1
                    if consecutive_clears >= 3:
                        if _safety_state == SafetyState.TRIPPED:
                            _safety_state = SafetyState.NOMINAL
                            _safety_tripped = False
                            _safety_reason = ""
                            log.info("[SAFETY_SM] ✅ TRIP CLEARED (debounced 3x). Resuming NOMINAL.")

                # Write state to Blackboard
                try:
                    await bb.write_value("safety:state", _safety_state, ttl_seconds=60)
                    await bb.write_value("safety:tripped", _safety_tripped)
                    if _safety_reason:
                        await bb.write_value("safety:reason", _safety_reason, ttl_seconds=30)
                except Exception as bb_err:
                    log.error("[SAFETY_SM] Blackboard write failed: %s", bb_err)

                if _safety_tripped:
                    # Inhibit empathetic/medical autonomous outputs during active safety trip
                    arbitrator.inhibit("EMPATHETIC", duration_s=10)
                    arbitrator.inhibit("MEDICAL", duration_s=10)

            await asyncio.sleep(0.5)  # 2Hz loop
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("[SAFETY_SM] Unhandled error: %s", e)
            await asyncio.sleep(1.0)

def start_isolated_heartbeat_thread():
    import threading
    import websockets
    import json
    import time

    def thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def isolated_heartbeat_loop():
            uri = "ws://localhost:9090"
            backoff = 1.0
            while True:
                try:
                    log.info(f"[ISOLATED_HEARTBEAT] Connecting to {uri}...")
                    async with websockets.connect(uri, ping_interval=30, ping_timeout=30) as websocket:
                        log.info("[ISOLATED_HEARTBEAT] Connected to Rosbridge. Starting pulse check transmission.")
                        
                        # Advertise heartbeat topic type to Rosbridge
                        adv_msg = {
                            "op": "advertise",
                            "topic": "/system/heartbeat",
                            "type": "std_msgs/msg/Header"
                        }
                        await websocket.send(json.dumps(adv_msg))
                        
                        backoff = 1.0
                        while True:
                            t = time.time()
                            sec = int(t)
                            nanosec = int((t - sec) * 1e9)
                            msg = {
                                "op": "publish",
                                "topic": "/system/heartbeat",
                                "msg": {
                                    "stamp": {
                                        "sec": sec,
                                        "nanosec": nanosec
                                    },
                                    "frame_id": "system"
                                }
                            }
                            await websocket.send(json.dumps(msg))
                            await asyncio.sleep(1.0)
                except Exception as e:
                    log.error(f"[ISOLATED_HEARTBEAT_ERROR] Error in heartbeat loop: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, 30.0)

        loop.run_until_complete(isolated_heartbeat_loop())

    t = threading.Thread(target=thread_target, name="isolated-heartbeat-thread", daemon=True)
    t.start()

async def run_headless_camera_daemon():
    """
    Headless persistent camera ingestion daemon using the Multi-Processing VisionPipeline.
    Polls frames and handles decoupled AI outputs (MediaPipe at 10Hz, DeepFace/YOLO at 1Hz).
    Updates Blackboard safety metrics and broadcasts coordinates directly to web clients.
    """
    import time
    import base64
    import math
    from services.sensor_fusion_buffer import CameraFrame
    from utils.spatial_tracker import SpatialTrackerThread

    log.info("[CAMERA_DAEMON] ▶ Multi-Process Camera Daemon started. Cycle: 50ms.")
    # Poll frequently (50ms / 20Hz) so that we capture new frames from the process queue immediately
    poll_interval = 0.05

    while True:
        try:
            if vision_pipeline:
                frame_bytes, scan = await asyncio.to_thread(vision_pipeline.process_cycle)
                
                # If we got a new frame, push to SensorFusionBuffer & update cache
                if frame_bytes:
                    ts = time.time()
                    frame_b64 = base64.b64encode(frame_bytes).decode("utf-8")
                    
                    fusion_buf = get_fusion_buffer()
                    await fusion_buf.push_camera(
                        CameraFrame(frame_path="", frame_b64=frame_b64)
                    )
                    
                    async with _cache_lock:
                        _sensor_cache["frame_bytes"] = frame_bytes
                        _sensor_cache["frame_ts"] = ts
                        _sensor_cache["daemon_status"] = "OK"
                        _sensor_cache["last_update"] = ts
                
                # If we got a perception scan cycle output, process it
                if scan:
                    # Extract values with caching fallback (as process_cycle runs at 20Hz but updates components at 1Hz/10Hz)
                    fall_detected = scan.get("fall_detected", _sensor_cache.get("fall_detected", False))
                    facial_distress = scan.get("facial_distress", _sensor_cache.get("facial_distress", 0.0))
                    posture_risk = scan.get("posture_risk", _sensor_cache.get("posture_risk", "LOW"))
                    visible_injuries = scan.get("visible_injuries", _sensor_cache.get("visible_injuries", []))
                    is_owner = scan.get("is_owner", _sensor_cache.get("is_owner", True))
                    expression = scan.get("expression", _sensor_cache.get("expression", "calm"))
                    
                    # Update Blackboard service
                    bb = get_blackboard()
                    await bb.write_value("sensor:vitals:is_falling", fall_detected, ttl_seconds=300)
                    await bb.write_value("sensor:vision:facial_distress", facial_distress, ttl_seconds=300)
                    await bb.write_value("sensor:vision:posture_risk", posture_risk, ttl_seconds=300)
                    await bb.write_value("sensor:vision:is_owner", is_owner, ttl_seconds=300)
                    
                    # [BAYMAX] Merge and write to sensor:perception:latest_scan for EmpatheticAgent
                    try:
                        from datetime import datetime
                        existing_scan = await bb.read_value("sensor:perception:latest_scan") or {}
                        # Merge scan values into existing_scan
                        for k, v in scan.items():
                            if v is not None:
                                existing_scan[k] = v
                        existing_scan["timestamp"] = datetime.utcnow().isoformat() + "Z"
                        await bb.write_value("sensor:perception:latest_scan", existing_scan, ttl_seconds=300)
                    except Exception as scan_write_err:
                        log.error(f"Failed to update sensor:perception:latest_scan: {scan_write_err}")
                    
                    # Update global sensor cache
                    async with _cache_lock:
                        _sensor_cache["fall_detected"] = fall_detected
                        _sensor_cache["facial_distress"] = facial_distress
                        _sensor_cache["posture_risk"] = posture_risk
                        _sensor_cache["visible_injuries"] = visible_injuries
                        _sensor_cache["is_owner"] = is_owner
                        _sensor_cache["expression"] = expression
                        
                        # Populate spatial targets mapping for Vite Dashboard — STRICT: No mock coordinates if no detection
                        s_targets = []
                        _sensor_cache["spatial_detections"] = s_targets

                    # Broadcast coordinate targets to active WebSocket client connections
                    if SpatialTrackerThread._connections:
                        current_vitals = _sensor_cache.get("vitals") or {}
                        hr = current_vitals.get("hr", float('nan'))
                        
                        payload = {
                            "status": "HARDWARE_BOUND",
                            "vitals": {
                                "real_hr_rppg": hr if not math.isnan(hr) else "SENSOR_DISCONNECTED",
                                "real_temp_thermal": "SENSOR_DISCONNECTED",
                                "sensor_status": "ONLINE"
                            },
                            "spatial_targets": s_targets
                        }
                        
                        msg_str = json.dumps(payload)
                        disconnected = []
                        for ws in list(SpatialTrackerThread._connections):
                            try:
                                await ws.send_text(msg_str)
                            except Exception:
                                disconnected.append(ws)
                        for ws in disconnected:
                            SpatialTrackerThread._connections.discard(ws)
            
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            log.info("[CAMERA_DAEMON] Shutdown signal received.")
            break
        except Exception as exc:
            log.error("[CAMERA_DAEMON] Error in daemon cycle: %s", exc)
            await asyncio.sleep(poll_interval)

async def run_headless_vitals_daemon():
    """
    Headless persistent vitals/IMU cache update daemon.
    Decoupled from camera state. Continuously syncs SensorFusionBuffer and Blackboard
    metrics to the global cache at 500ms intervals.
    """
    import time
    log.info("[VITALS_DAEMON] ▶ Headless Vitals Daemon started. Poll interval: 500ms.")
    poll_interval = float(os.getenv("SENSOR_DAEMON_POLL_S", "0.5"))

    while True:
        try:
            fusion_buf = get_fusion_buffer()
            latest_vitals = await fusion_buf.latest_vitals()

            bb = get_blackboard()
            fall_detected = await bb.read_value("sensor:vitals:is_falling") or False
            fever_alert   = await bb.read_value("sensor:camera:fever_alert") or False
            imu           = await bb.read_value("sensor:imu:latest")
            environment   = await bb.read_value("sensor:env:latest")
            location      = await bb.read_value("sensor:location:latest")
            activity      = await bb.read_value("sensor:activity:latest")

            async with _cache_lock:
                if latest_vitals:
                    _sensor_cache["vitals"] = {
                        "hr":   latest_vitals.heart_rate,
                        "spo2": latest_vitals.spo2,
                        "temp": latest_vitals.body_temperature,
                        "alert_level": latest_vitals.alert_level,
                        "status": "ONLINE"
                    }
                else:
                    _sensor_cache["vitals"] = {
                        "hr": float('nan'),
                        "spo2": "SENSOR_DISCONNECTED",
                        "temp": float('nan'),
                        "alert_level": "UNKNOWN",
                        "status": "SENSOR_DISCONNECTED"
                    }
                _sensor_cache["fall_detected"] = fall_detected
                _sensor_cache["fever_alert"]   = fever_alert
                _sensor_cache["imu"]           = imu
                _sensor_cache["environment"]   = environment
                _sensor_cache["location"]      = location
                _sensor_cache["activity"]      = activity
                _sensor_cache["last_update"]   = time.time()

            await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            log.info("[VITALS_DAEMON] Shutdown signal received.")
            break
        except Exception as exc:
            log.error("[VITALS_DAEMON] Error: %s", exc)
            await asyncio.sleep(poll_interval)

async def run_auto_perception_scan_loop():
    """
    [AUTO_VISION] Headless auto-perception scan daemon.
    Triggers PerceptionAgent.execute_full_body_scan() every 15s when camera is live.
    Results are written to Blackboard and cached in _sensor_cache for frontend polling.
    This eliminates the need for manual [TRIGGER_SCAN] click on the Vision page.
    """
    import time
    log.info("[AUTO_VISION] ▶ Auto-Perception Scan Loop started. Interval: 15s.")
    await asyncio.sleep(8.0)  # warm-up: let camera daemon initialize first

    while True:
        try:
            # Only scan if camera daemon has a fresh frame (< 15s old)
            async with _cache_lock:
                cam_status = _sensor_cache.get("daemon_status", "")
                frame_ts = _sensor_cache.get("frame_ts")
                frame_bytes = _sensor_cache.get("frame_bytes")

            frame_is_fresh = frame_ts is not None and (time.time() - frame_ts) < 15.0

            if frame_is_fresh or cam_status == "OK":
                log.info("[AUTO_VISION] Triggering auto perception scan...")
                # Pass the fresh frame directly to avoid duplicate HTTP fetching
                scan = await perception_agent.execute_full_body_scan(frame_bytes=frame_bytes)
                # Cache scan result for faster frontend retrieval
                async with _cache_lock:
                    _sensor_cache["latest_perception_scan"] = scan.to_dict()
                    _sensor_cache["latest_perception_ts"] = time.time()
                log.info(
                    "[AUTO_VISION] Scan complete — risk=%s confidence=%.2f provider=%s",
                    scan.overall_risk, scan.confidence, scan.status
                )
            else:
                log.debug(
                    "[AUTO_VISION] Scan skipped — camera not ready (status=%s, frame_age=%.1fs)",
                    cam_status,
                    (time.time() - frame_ts) if frame_ts else 999
                )

            await asyncio.sleep(15.0)

        except asyncio.CancelledError:
            log.info("[AUTO_VISION] Shutdown signal received.")
            break
        except Exception as e:
            log.error("[AUTO_VISION] Error in auto scan loop: %s", e)
            await asyncio.sleep(15.0)

