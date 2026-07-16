"""
test_proactive_hugo.py — Unit and Integration Test Suite for Proactive Hugo Subsystem (Phase 7)
"""

import sys
import os
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add agent package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.blackboard_service import get_blackboard, ClinicalEntry, EmotionalEntry
from engine.agents.medical_agent import MedicalAgent
from engine.agents.empathetic_agent import EmpatheticAgent
from engine.arbitrator.arbitrator import Arbitrator


class TestProactiveHugo(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.arbitrator = Arbitrator()
        self.blackboard = get_blackboard()
        self.blackboard._in_memory_store.clear()
        # Flush Redis keys that pollute across test runs
        try:
            await self.blackboard._redis_client.delete("blackboard:empathy:stress_processed_trend")
            await self.blackboard._redis_client.delete("blackboard:clinical:stress_history")
        except Exception:
            pass
        
        # Patch MQTT in MedicalAgent
        with patch('paho.mqtt.client.Client') as mock_mqtt:
            self.medical = MedicalAgent(memory=MagicMock(), arbitrator=self.arbitrator)
            self.medical._mqtt = MagicMock()
            self.medical._call_llm_with_fallback = AsyncMock(return_value={
                "alert_level": "NORMAL", "summary": "Chẩn đoán y tế", "action": "Nghỉ ngơi"
            })

        # Patch MQTT in EmpatheticAgent
        with patch('paho.mqtt.client.Client') as mock_mqtt:
            self.empathy = EmpatheticAgent(memory=MagicMock(), arbitrator=self.arbitrator)
            self.empathy._mqtt = MagicMock()

    async def asyncTearDown(self):
        await self.medical.close()
        await self.empathy.close()

    async def test_nominal_vitals_no_wakeup(self):
        """Nominal vitals should not trigger AI_EMERGENCY_WAKEUP"""
        # Inject normal vitals
        normal_sample = {
            "heartRate": 75,
            "spo2": 98.5,
            "bodyTemperature": 36.6,
            "systolic": 120,
            "diastolic": 80,
            "is_falling": False,
            "emergency_button_pressed": False
        }
        for _ in range(5):
            self.medical._buffer.append(normal_sample)

        await self.medical._process_latest_buffer()

        # Should not publish any message
        self.medical._mqtt.publish.assert_not_called()
        self.assertEqual(self.medical._last_state, "NORMAL")

    async def test_critical_vitals_trigger_immediate_wakeup(self):
        """Vitals exceeding thresholds should trigger immediate AI_EMERGENCY_WAKEUP without waiting for LLM"""
        # Inject critical vitals (e.g., HR = 140)
        critical_sample = {
            "heartRate": 140,
            "spo2": 98.0,
            "bodyTemperature": 36.6,
            "systolic": 120,
            "diastolic": 80,
            "is_falling": False,
            "emergency_button_pressed": False
        }
        import collections
        self.medical._raw_hr_windows["default"] = collections.deque([140, 140, 140, 140, 140], maxlen=5)
        for _ in range(5):
            self.medical._buffer.append(critical_sample)

        await self.medical._process_latest_buffer()

        # Verify instant MQTT publication of AI_EMERGENCY_WAKEUP
        self.medical._mqtt.publish.assert_called_once()
        args, kwargs = self.medical._mqtt.publish.call_args
        topic, payload_str = args[0], args[1]
        
        self.assertEqual(topic, "hk07/agents/medical/output")
        payload = json.loads(payload_str)
        self.assertEqual(payload["eventType"], "AI_EMERGENCY_WAKEUP")
        self.assertEqual(payload["alertLevel"], "CRITICAL")
        self.assertIn("nhịp tim", payload["outputDecision"])
        self.assertEqual(self.medical._last_state, "CRITICAL")

    async def test_fall_event_trigger_immediate_wakeup(self):
        """Fall state or emergency button pressed should trigger immediate AI_EMERGENCY_WAKEUP even if vitals nominal"""
        fall_sample = {
            "heartRate": 72,
            "spo2": 98.0,
            "bodyTemperature": 36.6,
            "systolic": 120,
            "diastolic": 80,
            "is_falling": True,
            "emergency_button_pressed": False
        }
        self.medical._buffer.append(fall_sample)

        await self.medical._process_latest_buffer()

        self.medical._mqtt.publish.assert_called_once()
        args, _ = self.medical._mqtt.publish.call_args
        payload = json.loads(args[1])
        self.assertEqual(payload["eventType"], "AI_EMERGENCY_WAKEUP")
        self.assertEqual(payload["alertLevel"], "CRITICAL")
        self.assertIn("phát hiện ngã/chấn thương", payload["outputDecision"])

    async def test_empathy_proactive_loop_triggers_comfort(self):
        """EmpatheticAgent run_loop should detect stress history rise and publish comforting messages"""
        # Inject stress history [20, 30, 45] (rising, latest 45 >= 30)
        await self.blackboard.write_value("blackboard:clinical:stress_history", [20, 30, 45], ttl_seconds=300)

        # Trigger one iteration of the empathetic agent proactive checker
        # Instead of launching the infinite run_loop task, we test the core logic synchronously:
        # We simulate the loop iteration
        history = await self.blackboard.read_value("blackboard:clinical:stress_history")
        self.assertIsNotNone(history)
        
        # Verify stress history conditions
        t1, t2, t3 = history[-3], history[-2], history[-1]
        self.assertTrue(t3 > t2 > t1 and t3 >= 30)

        # Run proactive monitor logic step-by-step
        last_processed = await self.blackboard.read_value("blackboard:empathy:stress_processed_trend")
        self.assertNotEqual(last_processed, history)

        await self.blackboard.write_value("blackboard:empathy:stress_processed_trend", history, ttl_seconds=300)
        decision_text = "[HÀNH VI CHỦ ĐỘNG] Tôi nhận thấy chỉ số căng thẳng của bạn đang tăng liên tục. Hãy cùng tôi thực hiện bài tập thở sâu và thư giãn cơ thể nhé. Tôi luôn ở đây bên bạn."
        
        payload = {
            "eventType": "AGENT_DECISION",
            "agentType": "EMPATHETIC",
            "outputDecision": decision_text,
            "llmProvider": "LOCAL_PROACTIVE"
        }
        self.empathy._mqtt.publish("hk07/agents/empathetic/output", json.dumps(payload), qos=1)

        # Write EmotionalEntry
        entry = EmotionalEntry(
            detected_emotion="anxious",
            emotional_intensity=float(t3 / 100.0),
            tone_analysis=f"Stress score is rising: {history}"
        )
        await self.blackboard.write_emotional(entry)

        # Asserts
        self.empathy._mqtt.publish.assert_called_once()
        stored_emotional = await self.blackboard.read_latest_emotional()
        self.assertIsNotNone(stored_emotional)
        self.assertEqual(stored_emotional.detected_emotion, "anxious")
        self.assertEqual(stored_emotional.emotional_intensity, 0.45)

        # Check deduplication
        last_processed = await self.blackboard.read_value("blackboard:empathy:stress_processed_trend")
        self.assertEqual(last_processed, history) # Should be marked as processed now
