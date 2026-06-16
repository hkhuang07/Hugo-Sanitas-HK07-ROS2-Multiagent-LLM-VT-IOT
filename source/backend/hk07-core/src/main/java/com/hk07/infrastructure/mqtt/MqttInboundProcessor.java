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
        Object rawPayload = message.getPayload();
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

        if (topic == null) {
            log.warn("[MQTT_INBOUND] Received message with null topic");
            return;
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
            } else if (topic.equals("hk07/control/subsumption/inhibit")) {
                handleSubsumptionInhibit(payload);
            } else if (topic.startsWith("hk07/agents/")) {
                handleAgentOutput(topic, payload);
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
            healthService.setBypassAggregationForDevice(deviceId, true);
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

    private void handleAgentOutput(String topic, String payload) {
        String agentName = topic.split("/")[2].toUpperCase();
        log.info("[AGENT_OUTPUT] Agent: {} | Decision: {}", agentName,
                payload.length() > 100 ? payload.substring(0, 100) + "..." : payload);
        // Broadcast agent decision to dashboard
        wsTemplate.convertAndSend("/topic/agent-events", payload);

        // Audit for AI_EMERGENCY_WAKEUP
        if (payload.contains("AI_EMERGENCY_WAKEUP")) {
            log.warn("[EMERGENCY_WAKEUP] AI_EMERGENCY_WAKEUP triggered. Instantly setting bypass aggregation.");
            try {
                JsonNode node = objectMapper.readTree(payload);
                if (node.has("userId")) {
                    java.util.UUID userUuid = java.util.UUID.fromString(node.get("userId").asText());
                    healthService.setBypassAggregation(userUuid, true);
                } else {
                    healthService.setBypassAggregationForAll(true);
                }
            } catch (Exception e) {
                healthService.setBypassAggregationForAll(true);
            }
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
}
