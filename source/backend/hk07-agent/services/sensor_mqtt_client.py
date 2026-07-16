import os
import logging
import json
import asyncio
import math
from services.blackboard_service import get_blackboard
import paho.mqtt.client as mqtt

log = logging.getLogger("hk07.sensor_mqtt")

_mqtt_client = None

def on_mqtt_message(client, userdata, msg):
    try:
        import json
        import asyncio
        topic = msg.topic
        payload = json.loads(msg.payload.decode('utf-8'))
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(handle_mqtt_payload(topic, payload), loop)
    except Exception:
        pass

async def handle_mqtt_payload(topic, payload):
    try:
        from services.blackboard_service import get_blackboard
        import math
        bb = get_blackboard()
        if topic == "hk07/sensors/environment/state":
            await bb.write_value("sensor:env:latest", payload, ttl_seconds=3)
        elif topic == "hk07/sensors/location/gps":
            await bb.write_value("sensor:location:latest", payload, ttl_seconds=5)
        elif topic == "hk07/sensors/activity/metrics":
            await bb.write_value("sensor:activity:latest", payload, ttl_seconds=3)
            wrist_motion = payload.get("wrist_motion", [0.0, 0.0, 0.0])
            mag = math.sqrt(sum(x**2 for x in wrist_motion))
            await bb.write_value("sensor:vitals:wrist_motion_magnitude", mag, ttl_seconds=3)
        elif "vitals" in topic or "wristband" in topic:
            names = payload.get("name", [])
            pos = payload.get("position", [])
            vitals_map = {}
            for i, name in enumerate(names):
                if i < len(pos):
                    vitals_map[name] = pos[i]
            
            hr = vitals_map.get("heart_rate")
            if hr is not None and not math.isnan(hr):
                await bb.write_value("sensor:vitals:heart_rate", float(hr), ttl_seconds=3)
            
            soc = vitals_map.get("battery_level")
            if soc is not None:
                await bb.write_value("sensor:vitals:battery_level", float(soc), ttl_seconds=3)
                
            # STRICT: only write real values received from MQTT
            # NEVER inject fake defaults (72, 98, 100, etc.)
            vitals_latest = {}
            if vitals_map.get("heart_rate") is not None:
                vitals_latest["heart_rate"] = vitals_map["heart_rate"]
            if vitals_map.get("spo2") is not None:
                vitals_latest["spo2"] = vitals_map["spo2"]
            if vitals_map.get("respiratory_rate") is not None:
                vitals_latest["respiratory_rate"] = vitals_map["respiratory_rate"]
            if vitals_map.get("stress_score") is not None:
                vitals_latest["stress_score"] = vitals_map["stress_score"]
            if vitals_map.get("battery_level") is not None:
                vitals_latest["battery_level"] = vitals_map["battery_level"]
            if vitals_map.get("battery_temp") is not None:
                vitals_latest["battery_temp"] = vitals_map["battery_temp"]
            if vitals_map.get("wrist_motion_magnitude") is not None:
                vitals_latest["wrist_motion_magnitude"] = vitals_map["wrist_motion_magnitude"]
            if vitals_map.get("pedometer_steps") is not None:
                vitals_latest["pedometer_steps"] = vitals_map["pedometer_steps"]
            if vitals_map.get("activity_type") is not None:
                vitals_latest["activity_type"] = vitals_map["activity_type"]
            if vitals_latest:  # only write when at least one real value received
                await bb.write_value("sensor:vitals:latest", vitals_latest, ttl_seconds=3)
    except Exception:
        pass

def init_mqtt_client():
    global _mqtt_client
    try:
        import paho.mqtt.client as mqtt
        broker = os.getenv("MQTT_BROKER", "localhost")
        port = int(os.getenv("MQTT_PORT", 1883))
        if hasattr(mqtt, "CallbackAPIVersion"):
            _mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        else:
            _mqtt_client = mqtt.Client()
        _mqtt_client.on_message = on_mqtt_message
        _mqtt_client.connect(broker, port, keepalive=60)
        _mqtt_client.subscribe([
            ("hk07/sensors/environment/state", 0),
            ("hk07/sensors/location/gps", 0),
            ("hk07/sensors/activity/metrics", 0),
            ("hk07/sensors/wristband/+/vitals", 0),
            ("hk07/vitals/wristband", 0)
        ])
        _mqtt_client.loop_start()
        log.info(f"[MQTT] Persistent client connected to {broker}:{port} and subscribed to direct sensor topics.")
    except Exception as e:
        log.error(f"[MQTT] Failed to initialize client: {e}")

def close_mqtt_client():
    global _mqtt_client
    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
            log.info("[MQTT] Client disconnected cleanly.")
        except Exception as e:
            log.error(f"[MQTT] Error during disconnect: {e}")

