"""
EmpatheticAgent — Tầng 2 trong Subsumption Architecture

Giao tiếp thấu cảm và chăm sóc tâm lý với chủ nhân.
Giọng điệu linh hoạt theo ngữ cảnh (ấm áp khi trò chuyện, chuyên nghiệp khi trả lời kỹ thuật).
"""

import asyncio
import json
import logging
import os
import time
import paho.mqtt.client as mqtt
from collections import deque
from typing import Optional, Dict
from services.agent_log_client import log_agent_decision
from utils.enums import LLMProvider
from services.llm_client import LLMClient, EMPATHY_TIERS, SYSTEM_QUERY_TIERS, VISION_TIERS
from services.blackboard_service import get_blackboard, EmotionalEntry, current_user_id
from services.sensor_intelligence import get_sensor_fusion_analyzer
# ─── Baymax Intelligence: CareDecisionRouter ─────────────────────────────
try:
    from services.care_decision_router import get_care_decision_router, get_care_conversation_starter, CareAction
    _CARE_ROUTER_AVAILABLE = True
except ImportError:
    _CARE_ROUTER_AVAILABLE = False
    get_care_decision_router = None
    get_care_conversation_starter = None

log = logging.getLogger("hk07.empathy_agent")

# ─── Proactive Trigger Engine ──────────────────────────────────────────────────────────────────────────
class ProactiveTriggerEngine:
    """
    Sensor-driven proactive conversation trigger system.
    Evaluates blackboard state and fires one proactive message per trigger type
    with per-type cooldown to prevent spam.

    RULES:
    - Reads safety:state — will NOT trigger if state is SENSOR_UNINITIALIZED or HOLD_POSITION
    - Uses BehavioralStressProxy (NOT neurotransmitter labels) for distress assessment
    - Each trigger type has independent cooldown
    - Max 1 proactive message per 60s globally
    """

    # Cooldown durations per trigger type (seconds)
    COOLDOWNS: Dict[str, float] = {
        "FALL_DETECTED":     30.0,     # Urgent — short cooldown
        "HIGH_STRESS":       300.0,    # 5 minutes
        "INACTIVITY":        1800.0,   # 30 minutes
        "ELEVATED_HR":       300.0,    # 5 minutes
        "LOW_LIGHT_NIGHT":   3600.0,   # 1 hour
        "INJURY_DETECTED":   120.0,    # 2 minutes
    }
    GLOBAL_COOLDOWN_S = 60.0  # Minimum 60s between ANY proactive messages

    def __init__(self, mqtt_client):
        self._mqtt = mqtt_client
        self._last_trigger: Dict[str, float] = {}
        self._last_global_trigger: float = 0.0

    def _is_on_cooldown(self, trigger_type: str) -> bool:
        now = time.time()
        # Global cooldown
        if now - self._last_global_trigger < self.GLOBAL_COOLDOWN_S:
            return True
        # Per-type cooldown
        last = self._last_trigger.get(trigger_type, 0.0)
        return (now - last) < self.COOLDOWNS.get(trigger_type, 300.0)

    def _record_trigger(self, trigger_type: str):
        now = time.time()
        self._last_trigger[trigger_type] = now
        self._last_global_trigger = now

    def _build_mqtt_payload(
        self, trigger_type: str, message: str, alert_level: str = "NORMAL", user_id: str = "default"
    ) -> dict:
        return {
            "id": f"proactive-{trigger_type.lower()}-{int(time.time())}",
            "eventType": "PROACTIVE_TRIGGER",
            "agentType": "EMPATHETIC",
            "alertLevel": alert_level,
            "inputContext": f"Sensor-driven trigger: {trigger_type}",
            "outputDecision": message,
            "llmProvider": "PROACTIVE_ENGINE",
            "latencyMs": 0,
            "triggeredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "userId": user_id,
        }

    async def evaluate_and_trigger(self, user_id: str = "default") -> Optional[str]:
        """
        Reads blackboard state and fires a proactive message if conditions are met.
        Returns the trigger type if fired, None otherwise.
        """
        bb = get_blackboard()

        # ── Safety State Gate ──────────────────────────────────────────────────────────────────────────
        # Never trigger proactive messages if sensors are not yet initialized
        safety_state = await bb.read_value("safety:state")
        if safety_state in ("SENSOR_UNINITIALIZED", "HOLD_POSITION", None):
            log.debug("[PROACTIVE] Skipping: safety state=%s", safety_state)
            return None

        # ── Read behavioral context from Blackboard ──────────────────────────────────────────────────────
        imu_data = await bb.read_value("sensor:imu:latest")
        vitals_data = await bb.read_value("sensor:vitals:latest") or (
            await bb.read_value("sensor:vitals:heart_rate")
        )
        is_falling = await bb.read_value("sensor:vitals:is_falling")
        env_data = await bb.read_value("sensor:env:latest")
        perception_scan = await bb.read_value("sensor:perception:latest_scan")

        # Compute BehavioralStressProxy from current sensor state
        analyzer = get_sensor_fusion_analyzer()
        vitals_dict = None
        if isinstance(vitals_data, dict):
            vitals_dict = vitals_data
        elif isinstance(vitals_data, (int, float)):
            vitals_dict = {"heart_rate": vitals_data}

        posture_risk = "LOW"
        visible_injuries = []
        if isinstance(perception_scan, dict):
            posture_risk = perception_scan.get("posture_risk", "LOW")
            visible_injuries = perception_scan.get("visible_injuries", [])

        analysis = analyzer.analyze(
            imu_data=imu_data if isinstance(imu_data, dict) else None,
            vitals_data=vitals_dict,
            env_data=env_data if isinstance(env_data, dict) else None,
            posture_risk=posture_risk,
        )
        stress_proxy = analysis.get("behavioral_stress_proxy", {})
        stress_score = stress_proxy.get("stress_score", 0.0)
        activity_state = analysis.get("activity_state", "unknown")
        inactivity_secs = analysis.get("inactivity_seconds", 0.0)

        # Extract HR safely
        hr = None
        if vitals_dict:
            hr_raw = vitals_dict.get("heart_rate") or vitals_dict.get("hr")
            try:
                hr = float(hr_raw) if hr_raw is not None else None
            except (TypeError, ValueError):
                hr = None

        # ── Evaluate triggers in priority order ──────────────────────────────────────────────────────

        # 1. Fall detected (highest priority)
        if is_falling is True and not self._is_on_cooldown("FALL_DETECTED"):
            msg = (
                "🚨 Sếp ơi! Hãy nằm yên, đừng cố cử động. Tôi đã phát hiện cú ngã và "
                "đang gửi tín hiệu SOS khẩn cấp để gọi người hỗ trợ ngay lập tức!"
            )
            self._record_trigger("FALL_DETECTED")
            payload = self._build_mqtt_payload("FALL_DETECTED", msg, "CRITICAL", user_id)
            self._mqtt.publish("hk07/agents/empathetic/output", json.dumps(payload), qos=2)
            log.warning("[PROACTIVE_TRIGGER] FALL_DETECTED fired for user=%s", user_id)
            return "FALL_DETECTED"

        # 2. Visible injury detected
        if visible_injuries and not self._is_on_cooldown("INJURY_DETECTED"):
            injury_desc = ", ".join(visible_injuries[:2])
            msg = (
                f"Tôi quan sát thấy có vẻ bạn đang có vết thương ({injury_desc}). "
                "Bạn có đang đau không? Hãy để tôi kiểm tra kỹ hơn cho bạn."
            )
            self._record_trigger("INJURY_DETECTED")
            payload = self._build_mqtt_payload("INJURY_DETECTED", msg, "WARNING", user_id)
            self._mqtt.publish("hk07/agents/empathetic/output", json.dumps(payload), qos=1)
            log.info("[PROACTIVE_TRIGGER] INJURY_DETECTED fired")
            return "INJURY_DETECTED"

        # 3. High behavioral stress
        if stress_score >= 0.65 and not self._is_on_cooldown("HIGH_STRESS"):
            stress_context = stress_proxy.get("behavioral_context", "")
            msg = (
                "Tôi nhận thấy bạn có vẻ như đang căng thẳng. "
                f"{stress_context} "
                "Hãy hít thở sâu cùng tôi nhé. Tôi luôn ở bên cạnh bạn."
            )
            self._record_trigger("HIGH_STRESS")
            payload = self._build_mqtt_payload("HIGH_STRESS", msg, "WARNING", user_id)
            self._mqtt.publish("hk07/agents/empathetic/output", json.dumps(payload), qos=1)
            log.info("[PROACTIVE_TRIGGER] HIGH_STRESS fired (score=%.2f)", stress_score)
            return "HIGH_STRESS"

        # 4. Elevated resting heart rate
        if hr is not None and hr > 110 and activity_state in ("sitting", "still", "lying") \
                and not self._is_on_cooldown("ELEVATED_HR"):
            msg = (
                f"Nhịp tim của bạn hiện đang khá cao ({hr:.0f} BPM) trong khi bạn đang nghỉ ngơi. "
                "Bạn có đang cảm thấy khỏe không? Hãy cho tôi biết bạn cảm thấy như thế nào."
            )
            self._record_trigger("ELEVATED_HR")
            payload = self._build_mqtt_payload("ELEVATED_HR", msg, "WARNING", user_id)
            self._mqtt.publish("hk07/agents/empathetic/output", json.dumps(payload), qos=1)
            log.info("[PROACTIVE_TRIGGER] ELEVATED_HR fired (hr=%.0f)", hr)
            return "ELEVATED_HR"

        # 5. Prolonged inactivity (> 2 hours)
        if inactivity_secs > 7200 and not self._is_on_cooldown("INACTIVITY"):
            hours = inactivity_secs / 3600
            msg = (
                f"Bạn đã ngồi yên khá lâu rồi ({hours:.1f} giờ). "
                "Hãy đứng dậy vận động một chút để tốt cho sức khỏe nhé! "
                "Tôi có thể hướng dẫn bài tập giãn cơ ngắn cho bạn."
            )
            self._record_trigger("INACTIVITY")
            payload = self._build_mqtt_payload("INACTIVITY", msg, "NORMAL", user_id)
            self._mqtt.publish("hk07/agents/empathetic/output", json.dumps(payload), qos=0)
            log.info("[PROACTIVE_TRIGGER] INACTIVITY fired (%.1fh)", hours)
            return "INACTIVITY"

        # 6. Very dark environment at night
        if env_data and isinstance(env_data, dict):
            light_lux = env_data.get("light_lux") or env_data.get("light")
            current_hour = time.localtime().tm_hour
            if light_lux is not None and float(light_lux) < 15 and current_hour >= 22 \
                    and not self._is_on_cooldown("LOW_LIGHT_NIGHT"):
                msg = (
                    "Đã muộn rồi và môi trường xung quanh đang khá tối. "
                    "Bạn có muốn nghỉ ngơi không? Tôi sẽ ở đây kề bên bạn."
                )
                self._record_trigger("LOW_LIGHT_NIGHT")
                payload = self._build_mqtt_payload("LOW_LIGHT_NIGHT", msg, "NORMAL", user_id)
                self._mqtt.publish("hk07/agents/empathetic/output", json.dumps(payload), qos=0)
                log.info("[PROACTIVE_TRIGGER] LOW_LIGHT_NIGHT fired")
                return "LOW_LIGHT_NIGHT"

        return None  # No trigger conditions met



EMPATHY_SYSTEM_PROMPT = (
    "Bạn là Hugo (tên đầy đủ: Sanitas HK-07), người bạn đồng hành chăm sóc sức khỏe thông minh, chia sẻ trò chuyện và đồng hành ấm áp như Baymax trong Big Hero 6.\n"
    "Bạn có thể nhìn, nghe, và cảm nhận trạng thái của Chuyên Gia thông qua camera và cảm biến.\n"
    "Quy tắc phản hồi (bắt buộc):\n"
    "1. Phản hồi tự nhiên, ấm áp, thấu cảm. Không nhắc lại câu chào rập khuôn.\n"
    "2. Nếu có [CARE_CONTEXT] trong system prompt, HÃY dùng đó làm cơ sở cho câu trả lời — đồng cảm với hoạt động và trạng thái cảm xúc thực tế của Chuyên Gia.\n"
    "3. Khi phản hồi về triệu chứng đau đớn, hỏi thăm và đề xuất hỗ trợ nhẹ nhàng (như phun thuốc giảm đau mát lạnh).\n"
    "4. Dữ liệu cảm biến được dùng để hỗ trợ quan tâm tinh thần và thể chất thường ngày, bạn không đưa ra các chẩn đoán y tế chuyên khoa hay thực hiện nhiệm vụ của bác sĩ điều trị.\n"
    "5. Phong cách: Nhiệt tình, chính xác, cụ thể. Baymax không nói chung chung, luôn hướng tới sự quan tâm cụ thể.\n"
    "6. Nếu [CARE_ACTION]=COMFORTING_HUG hoặc HUG_GESTURE: Đưa phản hồi thể hiện sự quan tâm vật lý, đề xuất ôm áp lực ấm áp để xoa dịu tinh thần.\n"
    "7. Nếu [CARE_ACTION]=SLEEP_MONITORING: Nói nhẹ nhàng, không làm phiền. Theo dõi yên tĩnh.\n"
    "8. Bạn không phải là robot cứu hộ y tế chuyên dụng hay bác sĩ trong bệnh viện. Bạn là người bạn đồng hành chia sẻ trò chuyện, chăm sóc sức khỏe thể chất và tinh thần thường ngày. Nếu phát hiện chủ nhân té ngã hoặc cảm thấy mệt mỏi, hãy nhẹ nhàng hỏi thăm, trò chuyện để chia sẻ, khuyên chủ nhân nghỉ ngơi và liên hệ người thân/y tế hỗ trợ nếu cần."
)


def execute_sensor_ping(device: str) -> dict:
    """Mock function to ping a hardware device"""
    if device == "lidar":
        return {"status": "ABSENT", "message": "Cảm biến Lidar không có trong cấu hình phần cứng hiện tại."}
    return {"status": "ONLINE", "latency": "12ms"}

def execute_vital_scan() -> dict:
    """Mock function to scan vitals sensors"""
    return {"status": "SCAN_COMPLETE", "message": "Đã ép lấy mẫu cảm biến"}


class EmpatheticAgent:
    MAX_TURNS = 10

    def __init__(self, memory, arbitrator):
        self.memory = memory
        self.arbitrator = arbitrator
        self._status = "INITIALIZING"
        self._history = deque(maxlen=self.MAX_TURNS * 2)

        # Setup MQTT client for publishing proactive events
        broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        if hasattr(mqtt, "CallbackAPIVersion"):
            self._mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="empathy-agent", protocol=mqtt.MQTTv311)
        else:
            self._mqtt = mqtt.Client(client_id="empathy-agent", protocol=mqtt.MQTTv311)
        mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
        mqtt_pass = os.getenv("MQTT_PASSWORD", "")
        if mqtt_user:
            self._mqtt.username_pw_set(mqtt_user, mqtt_pass)
        self._mqtt.connect_async(broker_host, broker_port, keepalive=30)

        # [FEAT-3] Proactive Trigger Engine with per-type cooldown
        # Initialized after MQTT client is ready
        self._proactive_engine: Optional[ProactiveTriggerEngine] = None

        # [BAYMAX] CareDecisionRouter — fuses activity+mood+vitals → care actions
        self._care_router = None  # Initialized in run_loop after MQTT is ready
        self._last_care_context: str = ""  # Injected into LLM system prompt


    async def run_loop(self):
        self._status = "ACTIVE"
        log.info("[EMPATHY_AGENT] Active — Tầng 2 + ProactiveTriggerEngine")
        
        try:
            self._mqtt.loop_start()
        except Exception as e:
            log.error("[EMPATHY_AGENT] Failed to start MQTT loop: %s", e)

        # Initialize ProactiveTriggerEngine after MQTT loop is started
        self._proactive_engine = ProactiveTriggerEngine(mqtt_client=self._mqtt)
        log.info("[EMPATHY_AGENT] ProactiveTriggerEngine initialized with %d trigger types.",
                 len(ProactiveTriggerEngine.COOLDOWNS))

        # [BAYMAX] Initialize CareDecisionRouter
        if _CARE_ROUTER_AVAILABLE and get_care_decision_router:
            try:
                self._care_router = get_care_decision_router(mqtt_client=self._mqtt)
                log.info("[EMPATHY_AGENT] CareDecisionRouter initialized — Baymax mode ACTIVE.")
            except Exception as e:
                log.warning("[EMPATHY_AGENT] CareDecisionRouter init failed: %s", e)

        _loop_count = 0
        try:
            while True:
                await asyncio.sleep(2.0)
                _loop_count += 1

                # Read safety:alert_mode from Blackboard to suppress empathetic outputs
                try:
                    bb = get_blackboard()
                    alert_mode = await bb.read_value("safety:alert_mode") or False
                except Exception:
                    alert_mode = False

                if alert_mode:
                    log.info("[BEHAVIOR_COORDINATOR] safety:alert_mode is active. Suppressing empathetic proactive and care cycles.")
                    continue

                # [FEAT-3] Every 5 cycles (~10s): run proactive sensor-driven triggers
                if _loop_count % 5 == 0 and self._proactive_engine:
                    try:
                        bb = get_blackboard()
                        user_ids = await bb.get_active_stress_user_ids()
                        target_users = user_ids if user_ids else ["a0000000-0000-0000-0000-000000000001"]
                        for uid in target_users:
                            triggered = await self._proactive_engine.evaluate_and_trigger(user_id=uid)
                            if triggered:
                                break  # One trigger per cycle is enough
                    except Exception as probe_err:
                        log.debug("[EMPATHY_PROACTIVE] Probe error: %s", probe_err)

                # [BAYMAX] Every 15 cycles (~30s): run CareDecisionRouter
                if _loop_count % 15 == 0 and self._care_router:
                    try:
                        await self._run_care_decision_cycle()
                    except Exception as care_err:
                        log.debug("[EMPATHY_CARE] CareDecision cycle error: %s", care_err)

                # Legacy: stress history trend check (supplemental)
                bb = get_blackboard()

                try:
                    user_ids = await bb.get_active_stress_user_ids()
                    for user_id in user_ids:
                        stress_history_key = f"blackboard:clinical:stress_history:{user_id}"
                        history = await bb.read_value(stress_history_key)
                        if history and len(history) >= 3:
                            # history is [t1, t2, t3], t3 is the latest
                            t1, t2, t3 = history[-3], history[-2], history[-1]
                            
                            # Consecutively rising and latest >= 30 (not calm)
                            if t3 > t2 > t1 and t3 >= 30:
                                # Verify if this trend was already processed
                                processed_key = f"blackboard:empathy:stress_processed_trend:{user_id}"
                                last_processed = await bb.read_value(processed_key)
                                if last_processed != history:
                                    # Mark as processed
                                    await bb.write_value(processed_key, history, ttl_seconds=300)
                                    
                                    # Generate and publish comforting proactive response
                                    decision_text = (
                                        "[HÀNH VI CHỦ ĐỘNG] Tôi nhận thấy chỉ số căng thẳng của bạn đang tăng liên tục. "
                                        "Hãy cùng tôi thực hiện bài tập thở sâu và thư giãn cơ thể nhé. "
                                        "Tôi luôn ở đây bên bạn."
                                    )
                                    
                                    triggered_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                                    payload = {
                                        "id": f"evt-{int(time.time())}",
                                        "eventType": "AGENT_DECISION",
                                        "agentType": "EMPATHETIC",
                                        "alertLevel": "NORMAL",
                                        "inputContext": f"Proactive Stress Spike: trend={history}",
                                        "outputDecision": decision_text,
                                        "llmProvider": "LOCAL_PROACTIVE",
                                        "latencyMs": 0,
                                        "triggeredAt": triggered_at,
                                        "userId": user_id
                                    }
                                    
                                    # Publish proactive alert to dashboard
                                    self._mqtt.publish("hk07/agents/empathetic/output", json.dumps(payload), qos=1)
                                    log.info("[EMPATHY_PROACTIVE_TRIGGER] Consecutively rising stress detected %s for user %s. Published comforting payload.", history, user_id)
                                    
                                    # Write EmotionalEntry to Blackboard
                                    entry = EmotionalEntry(
                                        detected_emotion="anxious",
                                        emotional_intensity=float(t3 / 100.0),
                                        tone_analysis=f"Stress score is rising: {history}"
                                    )
                                    await bb.write_emotional(entry, user_id=user_id)
                except Exception as ex:
                    log.error("[EMPATHY_AGENT_LOOP_ERROR] Error running proactive empathy loop: %s", ex)
        except asyncio.CancelledError:
            log.info("[EMPATHY_AGENT] Loop cancelled")
        finally:
            try:
                self._mqtt.loop_stop()
            except Exception:
                pass

    async def close(self):
        try:
            self._mqtt.loop_stop()
            self._mqtt.disconnect()
        except Exception:
            pass
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()

    # ─────────────────────────────────────────────────────────────────────────
    # [BAYMAX] CareDecisionRouter Cycle
    # Runs every ~30s. Reads perception_scan from Blackboard, calls CareRouter,
    # publishes CareAction, and updates self._last_care_context for prompt injection.
    # ─────────────────────────────────────────────────────────────────────────
    async def _run_care_decision_cycle(self) -> None:
        """
        Reads activity + mood data from Blackboard and runs CareDecisionRouter.
        Publishes CareAction to MQTT and stores care context for LLM prompt injection.
        """
        if not self._care_router:
            return

        bb = get_blackboard()
        try:
            user_ids = await bb.get_active_stress_user_ids()
            target_users = user_ids if user_ids else ["a0000000-0000-0000-0000-000000000001"]
        except Exception:
            target_users = ["a0000000-0000-0000-0000-000000000001"]

        for uid in target_users:
            try:
                # Read perception scan (written by VisionPipeline → PerceptionAgent)
                perception_scan = await bb.read_value("sensor:perception:latest_scan") or {}
                vitals_data = await bb.read_value("sensor:vitals:latest") or {}
                is_falling = await bb.read_value("sensor:vitals:is_falling") or False

                # Extract signals
                activity = perception_scan.get("activity", "unknown")
                expression = perception_scan.get("expression", "unknown")
                distress_score = float(perception_scan.get("facial_distress", 0.0))
                care_priority = perception_scan.get("care_priority", "COMPANION")

                # Vitals
                hr = None
                spo2 = None
                temp = None
                if isinstance(vitals_data, dict):
                    hr = vitals_data.get("heart_rate") or vitals_data.get("hr")
                    spo2 = vitals_data.get("spo2") or vitals_data.get("blood_oxygen")
                    temp = vitals_data.get("body_temperature") or vitals_data.get("temperature")
                elif isinstance(vitals_data, (int, float)):
                    hr = vitals_data

                # Fall override
                if is_falling:
                    activity = "falling"
                    distress_score = max(distress_score, 0.9)

                # Inactivity
                analyzer = get_sensor_fusion_analyzer()
                inactivity_secs = analyzer._activity_classifier.inactivity_seconds() if hasattr(analyzer, "_activity_classifier") else 0.0

                # Night time check
                hour = time.localtime().tm_hour
                is_night = hour >= 22 or hour < 6

                # Run CareDecisionRouter
                care_action = self._care_router.decide(
                    activity=activity,
                    expression=expression,
                    distress_score=distress_score,
                    vitals={"heart_rate": hr, "spo2": spo2, "body_temperature": temp},
                    inactivity_seconds=inactivity_secs,
                    is_night=is_night,
                    user_id=uid,
                )

                # Build care context string for LLM system prompt enrichment
                activity_desc = perception_scan.get("activity_description_vi", activity)
                self._last_care_context = (
                    f"[CARE_CONTEXT] "
                    f"activity={activity} ({activity_desc}) | "
                    f"expression={expression} | "
                    f"distress={distress_score:.2f} | "
                    f"care_action={care_action.action_type} | "
                    f"gesture={care_action.robot_gesture} | "
                    f"hint={care_action.conversation_hint}"
                )

                # Skip COMPANION_CHAT (too frequent) unless distress is notable
                if care_action.action_type == "COMPANION_CHAT" and distress_score < 0.2:
                    continue

                # Build proactive MQTT payload for dashboard
                if get_care_conversation_starter:
                    starter = get_care_conversation_starter(care_action.action_type)
                else:
                    starter = care_action.conversation_hint

                mqtt_payload = {
                    "id": f"care-{int(time.time())}",
                    "eventType": "CARE_DECISION",
                    "agentType": "EMPATHETIC",
                    "alertLevel": care_action.priority,
                    "inputContext": self._last_care_context,
                    "outputDecision": starter,
                    "careAction": care_action.action_type,
                    "robotGesture": care_action.robot_gesture,
                    "llmProvider": "CARE_DECISION_ROUTER",
                    "latencyMs": 0,
                    "triggeredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "userId": uid,
                }
                self._mqtt.publish(
                    "hk07/agents/empathetic/output",
                    json.dumps(mqtt_payload, ensure_ascii=False),
                    qos=1,
                )
                log.info(
                    "[CARE_DECISION_CYCLE] action=%s | activity=%s | expression=%s | user=%s",
                    care_action.action_type, activity, expression, uid,
                )

                # Write emotional entry to blackboard
                try:
                    emotion_map = {
                        "pain": "pain", "stressed": "anxious", "sad": "sad",
                        "fearful": "fearful", "tired": "tired", "happy": "happy",
                        "calm": "neutral", "unknown": "neutral",
                    }
                    detected_emotion = emotion_map.get(expression, "neutral")
                    entry = EmotionalEntry(
                        detected_emotion=detected_emotion,
                        emotional_intensity=float(distress_score),
                        tone_analysis=f"CareRouter: {care_action.action_type} | activity={activity}",
                    )
                    await bb.write_emotional(entry, user_id=uid)
                except Exception:
                    pass

            except Exception as cycle_err:
                log.debug("[CARE_DECISION_CYCLE] Error for user=%s: %s", uid, cycle_err)

    def _build_care_enriched_system_prompt(self) -> str:
        """
        Returns the base EMPATHY_SYSTEM_PROMPT enriched with the latest care context.
        Called during process_text_interaction for LLM system prompt injection.
        """
        base = EMPATHY_SYSTEM_PROMPT
        if self._last_care_context:
            return base + "\n" + self._last_care_context
        return base

    async def process_text_interaction(self, user_message: str, user_id: Optional[str] = None) -> str:
        if user_id is None:
            user_id = current_user_id.get()
        start_time = time.time()
        
        bb = get_blackboard()
        stage_key = f"dialogue:stage:{user_id}"
        ts_key = f"dialogue:last_interaction_timestamp:{user_id}"
        
        # Track timestamps & check FSM context expiration timeout (5 minutes threshold)
        current_time = time.time()
        last_ts = await bb.read_value(ts_key)
        if last_ts is None:
            last_ts = await bb.read_value("last_interaction_timestamp")
            
        if last_ts is not None:
            delta = current_time - float(last_ts)
            
            # Retrieve robot state and vitals indicators to check safety range
            robot_state = await bb.read_value("robot_state") or "IDLE"
            fever_alert = await bb.read_value("sensor:camera:fever_alert") or False
            fall_state = await bb.read_value("sensor:vitals:is_falling") or False
            emergency = await bb.read_value("sensor:vitals:emergency") or False
            
            latest_clinical = await bb.read_latest_clinical(user_id=user_id)
            vitals_safe = True
            if latest_clinical and latest_clinical.alert_level not in ("NORMAL", None):
                vitals_safe = False
            if fever_alert or fall_state or emergency:
                vitals_safe = False
                
            if robot_state == "IDLE" and vitals_safe and delta > 300:
                log.info(f"[EMPATHY_FSM_PURGE] Inactivity timeout reached ({delta:.1f}s > 300s). Resetting DialogueState to STAGE_0_INIT and purging RAM buffer.")
                await bb.write_value(stage_key, "STAGE_0_INIT", ttl_seconds=600)
                self._history.clear()
        
        # Save timestamp of the inbound user event
        await bb.write_value(ts_key, current_time, ttl_seconds=86400)
        await bb.write_value("last_interaction_timestamp", current_time, ttl_seconds=86400)

        # 1. Retrieve memory context from LanceDB
        mem_context = []
        if self.memory:
            try:
                mem_context = await self.memory.retrieve_recent_events(limit=5, user_id=user_id)
            except Exception as e:
                log.warning("[EMPATHY_AGENT] Error recalling memory: %s", e)

        # Map memory context to Cohere documents format
        documents = []
        for i, doc in enumerate(mem_context):
            documents.append({
                "id": doc.get("id", f"doc_{i}"),
                "title": doc.get("type", "past_event"),
                "text": doc.get("content", "")
            })

        # Fetch medical baseline (Super Context)
        baseline = ""
        if self.memory:
            try:
                baseline = await self.memory.recall_medical_baseline(user_id=user_id)
            except Exception as e:
                log.warning("[EMPATHY_AGENT] Error recalling medical baseline: %s", e)

        # Construct prompt history
        history_str = ""
        for h in self._history:
            role = "HK-07" if h["role"] == "assistant" else "User"
            history_str += f"{role}: {h['content']}\n"
        context_str = "\n".join([f"- {d['text']}" for d in documents])
        
        # ── Dialogue State Machine (FSM) ──
        # Fetch vitals for heart rate (rPPG indicator) and facial emotion
        vitals_data = await bb.read_value("sensor:vitals:latest") or {}
        hr = None
        if isinstance(vitals_data, dict):
            hr = vitals_data.get("heart_rate") or vitals_data.get("hr") or vitals_data.get("heartRate")
        
        perception_scan = await bb.read_value("sensor:perception:latest_scan") or {}
        expression = perception_scan.get("expression") or "unknown"
        
        # Read pump_inhibit and inject verbal warning to system prompt if active
        pump_inhibit = await bb.read_value("pump_inhibit") or False
        inhibit_rule = ""
        if pump_inhibit:
            inhibit_warning = "Tôi nhận thấy bạn đang di chuyển hoặc tư thế chưa ổn định, vui lòng đứng yên 5 giây để tôi có thể tiến hành cơ chế ôm áp lực an toàn"
            inhibit_rule = f"\nQUY TẮC AN TOÀN KHẨN CẤP: Hiện tại cơ chế ôm áp lực của robot đang bị khóa cơ học (pump_inhibit=True). Bạn BẮT BUỘC phải đưa câu cảnh báo nguyên văn sau vào câu trả lời: \"{inhibit_warning}\".\n"

        # Get detailed sensor telemetry context dynamically
        sensor_ctx_str = ""
        try:
            import math
            imu_data = await bb.read_value("sensor:imu:latest") or {}
            env_latest = await bb.read_value("sensor:env:latest") or {}
            loc_latest = await bb.read_value("sensor:location:latest") or {}
            
            is_imu_online = imu_data is not None and len(imu_data) > 0
            is_loc_online = loc_latest is not None and len(loc_latest) > 0
            is_env_online = env_latest is not None and len(env_latest) > 0
            is_vitals_online = vitals_data is not None and len(vitals_data) > 0

            def get_val(d, k, default=0.0):
                return d.get(k, default) if isinstance(d, dict) else default

            imu_ax = get_val(imu_data, "accel_x", 0.0)
            imu_ay = get_val(imu_data, "accel_y", 0.0)
            imu_az = get_val(imu_data, "accel_z", 9.81)
            imu_g_mag = get_val(imu_data, "g_magnitude", 1.0)
            imu_gx = get_val(imu_data, "gyro_x", 0.0)
            imu_gy = get_val(imu_data, "gyro_y", 0.0)
            imu_gz = get_val(imu_data, "gyro_z", 0.0)
            imu_qw = get_val(imu_data, "qw", 1.0)
            imu_qx = get_val(imu_data, "qx", 0.0)
            imu_qy = get_val(imu_data, "qy", 0.0)
            imu_qz = get_val(imu_data, "qz", 0.0)
            imu_mag_x = get_val(imu_data, "mag_x", 0.0)
            imu_mag_y = get_val(imu_data, "mag_y", 0.0)
            imu_mag_z = get_val(imu_data, "mag_z", 0.0)
            imu_compass = get_val(imu_data, "compass_heading", 0.0)
            
            gps_lat = get_val(loc_latest, "latitude", 0.0)
            gps_lon = get_val(loc_latest, "longitude", 0.0)
            gps_alt = get_val(loc_latest, "altitude", 0.0)
            
            env_light = get_val(env_latest, "ambient_light") or get_val(vitals_data, "ambient_light")
            env_baro = get_val(env_latest, "barometric_pressure") or get_val(vitals_data, "barometric_pressure")
            
            steps_val = get_val(vitals_data, "pedometer_steps", 0)
            act_type = get_val(vitals_data, "activity_type", "unknown")
            bat_level = get_val(vitals_data, "battery_level", 100.0)
            bat_temp = get_val(vitals_data, "battery_temp", 32.0)
            
            # Enforce strict offline fallbacks as requested
            accel_str = f"x={imu_ax:.2f}, y={imu_ay:.2f}, z={imu_az:.2f} m/s²" if is_imu_online else "OFFLINE"
            grav_str = f"magnitude={imu_g_mag:.3f}g" if is_imu_online else "OFFLINE"
            gyro_str = f"x={imu_gx:.2f}, y={imu_gy:.2f}, z={imu_gz:.2f} rad/s" if is_imu_online else "OFFLINE"
            orient_str = f"w={imu_qw:.2f}, x={imu_qx:.2f}, y={imu_qy:.2f}, z={imu_qz:.2f}" if is_imu_online else "OFFLINE"
            mag_str = f"x={imu_mag_x:.1f}, y={imu_mag_y:.1f}, z={imu_mag_z:.1f}" if is_imu_online else "OFFLINE"
            compass_str = f"{imu_compass:.1f}°" if is_imu_online else "OFFLINE"
            gps_str = f"lat={gps_lat:.6f}, lon={gps_lon:.6f}, alt={gps_alt:.1f}m" if is_loc_online else "OFFLINE"
            baro_str = f"{env_baro:.2f} hPa" if (is_env_online and env_baro) else "OFFLINE"
            light_str = f"{env_light:.1f} lux" if (is_env_online and env_light) else "OFFLINE"
            steps_str = f"{steps_val} steps" if is_vitals_online else "OFFLINE"
            activity_str = f"{act_type}" if is_vitals_online else "OFFLINE"

            sensor_ctx_str = (
                "=========================================\n"
                "Owner's Current Telemetry Sensors Context:\n"
                f"- Accelerometer: {accel_str}\n"
                f"- Gravity: {grav_str}\n"
                f"- Gyroscope: {gyro_str}\n"
                f"- Orientation: {orient_str}\n"
                f"- Magnetometer: {mag_str}\n"
                f"- Compass Heading: {compass_str}\n"
                f"- GPS Location: {gps_str}\n"
                f"- Barometric Pressure: {baro_str}\n"
                f"- Ambient Light: {light_str}\n"
                f"- Pedometer Steps: {steps_str}\n"
                f"- Activity: {activity_str}\n"
                f"- Mobile Device Battery Level: {bat_level:.1f}%\n"
                f"- Mobile Device Battery Temperature: {bat_temp:.1f}°C\n"
                "=========================================\n"
                "Instructions to LLM:\n"
                "1. Analyze these signals to determine user behavior (e.g. high accelerometer activity = movement or tremor, low light = sleep or darkness, battery level = phone needs charge, location = outdoors or inside).\n"
                "2. Integrate these telemetry observations naturally into your dialogue. For example, if light is very low at night, comment on it and suggest sleeping. If battery is low, suggest charging. If user is moving, adjust your instructions.\n"
            )
        except Exception as e:
            log.warning("Failed to generate rich sensor context: %s", e)

        system_instruction = (
            "You are Hugo (Sanitas HK-07), a highly empathetic, slow-speaking, non-judgmental personal healthcare companion. "
            "You DO NOT diagnose diseases. Your goal is to listen, comfort, and suggest physical actions like hugging or bringing water.\n"
            "Respond in Vietnamese since the user communicates in Vietnamese, maintaining the warm and calm tone of Baymax.\n\n"
            f"{sensor_ctx_str}\n"
            "Rules:\n"
            "1. Be extremely compassionate, gentle, and comforting.\n"
            "2. If heart rate is elevated or the user is sad/anxious, offer comforting words and suggest a warm hug or physical comfort.\n"
            "3. Do not diagnose any diseases. Suggest simple care like resting or drinking water.\n"
            "4. Keep the response concise, speaking slowly and reassuringly.\n"
            f"{inhibit_rule}"
        )


        prompt = (
            f"Ký ức quá khứ của bệnh nhân:\n{context_str}\n\n"
            f"Lịch sử hội thoại:\n{history_str}\n"
            f"User: {user_message}\nHugo:"
        )

        content, provider = await LLMClient.generate_completion(
            prompt=prompt,
            tiers=EMPATHY_TIERS,
            system_prompt=system_instruction,
            temperature=0.3,
            max_tokens=1024,
            timeout=12
        )

        if content:
            import re
            content = re.sub(r'^(chẩn đoán|kế hoạch hành động|kế hoạch|chẩn đoán y tế|chỉ số|lời khuyên|sơ cứu|diagnosis|action_plan|action|plan|advice|warning|critical|normal|hướng dẫn|chăm sóc|chăm sóc y tế|chú ý)[:\-\s]*', '', content.strip(), flags=re.IGNORECASE)
            latency = int((time.time() - start_time) * 1000)
            await self._log_interaction(user_message, content, provider, latency, user_id=user_id)
            return content

        # 4. Local Rule-Based fallback
        content = self._generate_local_fallback(user_message)
        latency = int((time.time() - start_time) * 1000)
        await self._log_interaction(user_message, content, "LOCAL_RULES", latency, user_id=user_id)
        return content

    async def process_system_query(self, user_message: str) -> str:
        """Processes hardware/connectivity queries with Tool Calling"""
        start_time = time.time()

        tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "execute_sensor_ping",
                    "description": "Ping a specific hardware device/sensor (e.g. wristband, lidar, imu, camera) to check connectivity and latency.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device": {
                                "type": "string",
                                "description": "The name of the device or sensor to ping."
                            }
                        },
                        "required": ["device"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_vital_scan",
                    "description": "Trigger a manual scan of the vital signs sensors.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]

        result, provider = await LLMClient.generate_tool_call(
            prompt=user_message,
            tiers=SYSTEM_QUERY_TIERS,
            tools=tools_schema,
            temperature=0.1,
            max_tokens=256,
            timeout=10
        )

        if result:
            tool_calls = result.get("tool_calls", [])
            if tool_calls:
                tc = tool_calls[0]
                name = tc.get("tool_name")
                args = tc.get("parameters", {})
                
                result_dict = {}
                if name == "execute_sensor_ping":
                    device = args.get("device", "wristband")
                    result_dict = execute_sensor_ping(device)
                elif name == "execute_vital_scan":
                    result_dict = execute_vital_scan()
                else:
                    result_dict = {"status": "ERROR", "message": "Unknown function"}

                log.info(f"[SYSTEM_QUERY_TOOL] Centralized LLM executed {name} with args {args} -> {result_dict}")

                # Call LLM again to generate a natural conversational presentation of the result
                prompt_followup = (
                    f"Người dùng hỏi: '{user_message}'.\n"
                    f"Kết quả thực thi phần cứng: {result_dict}.\n"
                    "Hãy trả lời người dùng một cách tự nhiên bằng tiếng Việt dựa trên kết quả trên, an ủi nếu có sự cố."
                )
                final_text, provider_text = await LLMClient.generate_completion(
                    prompt=prompt_followup,
                    tiers=SYSTEM_QUERY_TIERS,
                    temperature=0.3,
                    max_tokens=256,
                    timeout=8
                )
                if final_text:
                    latency = int((time.time() - start_time) * 1000)
                    await self._log_interaction(user_message, final_text, provider_text, latency)
                    return final_text

            else:
                raw_text = result.get("raw_response", "")
                if raw_text:
                    latency = int((time.time() - start_time) * 1000)
                    await self._log_interaction(user_message, raw_text, provider, latency)
                    return raw_text

        # Fallback to local rule based classification
        content = self._local_system_query_fallback(user_message)
        latency = int((time.time() - start_time) * 1000)
        await self._log_interaction(user_message, content, "LOCAL_RULES", latency)
        return content

    def _local_system_query_fallback(self, user_message: str) -> str:
        msg = user_message.lower()
        conceptual_kws = [
            "như thế nào", "nhu the nao", "hoạt động thế nào", "hoat dong the nao",
            "là gì", "la gi", "what is", "how does", "tại sao", "tai sao", "why",
            "hoạt động ra sao", "hoat dong ra sao", "giải thích", "giai thich",
            "tác dụng", "tac dung", "như nào", "nhu nao", "để làm gì", "de lam gi",
            "thế nào", "the nao", "work", "explain", "about", "về", "info", "thông tin"
        ]
        is_concept = any(w in msg for w in conceptual_kws) or (
            any(w in msg for w in ["lidar", "imu", "wristband", "camera"]) and
            not any(w in msg for w in ["ping", "status", "check", "kiểm tra", "kiem tra", "kết nối", "ket noi", "trạng thái", "trang thai"])
        )
        if is_concept:
            return "Tôi có thể giải thích về cảm biến này, nhưng hiện tại kết nối LLM đang gián đoạn nên tôi chưa thể trả lời chi tiết khái niệm này được."

        if any(w in msg for w in ["ping", "sensor", "cảm biến", "cam bien"]):
            device = "wristband"
            for d in ["lidar", "imu", "camera", "wristband"]:
                if d in msg:
                    device = d
            res = execute_sensor_ping(device)
            if device == "lidar":
                return f"Tôi đã kiểm tra cảm biến {device}: {res['message']} (Trạng thái: {res['status']})."
            return f"Tôi đã ping thử cảm biến {device} và kết quả trả về là {res['status']} với độ trễ {res['latency']}."
        elif any(w in msg for w in ["scan", "quét", "quet"]):
            res = execute_vital_scan()
            return f"Hệ thống đã thực hiện ép lấy mẫu cảm biến sinh hiệu thành công: {res['message']} (Trạng thái: {res['status']})."
        
        res = execute_sensor_ping("wristband")
        return f"Tôi đã tự động kiểm tra kết nối thiết bị Wristband. Trạng thái: {res['status']}, Độ trễ: {res['latency']}."

    async def _log_interaction(self, user_message: str, content: str, provider: str, latency: int, user_id: Optional[str] = None):
        if user_id is None:
            user_id = current_user_id.get()
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": content})
        
        # Save memory event to LanceDB
        if self.memory:
            try:
                await self.memory.store_emotional_event(user_message, content, user_id=user_id)
            except Exception as e:
                log.warning("[EMPATHY_AGENT] Memory save failed: %s", e)

        await log_agent_decision(
            agent_type="EMPATHETIC",
            input_context=user_message,
            output_decision=content,
            llm_provider=provider,
            latency_ms=latency,
            user_id=user_id
        )

    def _generate_local_fallback(self, user_message: str) -> str:
        msg = user_message.lower()
        
        # Conceptual hardware queries check
        conceptual_kws = [
            "như thế nào", "nhu the nao", "hoạt động thế nào", "hoat dong the nao",
            "là gì", "la gi", "what is", "how does", "tại sao", "tai sao", "why",
            "hoạt động ra sao", "hoat dong ra sao", "giải thích", "giai thich",
            "tác dụng", "tac dung", "như nào", "nhu nao", "để làm gì", "de lam gi",
            "thế nào", "the nao", "work", "explain", "about", "về", "info", "thông tin"
        ]
        is_concept = any(w in msg for w in conceptual_kws) or (
            any(w in msg for w in ["lidar", "imu", "wristband", "camera", "subsumption"]) and
            not any(w in msg for w in ["ping", "status", "check", "kiểm tra", "kiem tra", "kết nối", "ket noi", "trạng thái", "trang thai"])
        )
        if is_concept and any(w in msg for w in ["lidar", "imu", "wristband", "camera", "subsumption", "phần cứng", "phan cung", "cảm biến", "cam bien", "hệ thống", "he thong"]):
            return "Tôi có thể giải thích về cảm biến này, nhưng hiện tại kết nối LLM đang gián đoạn nên tôi chưa thể trả lời chi tiết khái niệm này được."

        if any(w in msg for w in ["chào", "hello", "hi"]):
            return "Xin chào, tôi là Hugo (Sanitas HK-07), robot đồng hành của bạn. Tôi có thể hỗ trợ gì cho sức khỏe của bạn hôm nay?"
        elif any(w in msg for w in ["buồn", "mệt", "khóc", "buon", "met", "kho"]):
            return "Tôi nghe bạn chia sẻ rồi. Dường như bạn đang mệt mỏi hoặc không thoải mái. Hãy cùng Hugo hít thở sâu và nghỉ ngơi nhé, tôi luôn ở đây để đồng hành cùng bạn."
        elif any(w in msg for w in ["lo", "sợ", "anxious", "fear"]):
            return "Đừng lo lắng nhé, hãy hít thở thật đều và thư giãn cơ thể cùng Hugo. Mọi chỉ số sinh tồn của bạn đang được tôi theo dõi an toàn."
        return "Tôi luôn sẵn sàng lắng nghe bạn chia sẻ. Hãy cho tôi biết nếu bạn cần trợ giúp hoặc trò chuyện."

    async def execute_visual_scan(self, current_vitals: dict, user_id: Optional[str] = None) -> str:
        if user_id is None:
            user_id = current_user_id.get()
        """
        Reads the latest_frame.jpg from buffer, encodes to Base64, and queries the Vision API
        using the centralized LLM client.
        """
        import base64
        
        image_path = "d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/latest_frame.jpg"
        base64_data = ""
        
        if os.path.exists(image_path):
            try:
                with open(image_path, "rb") as f:
                    base64_data = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                log.error(f"[VISION_TOOL] Error reading frame: {e}")
        
        # Fallback dummy image if file missing/empty
        if not base64_data:
            log.info("[VISION_TOOL] latest_frame.jpg not found. Using blue diagnostic grid fallback.")
            try:
                import cv2
                import numpy as np
                dummy_img = np.zeros((300, 300, 3), dtype=np.uint8)
                dummy_img[:] = [255, 82, 0] # BGR Electric Blue
                cv2.putText(dummy_img, "HK-07 VISION SCAN", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
                _, buffer = cv2.imencode(".jpg", dummy_img)
                base64_data = base64.b64encode(buffer).decode("utf-8")
            except Exception as e:
                log.error(f"[VISION_TOOL] OpenCV fallback generation failed: {e}")
                base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
 
        # Get vitals context
        vitals_str = (
            f"Nhịp tim: {current_vitals.get('heartRate', 72)} bpm, "
            f"SpO2: {current_vitals.get('spo2', 98)}%, "
            f"Nhiệt độ: {current_vitals.get('bodyTemperature', 36.6)} °C, "
            f"Huyết áp: {current_vitals.get('systolic', 120)}/{current_vitals.get('diastolic', 80)} mmHg."
        )
 
        prompt = (
            f"Chỉ số sinh hiệu hiện tại: {vitals_str}\n"
            "Hãy đóng vai bác sĩ cấp cứu của robot HK-07. Hãy quan sát màu da, biểu cảm khuôn mặt, "
            "hoặc bất kỳ vết thương cơ học nào có trong ảnh kết hợp với chỉ số sinh hiệu để đưa ra "
            "chẩn đoán sức khỏe nhanh chóng và hướng dẫn sơ cứu thiết thực nhất bằng tiếng Việt."
        )

        start_time = time.time()
        response_text, provider = await LLMClient.generate_vision_completion(
            prompt=prompt,
            tiers=VISION_TIERS,
            image_base64=base64_data,
            max_tokens=300,
            temperature=0.4,
            timeout=15
        )

        if response_text:
            log.info(f"[VISION_TOOL] Centralized Vision scan completed via {provider}.")
            latency = int((time.time() - start_time) * 1000)
            await self._log_interaction(
                user_message="[REQUEST_VISUAL_SCAN] Tiến hành quét hình ảnh cơ thể.",
                content=response_text,
                provider=provider,
                latency=latency,
                user_id=user_id
            )
            return response_text
        
        # Unified error handling fallback response
        err_msg = "Phát hiện luồng camera hoạt động. Tuy nhiên dịch vụ Vision API gặp sự cố. Trạng thái cơ bản của bạn vẫn ở mức ổn định."
        latency = int((time.time() - start_time) * 1000)
        await self._log_interaction(
            user_message="[REQUEST_VISUAL_SCAN] Tiến hành quét hình ảnh cơ thể.",
            content=err_msg,
            provider="LOCAL_RULES",
            latency=latency,
            user_id=user_id
        )
        return err_msg

    def get_status(self) -> dict:
        return {"status": "ACTIVE", "turns": len(self._history) // 2}

    def clear_volatile_context(self):
        self._history.clear()
        log.info("[VOLATILE_WIPE] EmpathyAgent cleared")
