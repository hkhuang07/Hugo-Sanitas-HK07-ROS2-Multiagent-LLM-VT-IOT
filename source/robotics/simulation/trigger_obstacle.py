import paho.mqtt.client as mqtt
import json
import time
import sys

broker = "127.0.0.1"
port = 1883

try:
    client = mqtt.Client(client_id="sim-obstacle", protocol=mqtt.MQTTv311)
    client.connect(broker, port, 60)
except Exception as e:
    print(f"Error: Unable to connect to MQTT broker at {broker}:{port}. Make sure Mosquitto is running.")
    print(e)
    sys.exit(1)

payload = {
  "ranges": [1.2, 0.8, 0.45, 1.5, 2.0],  # range 0.45m < 0.5m will trigger obstacle stop
  "timestamp_ms": int(time.time() * 1000)
}

print(">>> [TEST] Triggering Safety Incident (Obstacle detected at 0.45m)...")
client.publish("hk07/sensors/lidar/scan", json.dumps(payload), qos=1)
print(">>> Published to hk07/sensors/lidar/scan")
print(f">>> Payload: {json.dumps(payload, indent=2)}")
client.disconnect()
