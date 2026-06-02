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
from arbitrator.arbitrator import Arbitrator

log = logging.getLogger("hk07.agent_orchestrator_v2")

class GraphState(TypedDict):
    messages: List[Dict[str, str]]
    vitals: Dict[str, Any]
    current_agents: List[str]  # Changed from current_agent (singular) to multiple
    outputs: Dict[str, str]  # tool_name -> output
    alert_level: Optional[str]
    actions: List[str]  # Multiple actions from different agents
    raw_orchestration_response: str


class AgentOrchestratorV2:
    def __init__(self, memory=None, arbitrator=None):
        self.router_agent = RouterAgentV2()
        self.safety_agent = SafetyAgent(arbitrator)
        self.medical_agent = MedicalAgent(memory, arbitrator)
        self.empathetic_agent = EmpatheticAgent(memory, arbitrator)
        self.memory = memory
        self.arbitrator = arbitrator or Arbitrator()

    async def initialize(self):
        log.info("[ORCHESTRATOR_V2] Sub-agents initialized successfully.")

    async def route_and_execute(self, user_message: str, current_vitals: dict) -> GraphState:
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
            "outputs": {},
            "alert_level": "NORMAL",
            "actions": [],
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
            res = await self._execute_tool("trigger_sos_protocol", {}, current_vitals)
            state["outputs"]["trigger_sos_protocol"] = res
            state["actions"].append("EMERGENCY_RESPONSE")
            
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
                        med_result = await self._execute_tool("analyze_clinical_symptoms", med_params, current_vitals)
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
                    tasks.append((tool_name, self._execute_tool(tool_name, parameters, current_vitals)))

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
        
        # Save audit trail
        log.info("[AUDIT_TRAIL_V2] Processed event. Agents: %s, Alert: %s, Actions: %s", 
                 state["current_agents"], state["alert_level"], state["actions"])
        
        return state

    async def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], vitals: dict) -> str:
        """Execute a single tool and return its output"""
        try:
            if tool_name == "analyze_clinical_symptoms":
                # Invoke Medical Agent
                symptom = parameters.get("symptom_description", "")
                urgency = parameters.get("urgency_level", "MEDIUM")
                
                res = await self.medical_agent.process_text_interaction(
                    symptom, 
                    vitals, 
                    mode="MEDICAL_ADVICE"
                )
                
                # Parse JSON response if available
                try:
                    res_json = json.loads(res)
                    result = f"[醫療分析]\n診斷: {res_json.get('diagnosis', '')}\n建議: {res_json.get('action', '')}"
                except:
                    result = res
                
                return result

            elif tool_name == "speak_empathetic_response":
                # Invoke Empathetic Agent
                user_msg = parameters.get("user_message", "")
                emotional_tone = parameters.get("emotional_tone", "NEUTRAL")
                
                res = await self.empathetic_agent.process_text_interaction(user_msg)
                return res

            elif tool_name == "search_medical_guidelines":
                # Search medical knowledge base
                query = parameters.get("query", "")
                
                if self.memory:
                    results = await self.memory.search_similar_patterns(query, limit=3)
                    if results:
                        return f"[醫療指南]\n" + "\n".join([r.get("content", "") for r in results])
                
                return "[No medical guidelines found]"

            elif tool_name == "trigger_sos_protocol":
                # Emergency response (Safety Agent)
                reason = parameters.get("emergency_reason", "Unknown emergency")
                
                # Activate emergency inhibition
                self.arbitrator.inhibit("MEDICAL", duration_s=30)
                self.arbitrator.inhibit("EMPATHETIC", duration_s=30)
                
                log.critical("[SOS_PROTOCOL] Emergency activated: %s", reason)
                return "[緊急対応開始]\n救急車を呼んでいます。位置情報を送信しています。"

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
        # Clean up client pools
        if self.medical_agent._client:
            await self.medical_agent._client.aclose()
        if self.empathetic_agent._client:
            await self.empathetic_agent._client.aclose()
