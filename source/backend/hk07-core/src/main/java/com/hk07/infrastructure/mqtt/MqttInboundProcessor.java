package com.hk07.infrastructure.mqtt;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hk07.domain.health.dto.VitalSignDto;
import com.hk07.domain.health.service.HealthService;
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
    private final SimpMessagingTemplate wsTemplate;

    @ServiceActivator(inputChannel = "mqttInboundChannel")
    public void processInbound(Message<?> message) {
        String topic   = (String) message.getHeaders().get("mqtt_receivedTopic");
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

        // Fire-and-forget on Virtual Thread — listener never blocks
        healthService.processVitalSign(vital);
    }

    private void handleLidarScan(String payload) {
        log.debug("[LIDAR_SCAN] Received scan data ({}B)", payload.length());
        // Phase-01 Safety: Forward to SafetyService → Subsumption check
        // Broadcast raw scan to safety dashboard
        wsTemplate.convertAndSend("/topic/safety-scan", payload);
    }

    private void handleImuState(String payload) {
        log.debug("[IMU_STATE] {}", payload);
        // Phase-01 Safety: Fall detection logic
        wsTemplate.convertAndSend("/topic/safety-imu", payload);
    }

    private void handleAgentOutput(String topic, String payload) {
        String agentName = topic.split("/")[2].toUpperCase();
        log.info("[AGENT_OUTPUT] Agent: {} | Decision: {}", agentName,
                payload.length() > 100 ? payload.substring(0, 100) + "..." : payload);
        // Broadcast agent decision to dashboard
        wsTemplate.convertAndSend("/topic/agent-events", payload);
    }
}
