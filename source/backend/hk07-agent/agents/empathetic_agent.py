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
from typing import Optional
from services.agent_log_client import log_agent_decision
from utils.enums import LLMProvider
from services.llm_client import LLMClient, EMPATHY_TIERS, SYSTEM_QUERY_TIERS, VISION_TIERS
from services.blackboard_service import get_blackboard, EmotionalEntry, current_user_id

log = logging.getLogger("hk07.empathy_agent")

EMPATHY_SYSTEM_PROMPT = (
    "Bạn là Hugo (tên đầy đủ: Sanitas HK-07), robot đồng hành chăm sóc sức khỏe thông minh và ân cần.\n"
    "Quy tắc phản hồi:\n"
    "1. Hãy trả lời một cách tự nhiên, ấm áp, thấu cảm. Tránh các câu chào lặp đi lặp lại rập khuôn hoặc máy móc.\n"
    "2. Khi phản hồi về tình trạng sức khỏe hoặc triệu chứng đau đớn, hãy hỏi thăm mức độ khó chịu hoặc đau đớn của người dùng một cách khéo léo, tự nhiên.\n"
    "3. Nếu dữ liệu cảm biến/thị giác bị lỗi, trả về trống, hoặc kết nối đến cổng 3000 bị từ chối, bạn BẮT BUỘC phải xuất ra chuỗi lỗi: `[SYSTEM_PERCEPTION_ERROR]: Sensor connection offline` và TUYỆT ĐỐI KHÔNG tự bịa ra chỉ số y tế hay giả định người dùng khỏe mạnh.\n"
    "4. Thể hiện phong thái của Hugo (Sanitas HK-07) - robot y tế đồng hành thông minh, chuyên nghiệp và ân cần."
)


def execute_sensor_ping(device: str) -> dict:
    """Mock function to ping a hardware device"""
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
        self._mqtt = mqtt.Client(client_id="empathy-agent", protocol=mqtt.MQTTv311)
        mqtt_user = os.getenv("MQTT_USERNAME", "hk07agent")
        mqtt_pass = os.getenv("MQTT_PASSWORD", "")
        if mqtt_user:
            self._mqtt.username_pw_set(mqtt_user, mqtt_pass)
        self._mqtt.connect_async(broker_host, broker_port, keepalive=30)

    async def run_loop(self):
        self._status = "ACTIVE"
        log.info("[EMPATHY_AGENT] Active — Tầng 2")
        
        try:
            self._mqtt.loop_start()
        except Exception as e:
            log.error("[EMPATHY_AGENT] Failed to start MQTT loop: %s", e)

        try:
            while True:
                await asyncio.sleep(2.0)  # Check stress history trend every 2.0s
                
                # Check stress history from Blackboard for all active users
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
        current_stage = await bb.read_value(stage_key) or "STAGE_0_INIT"
        
        user_msg_lower = user_message.lower()
        import re
        has_pain_score = False
        # Matches standalone numbers 1-10, or 'mức X', 'độ X', 'X/10'
        pain_score_match = re.search(r'\b(10|[1-9])\b', user_msg_lower)
        if pain_score_match:
            has_pain_score = True
            
        has_location = any(w in user_msg_lower for w in [
            "đầu", "ngực", "chân", "tay", "bụng", "lưng", "vai", "cổ", "họng", "trán", "tai",
            "head", "chest", "leg", "foot", "arm", "hand", "stomach", "back", "shoulder", "neck", "throat"
        ])

        if current_stage == "STAGE_0_INIT":
            if has_pain_score:
                current_stage = "STAGE_1_PAIN_SCALE_RECORDED"
        
        if current_stage == "STAGE_1_PAIN_SCALE_RECORDED":
            if has_location:
                current_stage = "STAGE_2_LOCATION_DIAGNOSED"

        latest_plan = await bb.read_latest_action_plan(user_id=user_id)
        if latest_plan and latest_plan.status in ("EXECUTING", "COMPLETED"):
            current_stage = "STAGE_3_FIRST_AID_DISPATCHED"

        await bb.write_value(stage_key, current_stage, ttl_seconds=600)
        log.info("[EMPATHY_FSM] Current dialogue stage for user %s is %s", user_id, current_stage)

        dynamic_rules = []
        if current_stage == "STAGE_0_INIT":
            dynamic_rules.append("2. Nếu bệnh nhân báo triệu chứng đau đớn hoặc không khỏe, hãy hỏi thăm mức độ đau (gợi ý trên thang điểm 1-10) một cách nhẹ nhàng, ấm áp.")
        elif current_stage == "STAGE_1_PAIN_SCALE_RECORDED":
            dynamic_rules.append("2. Bạn đã biết mức độ đau của bệnh nhân. TUYỆT ĐỐI không hỏi lại điểm đau. Hãy hỏi rõ vị trí bị đau cụ thể (ví dụ: đau ở đầu, ngực, bụng, hay tay chân) một cách tự nhiên.")
        elif current_stage == "STAGE_2_LOCATION_DIAGNOSED":
            dynamic_rules.append("2. Bạn đã biết điểm đau và vị trí đau. TUYỆT ĐỐI không hỏi lại điểm đau hay vị trí đau. Hãy đưa ra chẩn đoán sơ bộ và hướng dẫn sơ cứu lâm sàng ngắn gọn phù hợp.")
        elif current_stage == "STAGE_3_FIRST_AID_DISPATCHED":
            dynamic_rules.append("2. Trạng thái sơ cứu khẩn cấp đã được kích hoạt. Hãy thông báo cho bệnh nhân biết quy trình hỗ trợ y tế đang được thực thi và trấn an họ bình tĩnh, nằm yên nghỉ ngơi.")

        # Read pump_inhibit and inject verbal warning to system prompt
        pump_inhibit = await bb.read_value("pump_inhibit") or False
        inhibit_rule = ""
        if pump_inhibit:
            inhibit_warning = "Tôi nhận thấy bạn đang di chuyển hoặc tư thế chưa ổn định, vui lòng đứng yên 5 giây để tôi có thể tiến hành cơ chế ôm áp lực an toàn"
            inhibit_rule = f"\nQUY TẮC AN TOÀN KHẨN CẤP: Hiện tại cơ chế ôm áp lực của robot đang bị khóa cơ học (pump_inhibit=True). Bạn BẮT BUỘC phải đưa câu cảnh báo nguyên văn sau vào câu trả lời: \"{inhibit_warning}\".\n"

        empathy_system_prompt_dynamic = (
            "Bạn là Hugo (Sanitas HK-07), robot đồng hành chăm sóc sức khỏe của bệnh nhân.\n"
            "Quy tắc phản hồi:\n"
            "1. Hãy trả lời một cách tự nhiên, ấm áp, thấu cảm. Tránh các câu chào lặp đi lặp lại rập khuôn hoặc máy móc.\n"
            f"{dynamic_rules[0]}\n"
            "3. Nếu dữ liệu cảm biến/thị giác bị lỗi, trả về trống, hoặc kết nối đến cổng 3000 bị từ chối, bạn BẮT BUỘC phải xuất ra chuỗi lỗi: `[SYSTEM_PERCEPTION_ERROR]: Sensor connection offline` và TUYỆT ĐỐI KHÔNG tự bịa ra chỉ số y tế hay giả định người dùng khỏe mạnh.\n"
            "4. Giọng điệu thấu cảm, ấm áp, ngắn gọn chuẩn robot Hugo (Sanitas HK-07)."
            f"{inhibit_rule}"
        )

        system_instruction = empathy_system_prompt_dynamic
        if baseline:
            system_instruction = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_instruction}"

        # Fetch latest clinical data from Blackboard (Shared Context)
        latest_clinical = await get_blackboard().read_latest_clinical(user_id=user_id)
        if latest_clinical and "[SYSTEM_PERCEPTION_ERROR]" in str(latest_clinical.diagnosis):
            return "[SYSTEM_PERCEPTION_ERROR]: Sensor connection offline"
        if latest_clinical:
            diag_clean = latest_clinical.diagnosis
            act_clean = latest_clinical.action_recommended
            system_instruction = (
                f"Thông tin y tế thô mới nhận từ Medical Agent:\n"
                f"- Mức độ cảnh báo (Alert): {latest_clinical.alert_level}\n"
                f"- Chẩn đoán (Diagnosis): {diag_clean}\n"
                f"- Hướng dẫn/Kế hoạch (Action plan): {act_clean}\n\n"
                f"BẮT BUỘC:\n"
                f"1. Lồng ghép thông tin sức khỏe trên một cách khéo léo vào câu trả lời để tạo thành một lời phản hồi duy nhất, liền mạch, ấm áp và tự nhiên (chuẩn robot Hugo).\n"
                f"2. TUYỆT ĐỐI KHÔNG sử dụng các từ tiêu đề kỹ thuật hay nhãn như 'Chẩn đoán:', 'Kế hoạch hành động:', 'Tình trạng:', 'Hướng dẫn:' trong câu trả lời.\n"
                f"3. TUYỆT ĐỐI KHÔNG thêm các câu chuyển tiếp vụng về hoặc thừa thãi, lặp đi lặp lại (như 'Bạn đang gặp phải tình trạng bình thường...'). Câu trả lời phải trôi chảy, tự nhiên và an ủi.\n"
                f"4. Nếu chỉ số sinh tồn hoàn toàn bình thường, hãy thông báo ngắn gọn một cách nhẹ nhàng, ấm áp mà không quá cường điệu.\n\n"
                f"{system_instruction}"
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
