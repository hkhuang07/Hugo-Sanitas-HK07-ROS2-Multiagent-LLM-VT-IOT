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
    print("=== Testing HK-07 Orchestrator (End-To-End) ===")
    
    # Initialize Memory
    memory = LanceMemory()
    await memory.initialize()
    
    # Initialize Arbitrator
    arbitrator = Arbitrator()
    
    # Initialize Orchestrator
    orchestrator = AgentOrchestrator(memory=memory, arbitrator=arbitrator)
    await orchestrator.initialize()

    # 1. Test case: Safety Agent (Real danger command)
    print("\n[TEST 1] Safety Agent (Should trigger DANGER status & inhibit due to distance < threshold):")
    state_safety = await orchestrator.route_and_execute("LiDAR phát hiện vật cản khoảng cách 0.3m", {})
    print(f"-> Selected Agent: {state_safety['current_agent']}")
    print(f"-> Response: {state_safety['output']}")
    print(f"-> Alert Level: {state_safety['alert_level']}")
    print(f"-> System Action: {state_safety['action']}")

    # 2. Test case: Safety System (Informational question - should now be routed to Empathetic LLM agent!)
    print("\n[TEST 2] Safety explanation question (Should route to EMPATHETIC LLM):")
    state_explain = await orchestrator.route_and_execute("Làm thế nào để hệ thống an toàn Lidar và Subsumption ngăn chặn va chạm?", {})
    print(f"-> Selected Agent: {state_explain['current_agent']}")
    print(f"-> Response: {state_explain['output']}")
    print(f"-> Alert Level: {state_explain['alert_level']}")
    print(f"-> System Action: {state_explain['action']}")

    # 3. Test case: Medical Agent
    print("\n[TEST 3] Medical Agent (Vitals check + request for cardiovascular advice):")
    vitals = {
        "heartRate": 135,
        "spo2": 96.0,
        "bodyTemperature": 36.6,
        "systolic": 130,
        "diastolic": 85
    }
    state_medical = await orchestrator.route_and_execute("Nhịp tim và huyết áp của tôi thế nào? Cho tôi lời khuyên bảo vệ sức khỏe tim mạch.", vitals)
    print(f"-> Selected Agent: {state_medical['current_agent']}")
    print(f"-> Response: {state_medical['output']}")
    print(f"-> Alert Level: {state_medical['alert_level']}")
    print(f"-> System Action: {state_medical['action']}")

    # 4. Test case: Empathetic Agent
    print("\n[TEST 4] Empathetic Agent (Greeting & emotional support query):")
    state_empathy = await orchestrator.route_and_execute("Tôi cảm thấy hơi mệt mỏi và lo lắng.", {})
    print(f"-> Selected Agent: {state_empathy['current_agent']}")
    print(f"-> Response: {state_empathy['output']}")
    print(f"-> Alert Level: {state_empathy['alert_level']}")
    print(f"-> System Action: {state_empathy['action']}")

    # Clean up
    await orchestrator.close()

if __name__ == "__main__":
    asyncio.run(run_tests())
