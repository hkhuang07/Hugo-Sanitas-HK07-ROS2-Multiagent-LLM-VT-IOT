"""
AgentOrchestrator — Điều phối dữ liệu (State) đi qua các Node Agent (Supervisor/Router -> Agent)
Định dạng State chuẩn theo Quách Hàng Giang MAS Standard.
"""

import logging
import json
from typing import TypedDict, List, Dict, Any, Optional

from engine.agents.router_agent import RouterAgent
from engine.agents.safety_agent import SafetyAgent
from engine.agents.care_agent import CareAgent
from engine.agents.empathetic_agent import EmpatheticAgent
from services.blackboard_service import current_user_id

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
        self.care_agent = CareAgent(memory, arbitrator)
        self.medical_agent = self.care_agent  # backward-compatibility alias
        self.empathetic_agent = EmpatheticAgent(memory, arbitrator)
        self.memory = memory

    async def initialize(self):
        log.info("[ORCHESTRATOR] Sub-agents initialized successfully.")

    async def route_and_execute(self, user_message: str, current_vitals: dict, user_id: Optional[str] = None) -> GraphState:
        if user_id is None:
            user_id = current_user_id.get()
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
        target = "EMPATHETIC_CHAT"
        try:
            route = await self.router_agent.classify_intent(user_message)
            # route is in the format "ROUTING_TARGET: TARGET"
            for possible_target in ["MEDICAL_ANALYSIS", "MEDICAL_ADVICE", "SYSTEM_QUERY", "EMPATHETIC_CHAT"]:
                if possible_target in route:
                    target = possible_target
                    break
            state["current_agent"] = target
            log.info("[ORCHESTRATOR] Router directed message to: %s (Raw: %s)", target, route)
        except Exception as e:
            log.error("[ORCHESTRATOR_ROUTING_ERROR] Failed to route: %s. Defaulting to EMPATHETIC_CHAT.", e)
            state["current_agent"] = "EMPATHETIC_CHAT"
            target = "EMPATHETIC_CHAT"

        # Step 2: Route to the target node agent
        try:
            msg_lower = user_message.lower()
            if any(k in msg_lower for k in ["quét tôi", "quét hình ảnh", "nhìn tôi", "chẩn đoán qua ảnh", "scan me", "visual scan", "look at me", "tôi trông thế nào"]):
                log.info("[ORCHESTRATOR] Keyword matching visual scan. Routing to execute_visual_scan().")
                res = await self.empathetic_agent.execute_visual_scan(current_vitals, user_id=user_id)
                state["current_agent"] = "VISUAL_SCAN"
                state["output"] = res
                state["alert_level"] = "NORMAL"
                state["action"] = "VISUAL_SCAN_DIAGNOSIS"
            elif target == "SYSTEM_QUERY":
                res = await self.empathetic_agent.process_system_query(user_message)
                state["output"] = res
                state["alert_level"] = "NORMAL"
                state["action"] = "HARDWARE_STATUS_CHECK"

            elif target == "MEDICAL_ANALYSIS":
                res = await self.medical_agent.process_text_interaction(user_message, current_vitals, mode="MEDICAL_ANALYSIS", user_id=user_id)
                try:
                    res_json = json.loads(res)
                    state["output"] = res_json.get("summary", res)
                    state["alert_level"] = res_json.get("alert_level", "NORMAL")
                    state["action"] = res_json.get("action", "CLINICAL_ADVICE")
                except Exception:
                    state["output"] = res
                    state["alert_level"] = "WARNING"
                    state["action"] = "CLINICAL_ADVICE"

            elif target == "MEDICAL_ADVICE":
                res = await self.medical_agent.process_text_interaction(user_message, current_vitals, mode="MEDICAL_ADVICE", user_id=user_id)
                try:
                    import re
                    res_json = json.loads(res)
                    diagnosis = res_json.get("diagnosis", "")
                    action_plan = res_json.get("action_plan", "")
                    state["alert_level"] = res_json.get("alert_level", "WARNING")
                    state["action"] = "MEDICAL_FIRST_AID"

                    # Strip technical prefix labels (e.g. "Chẩn đoán:", "Kế hoạch hành động:")
                    def clean_medical_text(text: str) -> str:
                        if not text:
                            return ""
                        text = re.sub(r'^(chẩn đoán|kế hoạch hành động|kế hoạch|chẩn đoán y tế|chỉ số|lời khuyên|sơ cứu|diagnosis|action_plan|action|plan|advice|warning|critical|normal|hướng dẫn|chăm sóc|chăm sóc y tế|chú ý)[:\-\s]*', '', text, flags=re.IGNORECASE)
                        return text.strip()

                    diag = clean_medical_text(diagnosis)
                    act = clean_medical_text(action_plan)

                    if diag and act:
                        if not (diag.startswith("Ồ") or diag.startswith("Ôi") or diag.startswith("Tôi")):
                            diag_prefix = "Ồ, "
                        else:
                            diag_prefix = ""
                        diag_clean = diag_prefix + diag[0].lower() + diag[1:] if len(diag) > 1 else diag
                        act_clean = act[0].upper() + act[1:] if len(act) > 1 else act
                        state["output"] = f"{diag_clean}. {act_clean} Tôi ở đây nếu bạn cần."
                    elif act:
                        act_clean = act[0].upper() + act[1:] if len(act) > 1 else act
                        state["output"] = f"{act_clean} Tôi ở đây nếu bạn cần."
                    elif diag:
                        diag_clean = diag[0].upper() + diag[1:] if len(diag) > 1 else diag
                        state["output"] = f"{diag_clean}. Tôi ở đây nếu bạn cần."
                    else:
                        state["output"] = "Tôi ở đây nếu bạn cần."
                except Exception:
                    state["output"] = res
                    state["alert_level"] = "WARNING"
                    state["action"] = "MEDICAL_FIRST_AID"

            else:  # EMPATHETIC_CHAT
                res = await self.empathetic_agent.process_text_interaction(user_message, user_id=user_id)
                state["output"] = res
                state["alert_level"] = "NORMAL"
                state["action"] = "COMPANION_CHAT"
                
        except Exception as e:
            log.error("[ORCHESTRATOR_EXECUTION_ERROR] Failed to execute %s: %s", target, e)
            state["output"] = "Tôi đang gặp chút sự cố xử lý thông tin. Hugo luôn ở đây đồng hành cùng bạn."
            state["alert_level"] = "WARNING"
            state["action"] = "COMPANION_CHAT"

        # Save routing & processing audit log
        log.info("[AUDIT_TRAIL] Processed event. Agent: %s, Alert: %s, Action: %s", 
                 state["current_agent"], state["alert_level"], state["action"])
        
        if self.memory and state.get("output"):
            await self.memory.ingest_chat_cycle(user_message, state["output"], user_id=user_id)
            
        return state

    async def close(self):
        await self.router_agent.close()
        # Clean up client pools
        if hasattr(self.medical_agent, '_client') and self.medical_agent._client:
            await self.medical_agent._client.aclose()
        if hasattr(self.empathetic_agent, '_client') and self.empathetic_agent._client:
            await self.empathetic_agent._client.aclose()

