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

        # MQTT client for inhibit signals
        broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self._mqtt = mqtt.Client(client_id="safety-agent-inhibit", protocol=mqtt.MQTTv311)
        mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
        mqtt_pass = os.getenv("MQTT_PASSWORD", "")
        if mqtt_user:
            self._mqtt.username_pw_set(mqtt_user, mqtt_pass)
        self._mqtt.connect_async(broker_host, broker_port, keepalive=30)
        self._mqtt.loop_start()

    async def run_loop(self):
        self._status = "ACTIVE"
        log.info("[SAFETY_AGENT] Tầng 0 ACTIVE — Subsumption armed")

        loop = asyncio.get_event_loop()
        mqtt_queue: asyncio.Queue = asyncio.Queue(maxsize=500)

        self._mqtt.on_message = lambda c, u, msg: loop.call_soon_threadsafe(
            mqtt_queue.put_nowait, (msg.topic, msg.payload.decode("utf-8", errors="replace"))
        )
        self._mqtt.subscribe([
            ("hk07/sensors/lidar/scan", 0),
            ("hk07/sensors/imu/state", 0),
            ("hk07/sensors/ambient_light", 0),
            ("hk07/sensors/wristband/+/vitals", 0),
        ])

        try:
            while True:
                try:
                    topic, payload = await asyncio.wait_for(mqtt_queue.get(), timeout=1.0)
                    await self._process_sensor(topic, payload)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
        finally:
            self._mqtt.loop_stop()

    async def _process_sensor(self, topic: str, payload: str):
        start_ns = time.perf_counter_ns()
        now = time.time()

        # Throttle logic
        parts = topic.split('/')
        sensor_type = parts[2] if len(parts) > 2 else "unknown"
        if sensor_type in self._last_processed:
            if now - self._last_processed[sensor_type] < 0.05:
                return
            self._last_processed[sensor_type] = now

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        danger = False
        trigger = SafetyTrigger.NONE
        msg = ""
        dist = 1.0
        accel = 1.0
        lux = 500.0

        if "lidar" in topic:
            ranges = data.get("ranges", [])
            if ranges:
                dist = min(r for r in ranges if r > 0.01)
                if dist < self.OBSTACLE_STOP_DISTANCE_M:
                    danger = True
                    trigger = SafetyTrigger.OBSTACLE
                    msg = f"Obstacle too close: {dist:.2f}m (threshold < {self.OBSTACLE_STOP_DISTANCE_M}m)"
        elif "imu" in topic:
            ax = data.get("accel_x", 0.0)
            ay = data.get("accel_y", 0.0)
            az = data.get("accel_z", 9.81)
            accel = (ax**2 + ay**2 + az**2) ** 0.5 / 9.81
            if accel > self.FALL_ACCEL_THRESHOLD:
                danger = True
                trigger = SafetyTrigger.FALL_RISK
                msg = f"Fall risk detected! Acceleration magnitude: {accel:.2f}g (threshold > {self.FALL_ACCEL_THRESHOLD}g)"
        elif "ambient_light" in topic:
            lux = data.get("lux", 100.0)
            if lux > self.LIGHT_GLARE_THRESHOLD:
                danger = True
                trigger = SafetyTrigger.LIGHT_GLARE
                msg = f"Blinding light glare detected! Ambient light: {lux:.1f} lux (threshold > {self.LIGHT_GLARE_THRESHOLD} lux)"
        elif "vitals" in topic:
            if data.get("emergency_button_pressed", False):
                danger = True
                trigger = SafetyTrigger.OWNER_EMERGENCY
                msg = "Emergency SOS button pressed by owner!"

        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

        if danger:
            inhibit_payload = json.dumps({
                "trigger": trigger.value,
                "distance_m": dist,
                "acceleration_g": accel,
                "lux": lux,
                "message": msg,
                "agent": "SAFETY",
                "timestamp_ms": int(time.time() * 1000)
            })
            # Publish QoS 2 for hard reliability
            self._mqtt.publish("hk07/control/subsumption/inhibit", inhibit_payload, qos=2)
            log.warning("[SAFETY_INHIBIT_SENT] Trigger: %s | Msg: %s | Latency: %.2fms", trigger.value, msg, elapsed_ms)

            # Run logging & reset logic in background so we don't block the sensor loop!
            async def run_bg_inhibit():
                try:
                    await log_agent_decision(
                        agent_type="SAFETY",
                        input_context=f"Sensor Topic: {topic}",
                        output_decision=msg,
                        llm_provider="DETERMINISTIC_MATH",
                        latency_ms=int(elapsed_ms)
                    )
                except Exception as ex:
                    log.error("[SAFETY_BG_LOG_ERROR] Exception: %s", ex)

                # Auto-reset subsumption after 3 seconds
                try:
                    self._subsumption_active = True
                    await asyncio.sleep(3.0)
                    self._subsumption_active = False
                    self._mqtt.publish("hk07/control/subsumption/inhibit", json.dumps({"trigger": "CLEAR", "agent": "SAFETY"}), qos=2)
                except Exception as ex:
                    log.error("[SAFETY_BG_RESET_ERROR] Exception: %s", ex)

            asyncio.create_task(run_bg_inhibit())

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
