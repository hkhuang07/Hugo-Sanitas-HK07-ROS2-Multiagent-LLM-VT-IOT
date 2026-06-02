import os
import sys
import math
import time
import random
import logging
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt
import json

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("vivo_bridge")

app = Flask(__name__)

# Configurations
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "hk07sim")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")

DEVICE_ID = "wristband-sim-001"
VITALS_TOPIC = f"hk07/sensors/wristband/{DEVICE_ID}/vitals"
IMU_TOPIC = "hk07/sensors/imu/state"

FALL_COOLDOWN_SEC = 3.0
last_fall_time = 0.0

# Initialize MQTT Client
mqtt_client = mqtt.Client(client_id="vivo-http-bridge", protocol=mqtt.MQTTv311)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

def connect_mqtt():
    try:
        log.info(f"Connecting to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}...")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        log.info("MQTT Loop started successfully.")
    except Exception as e:
        log.error(f"Failed to connect to MQTT broker: {e}. Bridge will try to publish later.")

connect_mqtt()

@app.route("/data", methods=["POST"])
def handle_sensor_data():
    global last_fall_time
    
    try:
        data = request.get_json(force=True)
        if not data or "payload" not in data:
            return jsonify({"status": "error", "message": "Invalid JSON format"}), 400
        
        payload_list = data.get("payload", [])
        
        # Default gravity acceleration
        x, y, z = 0.0, 0.0, 9.81
        found_accel = False
        
        # Parse accelerometer data
        for item in payload_list:
            if item.get("name") == "accelerometer":
                values = item.get("values", {})
                x = values.get("x", 0.0)
                y = values.get("y", 0.0)
                z = values.get("z", 9.81)
                found_accel = True
                break
        
        # Perform Fall Detection math
        g_magnitude = math.sqrt(x**2 + y**2 + z**2)
        
        # Trigger fall state on sudden shifts (free fall < 4m/s2 or high-g impact > 20m/s2)
        is_falling_now = (g_magnitude < 4.0) or (g_magnitude > 20.0)
        now_time = time.time()
        
        if is_falling_now:
            last_fall_time = now_time
            log.warning(f"[FALL DETECTED] Sudden acceleration change: {g_magnitude:.2f} m/s^2 (x: {x:.2f}, y: {y:.2f}, z: {z:.2f})")
            
        # Maintain fall state for a brief cooldown duration to allow downstream systems to react
        is_falling = (now_time - last_fall_time) < FALL_COOLDOWN_SEC
        timestamp_ms = int(now_time * 1000)
        
        # Compile Vitals Payload (Simulating companion data for ECG charts)
        vitals_payload = {
            "heartRate": random.randint(70, 80) if not is_falling else random.randint(130, 160),
            "systolic": 120.0 if not is_falling else 160.0,
            "diastolic": 80.0 if not is_falling else 100.0,
            "bodyTemperature": 36.6,
            "spo2": round(random.uniform(96.0, 99.0), 1) if not is_falling else round(random.uniform(88.0, 92.0), 1),
            "emergency_button_pressed": is_falling,
            "timestamp_ms": timestamp_ms
        }
        
        # Compile Raw IMU Payload
        imu_payload = {
            "accel_x": x,
            "accel_y": y,
            "accel_z": z,
            "timestamp_ms": timestamp_ms
        }
        
        # Publish to MQTT Broker
        if mqtt_client.is_connected():
            # Publish vital signs
            mqtt_client.publish(VITALS_TOPIC, json.dumps(vitals_payload), qos=1)
            
            # Publish IMU states if we processed a valid accelerometer packet
            if found_accel:
                mqtt_client.publish(IMU_TOPIC, json.dumps(imu_payload), qos=1)
                
            log.debug(f"Forwarded: HR={vitals_payload['heartRate']} SpO2={vitals_payload['spo2']} FallState={is_falling}")
        else:
            log.warning("MQTT not connected. Retrying connection...")
            connect_mqtt()
            
        return jsonify({
            "status": "success", 
            "g_force_ms2": round(g_magnitude, 2),
            "is_falling": is_falling
        }), 200
        
    except Exception as e:
        log.error(f"Error processing packet: {e}")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500

if __name__ == "__main__":
    # Listening on all interfaces (0.0.0.0) at port 8080 for phone push uplink
    log.info("Starting Multi-Protocol Bridge Server on 0.0.0.0:8080...")
    app.run(host="0.0.0.0", port=8080, debug=False)
