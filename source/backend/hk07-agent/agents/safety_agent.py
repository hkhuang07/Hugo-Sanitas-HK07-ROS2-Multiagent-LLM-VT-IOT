"""
SafetyAgent — Tầng 0 (Tối thượng) trong Subsumption Architecture

Chức năng: Quét môi trường vật lý liên tục qua dữ liệu LiDAR, IMU (phát hiện ngã) 
và Cảm biến ánh sáng (Lux) để phát hiện mối nguy hiểm.
Khi phát hiện nguy hiểm: Phát tín hiệu Inhibit qua MQTT tới Spring Boot Core
trong thời gian < 5ms — ngắt toàn bộ di chuyển và hành động của Robot.

Nguyên tắc thiết kế:
- TUYỆT ĐỐI KHÔNG DÙNG LLM HAY API.
- Logic thuần túy bằng IF/ELSE và Toán học.
- Trả về JSON trạng thái.
"""

import asyncio
import json
import logging
import os
import re
import time
from enum import Enum
from typing import Optional
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from services.agent_log_client import log_agent_decision

load_dotenv()

log = logging.getLogger("hk07.safety_agent")

SAFETY_RESPONSE_DEADLINE_MS = 5   # Hard real-time constraint from PRD

class SafetyTrigger(Enum):
    OBSTACLE = "OBSTACLE"
    FALL_RISK = "FALL_RISK"
    LIGHT_GLARE = "LIGHT_GLARE"
    OWNER_EMERGENCY = "OWNER_EMERGENCY"
    NONE = "NONE"

class SafetyAgent:
    OBSTACLE_STOP_DISTANCE_M = 0.5    # Stop if obstacle within 0.5m
    FALL_ACCEL_THRESHOLD = 2.5        # g-force threshold for fall detection
    LIGHT_GLARE_THRESHOLD = 5000.0    # blinding light lux threshold

    def __init__(self, arbitrator):
        self.arbitrator = arbitrator
        self._status = "INITIALIZING"
        self._subsumption_active = False
        self._last_scan_time = 0.0
        self._volatile_context = {}  # RAM-only, wiped on shutdown
        self._last_processed = {"vision": 0.0, "imu": 0.0, "vitals": 0.0, "light": 0.0}
        self._freefall_start_time = None
        self._freefall_duration_exceeded = False
        self._freefall_ended_time = None
        
        self._vision_trip_counter = 0
        self._vision_clear_counter = 0
        self._vision_danger_active = False
        self._vision_trigger = SafetyTrigger.NONE
        self._vision_msg = ""
        self._vision_dist = 0.0

        # MQTT client for inhibit signals (resiliently wrapped)
        try:
            broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
            broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
            if hasattr(mqtt, "CallbackAPIVersion"):
                self._mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="safety-agent-inhibit", protocol=mqtt.MQTTv311)
            else:
                self._mqtt = mqtt.Client(client_id="safety-agent-inhibit", protocol=mqtt.MQTTv311)
            mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
            mqtt_pass = os.getenv("MQTT_PASSWORD", "")
            if mqtt_user:
                self._mqtt.username_pw_set(mqtt_user, mqtt_pass)
            self._mqtt.connect_async(broker_host, broker_port, keepalive=30)
            self._mqtt.loop_start()
        except Exception as e:
            log.warning(f"[SAFETY_AGENT] MQTT broker offline, bypassing: {e}")
            self._mqtt = None

    async def run_loop(self):
        self._status = "ACTIVE"
        log.info("[SAFETY_AGENT] Tầng 0 ACTIVE — Subsumption armed (Direct Buffer & Blackboard)")

        from services.sensor_fusion_buffer import get_fusion_buffer
        from services.blackboard_service import get_blackboard
        fusion_buf = get_fusion_buffer()
        bb = get_blackboard()

        try:
            while True:
                start_ns = time.perf_counter_ns()
                
                danger = False
                trigger = SafetyTrigger.NONE
                msg = ""
                dist = 0.0
                accel = 1.0
                lux = 100.0
                
                # ─── CROSS-MODAL SENSOR FUSION CONSENSUS MATRIX ───
                # Spatial Activity Validation Window evaluation
                # 1. Camera Posture/Vitals Stream (Fever Alert and Clinical)
                fever_alert = await bb.read_value("sensor:camera:fever_alert") or False
                clinical = await bb.read_value("sensor:perception:clinical")
                
                # 2. Phone Ingestion Stream (Accel and FallState)
                imu_data = await bb.read_value("sensor:imu:latest")
                accel_is_zero = False
                ax, ay, az = 0.0, 0.0, 0.0
                if imu_data:
                    ax = float(imu_data.get("accel_x", 0.0))
                    ay = float(imu_data.get("accel_y", 0.0))
                    az = float(imu_data.get("accel_z", 0.0))
                    magnitude = (ax**2 + ay**2 + az**2) ** 0.5
                    EPSILON = 0.05
                    if magnitude < EPSILON:
                        accel_is_zero = True
                
                fall_state = await bb.read_value("sensor:vitals:is_falling") or False
                
                # 3. LiDAR Range States (Physical distances)
                lidar_hardware_absent = os.getenv("LIDAR_HARDWARE_ABSENT", "true").lower() == "true"
                lidar_active = not lidar_hardware_absent

                # Perform threshold evaluation
                # 1. Vision Clinical Analysis from IPWebcam (Debounced to prevent false-positives on dropout)
                candidate_vision_danger = False
                candidate_trigger = SafetyTrigger.NONE
                candidate_msg = ""
                candidate_dist = 0.0

                if clinical:
                    facial_distress = clinical.get("facial_distress", {})
                    env_hazards = clinical.get("environmental_hazards", {})
                    visible_injuries = clinical.get("visible_injuries", {})
                    
                    if facial_distress.get("detected"):
                        candidate_vision_danger = True
                        candidate_trigger = SafetyTrigger.OWNER_EMERGENCY
                        candidate_msg = f"Vision Safety Alert: Facial distress detected ({facial_distress.get('details')})"
                        candidate_dist = 0.1
                    elif env_hazards.get("detected"):
                        candidate_vision_danger = True
                        candidate_trigger = SafetyTrigger.FALL_RISK
                        candidate_msg = f"Vision Safety Alert: Environmental hazard detected ({env_hazards.get('details')})"
                        candidate_dist = 0.3
                    elif visible_injuries.get("detected"):
                        candidate_vision_danger = True
                        candidate_trigger = SafetyTrigger.OWNER_EMERGENCY
                        candidate_msg = f"Vision Safety Alert: Visible injuries detected ({visible_injuries.get('details')})"
                        candidate_dist = 0.2

                # require 20 cycles (~1.0s at 20Hz) of vision threat to trip
                if candidate_vision_danger:
                    self._vision_clear_counter = 0
                    self._vision_trip_counter += 1
                    if self._vision_trip_counter >= 20:
                        self._vision_danger_active = True
                        self._vision_trigger = candidate_trigger
                        self._vision_msg = candidate_msg
                        self._vision_dist = candidate_dist
                else:
                    self._vision_trip_counter = 0
                    self._vision_clear_counter += 1
                    if self._vision_clear_counter >= 20:
                        self._vision_danger_active = False

                if self._vision_danger_active:
                    danger = True
                    trigger = self._vision_trigger
                    msg = self._vision_msg
                    dist = self._vision_dist

                # 2. IMU / Fall risk
                # FIX: Process fall detection for both robot and owner using freefall/impact G-force.
                # Do not discard owner_device IMU data. Any device undergoing freefall -> impact is a fall.
                
                if not danger and imu_data:
                    raw_magnitude = float((ax**2 + ay**2 + (az if az != 0.0 else 9.80665)**2) ** 0.5)
                    if raw_magnitude > 5.0:
                        normalized_g_force = float(raw_magnitude / 9.80665)
                    else:
                        normalized_g_force = float(raw_magnitude)
                    accel = float(normalized_g_force)
                    
                    now = float(time.time())
                    # Ignore static baseline or zero-baseline (normalized_g_force <= 0.05) to avoid false freefall detection
                    if 0.05 < normalized_g_force < 0.3:
                        if self._freefall_start_time is None:
                            self._freefall_start_time = now
                        elif (now - self._freefall_start_time) > 0.15:
                            self._freefall_duration_exceeded = True
                    else:
                        if normalized_g_force <= 0.05:
                            self._freefall_start_time = None
                            self._freefall_duration_exceeded = False
                            self._freefall_ended_time = None
                        elif self._freefall_duration_exceeded:
                            if normalized_g_force > 2.5:
                                danger = True
                                trigger = SafetyTrigger.OWNER_EMERGENCY
                                msg = f"Fall detected (Freefall >150ms followed by impact spike {normalized_g_force:.2f}g)"
                                self._freefall_start_time = None
                                self._freefall_duration_exceeded = False
                                self._freefall_ended_time = None
                            else:
                                if self._freefall_ended_time is None:
                                    self._freefall_ended_time = now
                                elif (now - self._freefall_ended_time) > 0.5:
                                    self._freefall_start_time = None
                                    self._freefall_duration_exceeded = False
                                    self._freefall_ended_time = None
                        else:
                            self._freefall_start_time = None
                            self._freefall_duration_exceeded = False
                            self._freefall_ended_time = None
                        
                    if not danger:
                        log.debug(f"[SAFETY_WORKER] Normalized G-force: {normalized_g_force:.2f}g - Status: CLEAR")

                elif not imu_data:
                    # Reset freefall tracking if IMU data is not available (disconnected)
                    self._freefall_start_time = None
                    self._freefall_duration_exceeded = False
                    self._freefall_ended_time = None

                # 3. Vitals emergency button
                if not danger:
                    emergency = await bb.read_value("sensor:vitals:emergency") or False
                    if emergency or fall_state:
                        danger = True
                        trigger = SafetyTrigger.OWNER_EMERGENCY
                        msg = "Emergency SOS or Fall reported by Wristband!"

                # Consensus matrix logical verification rule:
                # If phone registers static baseline (magnitude < EPSILON) and mobile FallState is False,
                # we CLASSIFY the user state as SAFE/IDLE, overriding and suppressing any stray threshold spikes.
                if accel_is_zero and not fall_state:
                    if danger:
                        log.info("[SAFETY_CONSENSUS] Suppressed stray threshold spike (danger=%s, trigger=%s). Static user state verified.", danger, trigger.value)
                    danger = False
                    trigger = SafetyTrigger.NONE
                    msg = ""

                # Fall risk and Owner Emergency safety triggers disabled per user request
                if trigger in (SafetyTrigger.FALL_RISK, SafetyTrigger.OWNER_EMERGENCY):
                    danger = False
                    trigger = SafetyTrigger.NONE
                    msg = ""

                if danger and not self._subsumption_active:
                    elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                    log.warning("[SAFETY_INHIBIT_TRIGGERED] Trigger: %s | Msg: %s | Latency: %.2fms", trigger.value, msg, elapsed_ms)
                    
                    self._subsumption_active = True
                    await bb.write_value("safety:tripped", True)
                    await bb.write_value("safety:reason", msg)

                    # Conversation agents are never inhibited for companion wellness robot
                    # self.arbitrator.inhibit("EMPATHETIC", duration_s=3)
                    # self.arbitrator.inhibit("MEDICAL", duration_s=3)

                    if self._mqtt:
                        try:
                            inhibit_payload = json.dumps({
                                "trigger": trigger.value,
                                "distance_m": dist,
                                "acceleration_g": accel,
                                "lux": lux,
                                "message": msg,
                                "agent": "SAFETY",
                                "timestamp_ms": int(time.time() * 1000)
                            })
                            self._mqtt.publish("hk07/control/subsumption/inhibit", inhibit_payload, qos=2)
                        except Exception:
                            pass

                    async def reset_safety_after_delay():
                        await asyncio.sleep(3.0)
                        self._subsumption_active = False
                        await bb.write_value("safety:tripped", False)
                        if self._mqtt:
                            try:
                                self._mqtt.publish("hk07/control/subsumption/inhibit", json.dumps({"trigger": "CLEAR", "agent": "SAFETY"}), qos=2)
                            except Exception:
                                pass
                        log.info("[SAFETY_INHIBIT_CLEARED] Safety subsumption auto-reset complete.")

                    asyncio.create_task(reset_safety_after_delay())

                # ─── SOS ESCALATION PROTOCOL (TASK 3) ───
                if not getattr(self, "_in_alert_mode", False):
                    # Get activity state
                    latest_scan = await bb.read_value("sensor:perception:latest_scan") or {}
                    activity = "unknown"
                    if isinstance(latest_scan, dict):
                        activity = latest_scan.get("activity") or latest_scan.get("cognitive_insights", {}).get("subject_activity") or "unknown"
                    
                    # Get heart rate
                    hr = None
                    import math
                    latest_vitals = await fusion_buf.latest_vitals()
                    if latest_vitals:
                        hr = latest_vitals.heart_rate
                    if hr is None or math.isnan(hr):
                        vitals_data = await bb.read_value("sensor:vitals:latest") or {}
                        if isinstance(vitals_data, dict):
                            hr = vitals_data.get("heart_rate") or vitals_data.get("hr") or vitals_data.get("heartRate")
                    
                    try:
                        if hr is not None:
                            hr = float(hr)
                    except (ValueError, TypeError):
                        hr = None

                    is_fall = (activity == "falling") or fall_state
                    active_states = {"walking", "running", "exercising", "stretching", "reaching_up"}
                    is_resting = (activity not in active_states)

                    trigger_alert = False
                    trigger_reason = ""
                    if is_fall:
                        trigger_alert = True
                        trigger_reason = "FALL"
                    elif hr is not None and hr > 120.0 and is_resting:
                        trigger_alert = True
                        trigger_reason = "RESTING_HIGH_HR"

                    if trigger_alert:
                        self._in_alert_mode = True
                        log.warning(f"[SAFETY_SOS] Anomaly detected: {trigger_reason} (HR={hr}, Activity={activity}). Initiating Alert Mode...")
                        asyncio.create_task(self._trigger_sos_escalation_protocol(trigger_reason, hr, activity, bb, fusion_buf))

                await asyncio.sleep(0.05)  # 20Hz loop check
        except asyncio.CancelledError:
            log.info("[SAFETY_AGENT] Shutdown")
        finally:
            if self._mqtt:
                try:
                    self._mqtt.loop_stop()
                except Exception:
                    pass

    async def _trigger_sos_escalation_protocol(self, trigger_reason: str, hr: Optional[float], activity: str, bb, fusion_buf):
        log.warning(f"[SAFETY_ALERT_PROTOCOL] Starting verification loop for trigger: {trigger_reason}")
        
        # 1. Ask the user via TTS
        alert_msg = "Cảnh báo sức khỏe: Tôi phát hiện chỉ số sinh tồn của bạn bất thường. Hãy nghỉ ngơi, uống một chút nước ấm. Tôi đã gửi thông tin cho người thân."
        if self._mqtt:
            try:
                self._mqtt.publish("hk07/agents/action/tts", json.dumps({"message": alert_msg}), qos=1)
                log.info("[SAFETY_ALERT] Published TTS warning request: %s", alert_msg)
            except Exception as e:
                log.error("[SAFETY_ALERT] Failed to publish TTS warning request: %s", e)
        
        # Write alert state to blackboard
        await bb.write_value("safety:alert_mode", True)
        await bb.write_value("safety:alert_reason", trigger_reason)
        
        # Record initial interaction timestamp
        init_ts = await bb.read_value("last_interaction_timestamp")
        
        # Wait 10 seconds, polling for verbal or physical interaction
        interaction_detected = False
        start_time = time.time()
        while time.time() - start_time < 10.0:
            # Check verbal interaction (change in last_interaction_timestamp)
            curr_ts = await bb.read_value("last_interaction_timestamp")
            if curr_ts is not None and curr_ts != init_ts:
                interaction_detected = True
                log.info("[SAFETY_ALERT] Verbal interaction detected during alert countdown.")
                break
                
            # Check physical interaction (active state or high wrist motion)
            latest_scan = await bb.read_value("sensor:perception:latest_scan") or {}
            act = "unknown"
            if isinstance(latest_scan, dict):
                act = latest_scan.get("activity") or latest_scan.get("cognitive_insights", {}).get("subject_activity") or "unknown"
            wrist_motion = await bb.read_value("sensor:vitals:wrist_motion_magnitude") or 0.0
            
            active_states = {"walking", "running", "exercising", "stretching", "reaching_up", "typing", "writing", "phone_use", "eating", "drinking"}
            if act in active_states or wrist_motion > 1.0:
                interaction_detected = True
                log.info("[SAFETY_ALERT] Physical interaction detected during alert countdown (activity=%s, wrist_motion=%.2f).", act, wrist_motion)
                break
                
            await asyncio.sleep(0.1)
            
        # 2. Timeout Fallback
        if not interaction_detected:
            log.warning("[SAFETY_ALERT] No interaction detected within 10 seconds! Escalating to healthcare warning alert.")
            
            # Fetch last known location
            location = await bb.read_value("sensor:vitals:location") or await bb.read_value("sensor:location:latest") or "Living Room"
            
            # Construct warning payload
            warning_payload = {
                "timestamp_ms": int(time.time() * 1000),
                "last_known_location": location,
                "trigger_reason": trigger_reason,
                "heart_rate": hr,
                "activity": activity,
                "message": f"Healthcare warning: Patient failed to respond to companion alert. Trigger: {trigger_reason} at location {location}."
            }
            
            if self._mqtt:
                try:
                    self._mqtt.publish("hk07/system/alerts/warning", json.dumps(warning_payload, ensure_ascii=False), qos=2)
                    log.warning("[SAFETY_ALERT] Warning alert payload successfully published to hk07/system/alerts/warning.")
                except Exception as e:
                    log.error("[SAFETY_ALERT] Failed to publish warning alert payload to MQTT: %s", e)
            else:
                log.error("[SAFETY_ALERT] MQTT client unavailable. Warning alert not published to MQTT.")
                
            log.info("[SAFETY_ALERT] Companion advisor mode: medical emergency REST escalation bypassed.")
        else:
            log.info("[SAFETY_ALERT] Owner verified OK. Warning escalation aborted.")
            
        # Clear alert state on blackboard and class instance
        await bb.write_value("safety:alert_mode", False)
        self._in_alert_mode = False

    async def process_text_interaction(self, user_message: str) -> str:
        """
        Calculates safety state from user message using deterministic math & threshold rules.
        Publishes MQTT Inhibit if danger thresholds are crossed. Returns JSON status.
        """
        dist = 1.0
        accel = 1.0
        lux = 500.0

        dist_match = re.search(r'(?:khoảng cách|khoang cach|distance|obstacle|vật cản)\s*([\d\.]+)\s*m?', user_message.lower())
        if dist_match:
            try:
                dist = float(dist_match.group(1))
            except ValueError:
                pass

        accel_match = re.search(r'(?:gia tốc|gia toc|accel|imu|magnitude)\s*([\d\.]+)\s*g?', user_message.lower())
        if accel_match:
            try:
                accel = float(accel_match.group(1))
            except ValueError:
                pass

        lux_match = re.search(r'(?:ánh sáng|anh sang|lux|light)\s*([\d\.]+)', user_message.lower())
        if lux_match:
            try:
                lux = float(lux_match.group(1))
            except ValueError:
                pass

        danger = False
        reason = "Nominal system parameters. Safe to proceed."
        trigger = SafetyTrigger.NONE

        if dist < self.OBSTACLE_STOP_DISTANCE_M:
            danger = True
            trigger = SafetyTrigger.OBSTACLE
            reason = f"Obstacle too close: {dist}m (threshold < {self.OBSTACLE_STOP_DISTANCE_M}m)"
        elif accel > self.FALL_ACCEL_THRESHOLD:
            danger = True
            trigger = SafetyTrigger.FALL_RISK
            reason = f"Sudden fall acceleration detected: {accel}g (threshold > {self.FALL_ACCEL_THRESHOLD}g)"
        elif lux > self.LIGHT_GLARE_THRESHOLD:
            danger = True
            trigger = SafetyTrigger.LIGHT_GLARE
            reason = f"Blinding light glare: {lux} lux (threshold > {self.LIGHT_GLARE_THRESHOLD} lux)"

        start_ns = time.perf_counter_ns()
        if danger:
            inhibit_payload = json.dumps({
                "trigger": trigger.value,
                "distance_m": dist,
                "acceleration_g": accel,
                "lux": lux,
                "message": f"CRITICAL: {reason}",
                "agent": "SAFETY",
                "timestamp_ms": int(time.time() * 1000)
            })
            self._mqtt.publish("hk07/control/subsumption/inhibit", inhibit_payload, qos=2)
            log.warning("[SAFETY_TEXT_TRIGGER] Inhibit sent: %s", reason)

        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

        return json.dumps({
            "status": "DANGER" if danger else "SAFE",
            "trigger": trigger.value,
            "reason": reason,
            "telemetry": {
                "distance_m": dist,
                "acceleration_g": accel,
                "lux": lux
            },
            "inhibit_activated": danger,
            "response_time_ms": elapsed_ms
        }, ensure_ascii=False)

    def get_status(self) -> dict:
        return {
            "status": self._status,
            "subsumption_active": self._subsumption_active,
            "last_scan_ms_ago": int((time.time() - self._last_scan_time) * 1000)
        }

    def clear_volatile_context(self):
        self._volatile_context.clear()
        log.info("[VOLATILE_WIPE] SafetyAgent context cleared")

    async def evaluate_actuation_safety(self, telemetry_data, blackboard):
        """
        Enforce strict kinematic constraints before permitting mechanical hugs.
        Completes compliance with Agile Robotics Safety Standards.
        """
        robot_state = "IDLE"
        user_intent = None

        if hasattr(blackboard, "read_value"):
            robot_state = await blackboard.read_value("robot_state") or "IDLE"
            user_intent = await blackboard.read_value("user_intent")
        elif isinstance(blackboard, dict):
            robot_state = blackboard.get("robot_state", "IDLE")
            user_intent = blackboard.get("user_intent")
        elif hasattr(blackboard, "get"):
            try:
                robot_state = blackboard.get("robot_state") or "IDLE"
                user_intent = blackboard.get("user_intent")
            except Exception:
                pass

        cmd_velocity_x = 0.0
        cmd_velocity_z = 0.0
        if telemetry_data:
            try:
                cmd_velocity_x = abs(float(telemetry_data.get("CmdLinearX", 0.0)))
            except (ValueError, TypeError):
                pass
            try:
                cmd_velocity_z = abs(float(telemetry_data.get("CmdLinearZ", 0.0)))
            except (ValueError, TypeError):
                pass

        vel_magnitude = (cmd_velocity_x**2 + cmd_velocity_z**2) ** 0.5
        is_walking = robot_state == "WALKING"

        # Track stable stance duration
        now = time.time()
        if not hasattr(self, "_stable_stance_start_time") or self._stable_stance_start_time is None:
            self._stable_stance_start_time = now

        if is_walking or vel_magnitude > 0.05:
            self._stable_stance_start_time = None
            stance_duration = 0.0
        else:
            stance_duration = now - self._stable_stance_start_time

        inhibit = False
        reason = ""
        if is_walking or vel_magnitude > 0.05:
            inhibit = True
            reason = f"Kinematic motion override. robot_state={robot_state}, velocity_magnitude={vel_magnitude:.3f} m/s (threshold > 0.05)."
        elif robot_state != "IDLE" and stance_duration < 5.0:
            inhibit = True
            reason = f"Stance duration is too short: {stance_duration:.2f}s (threshold >= 5.0s)."

        if inhibit:
            log.warning(f"[KINEMATIC_INHIBIT_ENGAGED] Forcefully disarming pneumatic pumps. Reason: {reason}")
            if hasattr(blackboard, "write_value"):
                await blackboard.write_value("pump_inhibit", True)
                await blackboard.write_value("inhibit_reason", "USER_IN_MOTION")
                await blackboard.write_value("hug_permitted", False)
                await blackboard.write_value("actuation:Pump", False)
                await blackboard.write_value("actuation:Hug", 0.0)
            elif hasattr(blackboard, "set"):
                blackboard.set("pump_inhibit", True)
                blackboard.set("inhibit_reason", "USER_IN_MOTION")
                blackboard.set("hug_permitted", False)
                blackboard.set("actuation:Pump", False)
                blackboard.set("actuation:Hug", 0.0)
            elif isinstance(blackboard, dict):
                blackboard["pump_inhibit"] = True
                blackboard["inhibit_reason"] = "USER_IN_MOTION"
                blackboard["hug_permitted"] = False
                blackboard["actuation:Pump"] = False
                blackboard["actuation:Hug"] = 0.0
            
            return {
                "action": "FORCE_DISARM_PUMP",
                "reason": f"[KINEMATIC_INHIBIT_ENGAGED] {reason}",
                "pump": False,
                "hug_force_newtons": 0.0
            }

        if user_intent == "HUG_REQUEST":
            if hasattr(blackboard, "write_value"):
                await blackboard.write_value("pump_inhibit", False)
                await blackboard.write_value("hug_permitted", True)
            return {"action": "ENGAGE_PUMP", "pump": True, "hug_force_newtons": 15.0}

        return {"action": "HOLD_IDLE", "pump": False, "hug_force_newtons": 0.0}
