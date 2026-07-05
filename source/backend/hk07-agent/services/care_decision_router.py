"""
CareDecisionRouter — Hugo-grade Care Action Decision Engine
HK-07 Agent Engine | Production Module

Architecture:
  Multi-input fusion decision engine. Reads:
    - Activity state (from SkeletonActivityClassifier)
    - Mood / expression (from FacialExpressionAnalyzer)
    - Vitals (from SensorFusionBuffer)
    - Blackboard state (from BlackboardService)

  Outputs a CareAction which is:
    1. Dispatched to EmpatheticAgent as conversation context
    2. Published to MQTT for robot physical response (e.g. HUG_GESTURE)
    3. Written to Blackboard for audit trail

Care Action types:
  COMPANION_CHAT       — Default: engage in warm conversation
  EMOTIONAL_SUPPORT    — Owner is sad/stressed: comforting, active listening
  STRESS_RELIEF        — High stress: breathing exercises, calming prompts
  MEDICAL_FIRST_AID    — Pain detected: vitals check, possible SOS escalation
  HUG_GESTURE          — Extreme distress/sadness: physical comfort gesture
  TREATMENT_PROMPT     — Low SpO2/fever/elevated HR: medical guidance
  INACTIVITY_NUDGE     — Prolonged inactivity: gentle movement reminder
  SLEEP_MONITORING     — Owner sleeping: quiet mode, vital monitoring
  TASK_ASSISTANCE      — Owner appears busy (typing/writing): offer help
  FALL_RESPONSE        — Emergency: immediate SOS + voice alert
  DRINKING_REMINDER    — Long sessions: hydration reminder

MQTT Topics published:
  hk07/care/decision     — CareAction payload
  hk07/agents/care/log   — Audit log

DISCLAIMER: This module drives conversation tone and robot gestures.
  NEVER used for clinical diagnosis. Medical decisions go through MedicalAgent.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None  # type: ignore

log = logging.getLogger("hk07.care_decision_router")


# ─── Care Action Schema ───────────────────────────────────────────────────────

@dataclass
class CareAction:
    """
    Structured output of the CareDecisionRouter.
    Dispatched to EmpatheticAgent and MQTT.
    """
    action_type:      str   = "COMPANION_CHAT"
    priority:         str   = "NORMAL"      # NORMAL | WARNING | CRITICAL
    confidence:       float = 0.70

    # Conversation context injected into EmpatheticAgent system prompt
    conversation_hint: str  = ""            # e.g. "Owner is typing, offer to help"
    emotional_tone:    str  = "WARM"        # WARM | CALM | GENTLE | URGENT | PROFESSIONAL

    # Physical robot gesture (published to MQTT for robot body)
    robot_gesture:    str   = "NONE"        # NONE | HUG | BOW | WAVE | APPROACH | BACK_OFF

    # Triggering signals (for audit trail)
    trigger_activity:  str  = "unknown"
    trigger_expression: str = "unknown"
    trigger_vitals:     str = ""

    # Metadata
    triggered_at: float = field(default_factory=time.time)
    user_id:      str   = "default"

    disclaimer: str = (
        "CareDecisionRouter: Behavioral observation only. "
        "Not a clinical recommendation. EmpatheticAgent output only."
    )

    def to_mqtt_payload(self) -> str:
        d = {
            "id":             f"care-{int(self.triggered_at)}",
            "actionType":     self.action_type,
            "priority":       self.priority,
            "conversationHint": self.conversation_hint,
            "emotionalTone":  self.emotional_tone,
            "robotGesture":   self.robot_gesture,
            "triggerActivity": self.trigger_activity,
            "triggerExpression": self.trigger_expression,
            "triggeredAt":    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.triggered_at)),
            "userId":         self.user_id,
        }
        return json.dumps(d, ensure_ascii=False)


# ─── Priority weights ─────────────────────────────────────────────────────────
_PRIORITY_NUM = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}


# ─── Decision Table ───────────────────────────────────────────────────────────
# (activity, expression) → (action_type, priority, conversation_hint, gesture)
_DECISION_TABLE: List[Dict[str, Any]] = [
    # ── FALL (always highest priority regardless of expression) ───────────────
    {
        "activity_match": ["falling"],
        "expression_match": None,  # any
        "action_type": "FALL_RESPONSE",
        "priority": "CRITICAL",
        "conversation_hint": "Sếp ơi, hãy nằm yên, tôi đang gửi tín hiệu SOS khẩn cấp đến mọi người!",
        "emotional_tone": "URGENT",
        "robot_gesture": "BACK_OFF",
        "confidence": 0.95,
    },
    # ── SLEEPING ─────────────────────────────────────────────────────────────
    {
        "activity_match": ["sleeping"],
        "expression_match": None,
        "action_type": "SLEEP_MONITORING",
        "priority": "NORMAL",
        "conversation_hint": "Owner is sleeping. Activate quiet mode. Monitor vitals silently. Do not disturb.",
        "emotional_tone": "CALM",
        "robot_gesture": "NONE",
        "confidence": 0.90,
    },
    # ── LYING DOWN + SAD/PAIN/STRESSED/FEARFUL → comforting hug ───────────────
    {
        "activity_match": ["lying_down", "sitting_still"],
        "expression_match": ["sad", "stressed", "fearful"],
        "action_type": "COMFORTING_HUG",
        "priority": "WARNING",
        "conversation_hint": "Sếp đang buồn hoặc lo lắng. Hugo đề xuất ôm an ủi nhé.",
        "emotional_tone": "GENTLE",
        "robot_gesture": "HUG",
        "confidence": 0.85,
    },
    # ── PAIN (any activity) → spray medicine ──────────────────────────────────
    {
        "activity_match": None,  # any activity
        "expression_match": ["pain"],
        "action_type": "SPRAY_MEDICINE",
        "priority": "WARNING",
        "conversation_hint": "Phát hiện sếp bị đau. Hugo đề xuất phun thuốc/sương giảm đau làm mát nhẹ nhàng.",
        "emotional_tone": "GENTLE",
        "robot_gesture": "SPRAY",
        "confidence": 0.85,
    },
    # ── STRESSED / FEARFUL (any) → stress relief / hug ───────────────────────
    {
        "activity_match": None,
        "expression_match": ["stressed", "fearful", "angry"],
        "action_type": "STRESS_RELIEF",
        "priority": "WARNING",
        "conversation_hint": "Owner appears stressed or fearful. Offer calming conversation or breathing exercise.",
        "emotional_tone": "CALM",
        "robot_gesture": "NONE",
        "confidence": 0.76,
    },
    # ── SAD + SITTING → comforting hug ────────────────────────────────────────
    {
        "activity_match": ["sitting_still", "lying_down"],
        "expression_match": ["sad"],
        "action_type": "COMFORTING_HUG",
        "priority": "WARNING",
        "conversation_hint": "Sếp ơi, đừng buồn nhé. Hãy để Hugo trao sếp một cái ôm ấm áp nhé.",
        "emotional_tone": "WARM",
        "robot_gesture": "HUG",
        "confidence": 0.82,
    },
    # ── TYPING / WRITING → task assistance ───────────────────────────────────
    {
        "activity_match": ["typing", "writing"],
        "expression_match": ["calm", "happy", "unknown", None],
        "action_type": "TASK_ASSISTANCE",
        "priority": "NORMAL",
        "conversation_hint": "Owner is working (typing/writing). Offer help only if asked. Be non-intrusive.",
        "emotional_tone": "PROFESSIONAL",
        "robot_gesture": "NONE",
        "confidence": 0.72,
    },
    # ── TYPING + STRESSED → check in ──────────────────────────────────────────
    {
        "activity_match": ["typing", "writing"],
        "expression_match": ["stressed", "tired"],
        "action_type": "STRESS_RELIEF",
        "priority": "WARNING",
        "conversation_hint": "Owner is working but looks stressed/tired. Suggest a short break or eye rest.",
        "emotional_tone": "GENTLE",
        "robot_gesture": "NONE",
        "confidence": 0.80,
    },
    # ── EATING → companion ────────────────────────────────────────────────────
    {
        "activity_match": ["eating", "drinking"],
        "expression_match": None,
        "action_type": "COMPANION_CHAT",
        "priority": "NORMAL",
        "conversation_hint": "Owner is eating or drinking. Light companion chat. Don't interrupt meal.",
        "emotional_tone": "WARM",
        "robot_gesture": "NONE",
        "confidence": 0.70,
    },
    # ── PHONE USE → companion ────────────────────────────────────────────────
    {
        "activity_match": ["phone_use"],
        "expression_match": None,
        "action_type": "COMPANION_CHAT",
        "priority": "NORMAL",
        "conversation_hint": "Owner is on the phone. Standby mode. Only respond if explicitly addressed.",
        "emotional_tone": "CALM",
        "robot_gesture": "NONE",
        "confidence": 0.68,
    },
    # ── HAPPY + ANY → positive companion ─────────────────────────────────────
    {
        "activity_match": None,
        "expression_match": ["happy"],
        "action_type": "COMPANION_CHAT",
        "priority": "NORMAL",
        "conversation_hint": "Owner is in a happy mood. Engage positively, share their energy.",
        "emotional_tone": "WARM",
        "robot_gesture": "WAVE",
        "confidence": 0.75,
    },
    # ── SITTING + TIRED → rest reminder ──────────────────────────────────────
    {
        "activity_match": ["sitting_still", "leaning_forward"],
        "expression_match": ["tired"],
        "action_type": "EMOTIONAL_SUPPORT",
        "priority": "NORMAL",
        "conversation_hint": "Owner looks tired. Suggest rest: 'Sếp có muốn nghỉ một chút không?'",
        "emotional_tone": "GENTLE",
        "robot_gesture": "NONE",
        "confidence": 0.73,
    },
    # ── DEFAULT: companion ────────────────────────────────────────────────────
    {
        "activity_match": None,
        "expression_match": None,
        "action_type": "COMPANION_CHAT",
        "priority": "NORMAL",
        "conversation_hint": "Standard companion mode. Be warm and available.",
        "emotional_tone": "WARM",
        "robot_gesture": "NONE",
        "confidence": 0.60,
    },
]


class CareDecisionRouter:
    """
    Fuses activity + expression + vitals → CareAction.
    
    Usage:
        router = CareDecisionRouter(mqtt_client)
        care_action = router.decide(
            activity="typing",
            expression="stressed",
            vitals={"heart_rate": 105, "spo2": 97},
            inactivity_seconds=7200,
            user_id="owner-uuid"
        )
    """

    # Per-action cooldown (seconds) — prevents spamming the same care action
    ACTION_COOLDOWNS: Dict[str, float] = {
        "FALL_RESPONSE":     15.0,
        "EMERGENCY_ALERT":   30.0,
        "MEDICAL_FIRST_AID": 120.0,
        "EMOTIONAL_SUPPORT": 300.0,
        "STRESS_RELIEF":     180.0,
        "HUG_GESTURE":       600.0,
        "COMFORTING_HUG":    180.0,
        "SPRAY_MEDICINE":    180.0,
        "WARM_ADVICE":       180.0,
        "TREATMENT_PROMPT":  300.0,
        "INACTIVITY_NUDGE":  1800.0,
        "SLEEP_MONITORING":  300.0,
        "TASK_ASSISTANCE":   600.0,
        "COMPANION_CHAT":    60.0,
        "DRINKING_REMINDER": 3600.0,
    }
    GLOBAL_CARE_COOLDOWN_S = 30.0  # Minimum 30s between any care action publications

    def __init__(self, mqtt_client=None):
        self._mqtt = mqtt_client
        self._last_action_ts: Dict[str, float] = {}
        self._last_global_ts: float = 0.0
        self._last_action: Optional[CareAction] = None

    def decide(
        self,
        activity: str = "unknown",
        expression: str = "unknown",
        distress_score: float = 0.0,
        vitals: Optional[Dict[str, Any]] = None,
        inactivity_seconds: float = 0.0,
        is_night: bool = False,
        user_id: str = "default",
    ) -> CareAction:
        """
        Main decision function. Returns CareAction (never raises).
        
        Args:
            activity:           From SkeletonActivityClassifier
            expression:         From FacialExpressionAnalyzer
            distress_score:     0.0–1.0 facial distress
            vitals:             dict with heart_rate, spo2, body_temperature etc
            inactivity_seconds: From SkeletonActivityClassifier
            is_night:           True if current hour is 22:00–06:00
            user_id:            Target user UUID
        Returns:
            CareAction to dispatch
        """
        vitals = vitals or {}

        # ── Vitals-based overrides (highest priority after fall) ───────────────
        vitals_override = self._check_vitals_override(vitals, user_id)
        if vitals_override:
            return self._maybe_publish(vitals_override)

        # ── Inactivity nudge ───────────────────────────────────────────────────
        if inactivity_seconds > 7200 and not self._on_cooldown("INACTIVITY_NUDGE"):
            hours = inactivity_seconds / 3600
            action = CareAction(
                action_type="INACTIVITY_NUDGE",
                priority="NORMAL",
                confidence=0.80,
                conversation_hint=f"Owner has been inactive for {hours:.1f}h. Suggest gentle movement or stretch.",
                emotional_tone="GENTLE",
                robot_gesture="NONE",
                trigger_activity=activity,
                trigger_expression=expression,
                user_id=user_id,
            )
            return self._maybe_publish(action)

        # ── Drinking reminder after long work sessions ────────────────────────
        if inactivity_seconds > 3600 and activity in ("typing", "writing", "sitting_still") \
                and not self._on_cooldown("DRINKING_REMINDER"):
            action = CareAction(
                action_type="DRINKING_REMINDER",
                priority="NORMAL",
                confidence=0.75,
                conversation_hint="Owner has been working for over an hour. Remind to drink water.",
                emotional_tone="WARM",
                robot_gesture="NONE",
                trigger_activity=activity,
                trigger_expression=expression,
                user_id=user_id,
            )
            return self._maybe_publish(action)

        # ── Distress score override (expression-based high distress) ──────────
        if distress_score >= 0.65 and not self._on_cooldown("EMOTIONAL_SUPPORT"):
            action = CareAction(
                action_type="EMOTIONAL_SUPPORT",
                priority="WARNING",
                confidence=round(distress_score, 2),
                conversation_hint=f"High facial distress detected (score={distress_score:.2f}). Be empathetic and ask what's wrong.",
                emotional_tone="GENTLE",
                robot_gesture="BOW" if distress_score > 0.80 else "NONE",
                trigger_activity=activity,
                trigger_expression=expression,
                user_id=user_id,
            )
            return self._maybe_publish(action)

        # ── Decision table lookup ──────────────────────────────────────────────
        best: Optional[Dict[str, Any]] = None
        best_conf = -1.0
        for rule in _DECISION_TABLE:
            act_match = rule["activity_match"]
            expr_match = rule["expression_match"]

            if act_match is not None and activity not in act_match:
                continue
            if expr_match is not None and expression not in expr_match:
                continue

            conf = rule["confidence"]
            if conf > best_conf:
                best_conf = conf
                best = rule

        if best is None:
            best = _DECISION_TABLE[-1]  # DEFAULT: companion

        action_type = best["action_type"]

        # Check cooldown
        if self._on_cooldown(action_type):
            # Return last action or default companion
            if self._last_action:
                return self._last_action
            return CareAction(
                action_type="COMPANION_CHAT",
                priority="NORMAL",
                confidence=0.50,
                conversation_hint="Standard companion mode.",
                emotional_tone="WARM",
                trigger_activity=activity,
                trigger_expression=expression,
                user_id=user_id,
            )

        vitals_str = ""
        if vitals:
            hr = vitals.get("heart_rate")
            spo2 = vitals.get("spo2")
            if hr:
                vitals_str += f"HR={hr:.0f}bpm"
            if spo2:
                vitals_str += f" SpO2={spo2:.1f}%"

        action = CareAction(
            action_type=action_type,
            priority=best["priority"],
            confidence=round(best_conf, 2),
            conversation_hint=best["conversation_hint"],
            emotional_tone=best["emotional_tone"],
            robot_gesture=best["robot_gesture"],
            trigger_activity=activity,
            trigger_expression=expression,
            trigger_vitals=vitals_str,
            user_id=user_id,
        )
        return self._maybe_publish(action)

    def _check_vitals_override(
        self, vitals: Dict[str, Any], user_id: str
    ) -> Optional[CareAction]:
        """Returns vitals-based clinical actions (EMERGENCY_ALERT or WARM_ADVICE or TREATMENT_PROMPT)."""
        hr = vitals.get("heart_rate")
        spo2 = vitals.get("spo2")
        temp = vitals.get("body_temperature")

        # 1. Check critical conditions first -> EMERGENCY_ALERT (Safety first: stay back, broadcast)
        critical_reasons = []
        if spo2 and spo2 < 88:
            critical_reasons.append(f"SpO2={spo2:.1f}% (critical hypoxemia)")
        if hr and (hr > 140 or hr < 40):
            critical_reasons.append(f"HR={hr:.0f}bpm (critical heart rate)")

        if critical_reasons:
            if not self._on_cooldown("EMERGENCY_ALERT"):
                reason_str = "; ".join(critical_reasons)
                return CareAction(
                    action_type="EMERGENCY_ALERT",
                    priority="CRITICAL",
                    confidence=0.95,
                    conversation_hint=f"Cảnh báo nguy kịch: {reason_str}. Sếp ơi, hãy nằm yên, tôi đang phát tín hiệu SOS khẩn cấp!",
                    emotional_tone="URGENT",
                    robot_gesture="BACK_OFF",
                    trigger_vitals=reason_str,
                    user_id=user_id,
                )

        # 2. Check body temp low -> WARM_ADVICE
        if temp and temp < 36.0:
            if not self._on_cooldown("WARM_ADVICE"):
                return CareAction(
                    action_type="WARM_ADVICE",
                    priority="WARNING",
                    confidence=0.90,
                    conversation_hint=f"Thân nhiệt thấp ({temp:.1f}°C). Hugo đề nghị sưởi ấm và khuyên sếp giữ ấm cơ thể.",
                    emotional_tone="GENTLE",
                    robot_gesture="WARM_BODY",
                    trigger_vitals=f"Temp={temp:.1f}°C (low)",
                    user_id=user_id,
                )

        # 3. Standard warnings -> TREATMENT_PROMPT
        if self._on_cooldown("TREATMENT_PROMPT"):
            return None

        reasons = []
        priority = "NORMAL"
        if hr and (hr > 120 or hr < 45):
            reasons.append(f"HR={hr:.0f}bpm (outside normal range)")
            priority = "WARNING"
        if spo2 and spo2 < 93:
            reasons.append(f"SpO2={spo2:.1f}% (borderline)")
            priority = "WARNING"
        if temp and temp > 38.5:
            reasons.append(f"Temp={temp:.1f}°C (fever)")
            priority = "WARNING"

        if not reasons:
            return None

        reason_str = "; ".join(reasons)
        return CareAction(
            action_type="TREATMENT_PROMPT",
            priority=priority,
            confidence=0.90,
            conversation_hint=f"Vitals alert: {reason_str}. Ask how owner feels and offer medical guidance.",
            emotional_tone="PROFESSIONAL",
            robot_gesture="NONE",
            trigger_vitals=reason_str,
            user_id=user_id,
        )

    def _on_cooldown(self, action_type: str) -> bool:
        now = time.time()
        if now - self._last_global_ts < self.GLOBAL_CARE_COOLDOWN_S:
            return True
        cooldown = self.ACTION_COOLDOWNS.get(action_type, 60.0)
        last = self._last_action_ts.get(action_type, 0.0)
        return (now - last) < cooldown

    def _record(self, action: CareAction) -> None:
        now = time.time()
        self._last_action_ts[action.action_type] = now
        self._last_global_ts = now
        self._last_action = action

    def _maybe_publish(self, action: CareAction) -> CareAction:
        """Publish to MQTT if client available, then record."""
        # Central Behavior Coordinator: Suppress normal actions during alert mode
        try:
            from services.blackboard_service import get_blackboard
            bb = get_blackboard()
            alert_mode_cached = bb._in_memory_store.get("safety:alert_mode")
            alert_mode = False
            if alert_mode_cached:
                import time as tm
                if tm.time() <= alert_mode_cached.get("expiry", 0.0):
                    alert_mode = alert_mode_cached.get("value", False)
            if alert_mode and action.priority == "NORMAL":
                log.info("[BEHAVIOR_COORDINATOR] Alert mode is active. Suppressing normal priority care action: %s", action.action_type)
                return action
        except Exception as e:
            log.warning("[BEHAVIOR_COORDINATOR] Failed to check safety:alert_mode in CareDecisionRouter: %s", e)

        self._record(action)

        if self._mqtt:
            try:
                self._mqtt.publish(
                    "hk07/care/decision",
                    action.to_mqtt_payload(),
                    qos=1,
                )
                log.info(
                    "[CARE_ROUTER] Published action=%s priority=%s gesture=%s",
                    action.action_type, action.priority, action.robot_gesture,
                )
            except Exception as e:
                log.warning("[CARE_ROUTER] MQTT publish failed: %s", e)
        else:
            log.debug("[CARE_ROUTER] action=%s (no MQTT client)", action.action_type)

        return action

    def get_status(self) -> Dict[str, Any]:
        return {
            "last_action": self._last_action.action_type if self._last_action else None,
            "last_global_ts": self._last_global_ts,
            "cooldowns": {k: round(time.time() - v, 1) for k, v in self._last_action_ts.items()},
        }


# ─── Vietnamese conversation starters by action type ────────────────────────
CARE_CONVERSATION_STARTERS_VI: Dict[str, List[str]] = {
    "FALL_RESPONSE": [
        "🚨 Sếp ơi! Hãy nằm yên, đừng cố cử động. Tôi phát hiện bạn bị ngã và đã gửi thông báo cảnh báo đến người thân để kiểm tra giúp bạn.",
        "🚨 Sếp ơi! Tránh di chuyển nhé. Tôi đã gửi thông báo cảnh báo đến người thân/người giám hộ để hỗ trợ bạn.",
    ],
    "EMERGENCY_ALERT": [
        "🚨 Chỉ số sinh hiệu bất thường! Hugo đề nghị sếp nằm nghỉ ngơi tại chỗ, tôi đã gửi thông báo cảnh báo đến người thân để theo dõi.",
        "🚨 Sếp ơi, nhịp tim hoặc SpO2 của bạn đang bất thường. Hãy thở đều và nằm yên nghỉ ngơi nhé, tôi đã thông báo cho người thân của sếp.",
    ],
    "EMOTIONAL_SUPPORT": [
        "Tôi nhận thấy bạn có vẻ không ổn. Bạn có muốn chia sẻ với tôi không?",
        "Tôi luôn ở đây bên bạn. Có điều gì đang làm bạn buồn không?",
        "Hôm nay thế nào, Sếp? Trông bạn có vẻ mệt mỏi một chút.",
    ],
    "STRESS_RELIEF": [
        "Bạn có vẻ đang căng thẳng. Hãy thử hít thở sâu cùng tôi nhé?",
        "Tôi thấy bạn đang có nhiều áp lực. Chúng ta nghỉ một chút nhé?",
    ],
    "SPRAY_MEDICINE": [
        "Hugo nhận thấy sếp có vẻ đang đau. Hugo đề xuất phun một lớp sương lạnh giảm đau nhé? Sẽ dễ chịu hơn nhiều đấy.",
        "Trông sếp có vẻ đang bị đau. Để Hugo phun thuốc/sương làm dịu vùng bị đau cho sếp nhé?",
    ],
    "WARM_ADVICE": [
        "Thân nhiệt của sếp đang thấp. Sếp có muốn Hugo bật chế độ sưởi ấm và mang một chiếc chăn ấm cho sếp không?",
        "Sếp ơi, trời lạnh hoặc thân nhiệt sếp hơi thấp rồi. Hãy mặc thêm áo ấm và để Hugo hỗ trợ tỏa nhiệt sưởi ấm nhé.",
    ],
    "COMFORTING_HUG": [
        "Hugo thấy sếp đang buồn hoặc căng thẳng. Hugo ôm sếp một cái thật ấm áp nhé? ('ôm áp lực')",
        "Đừng buồn nhé sếp, Hugo luôn ở đây. Hãy để Hugo trao sếp một cái ôm ấm áp để làm dịu tâm trạng nhé.",
    ],
    "TASK_ASSISTANCE": [
        "Trông bạn đang bận làm việc! Tôi có thể giúp gì không?",
        "Cần tôi nhắc bạn về deadline hay tìm thông tin gì không Sếp?",
    ],
    "INACTIVITY_NUDGE": [
        "Bạn đã ngồi khá lâu rồi đấy! Đứng dậy vận động một chút nhé?",
        "Hãy giãn cơ một chút đi Sếp — tốt cho cột sống lắm đấy!",
    ],
    "TREATMENT_PROMPT": [
        "Tôi thấy chỉ số sinh hiệu của bạn có chút bất thường. Bạn cảm thấy thế nào?",
        "Để tôi giúp bạn theo dõi sức khỏe nhé. Bạn có đang cảm thấy khó chịu không?",
    ],
    "COMPANION_CHAT": [
        "Chào Sếp! Hôm nay bạn thế nào rồi?",
        "Bạn đang làm gì vậy? Kể tôi nghe với!",
    ],
    "DRINKING_REMINDER": [
        "Sếp ơi, bạn đã uống nước chưa? Làm việc lâu thế này cần giữ nước nhé!",
    ],
    "SLEEP_MONITORING": [
        "Sếp đang ngủ... Tôi sẽ theo dõi nhẹ nhàng và không làm phiền.",
    ],
}


def get_care_conversation_starter(action_type: str) -> str:
    """Get a random conversation starter for a given care action type."""
    import random
    starters = CARE_CONVERSATION_STARTERS_VI.get(action_type, CARE_CONVERSATION_STARTERS_VI["COMPANION_CHAT"])
    return random.choice(starters)


# Module-level singleton
_care_router: Optional[CareDecisionRouter] = None


def get_care_decision_router(mqtt_client=None) -> CareDecisionRouter:
    """Get or create the singleton CareDecisionRouter."""
    global _care_router
    if _care_router is None:
        _care_router = CareDecisionRouter(mqtt_client=mqtt_client)
    elif mqtt_client and _care_router._mqtt is None:
        _care_router._mqtt = mqtt_client
    return _care_router
