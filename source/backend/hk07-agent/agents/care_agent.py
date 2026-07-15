"""
CareAgent — Hugo healthcare and comfort companion agent
Pivoted from MedicalAgent for local-first empathetic care.
"""

import os
import logging
import json
import time
import asyncio
import collections
import httpx
from typing import Optional, Dict, Any, List

from services.blackboard_service import get_blackboard, ClinicalEntry
from services.agent_log_client import log_agent_decision
from services.llm_client import LocalOfflineFallback

log = logging.getLogger("hk07.care_agent")

def safe_extract_json(text: str) -> dict:
    fallback = {
        "alert_level": "NORMAL",
        "diagnosis": "Đang theo dõi sức khỏe và kiểm tra triệu chứng.",
        "action_plan": "Vui lòng giữ ấm cơ thể và uống nước ấm.",
        "source_note": "Hugo Safe Fallback"
    }
    if not text or not isinstance(text, str):
        return fallback
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass

    return fallback


class CareAgent:
    def __init__(self, memory=None, arbitrator=None):
        self.memory = memory
        self.arbitrator = arbitrator
        self._status = "ACTIVE"
        self._volatile_context = {}
        self.latest_vitals = {
            "heartRate": 72,
            "spo2": 98.0,
            "bodyTemperature": 36.6,
            "systolic": 120,
            "diastolic": 80
        }
        import collections
        self._buffer = collections.deque(maxlen=50)
        self._last_state = "NORMAL"
        self._last_analyzed_hr = 0.0
        self._raw_hr_windows = {}

    async def run_loop(self):
        self._status = "ACTIVE"
        log.info("[CARE_AGENT] Active — Hugo care and support loop started.")
        while True:
            await asyncio.sleep(10)

    def clear_volatile_context(self):
        self._volatile_context.clear()
        log.info("[CARE_AGENT] Volatile context cleared.")

    def get_status(self) -> dict:
        return {
            "status": self._status,
            "vitals": self.latest_vitals
        }

    async def _call_ollama_vision_vqa(self, image_bytes: bytes, question: str) -> str:
        """Call local Moondream model via Ollama vision endpoint for VQA"""
        import base64
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        model_name = os.getenv("OLLAMA_VISION_MODEL", "moondream")
        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        payload = {
            "model": model_name,
            "prompt": f"Based on the image, answer this question: {question}. Answer with only 'yes' or 'no' if possible.",
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 10}
        }
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(f"{url}/api/generate", json=payload)
                if resp.status_code == 200:
                    res_text = resp.json().get("response", "").strip()
                    log.info("[CARE_AGENT_VISION] Ollama vision response: %s", res_text)
                    return res_text
        except Exception as e:
            log.error("[CARE_AGENT_VISION_ERROR] Ollama VQA call failed: %s", e)
        return "no"

    async def process_text_interaction(
        self,
        user_message: str,
        current_vitals: dict,
        mode: str = "MEDICAL_ADVICE",
        user_id: Optional[str] = None
    ) -> str:
        if user_id is None:
            user_id = "default"
        
        start_time = time.time()
        bb = get_blackboard()

        # Update latest vitals local cache
        if current_vitals:
            self.latest_vitals.update(current_vitals)

        # 1. Fetch ambient temperature from blackboard
        ambient_temp = None
        try:
            env_data = await bb.read_value("sensor:env:latest") or {}
            if isinstance(env_data, dict):
                ambient_temp = env_data.get("temperature") or env_data.get("temp") or env_data.get("ambient_temp")
        except Exception as e:
            log.warning("[CARE_AGENT] Failed to read environment temperature: %s", e)

        # Rule 1: Temperature drop warning
        if ambient_temp is not None:
            try:
                temp_val = float(ambient_temp)
                if temp_val < 20.0:
                    result = {
                        "diagnosis": f"Nhiệt độ phòng hiện tại khá lạnh ({temp_val:.1f}°C).",
                        "action_plan": "Tôi đề xuất sếp đắp chăn ấm để giữ nhiệt độ cơ thể ổn định. Tôi đang kích hoạt robot mang một chiếc chăn ấm cho bạn. [OFFER_BLANKET_TRIGGERED]",
                        "alert_level": "WARNING",
                        "source_note": "Quy tắc môi trường của Hugo"
                    }
                    res_str = json.dumps(result, ensure_ascii=False)
                    await self._write_clinical_and_log(user_message, res_str, start_time, user_id)
                    return res_str
            except (ValueError, TypeError):
                pass

        # 2. Check for injury keyword & visual scratch check
        msg_lower = user_message.lower()
        injury_keywords = ["xước", "thương", "đau tay", "đau chân", "máu", "scratch", "wound", "cut", "injury", "blood"]
        is_injury_query = any(kw in msg_lower for kw in injury_keywords)

        if is_injury_query:
            image_path = "d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/latest_frame.jpg"
            image_bytes = None
            if os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as f:
                        image_bytes = f.read()
                except Exception as e:
                    log.error("[CARE_AGENT] Failed to read latest_frame.jpg: %s", e)

            if image_bytes:
                log.info("[CARE_AGENT] Running VQA skin scratch check")
                vqa_res = await self._call_ollama_vision_vqa(
                    image_bytes, 
                    "Is there a red scratch, cut, bleeding, or visible injury on the skin of the person in the image? Answer ONLY 'yes' or 'no'."
                )
                
                if "yes" in vqa_res.lower():
                    result = {
                        "diagnosis": "Tôi phát hiện có vết trầy xước ngoài da của sếp.",
                        "action_plan": "Bạn có muốn tôi kích hoạt vòi phun để phun thuốc sát trùng làm dịu vết trầy xước không? [ANTISEPTIC_SPRAY_TRIGGERED]",
                        "alert_level": "WARNING",
                        "source_note": "Phân tích thị giác Moondream"
                    }
                    res_str = json.dumps(result, ensure_ascii=False)
                    await self._write_clinical_and_log(user_message, res_str, start_time, user_id)
                    return res_str

        # 3. Use local SLM qwen2.5 for general comfort care queries
        # Get detailed sensor telemetry context dynamically for local SLM y khoa
        sensor_ctx_str = ""
        try:
            import math
            imu_data = await bb.read_value("sensor:imu:latest") or {}
            env_latest = await bb.read_value("sensor:env:latest") or {}
            loc_latest = await bb.read_value("sensor:location:latest") or {}
            
            is_imu_online = imu_data is not None and len(imu_data) > 0
            is_loc_online = loc_latest is not None and len(loc_latest) > 0
            is_env_online = env_latest is not None and len(env_latest) > 0
            is_vitals_online = current_vitals is not None and len(current_vitals) > 0

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
            imu_ax, imu_ay, imu_az = 0.0, 0.0, 0.0
            imu_g_mag = 0.0
            imu_gx, imu_gy, imu_gz = 0.0, 0.0, 0.0
            imu_qw, imu_qx, imu_qy, imu_qz = 1.0, 0.0, 0.0, 0.0
            imu_mag_x, imu_mag_y, imu_mag_z = 0.0, 0.0, 0.0
            imu_compass = 0.0
            if imu_data:
                imu_ax, imu_ay, imu_az = float(imu_data.get("accel_x", 0.0)), float(imu_data.get("accel_y", 0.0)), float(imu_data.get("accel_z", 0.0))
                imu_g_mag = (imu_ax**2 + imu_ay**2 + imu_az**2)**0.5 / 9.80665
                imu_gx, imu_gy, imu_gz = float(imu_data.get("gyro_x", 0.0)), float(imu_data.get("gyro_y", 0.0)), float(imu_data.get("gyro_z", 0.0))
                imu_qw, imu_qx, imu_qy, imu_qz = float(imu_data.get("qw", 1.0)), float(imu_data.get("qx", 0.0)), float(imu_data.get("qy", 0.0)), float(imu_data.get("qz", 0.0))
                imu_mag_x, imu_mag_y, imu_mag_z = float(imu_data.get("mag_x", 0.0)), float(imu_data.get("mag_y", 0.0)), float(imu_data.get("mag_z", 0.0))
                imu_compass = float(imu_data.get("compass_heading", 0.0))

            gps_lat, gps_lon, gps_alt = 0.0, 0.0, 0.0
            if is_loc_online:
                gps_data = await bb.read_value("sensor:location:data") or {}
                gps_lat = float(gps_data.get("latitude", 0.0))
                gps_lon = float(gps_data.get("longitude", 0.0))
                gps_alt = float(gps_data.get("altitude", 0.0))

            env_baro, env_light = 0.0, 0.0
            if env_latest:
                env_baro = float(env_latest.get("barometric_pressure", 1013.25))
                env_light = float(env_latest.get("ambient_light", 0.0))
            
            steps_val = get_val(current_vitals, "pedometer_steps", 0) or get_val(current_vitals, "stepCount", 0)
            act_type = get_val(current_vitals, "activity_type", "unknown") or get_val(current_vitals, "activity", "unknown")
            bat_level = get_val(current_vitals, "battery_level", None) or get_val(current_vitals, "battery", None)
            bat_temp = get_val(current_vitals, "battery_temp", None) or get_val(current_vitals, "batteryTemp", None)
            
            accel_str = f"x={imu_ax:.2f}, y={imu_ay:.2f}, z={imu_az:.2f} m/s²" if is_imu_online else "OFFLINE"
            grav_str = f"magnitude={imu_g_mag:.3f}g" if is_imu_online else "OFFLINE"
            gyro_str = f"x={imu_gx:.2f}, y={imu_gy:.2f}, z={imu_gz:.2f} rad/s" if is_imu_online else "OFFLINE"
            orient_str = f"w={imu_qw:.2f}, x={imu_qx:.2f}, y={imu_qy:.2f}, z={imu_qz:.2f}" if is_imu_online else "OFFLINE"
            mag_str = f"x={imu_mag_x:.1f}, y={imu_mag_y:.1f}, z={imu_mag_z:.1f}" if is_imu_online else "OFFLINE"
            compass_str = f"{imu_compass:.1f}°" if is_imu_online else "OFFLINE"
            gps_str = f"lat={gps_lat:.6f}, lon={gps_lon:.6f}, alt={gps_alt:.1f}m" if is_loc_online else "OFFLINE"
            baro_str = f"{env_baro:.2f} hPa" if is_env_online else "OFFLINE"
            light_str = f"{env_light:.1f} lux" if is_env_online else "OFFLINE"
            steps_str = f"{steps_val} steps" if is_vitals_online else "OFFLINE"
            activity_str = f"{act_type}" if is_vitals_online else "OFFLINE"
            bat_lvl_str = f"{bat_level:.1f}%" if bat_level is not None else "OFFLINE"
            bat_temp_str = f"{bat_temp:.1f}°C" if bat_temp is not None else "OFFLINE"

            sensor_ctx_str = (
                "=========================================\n"
                "TRẠNG THÁI CẢM BIẾN THỜI GIAN THỰC:\n"
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
                f"- Mobile Device Battery Level: {bat_lvl_str}\n"
                f"- Mobile Device Battery Temperature: {bat_temp_str}\n"
                "=========================================\n"
                "HƯỚNG DẪN CHẨN ĐOÁN:\n"
                "Phân tích các cảm biến này để chẩn đoán hoạt động & tâm trạng. Đưa lời khuyên đồng hành ấm áp.\n"
            )
        except Exception as e:
            log.warning("Failed to generate rich sensor context for CareAgent: %s", e)

        log.info("[CARE_AGENT] Querying local qwen2.5 LLM for companion advice")
        system_prompt = (
            "Bạn là Hugo/HK-07 (Hugo Sanitas HK07), người bạn đồng hành chăm sóc sức khỏe tinh thần và thể chất.\n"
            "Nhiệm vụ: Trả lời, thấu cảm, đưa ra đề xuất chăm sóc đơn giản theo quy trình Baymax chủ động.\n"
            f"{state_instruction}\n"
            "Hãy phản hồi bằng tiếng Việt duy trì giọng điệu ấm áp và điềm tĩnh.\n"
            f"{sensor_ctx_str}\n"
            "BẮT BUỘC TRẢ VỀ KẾT QUẢ DƯỚI ĐỊNH DẠNG JSON NGHIÊM NGẶT (Không chứa thêm bất kỳ đoạn text hội thoại nào bên ngoài JSON).\n"
            "Cấu trúc JSON như sau:\n"
            "{\n"
            '  "diagnosis": "Tóm tắt trạng thái của sếp ngắn gọn thấu cảm bằng tiếng Việt",\n'
            '  "action_plan": "Lời khuyên trò chuyện, đề xuất chăm sóc đơn giản ấm áp dựa theo Trạng thái hiện tại",\n'
            '  "alert_level": "NORMAL" | "WARNING",\n'
            '  "source_note": "Hugo Care Engine"\n'
            "}\n"
        )
        
        prompt = f"User query: {user_message}\nVitals: {self.latest_vitals}"
        res_text = None
        try:
            res_text = await asyncio.to_thread(
                LocalOfflineFallback._call_ollama_text_sync, prompt, system_prompt
            )
        except Exception as e:
            log.error("[CARE_AGENT_OLLAMA_ERROR] Ollama call failed: %s", e)

        if res_text:
            extracted = safe_extract_json(res_text)
            res_str = json.dumps(extracted, ensure_ascii=False)
        else:
            res_str = self._get_safe_text_fallback(user_message)

        await self._write_clinical_and_log(user_message, res_str, start_time, user_id)
        return res_str

    async def _write_clinical_and_log(self, user_message: str, res_str: str, start_time: float, user_id: str):
        latency = int((time.time() - start_time) * 1000)
        try:
            extracted = json.loads(res_str)
            bb = get_blackboard()
            entry = ClinicalEntry(
                agent_type="MEDICAL",
                alert_level=extracted.get("alert_level", "NORMAL"),
                vitals=self.latest_vitals,
                diagnosis=extracted.get("diagnosis", ""),
                action_recommended=extracted.get("action_plan", ""),
                confidence_score=0.9
            )
            await bb.write_clinical(entry, user_id=user_id)
        except Exception as e:
            log.error("[CARE_AGENT] Failed to write ClinicalEntry: %s", e)

        await log_agent_decision("CARE", user_message, res_str, "OLLAMA_CARE", latency)

    def _get_safe_text_fallback(self, user_message: str) -> str:
        return json.dumps({
            "diagnosis": "Tôi đang đồng hành và ghi nhận cảm nhận của sếp.",
            "action_plan": "Tôi khuyên sếp nên ngồi nghỉ ngơi thư giãn và uống một chút nước ấm. Tôi ở đây để ôm hoặc trò chuyện cùng sếp.",
            "alert_level": "NORMAL",
            "source_note": "Hugo Safe Fallback"
        }, ensure_ascii=False)


    # ─── Legacy Backward Compatibility Methods for MedicalAgent Tests ───
    def _aggregate_vitals(self) -> dict:
        if not self._buffer:
            return {"heartRate": 72.0, "spo2": 98.0, "bodyTemperature": 36.6, "systolic": 120.0, "diastolic": 80.0}
        
        sum_hr = sum(v.get("heartRate", 72) for v in self._buffer)
        sum_spo2 = sum(v.get("spo2", 98.0) for v in self._buffer)
        sum_temp = sum(v.get("bodyTemperature", 36.6) for v in self._buffer)
        sum_sys = sum(v.get("systolic", 120) for v in self._buffer)
        sum_dias = sum(v.get("diastolic", 80) for v in self._buffer)
        count = len(self._buffer)
        
        return {
            "heartRate": float(sum_hr / count),
            "spo2": float(sum_spo2 / count),
            "bodyTemperature": float(sum_temp / count),
            "systolic": float(sum_sys / count),
            "diastolic": float(sum_dias / count)
        }

    async def _process_latest_buffer(self) -> None:
        if not self._buffer:
            return
        
        latest = self._buffer[-1]
        hr = float(latest.get("heartRate", 72))
        is_fall = latest.get("is_falling", False)
        emergency_btn = latest.get("emergency_button_pressed", False)
        
        if is_fall or emergency_btn or hr >= 140:
            self._last_state = "CRITICAL"
            self._last_analyzed_hr = float(hr)
            payload = {
                "eventType": "AI_EMERGENCY_WAKEUP",
                "alertLevel": "CRITICAL",
                "outputDecision": "Phát hiện nhịp tim bất thường hoặc phát hiện ngã/chấn thương."
            }
            if self._mqtt:
                self._mqtt.publish("hk07/agents/medical/output", json.dumps(payload), qos=1)
            return
        
        new_state = "NORMAL"
        if hr > 120:
            new_state = "CRITICAL"
        elif hr > 100 or hr < 55:
            new_state = "WARNING"
            
        if new_state == "NORMAL" and self._last_state in ("CRITICAL", "WARNING"):
            # Transition to NORMAL calls LLM to log recovery but forces state to NORMAL
            self._last_state = "NORMAL"
            self._last_analyzed_hr = float(hr)
            await self._call_llm_with_fallback(latest)
            return
            
        skip = False
        if self._last_state == new_state:
            if self._last_state in ("CRITICAL", "WARNING"):
                if self._last_analyzed_hr > 0:
                    delta = abs(hr - self._last_analyzed_hr) / self._last_analyzed_hr
                    if delta < 0.15:
                        skip = True
        
        if skip:
            return
            
        res_json = await self._call_llm_with_fallback(latest)
        self._last_state = res_json.get("alert_level", "NORMAL")
        self._last_analyzed_hr = float(hr)

    async def _call_llm_with_fallback(self, vitals: dict, **kwargs) -> dict:
        hr = vitals.get("heartRate", 72)
        spo2 = vitals.get("spo2", 98.0)
        
        level = "NORMAL"
        if hr > 120 or hr < 45 or spo2 < 90:
            level = "CRITICAL"
        elif hr > 100 or hr < 55 or spo2 < 95:
            level = "WARNING"
            
        return {
            "alert_level": level,
            "diagnosis": "Legacy test evaluation",
            "action_plan": "Rest and monitor",
            "source_note": "Legacy fallback"
        }

    async def close(self) -> None:
        pass


# Backwards compatibility compatibility alias
MedicalAgent = CareAgent
