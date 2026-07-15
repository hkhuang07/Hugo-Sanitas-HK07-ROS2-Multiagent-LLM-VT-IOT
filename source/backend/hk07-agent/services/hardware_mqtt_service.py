"""
hardware_mqtt_service.py

Service to publish hardware commands (Movement, E-Stop, OTA) to the ESP32-S3
via MQTT on 'hk07/robot/command'.
"""
import json
import logging
import os
import paho.mqtt.client as mqtt

log = logging.getLogger("hk07.hardware_mqtt")

class HardwareMqttService:
    def __init__(self):
        self.broker = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
        self.port = int(os.getenv("MQTT_BROKER_PORT", 1883))
        self.topic_cmd = "hk07/robot/command"
        self.client = mqtt.Client(client_id="hk07-hardware-service")
        
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            log.info(f"[HardwareMqtt] Connected to {self.broker}:{self.port}")
        except Exception as e:
            log.error(f"[HardwareMqtt] Failed to connect: {e}")

    def send_command(self, command_id: int, param1: float = 0.0, param2: float = 0.0, priority: int = 1):
        """
        Sends a command to the hardware.
        Commands:
          0x00: Stop
          0x01: Move Forward
          0x02: Move Backward
          0x03: Turn Left
          0x04: Turn Right
          0x10: Arm Extend
          0x11: Arm Retract
          0xFF: E-Stop
        """
        payload = {
            "command": command_id,
            "param1": float(param1),
            "param2": float(param2),
            "priority": priority
        }
        try:
            self.client.publish(self.topic_cmd, json.dumps(payload), qos=1)
            log.info(f"[HardwareMqtt] Sent command: {payload}")
            return True
        except Exception as e:
            log.error(f"[HardwareMqtt] Failed to send command: {e}")
            return False

_instance = None

def get_hardware_mqtt_service() -> HardwareMqttService:
    global _instance
    if _instance is None:
        _instance = HardwareMqttService()
    return _instance
