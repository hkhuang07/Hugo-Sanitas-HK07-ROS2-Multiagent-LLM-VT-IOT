import paho.mqtt.client as mqtt
import json
import time
import sys

broker = "127.0.0.1"
port = 1883

try:
    client = mqtt.Client(client_id="sim-normal-vitals", protocol=mqtt.MQTTv311)
    client.connect(broker, port, 60)
except Exception as e:
    print(f"Error: Unable to connect to MQTT broker at {broker}:{port}. Make sure Mosquitto is running.")
    print(e)
    sys.exit(1)

payload = {
  "heartRate": 75,
  "systolic": 122.3,
  "diastolic": 81.5,
  "bodyTemperature": 36.7,
  "spo2": 98.5,
  "emergency_button_pressed": False,
  "timestamp_ms": int(time.time() * 1000)
}

print(">>> [TEST] Triggering baseline status (Normal health vitals)...")
client.publish("hk07/sensors/wristband/wristband-sim-001/vitals", json.dumps(payload), qos=1)
print(">>> Published to hk07/sensors/wristband/wristband-sim-001/vitals")
print(f">>> Payload: {json.dumps(payload, indent=2)}")
client.disconnect()
