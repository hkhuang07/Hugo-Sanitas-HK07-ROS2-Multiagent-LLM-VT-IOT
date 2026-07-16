"""
HugoHealthcareFSM — Baymax-style Proactive Healthcare Protocol
HK-07 Agent Engine | Production Module

FSM States (chạy tự động khi người dùng tương tác):
  STAGE_0_GREETING        → Chào hỏi chủ động, giới thiệu Hugo
  STAGE_1_PAIN_ASSESSMENT → Hỏi thang điểm đau 1-10 (Hugo HỎI user)
  STAGE_2_SCAN            → Đọc sensor + kích hoạt camera scan
  STAGE_3_DIAGNOSIS       → Phân tích kết quả + đưa ra nhận xét
  STAGE_4_CARE            → Thực hiện chăm sóc (tư vấn/ôm/phun thuốc)
  STAGE_5_SATISFACTION    → Không kết thúc cho đến khi user xác nhận hài lòng
  STAGE_6_COMPLETE        → Session kết thúc, reset về STAGE_0 sau 5 phút

Nguyên tắc Baymax cốt lõi:
  - Hugo CHỦ ĐỘNG khởi tạo protocol, không chờ user ra lệnh
  - Pain scale là câu HỎI USER, không phải câu tự đánh giá của Hugo
  - Không terminate session cho đến khi user xác nhận "Tôi ổn rồi"
  - Nếu sensor offline → thông báo rõ ràng, không dùng giá trị mặc định
  - Nếu camera offline → nói rõ, đề xuất giải pháp thay thế
"""

import time
import logging
from typing import Optional, Tuple
from enum import Enum

log = logging.getLogger("hk07.healthcare_fsm")


class HealthcareStage(str, Enum):
    STAGE_0_GREETING     = "STAGE_0_GREETING"
    STAGE_1_PAIN         = "STAGE_1_PAIN_ASSESSMENT"
    STAGE_2_SCAN         = "STAGE_2_SCAN"
    STAGE_3_DIAGNOSIS    = "STAGE_3_DIAGNOSIS"
    STAGE_4_CARE         = "STAGE_4_CARE"
    STAGE_5_SATISFACTION = "STAGE_5_SATISFACTION"
    STAGE_6_COMPLETE     = "STAGE_6_COMPLETE"


# ── Pain scale keywords that trigger FSM entry ─────────────────────────────────
PAIN_TRIGGER_KEYWORDS = [
    "đau", "ow", "ouch", "ow đau", "đau quá", "đau lắm", "bị thương",
    "khó chịu", "không ổn", "mệt", "buồn", "sợ", "lo", "chóng mặt",
    "đau đầu", "đau bụng", "đau ngực", "đau lưng", "nhức", "tê",
    "hurt", "pain", "sick", "dizzy", "unwell", "feel bad", "not ok"
]

SATISFACTION_KEYWORDS = [
    "ổn rồi", "tốt rồi", "khỏe rồi", "cảm ơn", "đủ rồi", "ok rồi",
    "hài lòng", "không cần nữa", "được rồi", "xong rồi", "ổn",
    "i'm fine", "i'm ok", "feeling better", "thank you", "done", "good now"
]

PAIN_SCALE_RESPONSE_PATTERN = [
    r'\b([1-9]|10)\b',  # số từ 1-10
    "điểm", "mức", "khoảng", "level"
]


class HugoHealthcareFSM:
    """
    Baymax-style Healthcare FSM.
    
    Usage:
        fsm = HugoHealthcareFSM()
        stage, prompt = await fsm.process(user_message, user_id, blackboard)
        # Return prompt nếu FSM override response, None nếu để LLM xử lý bình thường
    """

    # Stage prompts (Hugo nói gì tại mỗi bước)
    STAGE_PROMPTS = {
        HealthcareStage.STAGE_0_GREETING: (
            "Xin chào! Tôi là Hugo — Trợ lý Đồng hành và Chăm sóc Sức khỏe của bạn. "
            "Tôi được trang bị cảm biến sinh hiệu, camera nhận diện và AI để đồng hành cùng bạn. "
            "Tôi thấy bạn vừa liên lạc với tôi. Bạn có đang cảm thấy khỏe không? "
            "Bạn có muốn tôi kiểm tra sức khỏe cho bạn không?"
        ),
        HealthcareStage.STAGE_1_PAIN: (
            "Tôi nghe bạn đề cập đến cảm giác khó chịu. "
            "Để tôi hiểu rõ hơn tình trạng của bạn: "
            "**Từ thang điểm 1 đến 10, bạn đánh giá cơn đau/khó chịu của mình ở mức nào?** "
            "(1 = gần như không có, 10 = đau cực độ)"
        ),
        HealthcareStage.STAGE_2_SCAN: (
            "Cảm ơn bạn đã cho tôi biết. "
            "Bây giờ tôi sẽ đọc dữ liệu từ các cảm biến và dùng thị giác để kiểm tra tình trạng của bạn. "
            "[INITIATING_SENSOR_READ] Đang đọc dữ liệu sinh hiệu... "
            "[INITIATING_VISION_SCAN] Đang kích hoạt camera để quan sát..."
        ),
        HealthcareStage.STAGE_4_CARE: (
            "Dựa trên những gì tôi quan sát được, tôi có một số đề nghị chăm sóc cho bạn. "
            "Hãy để tôi ở bên cạnh bạn và hỗ trợ bạn qua giai đoạn này."
        ),
        HealthcareStage.STAGE_5_SATISFACTION: (
            "Bạn cảm thấy thế nào bây giờ? "
            "Tôi muốn đảm bảo bạn thực sự ổn trước khi tôi hoàn thành ca chăm sóc này. "
            "**Bạn có hài lòng với sức khỏe hiện tại của mình không?** "
            "(Nếu bạn nói 'Tôi ổn rồi' hoặc 'Cảm ơn', tôi sẽ kết thúc ca chăm sóc)"
        ),
        HealthcareStage.STAGE_6_COMPLETE: (
            "Rất vui được đồng hành cùng bạn. Tôi sẽ tiếp tục theo dõi sức khỏe của bạn "
            "và sẽ liên lạc nếu phát hiện bất kỳ điều gì bất thường. "
            "Hãy nghỉ ngơi đầy đủ và uống đủ nước nhé! 🌿"
        ),
    }

    def __init__(self):
        # Per-user stage state
        self._user_stages: dict[str, str] = {}
        self._user_pain_scores: dict[str, Optional[int]] = {}
        self._user_last_activity: dict[str, float] = {}
        self._SESSION_TIMEOUT_S = 300.0  # 5 minutes inactivity → reset

    def _get_stage(self, user_id: str) -> HealthcareStage:
        stage_str = self._user_stages.get(user_id, HealthcareStage.STAGE_0_GREETING)
        try:
            return HealthcareStage(stage_str)
        except ValueError:
            return HealthcareStage.STAGE_0_GREETING

    def _set_stage(self, user_id: str, stage: HealthcareStage):
        self._user_stages[user_id] = stage.value
        self._user_last_activity[user_id] = time.time()
        log.info("[HEALTHCARE_FSM] User=%s → Stage=%s", user_id, stage.value)

    def _check_session_timeout(self, user_id: str):
        """Auto-reset session if inactive for SESSION_TIMEOUT_S."""
        last = self._user_last_activity.get(user_id, 0)
        if time.time() - last > self._SESSION_TIMEOUT_S:
            if user_id in self._user_stages and self._user_stages[user_id] == HealthcareStage.STAGE_6_COMPLETE:
                # Reset completed session for fresh start
                self._user_stages.pop(user_id, None)
                self._user_pain_scores.pop(user_id, None)
                log.info("[HEALTHCARE_FSM] Session timeout reset for user=%s", user_id)

    def _extract_pain_score(self, message: str) -> Optional[int]:
        """Extract pain score 1-10 from user message."""
        import re
        # Match standalone numbers 1-10
        matches = re.findall(r'\b(10|[1-9])\b', message)
        if matches:
            return int(matches[0])
        # Vietnamese text numbers
        vi_map = {
            "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5,
            "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10,
            "mot": 1, "nham": 5, "sau": 6, "bay": 7, "tam": 8, "chin": 9, "muoi": 10
        }
        msg_lower = message.lower()
        for word, num in vi_map.items():
            if word in msg_lower:
                return num
        return None

    def _is_pain_trigger(self, message: str) -> bool:
        msg_lower = message.lower()
        return any(kw in msg_lower for kw in PAIN_TRIGGER_KEYWORDS)

    def _is_satisfaction_confirmed(self, message: str) -> bool:
        msg_lower = message.lower()
        return any(kw in msg_lower for kw in SATISFACTION_KEYWORDS)

    async def process(
        self,
        user_message: str,
        user_id: str,
        blackboard=None,
    ) -> Tuple[Optional[HealthcareStage], Optional[str]]:
        """
        Process user message through healthcare FSM.
        
        Returns:
            (stage, override_response) — if override_response is not None,
            use it directly instead of calling LLM. Otherwise, let LLM handle.
        """
        self._check_session_timeout(user_id)
        current_stage = self._get_stage(user_id)

        # ── STAGE_0: First interaction — proactive greeting ──────────────────
        if current_stage == HealthcareStage.STAGE_0_GREETING:
            # Check if user message contains pain trigger → skip to STAGE_1
            if self._is_pain_trigger(user_message):
                self._set_stage(user_id, HealthcareStage.STAGE_1_PAIN)
                return HealthcareStage.STAGE_1_PAIN, self.STAGE_PROMPTS[HealthcareStage.STAGE_1_PAIN]
            # Regular greeting → advance to STAGE_1 after greeting
            self._set_stage(user_id, HealthcareStage.STAGE_1_PAIN)
            # Don't override — let LLM generate greeting naturally but inject FSM context
            return HealthcareStage.STAGE_1_PAIN, None

        # ── STAGE_1: Waiting for pain score from user ────────────────────────
        if current_stage == HealthcareStage.STAGE_1_PAIN:
            pain_score = self._extract_pain_score(user_message)
            if pain_score is not None:
                self._user_pain_scores[user_id] = pain_score
                self._set_stage(user_id, HealthcareStage.STAGE_2_SCAN)
                # Acknowledge score and trigger scan stage
                if pain_score <= 3:
                    ack = f"Điểm đau {pain_score}/10 — Mức nhẹ. "
                elif pain_score <= 6:
                    ack = f"Điểm đau {pain_score}/10 — Mức trung bình. Tôi sẽ chú ý theo dõi kỹ hơn. "
                else:
                    ack = f"Điểm đau {pain_score}/10 — Mức cao! Tôi sẽ ưu tiên kiểm tra ngay. "
                return HealthcareStage.STAGE_2_SCAN, ack + self.STAGE_PROMPTS[HealthcareStage.STAGE_2_SCAN]
            # User didn't give a number — re-prompt
            if self._is_pain_trigger(user_message):
                return HealthcareStage.STAGE_1_PAIN, (
                    "Tôi nghe bạn nói đau. Để tôi hiểu rõ hơn — "
                    "**từ thang điểm 1 đến 10, cơn đau của bạn đang ở mức nào?**"
                )
            # User asking something else — let LLM handle but stay in STAGE_1
            return current_stage, None

        # ── STAGE_2: Scan in progress → advance to diagnosis ─────────────────
        if current_stage == HealthcareStage.STAGE_2_SCAN:
            self._set_stage(user_id, HealthcareStage.STAGE_4_CARE)
            return HealthcareStage.STAGE_4_CARE, None

        # ── STAGE_4: Care delivery → after any response move to satisfaction ─
        if current_stage == HealthcareStage.STAGE_4_CARE:
            self._set_stage(user_id, HealthcareStage.STAGE_5_SATISFACTION)
            return HealthcareStage.STAGE_5_SATISFACTION, None

        # ── STAGE_5: Satisfaction gate — must confirm before ending ──────────
        if current_stage == HealthcareStage.STAGE_5_SATISFACTION:
            if self._is_satisfaction_confirmed(user_message):
                self._set_stage(user_id, HealthcareStage.STAGE_6_COMPLETE)
                return HealthcareStage.STAGE_6_COMPLETE, self.STAGE_PROMPTS[HealthcareStage.STAGE_6_COMPLETE]
            # Not yet satisfied — provide care and re-check
            if self._is_pain_trigger(user_message):
                # Pain still present → back to STAGE_1
                self._set_stage(user_id, HealthcareStage.STAGE_1_PAIN)
                return HealthcareStage.STAGE_1_PAIN, (
                    "Tôi thấy bạn vẫn còn khó chịu. Hãy cho tôi đánh giá lại: "
                    "**Từ 1 đến 10, cơn đau hiện tại của bạn ở mức nào?**"
                )
            # Normal conversation but not satisfied — append satisfaction check
            return current_stage, None

        # ── STAGE_6: Completed — allow new session after timeout ─────────────
        if current_stage == HealthcareStage.STAGE_6_COMPLETE:
            # If new pain trigger → restart
            if self._is_pain_trigger(user_message):
                self._set_stage(user_id, HealthcareStage.STAGE_1_PAIN)
                return HealthcareStage.STAGE_1_PAIN, self.STAGE_PROMPTS[HealthcareStage.STAGE_1_PAIN]
            return current_stage, None

        return current_stage, None

    def get_stage_context(self, user_id: str) -> str:
        """Return stage context for injection into LLM system prompt."""
        stage = self._get_stage(user_id)
        pain_score = self._user_pain_scores.get(user_id)
        pain_info = f" | Pain Score: {pain_score}/10" if pain_score is not None else ""
        return f"[HEALTHCARE_FSM_STAGE: {stage.value}{pain_info}]"

    def reset_user_session(self, user_id: str):
        """Manually reset FSM for a user."""
        self._user_stages.pop(user_id, None)
        self._user_pain_scores.pop(user_id, None)
        self._user_last_activity.pop(user_id, None)


# ── Singleton ─────────────────────────────────────────────────────────────────
_healthcare_fsm: Optional[HugoHealthcareFSM] = None


def get_healthcare_fsm() -> HugoHealthcareFSM:
    global _healthcare_fsm
    if _healthcare_fsm is None:
        _healthcare_fsm = HugoHealthcareFSM()
    return _healthcare_fsm
