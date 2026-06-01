import sys
import os
import asyncio

# Reconfigure stdout to support UTF-8 on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.agent_orchestrator import AgentOrchestrator
from memory.lance_memory import LanceMemory
from arbitrator.arbitrator import Arbitrator

async def run_tests():
    print("=== Testing HK-07 Orchestrator (Cognitive Upgrade V2) ===")
    
    # Initialize Memory
    memory = LanceMemory()
    await memory.initialize()
    
    # Initialize Arbitrator
    arbitrator = Arbitrator()
    
    # Initialize Orchestrator
    orchestrator = AgentOrchestrator(memory=memory, arbitrator=arbitrator)
    await orchestrator.initialize()

    # 1. Test case: SYSTEM_QUERY (Hardware / sensor ping tool calling)
    print("\n[TEST 1] SYSTEM_QUERY - Hardware check & Tool Calling:")
    state_system = await orchestrator.route_and_execute("Kiểm tra cảm biến và ping thiết bị wristband", {})
    print(f"-> Selected Agent: {state_system['current_agent']}")
    print(f"-> Response: {state_system['output']}")
    print(f"-> Alert Level: {state_system['alert_level']}")
    print(f"-> System Action: {state_system['action']}")

    # 2. Test case: MEDICAL_ANALYSIS (Vitals reading analysis)
    print("\n[TEST 2] MEDICAL_ANALYSIS - Vitals health check:")
    vitals = {
        "heartRate": 135,
        "spo2": 96.0,
        "bodyTemperature": 36.6,
        "systolic": 130,
        "diastolic": 85
    }
    state_analysis = await orchestrator.route_and_execute("Nhịp tim và huyết áp của tôi hiện tại thế nào?", vitals)
    print(f"-> Selected Agent: {state_analysis['current_agent']}")
    print(f"-> Response: {state_analysis['output']}")
    print(f"-> Alert Level: {state_analysis['alert_level']}")
    print(f"-> System Action: {state_analysis['action']}")

    # 3. Test case: MEDICAL_ADVICE (Symptom declaration + first aid)
    print("\n[TEST 3] MEDICAL_ADVICE - Symptom declaration (pain/sickness):")
    state_advice = await orchestrator.route_and_execute("Tôi bị đau tay rất nhiều sau khi ngã và có vẻ tay bị sưng gãy", vitals)
    print(f"-> Selected Agent: {state_advice['current_agent']}")
    print(f"-> Response: {state_advice['output']}")
    print(f"-> Alert Level: {state_advice['alert_level']}")
    print(f"-> System Action: {state_advice['action']}")

    # 4. Test case: EMPATHETIC_CHAT (General small talk / emotional check)
    print("\n[TEST 4] EMPATHETIC_CHAT - Greetings & Support:")
    state_chat = await orchestrator.route_and_execute("Tôi cảm thấy mệt mỏi và lo lắng cho buổi khám ngày mai.", vitals)
    print(f"-> Selected Agent: {state_chat['current_agent']}")
    print(f"-> Response: {state_chat['output']}")
    print(f"-> Alert Level: {state_chat['alert_level']}")
    print(f"-> System Action: {state_chat['action']}")

    # Clean up
    await orchestrator.close()

if __name__ == "__main__":
    asyncio.run(run_tests())
