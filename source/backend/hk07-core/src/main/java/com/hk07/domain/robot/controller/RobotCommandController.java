package com.hk07.domain.robot.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.common.enums.SystemState;
import com.hk07.domain.robot.service.RobotCommandService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

/**
 * Robot Command Controller — Phase 07
 *
 * Provides operator/owner commands to control robot motion state.
 * Publishes commands to MQTT hk07/control/ topics.
 * Safety Agent (Python) is the final arbiter — it can override any command.
 */
@RestController
@RequestMapping("/api/v1/robot")
@RequiredArgsConstructor
public class RobotCommandController {

    private final RobotCommandService robotCommandService;

    @GetMapping("/state")
    public ResponseEntity<ApiResponse<SystemState>> getState() {
        return ResponseEntity.ok(ApiResponse.ok(robotCommandService.getCurrentState()));
    }

    @PostMapping("/command/hold")
    @PreAuthorize("hasAnyRole('OWNER','OPERATOR')")
    public ResponseEntity<ApiResponse<Void>> hold() {
        robotCommandService.issueHold();
        return ResponseEntity.ok(ApiResponse.ok("SAFE_HOLD command issued", null));
    }

    @PostMapping("/command/resume")
    @PreAuthorize("hasAnyRole('OWNER','OPERATOR')")
    public ResponseEntity<ApiResponse<Void>> resume() {
        robotCommandService.issueResume();
        return ResponseEntity.ok(ApiResponse.ok("RESUME command issued", null));
    }

    @PostMapping("/command/shutdown")
    @PreAuthorize("hasRole('OWNER')")
    public ResponseEntity<ApiResponse<Void>> shutdown() {
        robotCommandService.issueShutdown();
        return ResponseEntity.ok(ApiResponse.ok("SHUTDOWN sequence initiated — volatile data will be wiped", null));
    }

    /** Health endpoint for Docker healthcheck */
    @GetMapping("/health")
    public ResponseEntity<ApiResponse<String>> health() {
        return ResponseEntity.ok(ApiResponse.ok("HK-07 CORE ONLINE"));
    }
}
