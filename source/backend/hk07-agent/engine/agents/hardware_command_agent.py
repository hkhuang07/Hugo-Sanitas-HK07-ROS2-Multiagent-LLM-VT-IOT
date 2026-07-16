"""
hardware_command_agent.py

Agent responsible for parsing high-level intents and translating them into 
concrete hardware commands sent via the HardwareMqttService.
"""

import logging
from typing import Dict, Any, Optional
from services.hardware_mqtt_service import get_hardware_mqtt_service

log = logging.getLogger("hk07.hardware_agent")

class HardwareCommandAgent:
    def __init__(self, arbitrator=None):
        self.arbitrator = arbitrator
        self.mqtt_svc = get_hardware_mqtt_service()
        self.name = "HARDWARE_COMMAND"
        
        # Command map
        self.cmd_map = {
            "stop": 0x00,
            "forward": 0x01,
            "backward": 0x02,
            "left": 0x03,
            "right": 0x04,
            "arm_extend": 0x10,
            "arm_retract": 0x11,
            "estop": 0xFF
        }

    async def process_intent(self, intent: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a hardware-related intent.
        Example intent: "move_forward", "emergency_stop", "turn_left"
        params: {"speed": 50.0}
        """
        if self.arbitrator and self.arbitrator.is_inhibited(self.name):
            log.warning(f"[{self.name}] Agent is currently inhibited.")
            return {"status": "inhibited"}

        if not params:
            params = {}
            
        speed = params.get("speed", 50.0)
        
        # Map intents to commands
        intent_lower = intent.lower()
        cmd_code = 0x00
        
        if "forward" in intent_lower:
            cmd_code = self.cmd_map["forward"]
        elif "back" in intent_lower:
            cmd_code = self.cmd_map["backward"]
        elif "left" in intent_lower:
            cmd_code = self.cmd_map["left"]
        elif "right" in intent_lower:
            cmd_code = self.cmd_map["right"]
        elif "stop" in intent_lower or "halt" in intent_lower:
            cmd_code = self.cmd_map["stop"]
        elif "arm" in intent_lower and "extend" in intent_lower:
            cmd_code = self.cmd_map["arm_extend"]
        elif "arm" in intent_lower and "retract" in intent_lower:
            cmd_code = self.cmd_map["arm_retract"]
        elif "emergency" in intent_lower or "estop" in intent_lower:
            cmd_code = self.cmd_map["estop"]
        else:
            log.warning(f"[{self.name}] Unknown intent: {intent}")
            return {"status": "error", "message": f"Unknown intent: {intent}"}

        priority = 255 if cmd_code == 0xFF else 1
        
        success = self.mqtt_svc.send_command(
            command_id=cmd_code,
            param1=speed,
            param2=0.0,
            priority=priority
        )

        if success:
            return {"status": "success", "command_id": cmd_code, "action": intent}
        else:
            return {"status": "error", "message": "Failed to send MQTT command"}

