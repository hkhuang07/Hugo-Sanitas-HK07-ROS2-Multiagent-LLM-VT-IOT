"""
HK-07 Edge Controller for Webots Simulation

[HẠNCHẾ-#16 & #18 FIX]
- MQTT Fallback: Self-inhibit to 0 velocity on disconnect.
- Subsumption IPC: Subscribes to hk07/control/subsumption/inhibit to lock motors.
"""

import json
import logging
import os
import sys
import time

import paho.mqtt.client as mqtt

try:
    from controller import Robot
except ImportError:
    # Fallback mock for testing outside Webots
    class Robot:
        def step(self, time_step): return time_step
        def getMotor(self, name): return MockMotor()
        def getBasicTimeStep(self): return 32
    
    class MockMotor:
        def setPosition(self, pos): pass
        def setVelocity(self, vel): pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
log = logging.getLogger("hk07.edge_controller")

class EdgeController:
    def __init__(self):
        self.robot = Robot()
        self.timestep = int(self.robot.getBasicTimeStep())
        
        # Initialize motors
        self.left_motor = self.robot.getMotor("left wheel motor")
        self.right_motor = self.robot.getMotor("right wheel motor")
        self.left_motor.setPosition(float('inf'))
        self.right_motor.setPosition(float('inf'))
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)
        
        self.MAX_SPEED = 6.28
        self.subsumption_inhibited = False
        self.mqtt_connected = False
        
        self.mqtt_client = mqtt.Client(client_id="webots-edge-controller", protocol=mqtt.MQTTv311)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_message = self.on_message
        
        # MQTT Auth
        mqtt_user = os.getenv("MQTT_USERNAME", "admin")
        mqtt_pass = os.getenv("MQTT_PASSWORD", "secret")
        if mqtt_user:
            self.mqtt_client.username_pw_set(mqtt_user, mqtt_pass)

    def connect_mqtt(self):
        broker = os.getenv("MQTT_BROKER_HOST", "localhost")
        port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        try:
            self.mqtt_client.connect(broker, port, keepalive=30)
            self.mqtt_client.loop_start()
        except Exception as e:
            log.error("[EDGE] Failed to connect to MQTT broker: %s", e)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("[EDGE] Connected to MQTT broker.")
            self.mqtt_connected = True
            # [HẠNCHẾ-#18] Subscribe to Subsumption Inhibit command
            self.mqtt_client.subscribe("hk07/control/subsumption/inhibit", qos=1)
        else:
            log.error("[EDGE] MQTT Connect failed with code %d", rc)

    def on_disconnect(self, client, userdata, rc):
        log.warning("[EDGE] MQTT Disconnected (rc=%d)!", rc)
        self.mqtt_connected = False
        # [HẠNCHẾ-#16] Self-inhibit on disconnect to prevent blind movement
        self._halt_motors()
        log.warning("[EDGE] Self-Inhibited due to MQTT disconnect.")

    def on_message(self, client, userdata, msg):
        if msg.topic == "hk07/control/subsumption/inhibit":
            try:
                data = json.loads(msg.payload.decode("utf-8"))
                active = data.get("subsumptionActivated", False)
                self.subsumption_inhibited = active
                
                if active:
                    log.warning("[EDGE] SUBSUMPTION INHIBIT RECEIVED. HALTING MOTORS.")
                    self._halt_motors()
                else:
                    log.info("[EDGE] SUBSUMPTION CLEAR RECEIVED. MOTION RESTORED.")
            except Exception as e:
                log.error("[EDGE] Error parsing inhibit msg: %s", e)

    def _halt_motors(self):
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

    def run_loop(self):
        self.connect_mqtt()
        log.info("[EDGE] Starting control loop...")
        
        while self.robot.step(self.timestep) != -1:
            if self.subsumption_inhibited or not self.mqtt_connected:
                # Force halt
                self._halt_motors()
            else:
                # Normal patrol behavior mock (e.g. wander)
                self.left_motor.setVelocity(self.MAX_SPEED * 0.5)
                self.right_motor.setVelocity(self.MAX_SPEED * 0.5)

if __name__ == "__main__":
    controller = EdgeController()
    controller.run_loop()
