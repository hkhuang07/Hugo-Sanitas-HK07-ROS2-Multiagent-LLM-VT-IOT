import paho.mqtt.client as mqtt
import json
import time
import sys

broker = "127.0.0.1"
port = 1883

try:
    client = mqtt.Client(client_id="sim-fall", protocol=mqtt.MQTTv311)
    client.connect(broker, port, 60)
except Exception as e:
    print(f"Error: Unable to connect to MQTT broker at {broker}:{port}. Make sure Mosquitto is running.")
    print(e)
    sys.exit(1)

# Magnitude = sqrt(15^2 + 18^2 + 22^2)/9.81 = 3.27g > 2.5g (threshold)
payload = {
  "accel_x": 15.0,
  "accel_y": 18.0,
  "accel_z": 22.0,
  "timestamp_ms": int(time.time() * 1000)
}

print(">>> [TEST] Triggering Safety Incident (User Fall Risk detected by IMU)...")
client.publish("hk07/sensors/imu/state", json.dumps(payload), qos=1)
print(">>> Published to hk07/sensors/imu/state")
print(f">>> Payload: {json.dumps(payload, indent=2)}")
client.disconnect()
