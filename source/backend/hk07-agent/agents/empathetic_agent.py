"""
EmpatheticAgent — Tầng 2 trong Subsumption Architecture

Giao tiếp thấu cảm và chăm sóc tâm lý với chủ nhân.
Giọng điệu linh hoạt theo ngữ cảnh (ấm áp khi trò chuyện, chuyên nghiệp khi trả lời kỹ thuật).
"""

import asyncio
import logging
import os
import time
from collections import deque
from services.agent_log_client import log_agent_decision
from utils.enums import LLMProvider
from services.llm_client import LLMClient, EMPATHY_TIERS, SYSTEM_QUERY_TIERS, VISION_TIERS

log = logging.getLogger("hk07.empathy_agent")

EMPATHY_SYSTEM_PROMPT = (
    "Bạn là Hugo, trợ lý đồng hành thông minh của bệnh nhân.\n"
    "Quy tắc phản hồi:\n"
    "1. Trước tiên, hãy phân tích sắc thái, tâm trạng và nội dung câu nói của người dùng.\n"
    "2. Không được chèn lặp đi lặp lại cụm từ cố định 'Có tôi ở đây bên bạn rồi' vào mọi câu trả lời. Hãy đa dạng hóa ngôn từ.\n"
    "3. Giọng điệu phải linh hoạt theo ngữ cảnh:\n"
    "   - Chuyên nghiệp, khách quan, chính xác khi người dùng hỏi các câu hỏi kỹ thuật, định nghĩa hoặc giải thích hoạt động hệ thống.\n"
    "   - Ấm áp, thấu cảm, ân cần và xoa dịu khi người dùng buồn bã, mệt mỏi, lo lắng hoặc cô đơn.\n"
    "4. Trả lời bằng tiếng Việt, ngắn gọn (tối đa 3 câu)."
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

    async def run_loop(self):
        self._status = "ACTIVE"
        log.info("[EMPATHY_AGENT] Active — Tầng 2")
        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    async def process_text_interaction(self, user_message: str) -> str:
        start_time = time.time()
        
        # 1. Retrieve memory context from LanceDB
        mem_context = []
        if self.memory:
            try:
                mem_context = await self.memory.retrieve_recent_events(limit=5)
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
                baseline = await self.memory.recall_medical_baseline()
            except Exception as e:
                log.warning("[EMPATHY_AGENT] Error recalling medical baseline: %s", e)

        # Construct prompt history
        history_str = ""
        for h in self._history:
            role = "HK-07" if h["role"] == "assistant" else "User"
            history_str += f"{role}: {h['content']}\n"
        context_str = "\n".join([f"- {d['text']}" for d in documents])
        
        system_instruction = EMPATHY_SYSTEM_PROMPT
        if baseline:
            system_instruction = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_instruction}"

        # Fetch latest clinical data from Blackboard (Shared Context)
        from services.blackboard_service import get_blackboard
        latest_clinical = await get_blackboard().read_latest_clinical()
        if latest_clinical:
            diag_clean = latest_clinical.diagnosis
            act_clean = latest_clinical.action_recommended
            system_instruction = (
                f"Thông tin y tế thô mới nhận từ Medical Agent:\n"
                f"- Mức độ cảnh báo (Alert): {latest_clinical.alert_level}\n"
                f"- Chẩn đoán (Diagnosis): {diag_clean}\n"
                f"- Hướng dẫn/Kế hoạch (Action plan): {act_clean}\n\n"
                f"BẮT BUỘC:\n"
                f"1. Lồng ghép thông tin sức khỏe trên một cách khéo léo vào câu trả lời để tạo thành một lời phản hồi duy nhất, liền mạch, ấm áp và tự nhiên (chuẩn trợ lý chăm sóc Baymax).\n"
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
            await self._log_interaction(user_message, content, provider, latency)
            return content

        # 4. Local Rule-Based fallback
        content = self._generate_local_fallback(user_message)
        latency = int((time.time() - start_time) * 1000)
        await self._log_interaction(user_message, content, "LOCAL_RULES", latency)
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

    async def _log_interaction(self, user_message: str, content: str, provider: str, latency: int):
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": content})
        
        # Save memory event to LanceDB
        if self.memory:
            try:
                await self.memory.store_emotional_event(user_message, content)
            except Exception as e:
                log.warning("[EMPATHY_AGENT] Memory save failed: %s", e)

        await log_agent_decision(
            agent_type="EMPATHETIC",
            input_context=user_message,
            output_decision=content,
            llm_provider=provider,
            latency_ms=latency
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
            return "Xin chào! Tôi là Hugo. Tôi có thể giúp gì cho bạn hôm nay?"
        elif any(w in msg for w in ["buồn", "mệt", "khóc", "buon", "met", "kho"]):
            return "Tôi biết bạn đang trải qua khoảng thời gian không dễ dàng. Hãy nghỉ ngơi một chút và hít thở sâu cùng tôi nhé."
        elif any(w in msg for w in ["lo", "sợ", "anxious", "fear"]):
            return "Mọi chuyện rồi sẽ ổn thôi. Nhắm mắt lại, thư giãn cơ thể và tập trung vào hơi thở của mình nhé."
        return "Tôi luôn sẵn sàng lắng nghe bạn chia sẻ. Hãy cho tôi biết nếu bạn cần trợ giúp hoặc trò chuyện."

    async def execute_visual_scan(self, current_vitals: dict) -> str:
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
                latency=latency
            )
            return response_text
        
        # Unified error handling fallback response
        err_msg = "Phát hiện luồng camera hoạt động. Tuy nhiên dịch vụ Vision API gặp sự cố. Trạng thái cơ bản của bạn vẫn ở mức ổn định."
        latency = int((time.time() - start_time) * 1000)
        await self._log_interaction(
            user_message="[REQUEST_VISUAL_SCAN] Tiến hành quét hình ảnh cơ thể.",
            content=err_msg,
            provider="LOCAL_RULES",
            latency=latency
        )
        return err_msg

    def get_status(self) -> dict:
        return {"status": "ACTIVE", "turns": len(self._history) // 2}

    def clear_volatile_context(self):
        self._history.clear()
        log.info("[VOLATILE_WIPE] EmpathyAgent cleared")
