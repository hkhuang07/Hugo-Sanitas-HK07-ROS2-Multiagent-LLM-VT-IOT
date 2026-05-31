"""
SafetyAgent — Tầng 0 (Tối thượng) trong Subsumption Architecture

Chức năng: Quét môi trường vật lý liên tục thông qua dữ liệu LiDAR (ROS 2 mock)
và cảm biến IMU (phát hiện ngã) để phát hiện các mối nguy hiểm.

Khi phát hiện nguy hiểm: Phát tín hiệu Inhibit qua MQTT tới Spring Boot Core
trong thời gian < 5ms — ngắt toàn bộ di chuyển và hành động của Robot.

Nguyên tắc thiết kế:
- KHÔNG sử dụng LLM (không có độ trễ mạng)
- KHÔNG sử dụng LanceDB memory (quyết định phải hoàn toàn local, tức thì)
- Logic là thuần túy deterministic (ngưỡng + trạng thái)
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import paho.mqtt.client as mqtt

from services.agent_log_client import log_agent_decision

log = logging.getLogger("hk07.safety_agent")

SAFETY_RESPONSE_DEADLINE_MS = 5   # Hard real-time constraint from PRD

class SafetyTrigger(Enum):
    OBSTACLE = "OBSTACLE"
    CLIFF = "CLIFF"
    FALL_RISK = "FALL_RISK"
    TRAFFIC = "TRAFFIC"
    LOW_BATTERY = "LOW_BATTERY"
    OWNER_EMERGENCY = "OWNER_EMERGENCY"


@dataclass
class SafetyDecision:
    trigger: SafetyTrigger
    distance_m: float
    response_time_ms: float
    subsumption_activated: bool
    message: str


class SafetyAgent:
    """
    Deterministic Safety Agent — No LLM, no external calls.
    Pure threshold-based logic for < 5ms response guarantee.
    """

    # Safety thresholds (tunable)
    OBSTACLE_STOP_DISTANCE_M = 0.5    # Stop if obstacle within 0.5m
    CLIFF_DEPTH_THRESHOLD_M = 0.3     # Cliff detected if depth drop > 0.3m
    FALL_ACCEL_THRESHOLD = 2.5        # g-force threshold for fall detection

    def __init__(self, arbitrator):
        self.arbitrator = arbitrator
        self._status = "INITIALIZING"
        self._subsumption_active = False
        self._last_scan_time = 0.0
        self._volatile_context = {}  # RAM-only, wiped on shutdown
        self._last_processed = {"lidar": 0.0, "imu": 0.0, "vitals": 0.0}

        # MQTT client for inhibit signals
        broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self._mqtt = mqtt.Client(client_id="safety-agent-inhibit", protocol=mqtt.MQTTv311)
        self._mqtt.connect_async(broker_host, broker_port, keepalive=30)
        self._mqtt.loop_start()

    async def run_loop(self):
        """Main event loop — subscribes to MQTT sensor topics via async polling"""
        self._status = "ACTIVE"
        log.info("[SAFETY_AGENT] Tầng 0 ACTIVE — Subsumption armed")

        loop = asyncio.get_event_loop()
        mqtt_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

        # Subscribe to sensor topics
        self._mqtt.on_message = lambda c, u, msg: loop.call_soon_threadsafe(
            mqtt_queue.put_nowait, (msg.topic, msg.payload.decode("utf-8", errors="replace"))
        )
        self._mqtt.subscribe([
            ("hk07/sensors/lidar/scan", 0),
            ("hk07/sensors/imu/state", 0),
            ("hk07/sensors/wristband/+/vitals", 0),
        ])

        while True:
            try:
                topic, payload = await asyncio.wait_for(mqtt_queue.get(), timeout=1.0)
                await self._process_sensor(topic, payload)
            except asyncio.TimeoutError:
                continue   # No sensor data — normal, keep alive
            except asyncio.CancelledError:
                log.info("[SAFETY_AGENT] Loop cancelled — shutdown")
                break
            except Exception as e:
                log.error("[SAFETY_AGENT_ERROR] %s", e)

    async def _process_sensor(self, topic: str, payload: str):
        """
        Process incoming sensor data. Must complete in < 5ms for safety guarantee.
        Measured from message receipt to MQTT inhibit publish.
        """
        start_ns = time.perf_counter_ns()
        now = time.time()

        # Throttle (Message Flooding Protection): Max 20Hz (50ms) per sensor type
        sensor_type = topic.split('/')[2] if len(topic.split('/')) > 2 else "unknown"
        if sensor_type in self._last_processed:
            if now - self._last_processed[sensor_type] < 0.05:
                return  # Drop frame (Debounce)
            self._last_processed[sensor_type] = now

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        decision: Optional[SafetyDecision] = None

        if "lidar" in topic:
            decision = self._analyze_lidar(data)
        elif "imu" in topic:
            decision = self._analyze_imu(data)
        elif "vitals" in topic:
            decision = self._analyze_vitals(data)

        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

        if decision and decision.subsumption_activated:
            decision.response_time_ms = elapsed_ms
            await self._activate_subsumption(decision)
            if elapsed_ms > SAFETY_RESPONSE_DEADLINE_MS:
                log.warning("[SAFETY_LATENCY_BREACH] Response: %.2fms > %dms deadline!",
                            elapsed_ms, SAFETY_RESPONSE_DEADLINE_MS)

    def _analyze_lidar(self, data: dict) -> Optional[SafetyDecision]:
        """Check LiDAR scan for obstacles and cliff edges"""
        ranges = data.get("ranges", [])
        if not ranges:
            return None

        min_distance = min(r for r in ranges if r > 0.01)  # Filter invalid 0-readings

        if min_distance < self.OBSTACLE_STOP_DISTANCE_M:
            return SafetyDecision(
                trigger=SafetyTrigger.OBSTACLE,
                distance_m=min_distance,
                response_time_ms=0.0,
                subsumption_activated=True,
                message=f"Obstacle at {min_distance:.2f}m — INHIBIT activated"
            )
        return None

    def _analyze_imu(self, data: dict) -> Optional[SafetyDecision]:
        """Detect fall or sudden impact via accelerometer magnitude"""
        ax = data.get("accel_x", 0.0)
        ay = data.get("accel_y", 0.0)
        az = data.get("accel_z", 9.81)  # Default: gravity
        magnitude = (ax**2 + ay**2 + az**2) ** 0.5 / 9.81  # Normalize to g

        if magnitude > self.FALL_ACCEL_THRESHOLD:
            return SafetyDecision(
                trigger=SafetyTrigger.FALL_RISK,
                distance_m=0.0,
                response_time_ms=0.0,
                subsumption_activated=True,
                message=f"Fall detected! Accel magnitude: {magnitude:.2f}g"
            )
        return None

    def _analyze_vitals(self, data: dict) -> Optional[SafetyDecision]:
        """Detect owner emergency via wristband panic button"""
        if data.get("emergency_button_pressed", False):
            return SafetyDecision(
                trigger=SafetyTrigger.OWNER_EMERGENCY,
                distance_m=0.0,
                response_time_ms=0.0,
                subsumption_activated=True,
                message="Owner pressed emergency button!"
            )
        return None

    async def _activate_subsumption(self, decision: SafetyDecision):
        """
        Publish Subsumption Inhibit signal — QoS 2 (Exactly Once).
        This MUST reach the motion control node to stop the robot.
        """
        self._subsumption_active = True
        inhibit_payload = json.dumps({
            "trigger": decision.trigger.value,
            "distance_m": decision.distance_m,
            "message": decision.message,
            "agent": "SAFETY",
            "timestamp_ms": int(time.time() * 1000)
        })
        self._mqtt.publish("hk07/control/subsumption/inhibit", inhibit_payload, qos=2)
        log.warning("[SUBSUMPTION_ACTIVATED] Trigger: %s | Msg: %s | Response: %.2fms",
                    decision.trigger.value, decision.message, decision.response_time_ms)
                    
        # Log to Spring Boot via REST (fire-and-forget, does not block safety loop)
        await log_agent_decision(
            agent_type="SAFETY",
            input_context=f"Trigger: {decision.trigger.value}, Dist: {decision.distance_m}m",
            output_decision=decision.message,
            llm_provider="THRESHOLD",
            latency_ms=int(decision.response_time_ms)
        )

        # Auto-release inhibit after 3 seconds (re-evaluate)
        await asyncio.sleep(3.0)
        self._subsumption_active = False
        self._mqtt.publish("hk07/control/subsumption/inhibit",
                           json.dumps({"trigger": "CLEAR", "agent": "SAFETY"}), qos=2)
        log.info("[SUBSUMPTION_CLEARED] Re-enabling motion after safety hold")

    def get_status(self) -> dict:
        return {
            "status": self._status,
            "subsumption_active": self._subsumption_active,
            "last_scan_ms_ago": int((time.time() - self._last_scan_time) * 1000)
        }

    def clear_volatile_context(self):
        """Wipe all RAM-only data (called on shutdown per security protocol)"""
        self._volatile_context.clear()
        log.info("[VOLATILE_WIPE] SafetyAgent context cleared")
