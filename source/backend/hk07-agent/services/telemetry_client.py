"""
Telemetry Client — Communication with local SensorFusionBuffer and Blackboard.
Bypasses local HTTP gateway loops on port 3000 for high-performance direct retrieval.

CRITICAL FIX: NEVER return default/mock values when sensors are offline.
If no real data exists → return status=OFFLINE with clear offline indicators.
"""

import logging
import time
from services.sensor_fusion_buffer import get_fusion_buffer
from services.blackboard_service import get_blackboard

log = logging.getLogger("hk07.telemetry_client")

# How old (in seconds) a vitals sample can be before we treat it as STALE/OFFLINE
_VITALS_STALE_THRESHOLD_S = 30.0
_CAMERA_STALE_THRESHOLD_S = 60.0


async def fetch_sensor_telemetry() -> dict:
    """
    Directly extracts vitals and IMU state from SensorFusionBuffer and Blackboard.

    TRUTHFUL MODE:
    - If no real vitals data in buffer → status=OFFLINE (never return mock defaults)
    - If vitals data is stale (>30s old) → status=STALE with stale warning
    - Only status=ok when fresh real data exists from hardware sensors

    Returns:
        dict with keys:
          status: "ok" | "OFFLINE" | "STALE" | "ERROR"
          _sensor_online: bool (for downstream offline detection)
          heartRate, spo2, etc. — only present when status=ok or STALE
    """
    try:
        fusion_buf = get_fusion_buffer()
        vitals = await fusion_buf.latest_vitals()

        bb = get_blackboard()

        # ── Read IMU from Blackboard ─────────────────────────────────────────
        # IMU is written by sensor_mqtt / background daemon when hardware connected
        imu_raw = await bb.read_value("sensor:imu:latest")
        imu_last_ts = await bb.read_value("sensor:imu:last_update_ts")
        imu_online = (
            imu_raw is not None
            and isinstance(imu_raw, dict)
            and len(imu_raw) > 0
            and (imu_last_ts is None or (time.time() - float(imu_last_ts)) < _VITALS_STALE_THRESHOLD_S)
        )
        imu_data = imu_raw if imu_online else None

        # ── Check vitals freshness ────────────────────────────────────────────
        if vitals is None:
            # No vitals in buffer at all — sensor daemon never received data
            log.debug("[TELEMETRY_CLIENT] No vitals in fusion buffer — sensor OFFLINE")
            return {
                "status": "OFFLINE",
                "_sensor_online": False,
                "message": "Wristband/sensor chưa kết nối hoặc chưa khởi động script thu thập dữ liệu.",
                "imu": imu_data,
                "imu_online": imu_online,
            }

        # Check data freshness via timestamp
        data_age_s = time.time() - float(vitals.timestamp)
        if data_age_s > _VITALS_STALE_THRESHOLD_S:
            log.warning("[TELEMETRY_CLIENT] Vitals data is stale (age=%.1fs). Marking as STALE.", data_age_s)
            return {
                "status": "STALE",
                "_sensor_online": False,
                "message": f"Dữ liệu cảm biến đã cũ ({data_age_s:.0f}s). Wristband có thể đã ngắt kết nối.",
                "data_age_seconds": data_age_s,
                "heartRate": vitals.heart_rate,
                "spo2": vitals.spo2,
                "bodyTemperature": vitals.body_temperature,
                "systolic": vitals.systolic,
                "diastolic": vitals.diastolic,
                "stepCount": vitals.step_count,
                "imu": imu_data,
                "imu_online": imu_online,
            }

        # ── Check if values are actually real (not None) ─────────────────────
        # VitalsSample fields default to None — if all None, sensor never sent data
        has_real_vitals = any(v is not None for v in [
            vitals.heart_rate, vitals.spo2, vitals.body_temperature
        ])

        if not has_real_vitals:
            log.debug("[TELEMETRY_CLIENT] Vitals sample has all-None values — sensor OFFLINE")
            return {
                "status": "OFFLINE",
                "_sensor_online": False,
                "message": "Sensor đang online nhưng chưa nhận được dữ liệu sinh hiệu. Script cảm biến chưa chạy.",
                "imu": imu_data,
                "imu_online": imu_online,
            }

        # ── All checks pass: return real data ────────────────────────────────
        return {
            "status": "ok",
            "_sensor_online": True,
            "heartRate": vitals.heart_rate,
            "spo2": vitals.spo2,
            "bodyTemperature": vitals.body_temperature,
            "systolic": vitals.systolic,
            "diastolic": vitals.diastolic,
            "stepCount": vitals.step_count or 0,
            "imu": imu_data,
            "imu_online": imu_online,
            "data_age_seconds": data_age_s,
        }

    except Exception as e:
        log.error(f"[TELEMETRY_CLIENT] Direct telemetry read failed: {e}")
        return {"status": "ERROR", "_sensor_online": False, "error_code": "SYSTEM_PERCEPTION_ERROR", "message": str(e)}


async def capture_vision_payload() -> dict:
    """
    Directly retrieves structured perception data from the local Blackboard.

    TRUTHFUL MODE:
    - If no perception scan in Blackboard → status=OFFLINE (camera not running)
    - If scan is stale (>60s) → status=STALE
    - Never return "ok" with empty/fabricated data

    Returns:
        dict with keys:
          status: "ok" | "OFFLINE" | "STALE" | "ERROR"
          _camera_online: bool
    """
    try:
        bb = get_blackboard()

        # ── Check perception scan existence and freshness ────────────────────
        perception_scan = await bb.read_value("sensor:perception:latest_scan")
        perception_ts = await bb.read_value("sensor:perception:last_update_ts")

        if perception_scan is None:
            log.debug("[TELEMETRY_CLIENT] No perception scan in Blackboard — camera OFFLINE")
            return {
                "status": "OFFLINE",
                "_camera_online": False,
                "message": "Camera/IPWebcam chưa kết nối hoặc script nhận diện thị giác chưa chạy.",
                "visible_injuries": {"detected": False, "details": None},
                "facial_distress": {"detected": False, "details": None},
                "environmental_hazards": {"detected": False, "details": None},
            }

        # Check staleness
        scan_age_s = 0.0
        if perception_ts is not None:
            scan_age_s = time.time() - float(perception_ts)
            if scan_age_s > _CAMERA_STALE_THRESHOLD_S:
                log.warning("[TELEMETRY_CLIENT] Vision scan is stale (age=%.1fs). Camera may be disconnected.", scan_age_s)
                return {
                    "status": "STALE",
                    "_camera_online": False,
                    "message": f"Dữ liệu camera đã cũ ({scan_age_s:.0f}s). IPWebcam có thể đã ngắt kết nối.",
                    "data_age_seconds": scan_age_s,
                    "visible_injuries": {"detected": False, "details": None},
                    "facial_distress": {"detected": False, "details": None},
                    "environmental_hazards": {"detected": False, "details": None},
                }

        # ── Read clinical perception data ─────────────────────────────────────
        clinical_json = await bb.read_value("sensor:perception:clinical")

        res = {
            "status": "ok",
            "_camera_online": True,
            "visible_injuries": {"detected": False, "details": None},
            "facial_distress": {"detected": False, "details": None},
            "environmental_hazards": {"detected": False, "details": None},
            "data_age_seconds": scan_age_s,
        }

        if clinical_json and isinstance(clinical_json, dict):
            res.update(clinical_json)

        return res

    except Exception as e:
        log.error(f"[TELEMETRY_CLIENT] Direct vision read failed: {e}")
        return {"status": "ERROR", "_camera_online": False, "error_code": "SYSTEM_PERCEPTION_ERROR", "message": str(e)}
