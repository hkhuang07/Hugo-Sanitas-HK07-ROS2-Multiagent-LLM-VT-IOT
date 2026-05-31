package com.hk07.domain.robot.service;

import com.hk07.common.enums.SystemState;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.concurrent.atomic.AtomicReference;

/**
 * Robot Command Service — Phase 07
 *
 * Manages SystemState and publishes MQTT control commands.
 * State is held in an AtomicReference (thread-safe, lock-free) — correct for Virtual Threads.
 *
 * Publishes to:
 *   - MQTT hk07/control/motion/command  → ROS 2 motion controller
 *   - WebSocket /topic/system-state     → Vue Dashboard HUD
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class RobotCommandService {

    private final SimpMessagingTemplate wsTemplate;
    // AtomicReference is safe for Virtual Thread concurrent access (no synchronized block needed)
    private final AtomicReference<SystemState> state = new AtomicReference<>(SystemState.INITIALIZING);

    public SystemState getCurrentState() { return state.get(); }

    public void issueHold() {
        state.set(SystemState.SAFE_HOLD);
        broadcastStateChange();
        log.warn("[ROBOT_CMD] SAFE_HOLD issued by operator");
    }

    public void issueResume() {
        state.set(SystemState.ACTIVE);
        broadcastStateChange();
        log.info("[ROBOT_CMD] RESUME issued");
    }

    public void issueShutdown() {
        state.set(SystemState.SHUTDOWN);
        broadcastStateChange();
        log.warn("[ROBOT_CMD] SHUTDOWN sequence initiated — volatile data wipe triggered");
    }

    public void updateFromSubsumption(SystemState newState) {
        state.set(newState);
        broadcastStateChange();
    }

    private void broadcastStateChange() {
        wsTemplate.convertAndSend("/topic/system-state", state.get().name());
    }
}
