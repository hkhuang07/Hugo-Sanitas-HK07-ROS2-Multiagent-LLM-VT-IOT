package com.hk07.domain.robot.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.robot.service.RobotCommandService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import jakarta.servlet.http.HttpServletRequest;
import java.util.UUID;

/**
 * Emergency Controller
 * Provides emergency endpoints like /api/v1/emergency/sos
 */
@RestController
@RequestMapping("/api/v1/emergency")
@RequiredArgsConstructor
public class EmergencyController {

    private final RobotCommandService robotCommandService;

    @PostMapping("/sos")
    public ResponseEntity<ApiResponse<Void>> dispatchSos(Authentication auth, HttpServletRequest request) {
        UUID actorId = null;
        String role = "SYSTEM";
        if (auth != null) {
            actorId = UUID.fromString(auth.getName());
            role = auth.getAuthorities().stream()
                    .findFirst()
                    .map(GrantedAuthority::getAuthority)
                    .orElse("UNKNOWN")
                    .replace("ROLE_", "");
        }
        robotCommandService.recordSosDispatch(actorId, role, request.getRemoteAddr());
        return ResponseEntity.ok(ApiResponse.ok("SOS Dispatched Successfully", null));
    }
}
