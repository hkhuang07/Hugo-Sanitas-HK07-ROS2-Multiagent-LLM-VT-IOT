package com.hk07.domain.robot.service;

import com.hk07.common.enums.SystemState;
import com.hk07.domain.audit.service.AuditService;
import com.hk07.infrastructure.mqtt.MqttOutboundGateway;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Robot Command Service — Phase 07
 *
 * Manages SystemState and publishes MQTT control commands.
 * State is held in an AtomicReference (thread-safe, lock-free).
 *
 * [HẠNCHẾ-#11 FIX] Every state-changing command now calls AuditService.record()
 * asynchronously on a Virtual Thread. The command execution path is NOT blocked.
 * Each record is stored with a SHA-256 integrity hash for medical audit compliance.
 *
 * Usage: actorId/actorRole must be extracted from SecurityContext by the Controller
 * and passed into these methods.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class RobotCommandService {

    private final SimpMessagingTemplate wsTemplate;
    private final AuditService auditService;
    private final MqttOutboundGateway mqttGateway;

    private final AtomicReference<SystemState> state = new AtomicReference<>(SystemState.INITIALIZING);

    public SystemState getCurrentState() { return state.get(); }

    public void issueHold(UUID actorId, String actorRole, String ipAddress) {
        state.set(SystemState.SAFE_HOLD);
        broadcastStateChange();
        // [#11] Non-blocking audit log — runs on Virtual Thread
        auditService.record(actorId, actorRole, AuditService.SAFE_HOLD,
                null, "{\"reason\":\"operator_manual\"}", "SUCCESS", ipAddress);
        log.warn("[ROBOT_CMD] SAFE_HOLD issued by actor={} role={}", actorId, actorRole);
    }

    public void issueResume(UUID actorId, String actorRole, String ipAddress) {
        state.set(SystemState.ACTIVE);
        broadcastStateChange();
        auditService.record(actorId, actorRole, AuditService.RESUME,
                null, "{}", "SUCCESS", ipAddress);
        log.info("[ROBOT_CMD] RESUME issued by actor={}", actorId);
    }

    public void issueShutdown(UUID actorId, String actorRole, String ipAddress) {
        state.set(SystemState.SHUTDOWN);
        broadcastStateChange();
        auditService.record(actorId, actorRole, AuditService.SHUTDOWN,
                null, "{\"reason\":\"operator_manual_shutdown\"}", "SUCCESS", ipAddress);
        log.warn("[ROBOT_CMD] SHUTDOWN initiated by actor={}", actorId);
    }

    public void toggleSubsumption(UUID actorId, String actorRole, boolean active, String ipAddress) {
        // [HẠNCHẾ-#3 FIX] Broadcast state lock via WebSocket to disable buttons on other clients
        wsTemplate.convertAndSend("/topic/safety-alerts",
            "{\"subsumptionActivated\":" + active + ",\"triggerType\":\"" + (active ? "MANUAL_INHIBIT" : "MANUAL_CLEAR") + "\"}");
            
        // [HẠNCHẾ-#18 FIX] Publish to MQTT so Webots Edge Controller actually stops motors
        mqttGateway.sendToMqtt("hk07/control/subsumption/inhibit", "{\"subsumptionActivated\":" + active + "}");
        
        auditService.record(actorId, actorRole, active ? AuditService.INHIBIT : AuditService.INHIBIT_CLEAR,
                null, "{\"source\":\"operator_manual_override\"}", "SUCCESS", ipAddress);
        log.warn("[ROBOT_CMD] Subsumption override active={} by actor={}", active, actorId);
    }

    /**
     * Called by SafetyAgent Inhibit signal (MQTT → Spring Boot).
     * actorId=null when triggered autonomously by robot's safety subsystem.
     */
    public void updateFromSubsumption(SystemState newState) {
        state.set(newState);
        broadcastStateChange();
        // System-triggered: actorId=null, actorRole="SYSTEM"
        auditService.record(null, "SYSTEM", AuditService.INHIBIT,
                null, "{\"source\":\"subsumption_safety_agent\"}", "SUCCESS", "127.0.0.1");
    }

    public void recordSosDispatch(UUID actorId, String actorRole, String ipAddress) {
        state.set(SystemState.EMERGENCY);
        broadcastStateChange();
        // [HẠNCHẾ-#3 FIX] Broadcast to alert other clients
        wsTemplate.convertAndSend("/topic/safety-alerts",
            "{\"subsumptionActivated\":true,\"triggerType\":\"SOS_DISPATCH\"}");

        auditService.record(actorId, actorRole, AuditService.SOS_DISPATCH,
                null, "{\"channel\":\"manual_dispatch\"}", "SUCCESS", ipAddress);
        log.warn("[ROBOT_CMD] SOS_DISPATCH logged for actor={}", actorId);
    }

    private void broadcastStateChange() {
        wsTemplate.convertAndSend("/topic/system-state", state.get().name());
    }
}
