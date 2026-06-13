# Walkthrough: Phase 16, Phase 17 & Phase 18 Complete

This document walkthroughs the design and implementation for Phase 16 (ROS 2 Migration), Phase 17 (Clinical Depth & Blackboard Integration), and Phase 18 (rPPG & Thermal Vision Simulation & Integration).

---

## 🛠️ Phase 16: ROS 2 Migration & DDS Integration

Internal communication between mock simulation nodes and solver components has been successfully migrated from MQTT to ROS 2 DDS. External dashboard functionality is preserved intact via a new ROS 2-MQTT bridge.

### 1. ROS 2 Package Structure
Created a Python ROS 2 package named `sensors` inside the `source/sensors/` directory:
- [package.xml](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/sensors/package.xml): Specifies dependencies (`rclpy`, `sensor_msgs`, `geometry_msgs`, `std_msgs`).
- [setup.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/sensors/setup.py): Configures the entry points for the package executables.
- [setup.cfg](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/sensors/setup.cfg): Points script installers to correct ROS 2 directories.

### 2. Node Refactoring (`rclpy`)
Refactored simulated/solver nodes to inherit `rclpy.node.Node` and use standard message publishers/subscriptions:
- [lidar_pointcloud_sim.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/sensors/simulation/lidar_pointcloud_sim.py): Publishes 3D points as a binary stream in `sensor_msgs/PointCloud2` and vector force as `geometry_msgs/Twist`.
- [baymax_telemetry_sim.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/sensors/simulation/baymax_telemetry_sim.py): Publishes robot telemetry (PMU, Pneumatic, Joint Angles, Tactile, Vitals) using standard `sensor_msgs/JointState` maps and target kinematics as `sensor_msgs/Imu` (with position packed into `angular_velocity`).
- [hk07_physics_node.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/sensors/simulation/hk07_physics_node.py): Node solver that calculates spring forces and APF (Artificial Potential Field) repulsion from the point cloud. Publishes IK joint updates to `/telemetry/joint_states` and resolved state to `/telemetry/imu`.

### 3. ROS 2 - MQTT Bridge Node
- Created [ros2_mqtt_bridge_node.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/sensors/simulation/ros2_mqtt_bridge_node.py).
- Bridges the ROS 2 DDS space bidirectionally with Mosquitto MQTT:
  - Subscribes to all ROS 2 telemetry topics -> Converts messages to original flat JSON formats -> Publishes to target MQTT topics to keep Spring Boot & Vue dashboard running.
  - Subscribes to input MQTT topics (e.g. wristband data/state logs) -> Publishes corresponding standard ROS 2 messages.

---

## 🔬 Phase 17: Clinical Depth & Multimodal Blackboard Integration

Addressing the core gaps analyzed in [gap_analysis_and_evaluation.md](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/docs/gap_analysis_and_evaluation.md) regarding medical diagnostic depth, local fallback, and dynamic limits:

### 1. Dynamic Threshold configuration
Refactored [medical_agent.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/agents/medical_agent.py) to fetch dynamic warning thresholds from the Spring Boot `/api/thresholds/{deviceId}` REST endpoint using the authenticated JWT token cached by `AgentLogClient`.

### 2. HRV Stress Index calculation
Implemented an algorithm inside `MedicalAgent` to compute the Standard Deviation of Normal-to-Normal intervals (SDNN) over the last sliding buffer of physiological telemetry. The calculated heart rate variability is mapped to a standard 100-point clinical stress score with a medical disclaimer, replacing direct chemical claims.

### 3. Multimodal Blackboard Fusion
During user text queries, the `MedicalAgent` now queries the Blackboard for the latest visual body findings (`PerceptionScan` written by `PerceptionAgent`) and combines them with active vitals and stress readings into a cohesive multimodal context for LLM diagnostic inference.

### 4. EHR / Blackboard Synchronization
The parsed diagnostic conclusions (summary, actions) are wrapped into a standard `ClinicalEntry` schema and persisted directly back onto the Blackboard, allowing the downstream empathetic and action agents to consume synchronised patient context.

---

## 📹 Phase 18: OpenCV rPPG & Thermal Vision Simulation & Integration

This phase integrates simulated visual biometric sensors into the dashboard telemetry stream, resolving key gaps under the computer vision and ROS 2 middleware pillars.

### 1. ROS 2 Bridge Integration
Refactored [ros2_mqtt_bridge_node.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/sensors/simulation/ros2_mqtt_bridge_node.py) to bridge the new ROS 2 `/sensors/camera/thermal_rppg` topic (type `sensor_msgs/JointState` published by `rppg_thermal_node.py`). It extracts `rppg_heart_rate`, `thermal_temperature`, and `fever_alert`, formatting them into a standard JSON payload published to MQTT topic `hk07/sensors/camera/thermal_rppg`.

### 2. Spring Boot Core Configuration
- [MqttConfig.java](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-core/src/main/java/com/hk07/infrastructure/mqtt/MqttConfig.java): Added `hk07/sensors/camera/thermal_rppg` to the inbound message driver channel adapter list.
- [MqttInboundProcessor.java](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-core/src/main/java/com/hk07/infrastructure/mqtt/MqttInboundProcessor.java): Registered a topic handler parsing the payload and routing it to STOMP WebSocket destination `/topic/hk07/sensors/camera/thermal-rppg`.

### 3. Frontend Telemetry Sync (Bug Fix)
- Refactored [websocket.ts](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/services/websocket.ts) to resolve a critical bug where real WebSocket vital signs were stored in `vitalsStore` but ignored by the dashboard's text displays which relied on `telemetryStore`. Now, `/topic/vitals` updates write synchronously to both stores.
- Subscribed to the `/topic/hk07/sensors/camera/thermal-rppg` topic, updating `kinematicsStore`.
- Added state fields `rppgHeartRate`, `thermalTemperature`, and `feverAlert` inside [kinematics.ts](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/stores/kinematics.ts).

### 4. Cyber-Cinematic UI Component
- Modified [CompanionView.vue](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/views/CompanionView.vue) to render a `[ VISION_SENSORS_FEED ]` card, showing real-time rPPG Heart Rate, Forehead Temp, and Fever Alert indicators styled following the Cyber-Cinematic color system.

---

## 🧠 Phase 19: Local Edge LLM Fallback (Zero-Dependency)

This phase addresses the offline autonomy gap identified in [gap_analysis_and_evaluation.md](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/docs/gap_analysis_and_evaluation.md) by implementing a zero-dependency local rule-based fallback inside the LLM client routing layer.

### 1. Local Fallback Engine (`LocalOfflineFallback`)
- Implemented `LocalOfflineFallback` as a static class inside [llm_client.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/services/llm_client.py).
- Implements:
  - `get_completion_fallback()`: Generates caregiving, structured responses conforming to the Baymax persona for greetings, status queries, symptoms, and emergency warnings.
  - `get_tool_call_fallback()`: Formats intent classifications into the required JSON tool schema: `{"tools_to_invoke": [...], "tool_calls": [...]}`.
  - `get_vision_completion_fallback()`: Returns valid structured JSON data conforming to the `PerceptionScan` schema: `{"visible_injuries": ..., "facial_distress": ..., "environmental_hazards": ...}`.

### 2. Vietnamese Accent & Unaccented Input Handling
- Built a custom accent normalization function (`strip_accents()`) inside the local routing engine.
- Translates accented Vietnamese input (e.g. "sốt", "mệt", "đột quỵ") and unaccented input (e.g. "sot", "met", "dot quy") to match keywords cleanly.

### 3. Contextual Routing & Disambiguation
- Refactored matching rules to distinguish between:
  - **Conceptual Queries** (e.g. "Cảm biến Lidar hoạt động như thế nào?") -> routed to `speak_empathetic_response` to explain concepts.
  - **Status Checks** (e.g. "Kiểm tra trạng thái Lidar xem nào") -> routed to `execute_system_query`.
  - **Environment Scans** (e.g. "Lidar quét xung quanh") -> routed to `execute_environment_scan`.

### 4. Unified Fallback Hooks
- Safely wrapped all `LLMClient` endpoints (`generate_completion`, `generate_tool_call`, and `generate_vision_completion`) to return local fallback structures instantly if litellm is not installed or all remote API tiers fail.

---

## 🏥 Phase 20: Clinical EHR / FHIR Standard Gateway

This phase standardizes patient health data structures to be compliant with clinical interoperability standards (HL7 FHIR JSON format), resolving the data formatting gap.

### 1. FHIR Translation Engine (`FhirGatewayService`)
- Created [fhir_gateway_service.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/services/fhir_gateway_service.py).
- Implements:
  - `to_fhir_observations()`: Extracts numerical vitals (Heart Rate, SpO2, Body Temperature, Blood Pressure) and formats them into FHIR Observation resources with official LOINC codings (e.g. `8867-4` for Heart Rate, `2708-6` for SpO2, `8310-5` for Temp) and UCUM unit systems.
  - `to_fhir_condition()`: Formats patient encounter diagnoses into FHIR Condition resources with standardized SNOMED-CT clinical coding (e.g. `3424008` for Tachycardia, `386661006` for Fever, `38341003` for Hypertensive disorder).
  - `to_fhir_bundle()`: Combines observations and conditions into a single transaction Searchset Bundle resource.

### 2. REST API Exposure
- Registered three new API endpoints in [main.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/main.py):
  - `GET /api/v1/fhir/observation/latest`: Returns latest vitals as FHIR Observations.
  - `GET /api/v1/fhir/condition/latest`: Returns latest diagnosis as a FHIR Condition.
  - `GET /api/v1/fhir/clinical-bundle/latest`: Returns combined searchset bundle.

### 3. Unit Tests
- Created [test_fhir_gateway.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/tests/test_fhir_gateway.py) which verifies full compliance of generated Observation, Condition and Bundle resources against the FHIR specifications.
- Run result: **3/3 PASS**

---

## 🛡️ Phase 21: RTOS Fail-Safe Watchdog Simulation

This phase implements a hard-decoupled hardware-like watchdog representing an ESP32 co-processor that automatically deflates the soft robotics suit if the main Windows/Linux middleware crashes, resolving the fail-safe hardware gap.

### 1. Watchdog Heartbeat Monitoring (`rtos_watchdog_simulator.py`)
- Created [rtos_watchdog_simulator.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/robotics/sensors/simulation/rtos_watchdog_simulator.py).
- Spawns a ROS 2 node running at 10Hz.
- Monitors topic `/system/heartbeat` (bridged from MQTT `hk07/system/heartbeat` published by the Spring Boot middleware).
- If no heartbeat is received for more than 3.0 seconds, the watchdog trips and enforces a critical emergency wristband state (`is_falling = 1.0`, `emergency_button_pressed = 1.0`) on ROS 2 topic `/vitals/wristband`.

### 2. Emergency Suit Deflation Telemetry
- Subscribed `baymax_telemetry_sim.py` to `/vitals/wristband`.
- When the watchdog trips and publishes emergency flags, `baymax_telemetry_sim.py` immediately activates its fall cushioning mode, transitioning its internal state to `DISTRESSED`.
- Under `DISTRESSED` state, the simulated pressure release valve is activated (`relief_active = True`) and the soft robotics suit deflates instantly.

---

## ⚡ Hotfix: Safe Client Teardown & RouterAgentV2 Resource Release

Resolved an issue where stopping the agent engine during testing or shutdown caused a crash:
- **AttributeError Safe Guard**: Refactored `close()` in `AgentOrchestrator` and `AgentOrchestratorV2` to check if `_client` exists on `MedicalAgent` and `EmpatheticAgent` via `hasattr()` before attempting to close the asynchronous HTTP client connections.
- **RouterAgentV2 close() Method**: Appended a proper `async def close(self)` teardown method to `RouterAgentV2` in [router_agent_v2.py](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-agent/agents/router_agent_v2.py) to clean up its resources.
- Run result for `test_cognitive_orchestrator.py` integration test: **PASS (Exit Code: 0)**

---

## 🔍 Verification & Quality Checks
- **TypeScript Compiler**: Verified the frontend builds with zero errors (`vue-tsc --noEmit` returned 0 errors).
- **Unit Tests**:
  - `test_fhir_gateway.py` -> **3/3 PASS**
  - `test_medical_patterns.py` -> **4/4 PASS**
  - `test_cognitive_orchestrator.py` -> **PASS (Exit Code: 0)**
- **Roadmap Sync**: Updated the prioritized actions roadmap in [MASTER_CHANGELOG.md](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/docs/MASTER_CHANGELOG.md) and [CURSOR_BAYMAX_FULL_SYSTEM_BUILD.md](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/docs/00-project-init/prompts/CURSOR_BAYMAX_FULL_SYSTEM_BUILD.md).

