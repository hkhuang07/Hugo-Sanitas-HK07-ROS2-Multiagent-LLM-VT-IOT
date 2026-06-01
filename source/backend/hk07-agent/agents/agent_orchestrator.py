"""
AgentOrchestrator — Điều phối dữ liệu (State) đi qua các Node Agent (Supervisor/Router -> Agent)
Định dạng State chuẩn theo Quách Hàng Giang MAS Standard.
"""

import logging
import json
from typing import TypedDict, List, Dict, Any, Optional

from agents.router_agent import RouterAgent
from agents.safety_agent import SafetyAgent
from agents.medical_agent import MedicalAgent
from agents.empathetic_agent import EmpatheticAgent

log = logging.getLogger("hk07.agent_orchestrator")

class GraphState(TypedDict):
    messages: List[Dict[str, str]]
    vitals: Dict[str, Any]
    current_agent: str
    output: Optional[str]
    alert_level: Optional[str]
    action: Optional[str]


class AgentOrchestrator:
    def __init__(self, memory=None, arbitrator=None):
        self.router_agent = RouterAgent()
        self.safety_agent = SafetyAgent(arbitrator)
        self.medical_agent = MedicalAgent(memory, arbitrator)
        self.empathetic_agent = EmpatheticAgent(memory, arbitrator)

    async def initialize(self):
        log.info("[ORCHESTRATOR] Sub-agents initialized successfully.")

    async def route_and_execute(self, user_message: str, current_vitals: dict) -> GraphState:
        """
        Main routing loop:
        1. Router classifies intent (Node 0) and returns "ROUTING_TARGET: [SAFETY | MEDICAL | EMPATHETIC]"
        2. Execute the selected node agent (Node 1, 2 or 3)
        3. Returns GraphState containing parsed results
        """
        # Create initial state
        state: GraphState = {
            "messages": [{"role": "user", "content": user_message}],
            "vitals": current_vitals,
            "current_agent": "ROUTER",
            "output": None,
            "alert_level": None,
            "action": None
        }

        # Step 1: Classify intent via Router
        target = "EMPATHETIC"
        try:
            route = await self.router_agent.classify_intent(user_message)
            # route is in the format "ROUTING_TARGET: TARGET"
            for possible_target in ["SAFETY", "MEDICAL", "EMPATHETIC"]:
                if possible_target in route:
                    target = possible_target
                    break
            state["current_agent"] = target
            log.info("[ORCHESTRATOR] Router directed message to: %s (Raw: %s)", target, route)
        except Exception as e:
            log.error("[ORCHESTRATOR_ROUTING_ERROR] Failed to route: %s. Defaulting to EMPATHETIC.", e)
            state["current_agent"] = "EMPATHETIC"
            target = "EMPATHETIC"

        # Step 2: Route to the target node agent
        try:
            if target == "SAFETY":
                res = await self.safety_agent.process_text_interaction(user_message)
                try:
                    res_json = json.loads(res)
                    state["output"] = res_json.get("reason", res)
                    state["alert_level"] = "WARNING" if res_json.get("status") == "DANGER" else "NORMAL"
                    state["action"] = "INHIBIT_SYSTEM" if res_json.get("inhibit_activated") else "MONITOR"
                except Exception:
                    state["output"] = res
                    state["alert_level"] = "WARNING"
                    state["action"] = "CHECK_HARDWARE"
                
            elif target == "MEDICAL":
                res = await self.medical_agent.process_text_interaction(user_message, current_vitals)
                try:
                    res_json = json.loads(res)
                    state["output"] = res_json.get("summary", res)
                    state["alert_level"] = res_json.get("alert_level", "WARNING")
                    state["action"] = res_json.get("action", "CLINICAL_ADVICE")
                except Exception:
                    state["output"] = res
                    state["alert_level"] = "WARNING"
                    state["action"] = "CLINICAL_ADVICE"
                    
            else:  # EMPATHETIC
                res = await self.empathetic_agent.process_text_interaction(user_message)
                state["output"] = res
                state["alert_level"] = "NORMAL"
                state["action"] = "COMPANION_CHAT"
                
        except Exception as e:
            log.error("[ORCHESTRATOR_EXECUTION_ERROR] Failed to execute %s: %s", target, e)
            state["output"] = "Tôi đang gặp chút sự cố xử lý thông tin. Có tôi ở đây bên bạn rồi."
            state["alert_level"] = "WARNING"
            state["action"] = "COMPANION_CHAT"

        # Save routing & processing audit log
        log.info("[AUDIT_TRAIL] Processed event. Agent: %s, Alert: %s, Action: %s", 
                 state["current_agent"], state["alert_level"], state["action"])
        return state

    async def close(self):
        await self.router_agent.close()
        # Clean up client pools
        if self.medical_agent._client:
            await self.medical_agent._client.aclose()
        if self.empathetic_agent._client:
            await self.empathetic_agent._client.aclose()
