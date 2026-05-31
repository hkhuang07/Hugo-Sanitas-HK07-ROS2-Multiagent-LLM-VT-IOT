package com.hk07.infrastructure.mqtt;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hk07.domain.health.dto.VitalSignDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.integration.annotation.MessageEndpoint;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.messaging.Message;

/**
 * MQTT Inbound Message Processor
 *
 * Receives all messages from mqttInboundChannel and dispatches
 * them to the appropriate domain service based on the MQTT topic.
 *
 * Runs on Virtual Threads — each MQTT message gets its own lightweight thread.
 * No Thread.sleep() or blocking I/O here — all dispatches are async.
 */
@MessageEndpoint
@RequiredArgsConstructor
@Slf4j
public class MqttInboundProcessor {

    private final ObjectMapper objectMapper;

    @ServiceActivator(inputChannel = "mqttInboundChannel")
    public void processInbound(Message<?> message) {
        String topic = (String) message.getHeaders().get("mqtt_receivedTopic");
        String payload = message.getPayload().toString();

        if (topic == null) {
            log.warn("[MQTT_INBOUND] Received message with null topic");
            return;
        }

        log.debug("[MQTT_INBOUND] Topic: {} | PayloadSize: {}B", topic, payload.length());

        try {
            if (topic.startsWith("hk07/sensors/wristband/")) {
                handleVitalSign(topic, payload);
            } else if (topic.equals("hk07/sensors/lidar/scan")) {
                handleLidarScan(payload);
            } else if (topic.equals("hk07/sensors/imu/state")) {
                handleImuState(payload);
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

    private void handleVitalSign(String topic, String payload) throws JsonProcessingException {
        // Extract deviceId from topic: hk07/sensors/wristband/{deviceId}/vitals
        String[] parts = topic.split("/");
        String deviceId = parts.length >= 5 ? parts[3] : "unknown";

        VitalSignDto vital = objectMapper.readValue(payload, VitalSignDto.class);
        vital.setDeviceId(deviceId);
        log.info("[VITAL_SIGN] Device: {} | HR: {}bpm | SpO2: {}%",
                deviceId, vital.getHeartRate(), vital.getSpo2());

        // TODO Phase-04: Forward to HealthService for Medical Agent analysis + DB persistence
    }

    private void handleLidarScan(String payload) {
        log.debug("[LIDAR_SCAN] Received scan data ({}B)", payload.length());
        // TODO Phase-01 Safety: Forward to SafetyService → Subsumption check
    }

    private void handleImuState(String payload) {
        log.debug("[IMU_STATE] {}", payload);
        // TODO Phase-01 Safety: Fall detection logic
    }

    private void handleAgentOutput(String topic, String payload) {
        String agentName = topic.split("/")[2].toUpperCase();
        log.info("[AGENT_OUTPUT] Agent: {} | Decision: {}", agentName,
                payload.length() > 100 ? payload.substring(0, 100) + "..." : payload);
        // TODO Phase-04: Persist to AgentLog + broadcast via WebSocket
    }
}
