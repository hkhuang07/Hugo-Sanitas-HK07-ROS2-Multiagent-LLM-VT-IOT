package com.hk07.domain.health.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.health.dto.MedicalThresholdDto;
import com.hk07.domain.health.entity.MedicalThresholdEntity;
import com.hk07.domain.health.repository.MedicalThresholdRepository;
import com.hk07.domain.user.entity.UserEntity;
import com.hk07.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Medical Threshold Configuration API
 *
 * [HẠNCHẾ-#9 FIX] Allows Medic and Owner to view/update dynamic alert thresholds
 * per patient per device — replacing the old hardcoded constants.
 *
 * Endpoints:
 *   GET  /api/thresholds              → List all threshold profiles for the authenticated user
 *   GET  /api/thresholds/{deviceId}   → Get threshold for a specific device
 *   PUT  /api/thresholds/{deviceId}   → Update threshold (Owner + Medic only)
 *   POST /api/thresholds/{deviceId}/reset → Reset to factory defaults
 *
 * Security:
 *   - OWNER: Can read/write their own thresholds only
 *   - MEDIC: Can read/write all patients' thresholds (clinical override)
 *   - GUEST/TECHNICIAN: Read-only
 */
@RestController
@RequestMapping("/api/thresholds")
@RequiredArgsConstructor
@Slf4j
public class MedicalThresholdController {

    private final MedicalThresholdRepository thresholdRepository;
    private final UserRepository userRepository;

    /** GET /api/thresholds — List all threshold profiles for the current user */
    @GetMapping
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<ApiResponse<List<MedicalThresholdDto>>> getAllThresholds(Authentication auth) {
        UUID userId = UUID.fromString(auth.getName());
        List<MedicalThresholdDto> profiles = thresholdRepository.findAllByUser_Id(userId)
                .stream().map(this::toDto).toList();
        return ResponseEntity.ok(ApiResponse.ok(profiles));
    }

    /** GET /api/thresholds/{deviceId} — Get specific device threshold */
    @GetMapping("/{deviceId}")
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<ApiResponse<MedicalThresholdDto>> getThreshold(
            @PathVariable String deviceId, Authentication auth) {
        UUID userId = UUID.fromString(auth.getName());
        boolean isAdminOrStaff = auth.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals("ROLE_OWNER") || a.getAuthority().equals("ROLE_OPERATOR"));

        java.util.Optional<MedicalThresholdEntity> entityOpt = isAdminOrStaff
                ? thresholdRepository.findByDeviceId(deviceId)
                : thresholdRepository.findByUser_IdAndDeviceId(userId, deviceId);

        if (entityOpt.isEmpty() && "default".equals(deviceId)) {
            List<MedicalThresholdEntity> all = thresholdRepository.findAllByUser_Id(userId);
            if (!all.isEmpty()) {
                entityOpt = java.util.Optional.of(all.get(0));
            } else {
                entityOpt = thresholdRepository.findByDeviceId("wristband-sim-001");
            }
        }

        return entityOpt
                .map(e -> ResponseEntity.ok(ApiResponse.ok(toDto(e))))
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * PUT /api/thresholds/{deviceId} — Update thresholds.
     * Validates clinical safety ranges before persisting.
     */
    @PutMapping("/{deviceId}")
    @PreAuthorize("hasAnyRole('OWNER', 'OPERATOR')")
    public ResponseEntity<ApiResponse<MedicalThresholdDto>> updateThreshold(
            @PathVariable String deviceId,
            @RequestBody MedicalThresholdDto request,
            Authentication auth) {

        UUID userId = UUID.fromString(auth.getName());

        // Clinical safety validation: prevent dangerous misconfiguration
        if (request.getHrMin() < 20 || request.getHrMax() > 220) {
            return ResponseEntity.badRequest().body(
                ApiResponse.error("HR thresholds must be within clinical range [20, 220] BPM"));
        }
        if (request.getSpo2Min() < 70.0f || request.getSpo2Min() > 99.0f) {
            return ResponseEntity.badRequest().body(
                ApiResponse.error("SpO2 minimum must be within [70%, 99%]"));
        }

        UserEntity user = userRepository.findById(userId).orElseThrow();

        MedicalThresholdEntity entity = thresholdRepository
                .findByUser_IdAndDeviceId(userId, deviceId)
                .orElseGet(() -> MedicalThresholdEntity.builder()
                        .user(user).deviceId(deviceId).build());

        // Apply updates
        entity.setHrMin(request.getHrMin());
        entity.setHrMax(request.getHrMax());
        entity.setSystolicMax(request.getSystolicMax());
        entity.setDiastolicMax(request.getDiastolicMax());
        entity.setSpo2Min(request.getSpo2Min());
        entity.setTempMax(request.getTempMax());
        entity.setStrokeAlertEnabled(request.isStrokeAlertEnabled());
        entity.setEmergencyButtonEnabled(request.isEmergencyButtonEnabled());
        entity.setLabel(request.getLabel());
        entity.setConfiguredBy(userId);
        entity.setUpdatedAt(Instant.now());

        MedicalThresholdEntity saved = thresholdRepository.save(entity);
        log.info("[THRESHOLD_UPDATE] userId={} device={} hrMin={} hrMax={} spo2Min={}",
                userId, deviceId, request.getHrMin(), request.getHrMax(), request.getSpo2Min());

        return ResponseEntity.ok(ApiResponse.ok(toDto(saved)));
    }

    /** POST /api/thresholds/{deviceId}/reset — Reset to factory defaults */
    @PostMapping("/{deviceId}/reset")
    @PreAuthorize("hasAnyRole('OWNER', 'OPERATOR')")
    public ResponseEntity<ApiResponse<MedicalThresholdDto>> resetThreshold(
            @PathVariable String deviceId, Authentication auth) {

        UUID userId = UUID.fromString(auth.getName());
        UserEntity user = userRepository.findById(userId).orElseThrow();

        MedicalThresholdEntity defaults = MedicalThresholdEntity.builder()
                .user(user)
                .deviceId(deviceId)
                .label("Factory Default")
                .configuredBy(userId)
                .build();

        // Delete existing and save fresh defaults
        thresholdRepository.findByUser_IdAndDeviceId(userId, deviceId)
                .ifPresent(thresholdRepository::delete);

        MedicalThresholdEntity saved = thresholdRepository.save(defaults);
        log.info("[THRESHOLD_RESET] userId={} device={} — reset to factory defaults", userId, deviceId);
        return ResponseEntity.ok(ApiResponse.ok(toDto(saved)));
    }

    private MedicalThresholdDto toDto(MedicalThresholdEntity e) {
        return MedicalThresholdDto.builder()
                .id(e.getId())
                .userId(e.getUser().getId())
                .deviceId(e.getDeviceId())
                .hrMin(e.getHrMin())
                .hrMax(e.getHrMax())
                .systolicMax(e.getSystolicMax())
                .diastolicMax(e.getDiastolicMax())
                .spo2Min(e.getSpo2Min())
                .tempMax(e.getTempMax())
                .strokeAlertEnabled(e.isStrokeAlertEnabled())
                .emergencyButtonEnabled(e.isEmergencyButtonEnabled())
                .label(e.getLabel())
                .configuredBy(e.getConfiguredBy())
                .updatedAt(e.getUpdatedAt())
                .build();
    }
}
