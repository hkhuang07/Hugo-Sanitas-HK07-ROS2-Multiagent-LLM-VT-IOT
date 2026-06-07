"""
test_action_agent.py — Integration and Unit Test Suite for Action Agent

Tests:
  1. Safe execution of non-confirming steps (MQTT publishing).
  2. Safety-critical confirmation check pauses and updates status to AWAITING_CONFIRM.
  3. ActionAgent.confirm_plan resumes plan and completes it.
  4. Arbitrator safety gate blocking plan execution when ACTION is inhibited.
  5. Critical clinical vitals alert blocking nominal plan execution.
"""

import sys
import os
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add agent package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.blackboard_service import get_blackboard, ActionPlanEntry, ClinicalEntry
from agents.action_agent import ActionAgent
from arbitrator.arbitrator import Arbitrator


class TestActionAgent(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.arbitrator = Arbitrator()
        # Mock MQTT connect and publish to avoid actual network requests
        with patch('paho.mqtt.client.Client') as mock_mqtt:
            self.agent = ActionAgent(self.arbitrator)
            self.agent._mqtt = MagicMock()

        self.blackboard = get_blackboard()
        # Ensure clean blackboard state
        self.blackboard._in_memory_store.clear()

    async def asyncTearDown(self):
        await self.agent.close()

    async def test_safe_execution_no_confirm(self):
        """Should execute all steps successfully when requires_confirm is False"""
        plan = ActionPlanEntry(
            plan_id="plan-test-safe",
            steps=[
                {
                    "type": "SAFE_HOLD",
                    "mqtt_topic": "hk07/control/subsumption/inhibit",
                    "payload": {"trigger": "SAFE_HOLD", "agent": "ACTION_AGENT"},
                    "requires_confirm": False
                },
                {
                    "type": "SPEAK_MESSAGE",
                    "mqtt_topic": "hk07/agents/action/tts",
                    "payload": {"message": "Hello world"},
                    "requires_confirm": False
                }
            ]
        )

        # Mock REST calls so we don't hit the physical backend
        self.agent._call_core_rest = AsyncMock()

        result = await self.agent.execute_plan(plan)
        self.assertEqual(result, "Kế hoạch hành động hoàn thành thành công.")
        
        # Verify status is COMPLETED
        stored_plan = await self.blackboard.read_action_plan(plan.plan_id)
        self.assertIsNotNone(stored_plan)
        self.assertEqual(stored_plan.status, "COMPLETED")
        self.assertEqual(stored_plan.current_step_index, 1)

        # Verify MQTT was called
        self.assertEqual(self.agent._mqtt.publish.call_count, 2)
        self.agent._call_core_rest.assert_called_once_with("SAFE_HOLD")

    async def test_requires_confirm_pauses(self):
        """Should pause and set status to AWAITING_CONFIRM when step requires confirmation"""
        plan = ActionPlanEntry(
            plan_id="plan-test-confirm",
            steps=[
                {
                    "type": "SPEAK_MESSAGE",
                    "mqtt_topic": "hk07/agents/action/tts",
                    "payload": {"message": "Step 1"},
                    "requires_confirm": False
                },
                {
                    "type": "SOS_DISPATCH",
                    "mqtt_topic": "hk07/control/subsumption/inhibit",
                    "payload": {"trigger": "OWNER_EMERGENCY"},
                    "requires_confirm": True
                }
            ]
        )

        self.agent._call_core_rest = AsyncMock()

        result = await self.agent.execute_plan(plan)
        self.assertTrue(result.startswith("AWAITING_CONFIRM"))

        # Verify status in Blackboard
        stored_plan = await self.blackboard.read_action_plan(plan.plan_id)
        self.assertEqual(stored_plan.status, "AWAITING_CONFIRM")
        self.assertEqual(stored_plan.current_step_index, 1)

        # Step 1 should have run, Step 2 should NOT have run yet
        self.assertEqual(self.agent._mqtt.publish.call_count, 1)
        self.agent._call_core_rest.assert_not_called()

        # Resuming with confirm = True
        confirm_result = await self.agent.confirm_plan(plan.plan_id, confirm=True)
        self.assertEqual(confirm_result, "Kế hoạch hành động hoàn thành thành công.")

        # Check status after confirmation
        stored_plan_after = await self.blackboard.read_action_plan(plan.plan_id)
        self.assertEqual(stored_plan_after.status, "COMPLETED")
        self.assertEqual(self.agent._mqtt.publish.call_count, 2)
        self.agent._call_core_rest.assert_called_once_with("SOS_DISPATCH")

    async def test_requires_confirm_cancel(self):
        """Should cancel and stop execution when confirm = False"""
        plan = ActionPlanEntry(
            plan_id="plan-test-cancel",
            steps=[
                {
                    "type": "SOS_DISPATCH",
                    "mqtt_topic": "hk07/control/subsumption/inhibit",
                    "payload": {"trigger": "OWNER_EMERGENCY"},
                    "requires_confirm": True
                }
            ]
        )

        result = await self.agent.execute_plan(plan)
        self.assertTrue(result.startswith("AWAITING_CONFIRM"))

        confirm_result = await self.agent.confirm_plan(plan.plan_id, confirm=False)
        self.assertEqual(confirm_result, "Kế hoạch hành động đã bị hủy bởi người dùng.")

        stored_plan = await self.blackboard.read_action_plan(plan.plan_id)
        self.assertEqual(stored_plan.status, "CANCELLED")
        self.assertEqual(self.agent._mqtt.publish.call_count, 0)

    async def test_arbitrator_safety_gate(self):
        """Should fail the plan execution if ACTION is inhibited by safety arbitrator"""
        plan = ActionPlanEntry(
            plan_id="plan-test-inhibit",
            steps=[
                {
                    "type": "SPEAK_MESSAGE",
                    "mqtt_topic": "hk07/agents/action/tts",
                    "payload": {"message": "Hello"},
                    "requires_confirm": False
                }
            ]
        )

        # Inhibit action
        self.arbitrator.inhibit("ACTION", duration_s=10)

        result = await self.agent.execute_plan(plan)
        self.assertEqual(result, "Kế hoạch hành động bị chặn bởi bộ phân xử an toàn (Safety Arbitrator).")

        stored_plan = await self.blackboard.read_action_plan(plan.plan_id)
        self.assertEqual(stored_plan.status, "FAILED")

    async def test_critical_vitals_safety_gate(self):
        """Should block nominal plans if clinical vitals alert level is CRITICAL"""
        plan = ActionPlanEntry(
            plan_id="plan-test-critical-vitals",
            steps=[
                {
                    "type": "NAVIGATE_TO",
                    "mqtt_topic": "hk07/control/navigation/waypoint",
                    "payload": {"x": 1.0, "y": 1.0},
                    "requires_confirm": False
                }
            ]
        )

        # Write CRITICAL clinical entry to blackboard
        await self.blackboard.write_clinical(ClinicalEntry(
            alert_level="CRITICAL",
            diagnosis="Severe distress"
        ))

        result = await self.agent.execute_plan(plan)
        self.assertEqual(result, "Hành động thường bị chặn do hệ thống đang trong trạng thái khẩn cấp (CRITICAL).")

        stored_plan = await self.blackboard.read_action_plan(plan.plan_id)
        self.assertEqual(stored_plan.status, "FAILED")


if __name__ == "__main__":
    unittest.main()
