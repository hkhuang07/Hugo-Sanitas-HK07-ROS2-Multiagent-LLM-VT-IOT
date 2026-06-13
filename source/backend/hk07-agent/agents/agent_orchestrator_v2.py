"""
AgentOrchestrator v2 — Cognitive Orchestration with Tool Calling

Thay vì routing vào 1 agent, Orchestrator v2 sử dụng LLM Tool Calling để:
1. Quyết định ĐỒNG THỜI gọi nhiều tools (Mixture of Agents)
2. Execute các tools concurrently via asyncio.gather()
3. Aggregate kết quả từ tất cả tools

Định dạng State chuẩn theo Quách Hàng Giang MAS Standard.
"""

import asyncio
import logging
import json
from typing import TypedDict, List, Dict, Any, Optional

from agents.router_agent_v2 import RouterAgentV2
from agents.safety_agent import SafetyAgent
from agents.medical_agent import MedicalAgent
from agents.empathetic_agent import EmpatheticAgent
from agents.perception_agent import PerceptionAgent
from agents.action_agent import ActionAgent
from arbitrator.arbitrator import Arbitrator

from services.blackboard_service import get_blackboard, ClinicalEntry, ActionPlanEntry, current_user_id

log = logging.getLogger("hk07.agent_orchestrator_v2")

class GraphState(TypedDict):
    messages: List[Dict[str, str]]
    vitals: Dict[str, Any]
    current_agents: List[str]
    current_agent: Optional[str]
    outputs: Dict[str, str]
    output: Optional[str]
    alert_level: Optional[str]
    actions: List[str]
    action: Optional[str]
    raw_orchestration_response: str



class AgentOrchestratorV2:
    def __init__(self, memory=None, arbitrator=None):
        self.router_agent = RouterAgentV2()
        self.safety_agent = SafetyAgent(arbitrator)
        self.medical_agent = MedicalAgent(memory, arbitrator)
        self.empathetic_agent = EmpatheticAgent(memory, arbitrator)
        self.perception_agent = PerceptionAgent(arbitrator)
        self.action_agent = ActionAgent(arbitrator)
        self.memory = memory
        self.arbitrator = arbitrator or Arbitrator()

    async def initialize(self):
        log.info("[ORCHESTRATOR_V2] Sub-agents initialized successfully.")

    async def route_and_execute(self, user_message: str, current_vitals: dict, user_id: Optional[str] = None) -> GraphState:
        if user_id is None:
            user_id = current_user_id.get()
        """
        Main orchestration loop (Cognitive Orchestration):
        1. Router with Tool Calling analyzes intent and decides which tools to invoke
        2. Execute all selected tools CONCURRENTLY
        3. Aggregate outputs and return comprehensive state
        
        Example flow:
        - User: "Tôi ho ra máu và rất sợ" (I'm coughing blood and scared)
        - Router decides: ["analyze_clinical_symptoms", "speak_empathetic_response"]
        - Both tools execute in parallel
        - Return aggregated state with both medical findings + empathetic support
        """
        
        # Create initial state
        state: GraphState = {
            "messages": [{"role": "user", "content": user_message}],
            "vitals": current_vitals,
            "current_agents": [],
            "current_agent": "EMPATHETIC_CHAT",
            "outputs": {},
            "output": "",
            "alert_level": "NORMAL",
            "actions": [],
            "action": "COMPANION_CHAT",
            "raw_orchestration_response": ""
        }

        # Step 1: Orchestrate with Tool Calling (LLM decides which tools to invoke)
        orchestration = None
        try:
            orchestration = await self.router_agent.orchestrate_with_tools(user_message)
            state["raw_orchestration_response"] = orchestration.get("raw_response", "")
            state["current_agents"] = orchestration.get("tools_to_invoke", [])
            
            log.info("[ORCHESTRATOR_V2] LLM decided to invoke tools: %s", state["current_agents"])
        except Exception as e:
            log.error("[ORCHESTRATOR_V2_ROUTING_ERROR] Failed to orchestrate: %s. Defaulting to empathetic response.", e)
            orchestration = {
                "tools_to_invoke": ["speak_empathetic_response"],
                "tool_calls": [
                    {
                        "tool_name": "speak_empathetic_response",
                        "parameters": {
                            "user_message": user_message,
                            "emotional_tone": "NEUTRAL"
                        }
                    }
                ]
            }
            state["current_agents"] = ["speak_empathetic_response"]

        # Step 2: Check for Emergency (trigger_sos_protocol takes precedence)
        if "trigger_sos_protocol" in state["current_agents"]:
            log.critical("[ORCHESTRATOR_V2] EMERGENCY ACTIVATION via trigger_sos_protocol")
            state["alert_level"] = "CRITICAL"
            # trigger_sos_protocol is handled by Safety Agent (subsumption priority)
            res = await self._execute_tool("trigger_sos_protocol", {}, current_vitals, user_id=user_id)
            state["outputs"]["trigger_sos_protocol"] = res
            state["actions"].append("EMERGENCY_RESPONSE")
            state["output"] = res
            state["current_agent"] = "SAFETY"
            state["action"] = "EMERGENCY_RESPONSE"
            
            # Still invoke other tools for context, but Safety takes priority
            return state

        # Step 3: Check subsumption inhibition (Safety Agent may inhibit lower tiers)
        for tool in state["current_agents"]:
            if self.arbitrator.is_inhibited("MEDICAL") and "analyze_clinical_symptoms" in tool:
                log.warning("[ORCHESTRATOR_V2] Medical Agent inhibited by Safety subsumption")
                state["current_agents"].remove(tool)
            elif self.arbitrator.is_inhibited("EMPATHETIC") and "speak_empathetic_response" in tool:
                log.warning("[ORCHESTRATOR_V2] Empathetic Agent inhibited by Safety subsumption")
                state["current_agents"].remove(tool)

        # Step 4: Execute tools with Medical-first ordering to avoid race conditions
        if state["current_agents"]:
            try:
                tool_calls = orchestration.get("tool_calls", [])

                # Find medical tool call if present
                medical_call = None
                remaining_calls = []
                for tc in tool_calls:
                    name = tc.get("tool_name")
                    if name == "analyze_clinical_symptoms":
                        medical_call = tc
                    else:
                        remaining_calls.append(tc)

                # If medical is present and not inhibited, run it first and await completion
                if medical_call and "analyze_clinical_symptoms" in state["current_agents"]:
                    try:
                        med_params = medical_call.get("parameters", {})
                        med_result = await self._execute_tool("analyze_clinical_symptoms", med_params, current_vitals, user_id=user_id)
                        state["outputs"]["analyze_clinical_symptoms"] = med_result
                        log.info("[ORCHESTRATOR_V2] Medical tool completed before others")
                    except Exception as e:
                        log.error("[ORCHESTRATOR_V2] Medical tool failed: %s", e)
                        state["outputs"]["analyze_clinical_symptoms"] = f"[ERROR] {str(e)}"

                # Execute remaining tools concurrently (empathetic will run after medical write)
                tasks = []
                for tc in remaining_calls:
                    tool_name = tc.get("tool_name")
                    parameters = tc.get("parameters", {})
                    if tool_name not in state["current_agents"]:
                        continue
                    tasks.append((tool_name, self._execute_tool(tool_name, parameters, current_vitals, user_id=user_id)))

                if tasks:
                    results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
                    for (tool_name, _), result in zip(tasks, results):
                        if isinstance(result, Exception):
                            log.error("[ORCHESTRATOR_V2_TOOL_ERROR] Tool %s failed: %s", tool_name, result)
                            state["outputs"][tool_name] = f"[ERROR] {str(result)}"
                        else:
                            state["outputs"][tool_name] = result
                            log.info("[ORCHESTRATOR_V2] Tool %s completed successfully", tool_name)

                # Determine highest alert level from all outputs
                state["alert_level"] = self._aggregate_alert_levels(state["outputs"])

            except Exception as e:
                log.error("[ORCHESTRATOR_V2_EXECUTION_ERROR] Failed to execute tools: %s", e)
                state["outputs"]["_error"] = str(e)

        # Step 5: Compose final output (aggregate medical + empathetic if both present)
        if not state["outputs"] or all(v.startswith("[ERROR]") for v in state["outputs"].values()):
            # Fallback
            state["outputs"]["fallback"] = "Hugo chưa thể xử lý yêu cầu này. Xin hãy thử lại sau."
            state["alert_level"] = "WARNING"
            state["output"] = state["outputs"]["fallback"]
        else:
            parts = []
            emp_res = state["outputs"].get("speak_empathetic_response")
            if emp_res and not emp_res.startswith("[ERROR]"):
                parts.append(emp_res)
                
            med_res = state["outputs"].get("analyze_clinical_symptoms")
            if med_res and not med_res.startswith("[ERROR]"):
                if not emp_res:
                    parts.append(med_res)
                    
            scan_res = state["outputs"].get("execute_full_body_scan")
            if scan_res and not scan_res.startswith("[ERROR]"):
                # Perception result goes into empathetic context (silent blackboard write already done)
                if not emp_res and not med_res:
                    parts.append(scan_res)
                    
            env_res = state["outputs"].get("execute_environment_scan")
            if env_res and not env_res.startswith("[ERROR]"):
                parts.append(env_res)
                    
            search_res = state["outputs"].get("search_medical_guidelines")
            if search_res and not search_res.startswith("[ERROR]"):
                parts.append(search_res)
                
            sys_res = state["outputs"].get("execute_system_query")
            if sys_res and not sys_res.startswith("[ERROR]"):
                parts.append(sys_res)
            
            action_res = state["outputs"].get("execute_action_plan")
            if action_res and not action_res.startswith("[ERROR]"):
                parts.append(action_res)
                
            sos_res = state["outputs"].get("trigger_sos_protocol")
            if sos_res and not sos_res.startswith("[ERROR]"):
                parts.append(sos_res)
                
            state["output"] = "\n\n".join(parts)
        
        # Map back to single fields for compatibility
        state["current_agent"] = state["current_agents"][0] if state["current_agents"] else "EMPATHETIC_CHAT"
        if "trigger_sos_protocol" in state["current_agents"]:
            state["action"] = "EMERGENCY_RESPONSE"
        elif "execute_action_plan" in state["current_agents"]:
            state["action"] = "ACTUATOR_COMMAND_EXECUTION"
        elif "analyze_clinical_symptoms" in state["current_agents"]:
            state["action"] = "MEDICAL_FIRST_AID" if state["alert_level"] != "NORMAL" else "CLINICAL_ADVICE"
        elif "execute_system_query" in state["current_agents"]:
            state["action"] = "HARDWARE_STATUS_CHECK"
        else:
            state["action"] = "COMPANION_CHAT"

        # Save audit trail
        log.info("[AUDIT_TRAIL_V2] Processed event. Agents: %s, Alert: %s, Actions: %s", 
                 state["current_agents"], state["alert_level"], state["actions"])
        
        if self.memory and state.get("output"):
            await self.memory.ingest_chat_cycle(user_message, state["output"], user_id=user_id)
        
        return state


    async def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], vitals: dict, user_id: Optional[str] = None) -> str:
        if user_id is None:
            user_id = current_user_id.get()
        """Execute a single tool and return its output"""
        try:
            if tool_name == "analyze_clinical_symptoms":
                # Invoke Medical Agent
                symptom = parameters.get("symptom_description", "")
                urgency = parameters.get("urgency_level", "MEDIUM")
                
                res = await self.medical_agent.process_text_interaction(
                    symptom, 
                    vitals, 
                    mode="MEDICAL_ADVICE",
                    user_id=user_id
                )
                
                # Parse JSON response if available
                try:
                    import re
                    res_json = json.loads(res)
                    diag = res_json.get('diagnosis', '')
                    act = res_json.get('action_plan', res_json.get('action', ''))
                    alert = res_json.get('alert_level', 'NORMAL')
                    
                    # Write to Blackboard so EmpatheticAgent can use it
                    bb = get_blackboard()
                    await bb.write_clinical(ClinicalEntry(
                        alert_level=alert,
                        vitals=vitals,
                        diagnosis=diag,
                        action_recommended=act,
                        confidence_score=0.9
                    ), user_id=user_id)
                    
                    # Strip technical prefix labels (e.g. "Chẩn đoán:", "Kế hoạch hành động:")
                    def clean_medical_text(text: str) -> str:
                        if not text:
                            return ""
                        text = re.sub(r'^(chẩn đoán|kế hoạch hành động|kế hoạch|chẩn đoán y tế|chỉ số|lời khuyên|sơ cứu|diagnosis|action_plan|action|plan|advice|warning|critical|normal|hướng dẫn|chăm sóc|chăm sóc y tế|chú ý)[:\-\s]*', '', text, flags=re.IGNORECASE)
                        return text.strip()

                    diag = clean_medical_text(diag)
                    act = clean_medical_text(act)

                    if diag and act:
                        if not (diag.startswith("Ồ") or diag.startswith("Ôi") or diag.startswith("Tôi")):
                            diag_prefix = "Ồ, "
                        else:
                            diag_prefix = ""
                        diag_clean = diag_prefix + diag[0].lower() + diag[1:] if len(diag) > 1 else diag
                        act_clean = act[0].upper() + act[1:] if len(act) > 1 else act
                        result = f"{diag_clean}. {act_clean} Tôi ở đây nếu bạn cần."
                    elif act:
                        act_clean = act[0].upper() + act[1:] if len(act) > 1 else act
                        result = f"{act_clean} Tôi ở đây nếu bạn cần."
                    elif diag:
                        diag_clean = diag[0].upper() + diag[1:] if len(diag) > 1 else diag
                        result = f"{diag_clean}. Tôi ở đây nếu bạn cần."
                    else:
                        result = "Tôi ở đây nếu bạn cần."
                except Exception as e:
                    log.warning("[ORCHESTRATOR_V2] Failed to write clinical entry to blackboard: %s", e)
                    result = res
                
                return result

            elif tool_name == "execute_system_query":
                device = parameters.get("device", "wristband")
                res = await self.empathetic_agent.process_system_query(f"ping {device}")
                return res

            elif tool_name == "speak_empathetic_response":

                # Invoke Empathetic Agent
                user_msg = parameters.get("user_message", "")
                emotional_tone = parameters.get("emotional_tone", "NEUTRAL")
                
                res = await self.empathetic_agent.process_text_interaction(user_msg, user_id=user_id)
                return res

            elif tool_name == "search_medical_guidelines":
                # Search medical knowledge base
                query = parameters.get("query", "")
                
                # Helper to format citation source name
                def format_source_citation(source_url: str) -> str:
                    if not source_url:
                        return "Tài liệu Y tế"
                    if "moh.gov.vn" in source_url:
                        return "Bộ Y Tế VN (moh.gov.vn)"
                    if "cdc.gov" in source_url:
                        return "CDC Hoa Kỳ (cdc.gov)"
                    if "who.int" in source_url:
                        return "Tổ chức Y tế Thế giới WHO (who.int)"
                    try:
                        from urllib.parse import urlparse
                        return urlparse(source_url).netloc or source_url
                    except Exception:
                        return source_url
                
                if self.memory:
                    results = await self.memory.search_medical_guidelines(query, limit=3)
                    if results:
                        formatted_parts = []
                        for r in results:
                            source = r.get("source", "")
                            title = r.get("title", "Hướng dẫn y tế")
                            content = r.get("content", "")
                            citation = format_source_citation(source)
                            formatted_parts.append(
                                f"**{title}**\n{content}\n*(Nguồn: {citation})*"
                            )
                        guidelines_text = "\n\n".join(formatted_parts)
                        return f"Tôi tìm thấy thông tin hướng dẫn y khoa sau đây:\n\n{guidelines_text}"
                
                # Fallback: if no DB guidelines found, call Medical LLM to generate response from parametric knowledge
                # but only if query seems medical to avoid hallucinated tool calls polluting general chat
                query_lower = query.lower()
                medical_keywords = ["tim mạch", "tim", "huyết áp", "sốt", "ho", "đau", "sức khỏe", "y tế", "thuốc", "bệnh", "mệt", "medical", "heart", "health"]
                if any(kw in query_lower for kw in medical_keywords):
                    log.info("[ORCHESTRATOR_V2] Guidelines search empty. Falling back to Medical LLM generation.")
                    fallback_res = await self.medical_agent.process_text_interaction(
                        query, 
                        vitals, 
                        mode="MEDICAL_ADVICE",
                        user_id=user_id
                    )
                    # Parse JSON if returned by medical agent
                    try:
                        res_json = json.loads(fallback_res)
                        diag = res_json.get('diagnosis', '')
                        act = res_json.get('action_plan', res_json.get('action', ''))
                        return f"{diag}. {act}" if diag and act else fallback_res
                    except Exception:
                        return fallback_res
                
                # If not clearly medical, return empty string to avoid polluting empathy chat
                return ""

            elif tool_name == "trigger_sos_protocol":
                # Emergency response (Safety Agent)
                reason = parameters.get("emergency_reason", "Unknown emergency")
                
                # Activate emergency inhibition
                self.arbitrator.inhibit("MEDICAL", duration_s=30)
                self.arbitrator.inhibit("EMPATHETIC", duration_s=30)
                
                log.critical("[SOS_PROTOCOL] Emergency activated: %s", reason)
                return "[緊急対応開始]\n救急車を呼んでいます。位置情報を送信しています。"

            elif tool_name == "execute_full_body_scan":
                # Tier 0.5: Perception Agent full-body scan
                # Silent — writes to Blackboard, returns brief summary for orchestrator
                log.info("[ORCHESTRATOR_V2] Triggering PerceptionAgent full-body scan")
                scan = await self.perception_agent.execute_full_body_scan()
                risk = scan.overall_risk
                notes = scan.notes or ""
                conf = f"{scan.confidence:.0%}"
                summary = (
                    f"[PERCEPTION_SCAN] Risk={risk} | Confidence={conf}"
                    + (f" | {notes}" if notes else "")
                )
                # Upgrade alert_level if scan indicates high risk
                if risk in ("HIGH", "CRITICAL"):
                    log.warning("[ORCHESTRATOR_V2] Perception scan returned risk=%s", risk)
                return summary

            elif tool_name == "execute_environment_scan":
                # LiDAR snapshot from Fusion Buffer
                from services.sensor_fusion_buffer import get_fusion_buffer
                fusion_buf = get_fusion_buffer()
                lidar = await fusion_buf.latest_lidar()
                if lidar:
                    return (
                        f"[ENVIRONMENT_SCAN] Nearest obstacle: {lidar.min_distance_m:.2f}m | "
                        f"Threat: {lidar.threat_level} | Obstacles: {lidar.obstacle_count}"
                    )
                else:
                    return "[ENVIRONMENT_SCAN] No LiDAR data in buffer."

            elif tool_name == "execute_action_plan":
                plan_id = parameters.get("plan_id", f"plan-{int(__import__('time').time())}")
                steps = parameters.get("steps", [])
                
                # Check arbitrator safety gates
                if self.arbitrator.is_inhibited("ACTION"):
                    return "[ACTION_PLAN_BLOCKED] Kế hoạch hành động bị chặn do trạng thái an toàn."
                
                # Check critical vitals
                clinical = await get_blackboard().read_latest_clinical()
                if clinical and clinical.alert_level == "CRITICAL":
                    has_sos = any(s.get('type') == 'SOS_DISPATCH' for s in steps)
                    if not has_sos:
                        return "[ACTION_PLAN_BLOCKED] Kế hoạch hành động bị chặn do đang trong trạng thái cấp cứu."

                # Construct ActionPlanEntry
                plan_entry = ActionPlanEntry(
                    plan_id=plan_id,
                    steps=steps,
                    status="PENDING",
                    current_step_index=0
                )
                
                # Execute
                result = await self.action_agent.execute_plan(plan_entry)
                return result

            else:
                return f"[Unknown tool: {tool_name}]"

        except Exception as e:
            log.error("[TOOL_EXECUTION_ERROR] Tool %s failed: %s", tool_name, e)
            raise

    def _aggregate_alert_levels(self, outputs: Dict[str, str]) -> str:
        """Aggregate alert levels from all tool outputs"""
        # Priority: CRITICAL > WARNING > NORMAL
        if any("CRITICAL" in v or "緊急" in v or "SOS" in v for v in outputs.values()):
            return "CRITICAL"
        if any("WARNING" in v or "警告" in v for v in outputs.values()):
            return "WARNING"
        return "NORMAL"

    async def close(self):
        await self.router_agent.close()
        await self.action_agent.close()
        # Clean up client pools
        if hasattr(self.medical_agent, '_client') and self.medical_agent._client:
            await self.medical_agent._client.aclose()
        if hasattr(self.empathetic_agent, '_client') and self.empathetic_agent._client:
            await self.empathetic_agent._client.aclose()
