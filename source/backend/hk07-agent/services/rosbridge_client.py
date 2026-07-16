import asyncio
import websockets
import json
import logging
import time
import math
import os
from services.blackboard_service import get_blackboard
import services.sensor_mqtt_client as sensor_mqtt_client

ROBOT_MODE = os.getenv("ROBOT_MODE", "SIMULATED").upper()

class MqttClientProxy:
    def __getattr__(self, name):
        client = sensor_mqtt_client._mqtt_client
        if client is None:
            raise AttributeError("MQTT client is not initialized")
        return getattr(client, name)
        
    def __bool__(self):
        return sensor_mqtt_client._mqtt_client is not None

_mqtt_client = MqttClientProxy()

log = logging.getLogger("hk07.rosbridge")

async def rosbridge_client_loop():
    import websockets
    import json
    import base64
    import struct
    import math
    import time
    from services.sensor_fusion_buffer import get_fusion_buffer, VitalsSample
    from services.blackboard_service import get_blackboard

    uri = "ws://localhost:9090"
    backoff = 1.0
    last_phone_imu_time = 0.0
    
    while True:
        try:
            log.info(f"[ROSBRIDGE_CLIENT] Connecting to {uri}...")
            async with websockets.connect(uri, ping_interval=30, ping_timeout=30) as websocket:
                log.info("[ROSBRIDGE_CLIENT] Connected to rosbridge_suite.")
                backoff = 1.0
                
                # Subscribe to topics
                subscribe_topics = [
                    {"topic": "/telemetry/sensors/vitals", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/sensors/camera/thermal_rppg", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/vitals/wristband", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/imu", "type": "sensor_msgs/msg/Imu"},
                    {"topic": "/sensors/imu/state", "type": "sensor_msgs/msg/Imu"},
                    {"topic": "/hk07/perception/clinical", "type": "std_msgs/msg/String"},
                    {"topic": "/telemetry/pose", "type": "geometry_msgs/msg/PoseStamped"},
                    {"topic": "/telemetry/pmu", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/pneumatic", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/actuators/joints", "type": "sensor_msgs/msg/JointState"},
                    {"topic": "/telemetry/sensors/tactile", "type": "sensor_msgs/msg/JointState"}
                ]
                for sub in subscribe_topics:
                    req = {
                        "op": "subscribe",
                        "topic": sub["topic"],
                        "type": sub["type"]
                    }
                    await websocket.send(json.dumps(req))
                
                async for message in websocket:
                    data = json.loads(message)
                    op = data.get("op")
                    if op == "publish":
                        topic = data.get("topic")
                        msg = data.get("msg", {})
                        
                        fusion_buf = get_fusion_buffer()
                        bb = get_blackboard()
                        
                        # MQTT Dual Telemetry Bridge (Restores Vue telemetry panels updates)
                        if _mqtt_client:
                            t_sec = msg.get("header", {}).get("stamp", {}).get("sec", 0)
                            t_nsec = msg.get("header", {}).get("stamp", {}).get("nanosec", 0)
                            timestamp_ms = t_sec * 1000 + int(t_nsec / 1e6)
                            if timestamp_ms == 0:
                                timestamp_ms = int(time.time() * 1000)

                            if topic == "/telemetry/pmu":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                if len(names) >= 4 and len(pos) >= 4:
                                    pmu_payload = {
                                        "voltage": pos[names.index("voltage")],
                                        "current": pos[names.index("current")],
                                        "soc": pos[names.index("soc")],
                                        "temp": pos[names.index("temp")],
                                        "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                        "timestampMs": timestamp_ms
                                    }
                                    _mqtt_client.publish("hk07/telemetry/pmu", json.dumps(pmu_payload), qos=0)

                            elif topic == "/telemetry/pneumatic":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                if len(names) >= 4 and len(pos) >= 4:
                                    pne_payload = {
                                        "press_L": pos[names.index("press_L")],
                                        "press_R": pos[names.index("press_R")],
                                        "pump_active": bool(pos[names.index("pump_active")]),
                                        "relief_active": bool(pos[names.index("relief_active")]),
                                        "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                        "timestampMs": timestamp_ms
                                    }
                                    _mqtt_client.publish("hk07/telemetry/pneumatic", json.dumps(pne_payload), qos=0)

                            elif topic == "/telemetry/sensors/tactile":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                if len(names) >= 2 and len(pos) >= 2:
                                    tac_payload = {
                                        "hug_force": pos[names.index("hug_force")],
                                        "flex_rate": pos[names.index("flex_rate")],
                                        "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                        "timestampMs": timestamp_ms
                                    }
                                    _mqtt_client.publish("hk07/telemetry/tactile", json.dumps(tac_payload), qos=0)

                            elif topic == "/telemetry/actuators/joints":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                eff = msg.get("effort", [])
                                vel = msg.get("velocity", [])
                                joints_list = []
                                for i, name in enumerate(names):
                                    joints_list.append({
                                        "name": name,
                                        "angle": pos[i] if i < len(pos) else 0.0,
                                        "torque": eff[i] if i < len(eff) else 0.0,
                                        "temp": vel[i] if i < len(vel) else 0.0
                                    })
                                joints_payload = {
                                    "joints": joints_list,
                                    "is_simulated": (ROBOT_MODE == "SIMULATED")
                                }
                                _mqtt_client.publish("hk07/telemetry/actuators/joints", json.dumps(joints_payload), qos=0)

                            elif topic == "/sensors/camera/thermal_rppg":
                                names = msg.get("name", [])
                                pos = msg.get("position", [])
                                if len(names) >= 3 and len(pos) >= 3:
                                    rppg_payload = {
                                        "rppg_heart_rate": pos[names.index("rppg_heart_rate")],
                                        "thermal_temperature": pos[names.index("thermal_temperature")],
                                        "fever_alert": bool(pos[names.index("fever_alert")]),
                                        "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                        "timestampMs": timestamp_ms
                                    }
                                    _mqtt_client.publish("hk07/sensors/camera/thermal-rppg", json.dumps(rppg_payload), qos=0)

                            elif topic == "/telemetry/pose":
                                # Bridge PoseStamped coordinates directly to dashboard IMU store
                                pose = msg.get("pose", {})
                                pos_data = pose.get("position", {})
                                orientation = pose.get("orientation", {})
                                imu_payload = {
                                    "x": pos_data.get("x", 0.0),
                                    "y": pos_data.get("y", 0.0),
                                    "z": pos_data.get("z", 0.0),
                                    "qw": orientation.get("w", 1.0),
                                    "qx": orientation.get("x", 0.0),
                                    "qy": orientation.get("y", 0.0),
                                    "qz": orientation.get("z", 0.0),
                                    "is_simulated": (ROBOT_MODE == "SIMULATED"),
                                    "timestampMs": timestamp_ms
                                }
                                _mqtt_client.publish("hk07/telemetry/imu", json.dumps(imu_payload), qos=0)

                        if topic == "/telemetry/sensors/vitals":
                            pos = msg.get("position", [])
                            if len(pos) >= 5:
                                hr_val = pos[0] if pos[0] is not None else float('nan')
                                spo2_val = pos[1] if pos[1] is not None else float('nan')
                                temp_val = pos[2] if pos[2] is not None else float('nan')
                                sample = VitalsSample(
                                    heart_rate=float(hr_val),
                                    spo2=float(spo2_val),
                                    body_temperature=float(temp_val),
                                    step_count=0,
                                    alert_level="NORMAL"
                                )
                                await fusion_buf.push_vitals(sample)
                                
                        elif topic == "/sensors/camera/thermal_rppg":
                            pos = msg.get("position", [])
                            if len(pos) >= 2:
                                latest = await fusion_buf.latest_vitals()

                                hr_val = pos[0]
                                hr_final = None
                                if hr_val is not None and not math.isnan(hr_val) and hr_val > 0:
                                    hr_final = float(hr_val)
                                elif latest and latest.heart_rate is not None and not math.isnan(latest.heart_rate):
                                    hr_final = latest.heart_rate
                                # STRICT: if no real hr available → leave None (not 72.0)

                                temp_val = pos[1]
                                temp_final = None
                                if temp_val is not None and not math.isnan(temp_val) and temp_val > 0:
                                    temp_final = float(temp_val)
                                elif latest and latest.body_temperature is not None and not math.isnan(latest.body_temperature):
                                    temp_final = latest.body_temperature
                                # STRICT: if no real temp → leave None (not 36.6)

                                spo2_final = None
                                if latest and latest.spo2 is not None and not math.isnan(latest.spo2):
                                    spo2_final = latest.spo2
                                # STRICT: no real spo2 → None (not 98.0)

                                is_critical = False
                                if len(pos) >= 3 and pos[2] is not None and not math.isnan(pos[2]) and pos[2] > 0:
                                    is_critical = True

                                # Only push if at least one real value exists
                                if any(v is not None for v in [hr_final, temp_final, spo2_final]):
                                    sample = VitalsSample(
                                        heart_rate=hr_final,
                                        spo2=spo2_final,
                                        body_temperature=temp_final,
                                        alert_level="CRITICAL" if is_critical else "NORMAL"
                                    )
                                    await fusion_buf.push_vitals(sample)
                                await bb.write_value("sensor:camera:fever_alert", is_critical, ttl_seconds=3)
                                
                        elif topic == "/vitals/wristband":
                            pos = msg.get("position", [])
                            names = msg.get("name", [])
                            vitals_map = {}
                            for i, name in enumerate(names):
                                if i < len(pos):
                                    vitals_map[name] = pos[i]
                            
                            is_falling = bool(vitals_map.get("is_falling", False))
                            emergency = bool(vitals_map.get("emergency_button_pressed", False))
                            await bb.write_value("sensor:vitals:is_falling", is_falling, ttl_seconds=3)
                            await bb.write_value("sensor:vitals:emergency", emergency, ttl_seconds=3)
                            
                            wrist_motion_mag = vitals_map.get("wrist_motion_magnitude") or 0.0
                            await bb.write_value("sensor:vitals:wrist_motion_magnitude", float(wrist_motion_mag), ttl_seconds=3)
                            
                            hr = vitals_map.get("heart_rate")
                            if hr is not None and not math.isnan(hr):
                                await bb.write_value("sensor:vitals:heart_rate", float(hr), ttl_seconds=3)
                                
                            soc = vitals_map.get("battery_level")
                            if soc is not None and not math.isnan(soc):
                                await bb.write_value("sensor:vitals:battery_level", float(soc), ttl_seconds=3)
                            
                            # Compile vitals:latest — STRICT: only include fields with real values
                            # NEVER inject default mock values (72, 98, 36.6, etc.)
                            vitals_latest = {}
                            if vitals_map.get("heart_rate") is not None and not math.isnan(float(vitals_map["heart_rate"] or 0)):
                                vitals_latest["heart_rate"] = vitals_map["heart_rate"]
                            if vitals_map.get("spo2") is not None and not math.isnan(float(vitals_map["spo2"] or 0)):
                                vitals_latest["spo2"] = vitals_map["spo2"]
                            if vitals_map.get("respiratory_rate") is not None:
                                vitals_latest["respiratory_rate"] = vitals_map["respiratory_rate"]
                            if vitals_map.get("stress_score") is not None:
                                vitals_latest["stress_score"] = vitals_map["stress_score"]
                            if vitals_map.get("battery_level") is not None:
                                vitals_latest["battery_level"] = vitals_map["battery_level"]
                            if vitals_map.get("battery_temp") is not None:
                                vitals_latest["battery_temp"] = vitals_map["battery_temp"]
                            vitals_latest["wrist_motion_magnitude"] = wrist_motion_mag
                            if vitals_map.get("pedometer_steps") is not None:
                                vitals_latest["pedometer_steps"] = vitals_map["pedometer_steps"]
                            if vitals_map.get("activity_type") is not None:
                                vitals_latest["activity_type"] = vitals_map["activity_type"]
                            if vitals_latest:  # only write if we have at least one real field
                                await bb.write_value("sensor:vitals:latest", vitals_latest, ttl_seconds=3)
                            
                            # Environment Data — only write real sensor values, no defaults
                            light = vitals_map.get("ambient_light")
                            baro = vitals_map.get("barometric_pressure")
                            bat_lvl = vitals_map.get("battery_level")
                            bat_temp = vitals_map.get("battery_temp")
                            is_sim = vitals_map.get("is_simulated")

                            existing_env = await bb.read_value("sensor:env:latest") or {}
                            if not isinstance(existing_env, dict):
                                existing_env = {}

                            # STRICT: only update fields when hardware sends real values
                            if light is not None and not math.isnan(light):
                                existing_env["ambient_light"] = float(light)
                            # REMOVED: elif default 150.0 — never inject fake ambient light

                            if baro is not None and not math.isnan(baro):
                                existing_env["barometric_pressure"] = float(baro)

                            if bat_lvl is not None and not math.isnan(bat_lvl):
                                existing_env["battery_level"] = float(bat_lvl)
                            # REMOVED: elif default 100.0 — never inject fake battery level

                            if bat_temp is not None and not math.isnan(bat_temp):
                                existing_env["battery_temp"] = float(bat_temp)
                            # REMOVED: elif default 32.0 — never inject fake battery temp

                            if is_sim is not None:
                                existing_env["is_simulated"] = bool(is_sim)

                            if existing_env:  # only write if at least one real field
                                await bb.write_value("sensor:env:latest", existing_env, ttl_seconds=3)
                            
                            # GPS Location
                            lat = vitals_map.get("latitude")
                            lon = vitals_map.get("longitude")
                            alt = vitals_map.get("altitude")
                            if lat is not None and not math.isnan(lat):
                                loc_data = {
                                    "latitude": float(lat),
                                    "longitude": float(lon),
                                    "altitude": float(alt or 0.0)
                                }
                                await bb.write_value("sensor:location:latest", loc_data, ttl_seconds=5)

                            # Bridge real vitals to Spring Boot MQTT — STRICT: never generate fake spo2/bp/temp
                            if _mqtt_client:
                                hr = vitals_map.get("heart_rate")
                                if hr is not None and not math.isnan(hr) and hr > 0:
                                    hr = int(hr)
                                    # REMOVED: random-generated spo2/bp/temp — fabricated physiological data
                                    # spo2/bp are only bridged when the wristband actually sends them
                                    spo2 = vitals_map.get("spo2")  # real value only
                                    sys_bp = vitals_map.get("systolic")  # real value only
                                    dias_bp = vitals_map.get("diastolic")  # real value only

                                    bat_temp_val = vitals_map.get("battery_temp")
                                    # body_temperature from wristband direct reading only
                                    body_temp_raw = vitals_map.get("body_temperature") or vitals_map.get("skin_temp")
                                    body_temp = float(round(body_temp_raw, 2)) if body_temp_raw else None
                                else:
                                    hr = -1
                                    spo2 = -1.0
                                    sys_bp = -1.0
                                    dias_bp = -1.0
                                    body_temp = -1.0

                                vitals_payload = {
                                    "deviceId": "wristband-sim-001",
                                    "heartRate": hr,
                                    "spo2": spo2,
                                    "bodyTemperature": body_temp,
                                    "systolic": sys_bp,
                                    "diastolic": dias_bp,
                                    "epochTimestampMs": timestamp_ms
                                }
                                try:
                                    _mqtt_client.publish("hk07/sensors/wristband/wristband-sim-001/vitals", json.dumps(vitals_payload), qos=0)
                                except Exception as mqtt_err:
                                    log.error("[ROSBRIDGE_CLIENT_MQTT_ERROR] Failed to bridge wristband vitals: %s", mqtt_err)
                                
                        elif topic == "/sensors/imu/state":
                            now = time.time()
                            last_phone_imu_time = now
                            orientation = msg.get("orientation", {})
                            accel = msg.get("linear_acceleration", {})
                            gyro = msg.get("angular_velocity", {})
                            ax = float(accel.get("x", 0.0)) if accel.get("x") is not None else 0.0
                            ay = float(accel.get("y", 0.0)) if accel.get("y") is not None else 0.0
                            az = float(accel.get("z", 9.81)) if accel.get("z") is not None else 9.81
                            gx = float(gyro.get("x", 0.0)) if gyro.get("x") is not None else 0.0
                            gy = float(gyro.get("y", 0.0)) if gyro.get("y") is not None else 0.0
                            gz = float(gyro.get("z", 0.0)) if gyro.get("z") is not None else 0.0
                            px = 0.0
                            py = 0.0
                            pz = 0.0
                            
                            g_mag = (ax**2 + ay**2 + az**2) ** 0.5
                            wrist_motion_mag = 0.0
                            try:
                                wrist_motion_mag = await bb.read_value("sensor:vitals:wrist_motion_magnitude") or 0.0
                            except Exception:
                                pass
                                
                            imu_data = {
                                "accel_x": ax,
                                "accel_y": ay,
                                "accel_z": az,
                                "gyro_x": gx,
                                "gyro_y": gy,
                                "gyro_z": gz,
                                "qw": float(orientation.get("w", 1.0)) if orientation.get("w") is not None else 1.0,
                                "qx": float(orientation.get("x", 0.0)) if orientation.get("x") is not None else 0.0,
                                "qy": float(orientation.get("y", 0.0)) if orientation.get("y") is not None else 0.0,
                                "qz": float(orientation.get("z", 0.0)) if orientation.get("z") is not None else 0.0,
                                "x": px,
                                "y": py,
                                "z": pz,
                                "frame_id": msg.get("header", {}).get("frame_id", ""),
                                "wrist_motion_magnitude": wrist_motion_mag,
                                "g_magnitude": g_mag
                            }
                            await bb.write_value("sensor:imu:latest", imu_data, ttl_seconds=3)
                            
                        elif topic == "/hk07/perception/clinical":
                            try:
                                clinical_data = json.loads(msg.get("data", "{}"))
                                await bb.write_value("sensor:perception:clinical", clinical_data, ttl_seconds=3)
                            except Exception:
                                pass
                                
        except Exception as e:
            log.error(f"[ROSBRIDGE_CLIENT_ERROR] Connection error: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)

