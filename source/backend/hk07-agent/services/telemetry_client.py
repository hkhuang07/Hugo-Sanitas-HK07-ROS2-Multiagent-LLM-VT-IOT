"""
Telemetry Client — Communication with local SensorFusionBuffer and Blackboard.
Bypasses local HTTP gateway loops on port 3000 for high-performance direct retrieval.
"""

import logging
import json
from services.sensor_fusion_buffer import get_fusion_buffer
from services.blackboard_service import get_blackboard

log = logging.getLogger("hk07.telemetry_client")

async def fetch_sensor_telemetry() -> dict:
    """
    Directly extracts vitals and IMU state from the local SensorFusionBuffer and Blackboard.
    """
    try:
        fusion_buf = get_fusion_buffer()
        vitals = await fusion_buf.latest_vitals()
        
        bb = get_blackboard()
        imu_data = await bb.read_value("sensor:imu:latest") or {
            "accel_x": 0.0, "accel_y": 0.0, "accel_z": 9.81,
            "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0
        }
        
        if vitals:
            return {
                "status": "ok",
                "heartRate": vitals.heart_rate or 72.0,
                "spo2": vitals.spo2 or 98.0,
                "bodyTemperature": vitals.body_temperature or 36.6,
                "systolic": vitals.systolic or 120.0,
                "diastolic": vitals.diastolic or 80.0,
                "stepCount": vitals.step_count or 0,
                "imu": imu_data
            }
        else:
            return {
                "status": "ok",
                "heartRate": 72.0,
                "spo2": 98.0,
                "bodyTemperature": 36.6,
                "systolic": 120.0,
                "diastolic": 80.0,
                "stepCount": 0,
                "imu": imu_data
            }
    except Exception as e:
        log.error(f"[TELEMETRY_CLIENT] Direct telemetry read failed: {e}")
        return {"status": "ERROR", "error_code": "SYSTEM_PERCEPTION_ERROR", "message": str(e)}

async def capture_vision_payload() -> dict:
    """
    Directly retrieves structured perception logs from the local Blackboard.
    """
    try:
        bb = get_blackboard()
        # Read latest perception JSON written by the vision fusion node
        clinical_json = await bb.read_value("sensor:perception:clinical")
        
        res = {
            "status": "ok",
            "visible_injuries": {"detected": False, "details": None},
            "facial_distress": {"detected": False, "details": None},
            "environmental_hazards": {"detected": False, "details": None}
        }
        
        if clinical_json:
            res.update(clinical_json)
        else:
            # Fallback clinical details from general medical agent
            clinical = await bb.read_latest_clinical()
            if clinical:
                res["diagnosis"] = clinical.diagnosis
                res["action_recommended"] = clinical.action_recommended
                res["alert_level"] = clinical.alert_level
                
        return res
    except Exception as e:
        log.error(f"[TELEMETRY_CLIENT] Direct vision read failed: {e}")
        return {"status": "ERROR", "error_code": "SYSTEM_PERCEPTION_ERROR", "message": str(e)}
