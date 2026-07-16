import asyncio
import json
import os
import sys

# Ensure local package imports resolve when run from tests folder
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from engine.agents.agent_orchestrator_v2 import AgentOrchestratorV2
from engine.memory.lance_memory import LanceMemory
from engine.arbitrator.arbitrator import Arbitrator
from services.blackboard_service import get_blackboard


async def run_test():
    memory = LanceMemory()
    arbitrator = Arbitrator()
    orchestrator = AgentOrchestratorV2(memory=memory, arbitrator=arbitrator)

    user_message = "Tôi đau ngực quá"
    current_vitals = {
        "hr": 115,
        "spo2": 95,
        "bp": "130/85",
        "temperature": 37.2
    }

    print("=== Cognitive Orchestrator Integration Test ===")
    print(f"User message: {user_message}")
    print(f"Vitals: {json.dumps(current_vitals, ensure_ascii=False)}")

    state = await orchestrator.route_and_execute(user_message, current_vitals)

    print("\n--- Orchestrator State ---")
    print(json.dumps(state, ensure_ascii=False, indent=2))

    blackboard = get_blackboard()
    clinical_entry = await blackboard.read_latest_clinical()

    print("\n--- Blackboard Latest Clinical Entry ---")
    if clinical_entry:
        print(json.dumps(clinical_entry.__dict__, ensure_ascii=False, indent=2))
    else:
        print("No clinical entry was written to Blackboard.")

    print("\n--- Blackboard Backend ---")
    print(f"use_redis={blackboard._use_redis}")
    print(f"in_memory_keys={len([k for k in blackboard._in_memory_store if k.startswith('blackboard:clinical:')])}")

    await orchestrator.close()


if __name__ == "__main__":
    asyncio.run(run_test())
