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
        self._last_processed = {"lidar": 0.0, "imu": 0.0, "vitals": 0.0, "light": 0.0}
        self._freefall_start_time = None
        self._freefall_duration_exceeded = False
        self._freefall_ended_time = None

        # MQTT client for inhibit signals (resiliently wrapped)
        try:
            broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
            broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
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
                dist = 1.0
                accel = 1.0
                lux = 500.0

                # 1. LiDAR
                lidar = await fusion_buf.latest_lidar()
                if lidar:
                    dist = lidar.min_distance_m
                    if dist < self.OBSTACLE_STOP_DISTANCE_M:
                        danger = True
                        trigger = SafetyTrigger.OBSTACLE
                        msg = f"Obstacle too close: {dist:.2f}m (threshold < {self.OBSTACLE_STOP_DISTANCE_M}m)"

                # 2. IMU / Fall risk
                if not danger:
                    imu_data = await bb.read_value("sensor:imu:latest")
                    if imu_data:
                        ax = float(imu_data.get("accel_x", 0.0))
                        ay = float(imu_data.get("accel_y", 0.0))
                        az = float(imu_data.get("accel_z", 9.80665))
                        raw_magnitude = float((ax**2 + ay**2 + az**2) ** 0.5)
                        
                        # Convert to standard G-forces (resting at ~1.0g)
                        if raw_magnitude > 5.0:
                            normalized_g_force = float(raw_magnitude / 9.80665)
                        else:
                            normalized_g_force = float(raw_magnitude)
                            
                        accel = float(normalized_g_force)
                        
                        # Fall Detection State Machine
                        now = float(time.time())
                        if normalized_g_force < 0.3:
                            if self._freefall_start_time is None:
                                self._freefall_start_time = now
                            elif (now - self._freefall_start_time) > 0.15:
                                self._freefall_duration_exceeded = True
                        else:
                            if self._freefall_duration_exceeded:
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
                            log.info(f"[SAFETY_WORKER] Normalized G-force: {normalized_g_force:.2f}g - Status: CLEAR")

                # 3. Vitals Emergency button
                if not danger:
                    is_falling = await bb.read_value("sensor:vitals:is_falling") or False
                    emergency = await bb.read_value("sensor:vitals:emergency") or False
                    if emergency or is_falling:
                        danger = True
                        trigger = SafetyTrigger.OWNER_EMERGENCY
                        msg = "Emergency SOS or Fall reported by Wristband!"

                if danger and not self._subsumption_active:
                    elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                    log.warning("[SAFETY_INHIBIT_TRIGGERED] Trigger: %s | Msg: %s | Latency: %.2fms", trigger.value, msg, elapsed_ms)
                    
                    self._subsumption_active = True
                    await bb.write_value("safety:tripped", True)
                    await bb.write_value("safety:reason", msg)

                    # Trigger arbitration inhibit rules
                    self.arbitrator.inhibit("EMPATHETIC", duration_s=3)
                    self.arbitrator.inhibit("MEDICAL", duration_s=3)

                    # Try to publish inhibit signal via MQTT if available for external components
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

                    # Auto-reset subsumption after 3 seconds in background
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

                await asyncio.sleep(0.05)  # 20Hz loop check
        except asyncio.CancelledError:
            log.info("[SAFETY_AGENT] Shutdown")
        finally:
            if self._mqtt:
                try:
                    self._mqtt.loop_stop()
                except Exception:
                    pass

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
