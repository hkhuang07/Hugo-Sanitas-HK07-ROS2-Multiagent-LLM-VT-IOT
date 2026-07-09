package com.hk07.infrastructure.mqtt;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.hk07.domain.health.dto.VitalSignDto;
import com.hk07.domain.health.service.HealthService;
import com.hk07.domain.robot.service.RobotCommandService;
import com.hk07.common.enums.SystemState;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.integration.annotation.MessageEndpoint;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.messaging.Message;
import org.springframework.messaging.simp.SimpMessagingTemplate;

/**
 * MQTT Inbound Message Processor
 *
 * Receives all messages from mqttInboundChannel and dispatches
 * them to the appropriate domain service based on the MQTT topic.
 *
 * [HẠNCHẾ-#6 FIX] Virtual Thread dispatch:
 *   HealthService.processVitalSign() is annotated @Async → runs on a new
 *   Virtual Thread immediately (via VirtualThreadConfig / applicationTaskExecutor).
 *   The @ServiceActivator here is the STOMP listener thread; it returns instantly
 *   after calling the @Async method — the MQTT listener is NEVER blocked.
 *   This decouples the broker listener from the DB/WebSocket pipeline entirely.
 */
@MessageEndpoint
@RequiredArgsConstructor
@Slf4j
public class MqttInboundProcessor {

    private final ObjectMapper objectMapper;
    private final HealthService healthService;
    private final RobotCommandService robotCommandService;
    private final SimpMessagingTemplate wsTemplate;

    @ServiceActivator(inputChannel = "mqttInboundChannel")
    public void processInbound(Message<?> message) {
        String topic   = (String) message.getHeaders().get("mqtt_receivedTopic");
        if (topic == null) {
            log.warn("[MQTT_INBOUND] Received message with null topic");
            return;
        }

        Object rawPayload = message.getPayload();
        
        // Zero-JSON Skeleton Policy: process binary protobuf payload directly
        if ("hk07/telemetry/skeleton".equals(topic)) {
            if (rawPayload instanceof byte[]) {
                handleTelemetrySkeleton((byte[]) rawPayload);
            } else if (rawPayload != null) {
                handleTelemetrySkeleton(rawPayload.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
            }
            return;
        }

        String payload;
        if (rawPayload instanceof byte[]) {
            payload = new String((byte[]) rawPayload, java.nio.charset.StandardCharsets.UTF_8);
        } else {
            try {
                payload = new String(rawPayload.toString().getBytes(java.nio.charset.StandardCharsets.ISO_8859_1), java.nio.charset.StandardCharsets.UTF_8);
            } catch (Exception e) {
                payload = rawPayload.toString();
            }
        }

        log.debug("[MQTT_INBOUND] Topic: {} | PayloadSize: {}B", topic, payload.length());

        try {
            if (topic.startsWith("hk07/sensors/wristband/")) {
                handleVitalSign(topic, payload);
            } else if (topic.equals("hk07/sensors/imu/state")) {
                handleImuState(payload);
            // ── Mobile Phone Sensor Bridge Topics (vivo_http_mqtt_bridge.py) ──
            } else if (topic.equals("hk07/sensors/imu/target")) {
                handleMobileImuTarget(payload);
            } else if (topic.equals("hk07/sensors/environment/state")) {
                handleMobileEnvironment(payload);
            } else if (topic.equals("hk07/sensors/location/gps")) {
                handleMobileLocation(payload);
            } else if (topic.equals("hk07/sensors/activity/metrics")) {
                handleMobileActivity(payload);
            } else if (topic.equals("hk07/sensors/audio/hearing")) {
                handleMobileHearing(payload);
            // ── Robot Telemetry Topics ──
            } else if (topic.equals("hk07/telemetry/imu")) {
                handleTelemetryImu(payload);
            } else if (topic.equals("hk07/telemetry/pneumatic")) {
                handleTelemetryPneumatic(payload);
            } else if (topic.equals("hk07/telemetry/sensors/tactile")) {
                handleTelemetryTactile(payload);
            } else if (topic.equals("hk07/telemetry/actuators/joints")) {
                handleTelemetryJoints(payload);
            } else if (topic.equals("hk07/telemetry/pmu")) {
                handleTelemetryPmu(payload);
            } else if (topic.equals("hk07/telemetry/avoidance")) {
                handleTelemetryAvoidance(payload);
            } else if (topic.equals("hk07/telemetry/joint_states")) {
                handleTelemetryJointStates(payload);
            } else if (topic.equals("hk07/perception/clinical")) {
                handlePerceptionClinical(payload);
            } else if (topic.equals("hk07/sensors/camera/thermal_rppg")) {
                handleThermalRppg(payload);
            } else if (topic.equals("hk07/perception/biomarkers")) {
                handlePerceptionBiomarkers(payload);
            } else if (topic.equals("hk07/control/subsumption/inhibit")) {
                handleSubsumptionInhibit(payload);
            } else if (topic.startsWith("hk07/agents/")) {
                handleAgentOutput(topic, payload);
            } else if ("hk07/care/decision".equals(topic)) {
                handleCareDecision(payload);
            } else if (topic.equals("hk07/system/heartbeat")) {
                log.trace("[MQTT_HEARTBEAT] Broker alive: {}", payload);
            } else {
                log.warn("[MQTT_INBOUND] Unhandled topic: {}", topic);
            }
        } catch (Exception e) {
            log.error("[MQTT_INBOUND_ERROR] Topic: {} | Error: {}", topic, e.getMessage());
        }
    }

    /**
     * [HẠNCHẾ-#6 FIX] Dispatch to HealthService on a Virtual Thread.
     *
     * HealthService.processVitalSign() is @Async → Spring wraps the call in a
     * Runnable submitted to VirtualThreadPerTaskExecutor.
     * This method returns in < 1μs, keeping the MQTT listener non-blocking.
     */
    private void handleVitalSign(String topic, String payload) throws JsonProcessingException {
        String[] parts   = topic.split("/");
        String deviceId  = parts.length >= 5 ? parts[3] : "unknown";

        VitalSignDto vital = objectMapper.readValue(payload, VitalSignDto.class);
        vital.setDeviceId(deviceId);

        log.debug("[VITAL_SIGN] Device: {} | HR: {}bpm | SpO2: {}%",
                 deviceId, vital.getHeartRate(), vital.getSpo2());

        // Audit for FallState
        if (payload.contains("\"is_falling\":true") || payload.contains("\"is_falling\": true")
                || payload.contains("\"is_falling\":1") || payload.contains("\"is_falling\": 1")
                || payload.contains("\"vision_fall_detected\":true") || payload.contains("\"vision_fall_detected\": true")) {
            log.warn("[FALL_DETECTED] FallState active. Instantly setting bypass aggregation for device={}", deviceId);
            healthService.handleCriticalFallForDevice(deviceId);
        }

        // Fire-and-forget on Virtual Thread — listener never blocks
        healthService.processVitalSign(vital);
    }



    private void handleImuState(String payload) {
        log.debug("[IMU_STATE] {}", payload);
        wsTemplate.convertAndSend("/topic/safety-imu", payload);
    }

    /**
     * Bridges SafetyAgent MQTT inhibit → WebSocket safety-alerts for dashboard.
     */
    private void handleSubsumptionInhibit(String payload) throws JsonProcessingException {
        JsonNode data = objectMapper.readTree(payload);
        String trigger = data.has("trigger") ? data.get("trigger").asText("UNKNOWN") : "UNKNOWN";
        boolean active = !"CLEAR".equalsIgnoreCase(trigger);

        if (active) {
            robotCommandService.updateFromSubsumption(SystemState.SAFE_HOLD);
            healthService.setBypassAggregationForAll(true);
        } else {
            healthService.setBypassAggregationForAll(false);
        }

        var alert = new java.util.LinkedHashMap<String, Object>();
        alert.put("subsumptionActivated", active);
        alert.put("triggerType", trigger);
        if (data.has("distance_m")) alert.put("distanceM", data.get("distance_m").asDouble());
        if (data.has("message")) alert.put("message", data.get("message").asText());
        if (data.has("acceleration_g")) alert.put("accelerationG", data.get("acceleration_g").asDouble());
        if (data.has("lux")) alert.put("lux", data.get("lux").asDouble());

        wsTemplate.convertAndSend("/topic/safety-alerts", objectMapper.writeValueAsString(alert));
        log.info("[SUBSUMPTION_INHIBIT] active={} trigger={}", active, trigger);
    }

    private void handleCareDecision(String payload) {
        log.info("[CARE_DECISION] Received decision: {}", payload);

        try {
            JsonNode node = objectMapper.readTree(payload);
            String priority = node.has("priority") ? node.get("priority").asText("NORMAL") : "NORMAL";
            String actionType = node.has("actionType") ? node.get("actionType").asText("COMPANION_CHAT") : "COMPANION_CHAT";
            String conversationHint = node.has("conversationHint") ? node.get("conversationHint").asText() : "";

            // Filter out periodic standard COMPANION_CHAT status updates to avoid UI spam
            if ("COMPANION_CHAT".equalsIgnoreCase(actionType) && 
                (conversationHint == null || conversationHint.trim().isEmpty() || 
                 conversationHint.contains("Standard companion mode"))) {
                return;
            }

            // Construct standard agent event payload for frontend
            java.util.Map<String, Object> wrapper = new java.util.HashMap<>();
            wrapper.put("id", "care_" + java.util.UUID.randomUUID().toString());
            wrapper.put("agentType", "CARE");
            wrapper.put("inputContext", "Mqtt Inbound Care Stream");
            wrapper.put("outputDecision", actionType + ": " + conversationHint);
            wrapper.put("llmProvider", "THRESHOLD");
            wrapper.put("latencyMs", 0);
            wrapper.put("triggeredAt", java.time.LocalDateTime.now().toString());

            String jsonPayload = objectMapper.writeValueAsString(wrapper);
            wsTemplate.convertAndSend("/topic/agent-events", jsonPayload);
            wsTemplate.convertAndSend("/topic/agent-logs", jsonPayload);

            if ("CRITICAL".equalsIgnoreCase(priority)) {
                log.warn("[CRITICAL_EMERGENCY_BROADCAST] Action: {} | Hint: {}", actionType, conversationHint);

                // Map critical clinical care decisions to safety-alerts
                var alert = new java.util.LinkedHashMap<String, Object>();
                alert.put("subsumptionActivated", false);
                alert.put("triggerType", actionType);
                alert.put("message", conversationHint);
                alert.put("isCriticalEmergency", true);

                wsTemplate.convertAndSend("/topic/safety-alerts", objectMapper.writeValueAsString(alert));
            }
        } catch (Exception e) {
            log.error("[CARE_DECISION_ERROR] Failed to process care decision: {}", e.getMessage());
        }
    }

    private void handleAgentOutput(String topic, String payload) {
        String agentName = topic.split("/")[2].toUpperCase();
        log.info("[AGENT_OUTPUT] Agent: {} | Decision: {}", agentName,
                payload.length() > 100 ? payload.substring(0, 100) + "..." : payload);

        try {
            boolean isValidJson = false;
            JsonNode node = null;
            try {
                node = objectMapper.readTree(payload);
                isValidJson = node.isObject();
            } catch (Exception e) {
                // Not a valid JSON object
            }

            java.util.Map<String, Object> wrapper = new java.util.HashMap<>();
            if (isValidJson && node != null) {
                wrapper.put("id", node.has("id") ? node.get("id").asText() : "mqtt_" + java.util.UUID.randomUUID().toString());
                wrapper.put("agentType", node.has("agentType") ? node.get("agentType").asText().toUpperCase() : agentName);
                wrapper.put("inputContext", node.has("inputContext") ? node.get("inputContext").asText() : "MQTT Ingest");
                wrapper.put("outputDecision", node.has("outputDecision") ? node.get("outputDecision").asText() : (node.has("decision") ? node.get("decision").asText() : payload));
                wrapper.put("llmProvider", node.has("llmProvider") ? node.get("llmProvider").asText() : "UNKNOWN");
                wrapper.put("latencyMs", node.has("latencyMs") ? node.get("latencyMs").asInt() : 0);
                wrapper.put("triggeredAt", node.has("triggeredAt") ? node.get("triggeredAt").asText() : java.time.LocalDateTime.now().toString());
            } else {
                wrapper.put("id", "mqtt_" + java.util.UUID.randomUUID().toString());
                wrapper.put("agentType", agentName);
                wrapper.put("inputContext", "MQTT Ingest");
                wrapper.put("outputDecision", payload);
                wrapper.put("llmProvider", "UNKNOWN");
                wrapper.put("latencyMs", 0);
                wrapper.put("triggeredAt", java.time.LocalDateTime.now().toString());
            }

            String jsonPayload = objectMapper.writeValueAsString(wrapper);
            wsTemplate.convertAndSend("/topic/agent-events", jsonPayload);
            wsTemplate.convertAndSend("/topic/agent-logs", jsonPayload);

            // Audit for AI_EMERGENCY_WAKEUP
            if (payload.contains("AI_EMERGENCY_WAKEUP")) {
                log.warn("[EMERGENCY_WAKEUP] AI_EMERGENCY_WAKEUP triggered. Instantly setting bypass aggregation.");
                if (node != null && node.has("userId")) {
                    java.util.UUID userUuid = java.util.UUID.fromString(node.get("userId").asText());
                    healthService.setBypassAggregation(userUuid, true);
                } else {
                    healthService.setBypassAggregationForAll(true);
                }
            }
        } catch (Exception e) {
            log.error("[AGENT_OUTPUT_ERROR] Failed to wrap and send agent output: {}", e.getMessage());
            // Fallback
            wsTemplate.convertAndSend("/topic/agent-events", payload);
        }
    }

    private void handleTelemetryImu(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/telemetry/imu", payload);
    }

    private void handleTelemetryPneumatic(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/telemetry/pneumatic", payload);
    }

    private void handleTelemetryTactile(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/telemetry/tactile", payload);
    }

    private void handleTelemetryJoints(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/telemetry/joints", payload);
    }

    private void handleTelemetryPmu(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/telemetry/pmu", payload);
    }

    private void handlePerceptionClinical(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/perception/clinical", payload);
    }



    private void handleTelemetryAvoidance(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/telemetry/avoidance", payload);
    }

    private void handleTelemetryJointStates(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/telemetry/joint_states", payload);
    }

    private void handleThermalRppg(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/sensors/camera/thermal-rppg", payload);
    }

    // ── Mobile Phone Sensor Bridge Handlers ──────────────────────────────────

    /**
     * 9-DOF IMU from phone: accel/gyro/mag/quaternion/compass/position.
     * Bridged from MQTT hk07/sensors/imu/target → WebSocket /topic/hk07/sensors/imu.
     */
    private void handleMobileImuTarget(String payload) {
        log.debug("[MOBILE_IMU] {}", payload.length() > 80 ? payload.substring(0, 80) + "..." : payload);
        wsTemplate.convertAndSend("/topic/hk07/sensors/imu", payload);
    }

    /**
     * Environment sensors from phone: ambient light (lux) + barometric pressure (hPa) + delta.
     * Bridged from MQTT hk07/sensors/environment/state → WebSocket /topic/hk07/sensors/environment.
     */
    private void handleMobileEnvironment(String payload) {
        log.debug("[MOBILE_ENV] {}", payload);
        wsTemplate.convertAndSend("/topic/hk07/sensors/environment", payload);
    }

    /**
     * GPS location from phone: latitude/longitude/altitude.
     * Bridged from MQTT hk07/sensors/location/gps → WebSocket /topic/hk07/sensors/location.
     */
    private void handleMobileLocation(String payload) {
        log.debug("[MOBILE_GPS] {}", payload);
        wsTemplate.convertAndSend("/topic/hk07/sensors/location", payload);
    }

    /**
     * Activity metrics from phone: pedometer steps, activity type, wrist motion array.
     * Bridged from MQTT hk07/sensors/activity/metrics → WebSocket /topic/hk07/sensors/activity.
     */
    private void handleMobileActivity(String payload) {
        log.debug("[MOBILE_ACTIVITY] {}", payload);
        wsTemplate.convertAndSend("/topic/hk07/sensors/activity", payload);
    }

    /**
     * Inferred hearing parameters and voice-to-text transcript from phone microphone.
     * Bridged from MQTT hk07/sensors/audio/hearing → WebSocket /topic/hk07/sensors/hearing.
     */
    private void handleMobileHearing(String payload) {
        log.debug("[MOBILE_HEARING] {}", payload);
        wsTemplate.convertAndSend("/topic/hk07/sensors/hearing", payload);
    }

    private void handlePerceptionBiomarkers(String payload) {
        wsTemplate.convertAndSend("/topic/hk07/perception/biomarkers", payload);
    }

    private void handleTelemetrySkeleton(byte[] bytes) {
        try {
            if (bytes.length >= 13 && new String(bytes, 0, 13, java.nio.charset.StandardCharsets.UTF_8).startsWith("RAW_FALLBACK\0")) {
                // Parse fallback binary structure
                java.nio.ByteBuffer buf = java.nio.ByteBuffer.wrap(bytes);
                buf.order(java.nio.ByteOrder.LITTLE_ENDIAN);
                buf.position(13); // skip RAW_FALLBACK\0 header
                
                long timestampMs = buf.getLong();
                int alertLen = buf.getInt();
                int riskLen = buf.getInt();
                int userLen = buf.getInt();
                
                byte[] alertBytes = new byte[alertLen];
                buf.get(alertBytes);
                String alertLevel = new String(alertBytes, java.nio.charset.StandardCharsets.UTF_8);
                
                byte[] riskBytes = new byte[riskLen];
                buf.get(riskBytes);
                String overallRisk = new String(riskBytes, java.nio.charset.StandardCharsets.UTF_8);
                
                byte[] userBytes = new byte[userLen];
                buf.get(userBytes);
                String userId = new String(userBytes, java.nio.charset.StandardCharsets.UTF_8);
                
                java.util.List<java.util.Map<String, Object>> landmarksList = new java.util.ArrayList<>();
                while (buf.remaining() >= 16) {
                    float x = buf.getFloat();
                    float y = buf.getFloat();
                    float z = buf.getFloat();
                    float visibility = buf.getFloat();
                    
                    java.util.Map<String, Object> lmMap = new java.util.HashMap<>();
                    lmMap.put("x", x);
                    lmMap.put("y", y);
                    lmMap.put("z", z);
                    lmMap.put("visibility", visibility);
                    landmarksList.add(lmMap);
                }
                
                java.util.Map<String, Object> jsonMap = new java.util.HashMap<>();
                jsonMap.put("timestampMs", timestampMs);
                jsonMap.put("alertLevel", alertLevel);
                jsonMap.put("overallRisk", overallRisk);
                jsonMap.put("userId", userId);
                jsonMap.put("landmarks", landmarksList);
                
                String jsonPayload = objectMapper.writeValueAsString(jsonMap);
                wsTemplate.convertAndSend("/topic/hk07/telemetry/skeleton", jsonPayload);
                log.debug("[SKELETON_FALLBACK] Decoded fallback skeleton binary successfully.");
            } else {
                // Protobuf decode
                com.hk07.domain.telemetry.dto.PoseSkeletonProto.SkeletonFrame frame =
                    com.hk07.domain.telemetry.dto.PoseSkeletonProto.SkeletonFrame.parseFrom(bytes);
                    
                java.util.Map<String, Object> jsonMap = new java.util.HashMap<>();
                jsonMap.put("timestampMs", frame.getTimestampMs());
                jsonMap.put("alertLevel", frame.getAlertLevel());
                jsonMap.put("overallRisk", frame.getOverallRisk());
                jsonMap.put("userId", frame.getUserId());
                
                java.util.List<java.util.Map<String, Object>> landmarksList = new java.util.ArrayList<>();
                for (com.hk07.domain.telemetry.dto.PoseSkeletonProto.Landmark lm : frame.getLandmarksList()) {
                    java.util.Map<String, Object> lmMap = new java.util.HashMap<>();
                    lmMap.put("x", lm.getX());
                    lmMap.put("y", lm.getY());
                    lmMap.put("z", lm.getZ());
                    lmMap.put("visibility", lm.getVisibility());
                    landmarksList.add(lmMap);
                }
                jsonMap.put("landmarks", landmarksList);
                
                String jsonPayload = objectMapper.writeValueAsString(jsonMap);
                wsTemplate.convertAndSend("/topic/hk07/telemetry/skeleton", jsonPayload);
            }
        } catch (Exception e) {
            log.error("[SKELETON_DECODE_ERROR] Failed to decode skeleton binary: {}", e.getMessage());
        }
    }
}
