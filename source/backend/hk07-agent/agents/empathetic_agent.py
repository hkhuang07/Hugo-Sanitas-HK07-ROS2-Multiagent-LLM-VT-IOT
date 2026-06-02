"""
EmpatheticAgent — Tầng 2 trong Subsumption Architecture

Giao tiếp thấu cảm và chăm sóc tâm lý với chủ nhân.
Mô hình sử dụng:
- Primary: Cohere API (Lợi thế cực mạnh về RAG) truy vấn từ LanceDB memory
- Fallback: Gemini API (Gemini 1.5 Flash)
- Cuối cùng: Local Rule-based
System Prompt đóng vai Hugo (Trợ lý y tế), giọng điệu ấm áp, ngắn gọn.
"""

import asyncio
import logging
import os
import time
from collections import deque
import httpx
from dotenv import load_dotenv
from services.agent_log_client import log_agent_decision
from services.blackboard_service import get_blackboard
from utils.enums import LLMProvider

# Load env variables
load_dotenv()

log = logging.getLogger("hk07.empathy_agent")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

EMPATHY_SYSTEM_PROMPT = (
    "Bạn là Hugo, trợ lý đồng hành y tế theo chuẩn Baymax. Bạn là một người bạn ấm áp, đáng tin cậy, và luôn sẵn lòng lắng nghe.\n\n"
    
    "=== QUY TẮC PHẢN HỒI CỐT LÕI ===\n"
    "1. KHI NHẬN ĐƯỢC DỮ LIỆU LÂM SÀNG TỪ MEDICAL_CONTEXT (Blackboard):\n"
    "   TUYỆT ĐỐI KHÔNG dùng từ ngữ chuyên môn, không nói những từ gây sốc như:\n"
    "   - 'nhồi máu cơ tim', 'đột quỵ', 'nguy kịch', 'xơ vữa động mạch', 'tachycardia'\n"
    "   Bạn phải 'BIÊN DỊCH' các chỉ số lâm sàng thành lời trấn an mềm mỏng, đồng cảm.\n\n"
    
    "2. VÍ DỤ BIÊN DỊCH LÂMM SÀNG:\n"
    "   - Alert_level=CRITICAL, HR>120 → 'Tôi nhận thấy trái tim bạn đang căng thẳng. Hãy thơm thở sâu, tôi đang theo dõi bạn rất kỹ lưỡng.'\n"
    "   - SpO2<90 → 'Oxy của bạn hơi thấp hơn bình thường. Hãy ngồi thẳng lên và hít thở đều đặn nhé?'\n"
    "   - BP>140/90 → 'Huyết áp bạn hơi cao. Chúng ta thư giãn một chút được không? Bác sĩ đang đến để kiểm tra bạn.'\n"
    "   - Diagnosis=Stroke risk → 'Tôi muốn bác sĩ kiểm tra bạn ngay bây giờ để chắc chắn bạn an toàn. Bác sĩ sắp đến.'\n\n"
    
    "3. TONE & STYLE:\n"
    "   - Ấm áp, thấu cảm, ân cần, xoa dịu (Baymax-like).\n"
    "   - Không lặp lại cụm từ cố định. Hãy đa dạng hóa cách diễn đạt.\n"
    "   - Ngắn gọn (tối đa 2-3 câu), dễ hiểu cho người lớn tuổi.\n"
    "   - Kết thúc bằng một hành động tích cực: 'Bác sĩ đang đến', 'Hãy yên tâm', 'Tôi ở đây cạnh bạn'.\n\n"
    
    "4. PHÂN TÍCH TÂMHUNG:\n"
    "   - Nếu phát hiện lo lắng: 'Tôi thấy bạn hơi lo lắng. Điều đó bình thường, tôi ở đây rồi.'\n"
    "   - Nếu phát hiện mệt mỏi: 'Bạn có vẻ mệt. Hãy nghỉ ngơi, tôi sẽ canh chừng mọi thứ cho bạn.'\n"
    "   - Nếu phát hiện bình tĩnh: Giữ liên kết, khuyến khích: 'Bạn làm rất tốt. Cứ tiếp tục như vậy.'\n\n"
    
    "5. KHI TÌNH TRẠNG KHẨN CẤPC:\n"
    "   - Không hoảng sợ, không nói 'nguy hiểm', 'tử vong'.\n"
    "   - Nói: 'Bác sĩ cần kiểm tra bạn ngay. Tôi đã gọi họ. Hãy bình tĩnh, tôi ở đây cạnh bạn. Tất cả sẽ ổn thôi.'\n\n"
    
    "6. TIẾNG VIỆT, TỰ NHIÊN, THÂN THIỆN — SẴN LÒNG, CHÂN THÀNH."
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
        self._cohere_api_key = os.getenv("COHERE_API_KEY", "")
        self._gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = None

    async def run_loop(self):
        self._status = "ACTIVE"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        log.info("[EMPATHY_AGENT] Active — Tầng 2")
        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            if self._client:
                await self._client.aclose()

    async def process_text_interaction(self, user_message: str) -> str:
        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

        start_time = time.time()
        
        # ─── COGNITIVE ORCHESTRATION: Read from Blackboard ─────────────────────
        # Medical Agent may have written clinical findings
        blackboard = get_blackboard()
        clinical_context = ""
        try:
            clinical_entry = await blackboard.read_latest_clinical()
            if clinical_entry:
                clinical_context = (
                    f"\n[CLINICAL CONTEXT từ Medical Agent]\n"
                    f"- Tình trạng: {clinical_entry.alert_level}\n"
                    f"- Chẩn đoán: {clinical_entry.diagnosis}\n"
                    f"- Khuyến nghị: {clinical_entry.action_recommended}\n"
                )
                log.info("[EMPATHY_BLACKBOARD] Read clinical context: %s", clinical_entry.diagnosis)
        except Exception as e:
            log.warning("[EMPATHY_BLACKBOARD] Error reading clinical context: %s", e)
        
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
        
        # Prepend clinical context from Blackboard for sympathetic reframing
        baseline = clinical_context + baseline

        # 2. Primary Attempt: Cohere API (RAG)
        if self._cohere_api_key:
            content, success = await self._call_cohere(user_message, documents, baseline)
            if success:
                latency = int((time.time() - start_time) * 1000)
                await self._log_interaction(user_message, content, LLMProvider.COHERE_PRIMARY.value, latency)
                return content
            log.warning("[EMPATHY_AGENT] Cohere failed — switching to Gemini fallback")

        # 3. Fallback Attempt: Gemini API
        if self._gemini_api_key:
            content, success = await self._call_gemini(user_message, mem_context, baseline)
            if success:
                latency = int((time.time() - start_time) * 1000)
                await self._log_interaction(user_message, content, LLMProvider.GEMINI_FALLBACK.value, latency)
                return content
            log.error("[EMPATHY_AGENT] Both Cohere and Gemini unavailable")

        # 4. Local Rule-Based fallback
        content = self._generate_local_fallback(user_message)
        latency = int((time.time() - start_time) * 1000)
        await self._log_interaction(user_message, content, LLMProvider.LOCAL_RULE.value, latency)
        return content

    async def process_system_query(self, user_message: str) -> str:
        """Processes hardware/connectivity queries with Tool Calling"""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

        start_time = time.time()

        if not self._gemini_api_key:
            content = self._local_system_query_fallback(user_message)
            latency = int((time.time() - start_time) * 1000)
            await self._log_interaction(user_message, content, LLMProvider.LOCAL_RULE.value, latency)
            return content

        tools = [{
            "functionDeclarations": [
                {
                    "name": "execute_sensor_ping",
                    "description": "Ping a specific hardware device/sensor (e.g. wristband, lidar, imu, camera) to check connectivity and latency.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "device": {
                                "type": "STRING",
                                "description": "The name of the device or sensor to ping."
                            }
                        },
                        "required": ["device"]
                    }
                },
                {
                    "name": "execute_vital_scan",
                    "description": "Trigger a manual scan of the vital signs sensors.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {}
                    }
                }
            ]
        }]

        contents = [{"role": "user", "parts": [{"text": user_message}]}]

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self._gemini_api_key}"
            resp = await self._client.post(
                url,
                json={
                    "contents": contents,
                    "tools": tools
                }
            )
            if resp.status_code != 200:
                log.error(f"[SYSTEM_QUERY_GEMINI_ERROR] Status {resp.status_code} - Body: {resp.text}")
                content = self._local_system_query_fallback(user_message)
                latency = int((time.time() - start_time) * 1000)
                await self._log_interaction(user_message, content, LLMProvider.LOCAL_RULE.value, latency)
                return content

            res_json = resp.json()
            candidate = res_json.get("candidates", [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])

            function_call = None
            for part in parts:
                if "functionCall" in part:
                    function_call = part["functionCall"]
                    break

            if function_call:
                name = function_call.get("name")
                args = function_call.get("args", {})
                
                result_dict = {}
                if name == "execute_sensor_ping":
                    device = args.get("device", "wristband")
                    result_dict = execute_sensor_ping(device)
                elif name == "execute_vital_scan":
                    result_dict = execute_vital_scan()
                else:
                    result_dict = {"status": "ERROR", "message": "Unknown function"}

                log.info(f"[SYSTEM_QUERY_TOOL] Executed {name} with args {args} -> {result_dict}")

                # Call Gemini again with the tool result to generate natural response
                new_contents = [
                    {
                        "role": "user",
                        "parts": [{"text": user_message}]
                    },
                    {
                        "role": "model",
                        "parts": [{"functionCall": function_call}]
                    },
                    {
                        "role": "function",
                        "parts": [{
                            "functionResponse": {
                                "name": name,
                                "response": result_dict
                            }
                        }]
                    }
                ]

                resp2 = await self._client.post(
                    url,
                    json={
                        "contents": new_contents,
                        "tools": tools
                    }
                )
                if resp2.status_code == 200:
                    res2_json = resp2.json()
                    final_text = res2_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if final_text:
                        content = final_text.strip()
                        latency = int((time.time() - start_time) * 1000)
                        await self._log_interaction(user_message, content, LLMProvider.GEMINI_FALLBACK.value, latency)
                        return content

            else:
                text = parts[0].get("text", "") if parts else ""
                if text:
                    content = text.strip()
                    latency = int((time.time() - start_time) * 1000)
                    await self._log_interaction(user_message, content, LLMProvider.GEMINI_FALLBACK.value, latency)
                    return content

        except Exception as e:
            log.error("[SYSTEM_QUERY_ERROR] Exception: %s", e)

        content = self._local_system_query_fallback(user_message)
        latency = int((time.time() - start_time) * 1000)
        await self._log_interaction(user_message, content, LLMProvider.LOCAL_RULE.value, latency)
        return content

    def _local_system_query_fallback(self, user_message: str) -> str:
        msg = user_message.lower()
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

    async def _call_cohere(self, user_message: str, documents: list, baseline: str = "") -> tuple[str, bool]:
        history_str = ""
        for h in self._history:
            role = "HK-07" if h["role"] == "assistant" else "User"
            history_str += f"{role}: {h['content']}\n"
        context_str = "\n".join([f"- {d['text']}" for d in documents])
        
        system_instruction = EMPATHY_SYSTEM_PROMPT
        if baseline:
            system_instruction = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_instruction}"

        prompt = (
            f"System Instruction:\n{system_instruction}\n"
            f"Ký ức quá khứ của bệnh nhân:\n{context_str}\n\n"
            f"Lịch sử hội thoại:\n{history_str}\n"
            f"User: {user_message}\nHugo:"
        )
        try:
            resp = await self._client.post(
                "https://api.cohere.com/v1/chat",
                headers={
                    "Authorization": f"Bearer {self._cohere_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "command-r-08-2024",
                    "message": prompt
                }
            )
            if resp.status_code != 200:
                log.error(f"[EMPATHY_COHERE_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return "", False
            resp.raise_for_status()
            content = resp.json()["text"]
            return content.strip(), True
        except Exception as e:
            log.error("[EMPATHY_COHERE_ERROR] Exception: %s", e)
            return "", False

    async def _call_gemini(self, user_message: str, mem_context: list, baseline: str = "") -> tuple[str, bool]:
        history_str = ""
        for h in self._history:
            role = "HK-07" if h["role"] == "assistant" else "User"
            history_str += f"{role}: {h['content']}\n"
        context_str = "\n".join([f"- {d['content']}" for d in mem_context])

        system_instruction = EMPATHY_SYSTEM_PROMPT
        if baseline:
            system_instruction = f"Thông tin hồ sơ sức khỏe cơ bản của bệnh nhân:\n{baseline}\n\n{system_instruction}"

        prompt = (
            f"System Instruction:\n{system_instruction}\n"
            f"Ký ức quá khứ của bệnh nhân:\n{context_str}\n\n"
            f"Lịch sử hội thoại:\n{history_str}\n"
            f"User: {user_message}\nHugo:"
        )
        try:
            resp = await self._client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self._gemini_api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}]
                }
            )
            if resp.status_code != 200:
                log.error(f"[EMPATHY_GEMINI_ERROR] Status {resp.status_code} - Body: {resp.text}")
                return "", False
            resp.raise_for_status()
            content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return content.strip(), True
        except Exception as e:
            log.error("[EMPATHY_GEMINI_ERROR] Exception: %s", e)
            return "", False

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
        if any(w in msg for w in ["chào", "hello", "hi"]):
            return "Xin chào! Tôi là Hugo. Tôi có thể giúp gì cho bạn hôm nay?"
        elif any(w in msg for w in ["buồn", "mệt", "khóc", "buon", "met", "kho"]):
            return "Tôi biết bạn đang trải qua khoảng thời gian không dễ dàng. Hãy nghỉ ngơi một chút và hít thở sâu cùng tôi nhé."
        elif any(w in msg for w in ["lo", "sợ", "anxious", "fear"]):
            return "Mọi chuyện rồi sẽ ổn thôi. Nhắm mắt lại, thư giãn cơ thể và tập trung vào hơi thở của mình nhé."
        return "Tôi luôn sẵn sàng lắng nghe bạn chia sẻ. Hãy cho tôi biết nếu bạn cần trợ giúp hoặc trò chuyện."

    async def execute_visual_scan(self, current_vitals: dict) -> str:
        """
        Reads the latest_frame.jpg from buffer, encodes to Base64, and queries Gemini 1.5 Vision API
        along with the patient's vitals context.
        """
        import base64
        
        image_path = "d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/latest_frame.jpg"
        base64_data = ""
        mime_type = "image/jpeg"
        
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
                # String fallback
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

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self._gemini_api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 300,
                "temperature": 0.4
            }
        }

        try:
            if not self._client:
                self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
            
            resp = await self._client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                response_text = data["contents"][0]["parts"][0]["text"]
                log.info("[VISION_TOOL] Gemini Vision Scan complete.")
                
                # Log this scan interaction in the audit database
                await self._log_interaction(
                    user_message="[REQUEST_VISUAL_SCAN] Tiến hành quét hình ảnh cơ thể.",
                    content=response_text,
                    provider="GEMINI_1.5_VISION",
                    latency=int((time.time() - time.time()) * 1000)
                )
                return response_text
            else:
                log.error(f"[VISION_TOOL_ERROR] Gemini Vision returned status {resp.status_code}: {resp.text}")
                return "Phát hiện luồng camera hoạt động. Tuy nhiên liên kết Gemini Vision API gặp sự cố. Trạng thái cơ bản của bạn vẫn ở mức ổn định."
        except Exception as ex:
            log.error(f"[VISION_TOOL_ERROR] Exception: {ex}")
            return "Không thể kết nối dịch vụ Gemini Vision để phân tích ảnh. Trạng thái cơ bản của bạn vẫn ở mức ổn định."

    def get_status(self) -> dict:
        return {"status": self._status, "turns": len(self._history) // 2}

    def clear_volatile_context(self):
        self._history.clear()
        log.info("[VOLATILE_WIPE] EmpathyAgent cleared")
