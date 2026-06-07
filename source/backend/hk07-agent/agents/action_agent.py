"""
ActionAgent — Tier 2 (Execution) in Subsumption Architecture

Role: Propose and execute structured ActionPlans.
Actuation layers:
  1. MQTT: Publishes JSON payloads to specified topics (e.g. waypoint, tts).
  2. REST: Triggers Spring Boot Core REST endpoints for safety-critical states (Hold, Resume, SOS).

Subsumption Safety Gate:
  - Inhibit check: ActionAgent will abort if arbitrator.is_inhibited("ACTION") is True.
  - Critical Vitals check: Aborts nominal plans if clinical alert level is CRITICAL.
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, Any, Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from services.blackboard_service import get_blackboard, ActionPlanEntry
from services.agent_log_client import _client as log_client
from arbitrator.arbitrator import Arbitrator

load_dotenv()

log = logging.getLogger("hk07.action_agent")


class ActionAgent:
    def __init__(self, arbitrator: Optional[Arbitrator] = None):
        self.arbitrator = arbitrator or Arbitrator()
        self._status = "INITIALIZING"

        # Initialize MQTT client for publishing actions
        broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self._mqtt = mqtt.Client(client_id="action-agent", protocol=mqtt.MQTTv311)
        mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
        mqtt_pass = os.getenv("MQTT_PASSWORD", "")
        if mqtt_user:
            self._mqtt.username_pw_set(mqtt_user, mqtt_pass)
        self._mqtt.connect_async(broker_host, broker_port, keepalive=30)
        self._mqtt.loop_start()

        log.info("[ACTION_AGENT] Initialized — MQTT loop started.")

    async def execute_plan(self, plan: ActionPlanEntry) -> str:
        """
        Iterates and executes steps in the ActionPlanEntry.
        pauses on steps requiring confirmation.
        """
        # ── Safety checks ──────────────────────────────────────────────────────
        if self.arbitrator.is_inhibited("ACTION") or self.arbitrator.is_inhibited("EMPATHETIC"):
            plan.status = "FAILED"
            await get_blackboard().write_action_plan(plan)
            return "Kế hoạch hành động bị chặn bởi bộ phân xử an toàn (Safety Arbitrator)."

        # Check latest clinical entry alert level
        clinical = await get_blackboard().read_latest_clinical()
        if clinical and clinical.alert_level == "CRITICAL":
            # Safety critical state: we only execute emergency SOS dispatches, all other commands are blocked
            has_sos = any(s.get('type') == 'SOS_DISPATCH' for s in plan.steps)
            if not has_sos:
                plan.status = "FAILED"
                await get_blackboard().write_action_plan(plan)
                return "Hành động thường bị chặn do hệ thống đang trong trạng thái khẩn cấp (CRITICAL)."

        if plan.status not in ("CONFIRMED", "EXECUTING"):
            plan.status = "EXECUTING"
            await get_blackboard().write_action_plan(plan)

        bb = get_blackboard()

        for i in range(plan.current_step_index, len(plan.steps)):
            step = plan.steps[i]
            plan.current_step_index = i
            
            # Check for confirmation requirement
            if step.get("requires_confirm", False) and plan.status != "CONFIRMED":
                plan.status = "AWAITING_CONFIRM"
                await bb.write_action_plan(plan)
                log.warning("[ACTION_AGENT] Action plan %s requires confirmation at step %d (%s)", 
                            plan.plan_id, i, step.get("type"))
                return f"AWAITING_CONFIRM: {step.get('type')}"

            # Reset status to executing if it was confirmed in the prior step
            if plan.status == "CONFIRMED":
                plan.status = "EXECUTING"
                await bb.write_action_plan(plan)

            # Execute step
            try:
                log.info("[ACTION_AGENT] Executing step %d: %s", i, step.get("type"))
                await self._execute_step(step)
            except Exception as e:
                log.error("[ACTION_AGENT] Step execution failed: %s", e)
                plan.status = "FAILED"
                await bb.write_action_plan(plan)
                return f"Lỗi thực thi bước {i} ({step.get('type')}): {str(e)}"

        plan.status = "COMPLETED"
        await bb.write_action_plan(plan)
        log.info("[ACTION_AGENT] Action plan %s completed successfully", plan.plan_id)
        return "Kế hoạch hành động hoàn thành thành công."

    async def confirm_plan(self, plan_id: str, confirm: bool) -> str:
        """Confirm or cancel a plan currently in AWAITING_CONFIRM state"""
        bb = get_blackboard()
        plan = await bb.read_action_plan(plan_id)
        if not plan:
            return "Không tìm thấy kế hoạch hành động."

        if plan.status != "AWAITING_CONFIRM":
            return f"Kế hoạch không ở trạng thái chờ xác nhận (trạng thái hiện tại: {plan.status})."

        if not confirm:
            plan.status = "CANCELLED"
            await bb.write_action_plan(plan)
            log.info("[ACTION_AGENT] Action plan %s cancelled by user", plan_id)
            return "Kế hoạch hành động đã bị hủy bởi người dùng."

        # Mark as confirmed and resume execution loop
        plan.status = "CONFIRMED"
        return await self.execute_plan(plan)

    async def _execute_step(self, step: Dict[str, Any]):
        """Execute a single plan step via MQTT publish and REST calls"""
        step_type = step.get("type")
        topic = step.get("mqtt_topic")
        payload = step.get("payload", {})

        # 1. Publish to MQTT for low-latency robotics interface
        if topic:
            payload_str = json.dumps(payload)
            self._mqtt.publish(topic, payload_str, qos=1)
            log.info("[ACTION_AGENT] MQTT Publish topic=%s payload=%s", topic, payload_str)

        # 2. Call Spring Boot Core REST endpoints for safety state transitions
        if step_type in ("SAFE_HOLD", "RESUME", "SOS_DISPATCH"):
            await self._call_core_rest(step_type)

    async def _call_core_rest(self, step_type: str):
        """Call Spring Boot Core command endpoint using credentials from Log Client"""
        if not log_client:
            log.warning("[ACTION_AGENT] AgentLogClient not initialized — skipping REST call")
            return

        # Trigger login if not authenticated
        if not log_client._token:
            await log_client._authenticate()

        if not log_client._http or not log_client._token:
            log.warning("[ACTION_AGENT] Log client HTTP or token unavailable — skipping REST call")
            return

        headers = {"Authorization": f"Bearer {log_client._token}"}
        try:
            if step_type == "SAFE_HOLD":
                resp = await log_client._http.post("/api/v1/robot/command/hold", headers=headers)
                log.info("[ACTION_AGENT] REST hold endpoint status=%d response=%s", resp.status_code, resp.text[:100])
            elif step_type == "RESUME":
                resp = await log_client._http.post("/api/v1/robot/command/resume", headers=headers)
                log.info("[ACTION_AGENT] REST resume endpoint status=%d response=%s", resp.status_code, resp.text[:100])
            elif step_type == "SOS_DISPATCH":
                resp = await log_client._http.post("/api/v1/robot/command/sos", headers=headers)
                log.info("[ACTION_AGENT] REST sos endpoint status=%d response=%s", resp.status_code, resp.text[:100])
        except Exception as e:
            log.error("[ACTION_AGENT] REST core call failed for %s: %s", step_type, e)

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent": "ACTION",
            "tier": "2",
            "mqtt_connected": self._mqtt.is_connected() if hasattr(self._mqtt, "is_connected") else True,
        }

    async def close(self):
        log.info("[ACTION_AGENT] Closing ActionAgent resources.")
        self._mqtt.loop_stop()
        self._mqtt.disconnect()
