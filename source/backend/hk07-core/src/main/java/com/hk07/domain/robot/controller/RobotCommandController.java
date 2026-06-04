package com.hk07.domain.robot.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.common.enums.SystemState;
import com.hk07.domain.robot.service.RobotCommandService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.*;
import jakarta.servlet.http.HttpServletRequest;
import java.util.UUID;

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
    @org.springframework.security.access.prepost.PreAuthorize("hasAnyRole('OWNER','OPERATOR')")
    public ResponseEntity<ApiResponse<Void>> hold(Authentication auth, HttpServletRequest request) {
        UUID actorId = UUID.fromString(auth.getName());
        String role = auth.getAuthorities().stream().findFirst().map(GrantedAuthority::getAuthority).orElse("UNKNOWN").replace("ROLE_", "");
        robotCommandService.issueHold(actorId, role, request.getRemoteAddr());
        return ResponseEntity.ok(ApiResponse.ok("SAFE_HOLD command issued", null));
    }

    @PostMapping("/command/resume")
    @org.springframework.security.access.prepost.PreAuthorize("hasAnyRole('OWNER','OPERATOR')")
    public ResponseEntity<ApiResponse<Void>> resume(Authentication auth, HttpServletRequest request) {
        UUID actorId = UUID.fromString(auth.getName());
        String role = auth.getAuthorities().stream().findFirst().map(GrantedAuthority::getAuthority).orElse("UNKNOWN").replace("ROLE_", "");
        robotCommandService.issueResume(actorId, role, request.getRemoteAddr());
        return ResponseEntity.ok(ApiResponse.ok("RESUME command issued", null));
    }

    @PostMapping("/command/shutdown")
    @org.springframework.security.access.prepost.PreAuthorize("hasRole('OWNER')")
    public ResponseEntity<ApiResponse<Void>> shutdown(Authentication auth, HttpServletRequest request) {
        UUID actorId = UUID.fromString(auth.getName());
        String role = auth.getAuthorities().stream().findFirst().map(GrantedAuthority::getAuthority).orElse("UNKNOWN").replace("ROLE_", "");
        robotCommandService.issueShutdown(actorId, role, request.getRemoteAddr());
        return ResponseEntity.ok(ApiResponse.ok("SHUTDOWN sequence initiated — volatile data will be wiped", null));
    }

    @PostMapping("/command/subsumption")
    @org.springframework.security.access.prepost.PreAuthorize("hasAnyRole('OWNER','OPERATOR')")
    public ResponseEntity<ApiResponse<Void>> toggleSubsumption(
            @RequestBody java.util.Map<String, Boolean> payload,
            Authentication auth, HttpServletRequest request) {
        UUID actorId = UUID.fromString(auth.getName());
        String role = auth.getAuthorities().stream().findFirst().map(GrantedAuthority::getAuthority).orElse("UNKNOWN").replace("ROLE_", "");
        boolean active = payload.getOrDefault("active", true);
        robotCommandService.toggleSubsumption(actorId, role, active, request.getRemoteAddr());
        return ResponseEntity.ok(ApiResponse.ok("Subsumption override: " + active, null));
    }

    @PostMapping("/command/sos")
    @org.springframework.security.access.prepost.PreAuthorize("hasAnyRole('OWNER','OPERATOR','EMERGENCY_CONTACT')")
    public ResponseEntity<ApiResponse<Void>> dispatchSos(Authentication auth, HttpServletRequest request) {
        return dispatchSosInternal(auth, request);
    }

    /** E-STOP uplink from SafetyView — same SOS dispatch as /command/sos */
    @PostMapping("/sos-trigger")
    @org.springframework.security.access.prepost.PreAuthorize("hasAnyRole('OWNER','OPERATOR','EMERGENCY_CONTACT')")
    public ResponseEntity<ApiResponse<Void>> sosTrigger(Authentication auth, HttpServletRequest request) {
        return dispatchSosInternal(auth, request);
    }

    private ResponseEntity<ApiResponse<Void>> dispatchSosInternal(Authentication auth, HttpServletRequest request) {
        UUID actorId = UUID.fromString(auth.getName());
        String role = auth.getAuthorities().stream().findFirst().map(GrantedAuthority::getAuthority).orElse("UNKNOWN").replace("ROLE_", "");
        robotCommandService.recordSosDispatch(actorId, role, request.getRemoteAddr());
        return ResponseEntity.ok(ApiResponse.ok("SOS Dispatched", null));
    }

    /** Health endpoint for Docker healthcheck */
    @GetMapping("/health")
    public ResponseEntity<ApiResponse<String>> health() {
        return ResponseEntity.ok(ApiResponse.ok("HK-07 CORE ONLINE"));
    }
}
