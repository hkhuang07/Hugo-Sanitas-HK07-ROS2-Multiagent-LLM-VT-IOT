import sys
import os
import asyncio
import time
import json
import collections

# Configure path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.medical_agent import MedicalAgent, CircuitBreaker

async def test_patterns():
    print("=== Testing MedicalAgent Enterprise Patterns ===")

    # Mocking memory and arbitrator
    memory = None
    arbitrator = None

    # Initialize MedicalAgent
    agent = MedicalAgent(memory, arbitrator)
    
    # 1. Test Ring Buffer (collections.deque maxlen=50)
    print("\n--- Test 1: Ring Buffer Overflow & Drop-tail ---")
    for i in range(75):
        agent._buffer.append({
            "heartRate": 70 + i,
            "spo2": 98.0,
            "bodyTemperature": 36.6,
            "systolic": 120,
            "diastolic": 80
        })
    
    print(f"Buffer length after adding 75 items: {len(agent._buffer)} (Expected: 50)")
    assert len(agent._buffer) == 50, "Ring Buffer maxlen failed!"
    
    # Verify drop-tail: first element should be index 25 (70+25 = 95)
    first_item = agent._buffer[0]
    print(f"First item HR in buffer: {first_item['heartRate']} (Expected: 95)")
    assert first_item['heartRate'] == 95, "Drop-tail FIFO ordering failed!"
    print("Test 1: PASSED")

    # 2. Test Edge Computing (Moving Average Aggregation)
    print("\n--- Test 2: Edge Computing Sliding Window Average ---")
    agent._buffer.clear()
    for hr_val in [60, 70, 80, 90, 100]:
        agent._buffer.append({
            "heartRate": hr_val,
            "spo2": 95.0,
            "bodyTemperature": 36.5,
            "systolic": 120,
            "diastolic": 80
        })
    
    agg = agent._aggregate_vitals()
    print(f"Aggregated HeartRate average: {agg['heartRate']} (Expected: 80.0)")
    print(f"Aggregated SpO2 average: {agg['spo2']}% (Expected: 95.0%)")
    assert agg['heartRate'] == 80.0, "Aggregated HR is incorrect!"
    assert agg['spo2'] == 95.0, "Aggregated SpO2 is incorrect!"
    print("Test 2: PASSED")

    # 3. Test Circuit Breaker State Machine
    print("\n--- Test 3: Circuit Breaker State Transitions ---")
    cb = CircuitBreaker(failure_threshold=3, recovery_time=1.0)
    
    print(f"Initial State: {cb.state} (Expected: CLOSED)")
    assert cb.state == "CLOSED"
    assert cb.allow_request() is True
    
    # 3 Failures to trip
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    
    print(f"State after 3 failures: {cb.state} (Expected: OPEN)")
    assert cb.state == "OPEN"
    print(f"Is request allowed now? {cb.allow_request()} (Expected: False)")
    assert cb.allow_request() is False
    
    # Wait for recovery time (1 second) to enter HALF_OPEN
    print("Waiting 1.2s for recovery...")
    await asyncio.sleep(1.2)
    
    print(f"Is request allowed now? {cb.allow_request()} (Expected: True)")
    assert cb.allow_request() is True
    print(f"State after recovery probe: {cb.state} (Expected: HALF_OPEN)")
    assert cb.state == "HALF_OPEN"
    
    # Success resets to CLOSED
    cb.record_success()
    print(f"State after success probe: {cb.state} (Expected: CLOSED)")
    assert cb.state == "CLOSED"
    print("Test 3: PASSED")

    # 4. Test State-Transition Filtering & Delta calculation
    print("\n--- Test 4: State-Transition and Delta Filtering ---")
    agent._buffer.clear()
    agent._last_state = "NORMAL"
    agent._last_analyzed_hr = 0.0
    
    # Trigger 4.1: Transition NORMAL -> CRITICAL
    # We will simulate adding CRITICAL vitals (HR = 130)
    for _ in range(5):
        agent._buffer.append({
            "heartRate": 130, # HR_MAX is 120
            "spo2": 95.0,
            "bodyTemperature": 36.5,
            "systolic": 120,
            "diastolic": 80
        })
        
    print("Processing vitals. Expected: state transitions to CRITICAL.")
    # Mock _call_llm_with_fallback to verify it gets called
    call_count = 0
    async def mock_call_llm(vitals, **kwargs):
        nonlocal call_count
        call_count += 1
        return {"alert_level": "CRITICAL", "summary": "Alert", "action": "None"}
        
    agent._call_llm_with_fallback = mock_call_llm
    await agent._process_latest_buffer()
    await asyncio.sleep(0.1) # Give background task time to run
    
    print(f"Current State: {agent._last_state} (Expected: CRITICAL)")
    print(f"Last Analyzed HR: {agent._last_analyzed_hr} (Expected: 130.0)")
    print(f"LLM Call Count: {call_count} (Expected: 1)")
    assert agent._last_state == "CRITICAL"
    assert agent._last_analyzed_hr == 130.0
    assert call_count == 1
    
    # Trigger 4.2: Within CRITICAL, small delta HR (135 bpm -> delta < 15%)
    agent._buffer.clear()
    for _ in range(5):
        agent._buffer.append({
            "heartRate": 135, # Delta is |135-130|/130 = 0.038 < 15%
            "spo2": 95.0,
            "bodyTemperature": 36.5,
            "systolic": 120,
            "diastolic": 80
        })
    await agent._process_latest_buffer()
    await asyncio.sleep(0.1)
    
    print(f"LLM Call Count after small change: {call_count} (Expected: 1 - should be filtered/skipped)")
    assert call_count == 1
    
    # Trigger 4.3: Within CRITICAL, large delta HR (155 bpm -> delta = 19% > 15%)
    agent._buffer.clear()
    for _ in range(5):
        agent._buffer.append({
            "heartRate": 155, # Delta is |155-130|/130 = 0.192 >= 15%
            "spo2": 95.0,
            "bodyTemperature": 36.5,
            "systolic": 120,
            "diastolic": 80
        })
    await agent._process_latest_buffer()
    await asyncio.sleep(0.1)
    
    print(f"LLM Call Count after large delta: {call_count} (Expected: 2)")
    assert call_count == 2
    print(f"Updated Last Analyzed HR: {agent._last_analyzed_hr} (Expected: 155.0)")
    assert agent._last_analyzed_hr == 155.0

    # Trigger 4.4: Transition CRITICAL -> NORMAL (HR = 70)
    agent._buffer.clear()
    for _ in range(5):
        agent._buffer.append({
            "heartRate": 70, # Normal
            "spo2": 98.0,
            "bodyTemperature": 36.5,
            "systolic": 120,
            "diastolic": 80
        })
    await agent._process_latest_buffer()
    await asyncio.sleep(0.1)
    
    print(f"LLM Call Count after transition to NORMAL: {call_count} (Expected: 3)")
    print(f"Current State: {agent._last_state} (Expected: NORMAL)")
    assert agent._last_state == "NORMAL"
    assert call_count == 3
    print("Test 4: PASSED")

    print("\nALL PATTERN TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_patterns())
