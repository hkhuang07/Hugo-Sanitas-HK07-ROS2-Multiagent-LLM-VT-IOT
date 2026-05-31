package com.hk07.domain.user.service;

import com.hk07.common.exception.HK07BusinessException;
import com.hk07.common.exception.HK07NotFoundException;
import com.hk07.domain.user.dto.UserDto;
import com.hk07.domain.user.dto.WristbandConfigDto;
import com.hk07.domain.user.entity.UserEntity;
import com.hk07.domain.user.entity.WristbandConfigEntity;
import com.hk07.domain.user.repository.UserRepository;
import com.hk07.domain.user.repository.WristbandConfigRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

/**
 * User Service — Phase 03 (User Management)
 * Handles profile retrieval and wristband device configuration.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class UserService {

    private final UserRepository userRepository;
    private final WristbandConfigRepository wristbandConfigRepository;

    @Transactional(readOnly = true)
    public UserDto getById(UUID userId) {
        UserEntity user = userRepository.findById(userId)
                .orElseThrow(() -> new HK07NotFoundException("User", userId.toString()));
        return toDto(user);
    }

    @Transactional
    public UserDto updateDisplayName(UUID userId, String newName) {
        UserEntity user = userRepository.findById(userId)
                .orElseThrow(() -> new HK07NotFoundException("User", userId.toString()));
        user.setDisplayName(newName);
        return toDto(userRepository.save(user));
    }

    @Transactional
    public WristbandConfigDto upsertWristbandConfig(UUID userId, WristbandConfigDto dto) {
        UserEntity user = userRepository.findById(userId)
                .orElseThrow(() -> new HK07NotFoundException("User", userId.toString()));

        // Validate MQTT topic format (must start with hk07/)
        if (!dto.getMqttTopic().startsWith("hk07/sensors/wristband/")) {
            throw new HK07BusinessException(
                "Invalid MQTT topic. Must follow pattern: hk07/sensors/wristband/{deviceId}/vitals");
        }

        WristbandConfigEntity config = wristbandConfigRepository
                .findByUserId(userId)
                .orElse(WristbandConfigEntity.builder().user(user).build());

        config.setDeviceId(dto.getDeviceId());
        config.setMqttTopic(dto.getMqttTopic());
        config.setHeartRateThresholdMin(dto.getHeartRateThresholdMin());
        config.setHeartRateThresholdMax(dto.getHeartRateThresholdMax());
        config.setBloodPressureSystolicMax(dto.getBloodPressureSystolicMax());
        config.setSpo2Min(dto.getSpo2Min());
        config.setStrokeAlertEnabled(dto.isStrokeAlertEnabled());

        wristbandConfigRepository.save(config);
        log.info("[USER_WRISTBAND_CONFIG] userId={} deviceId={}", userId, dto.getDeviceId());

        return toWristbandDto(config);
    }

    // ─── Mappers ─────────────────────────────────────────────────────────────
    private UserDto toDto(UserEntity u) {
        WristbandConfigDto wb = u.getWristbandConfig() != null ? toWristbandDto(u.getWristbandConfig()) : null;
        return UserDto.builder()
                .id(u.getId()).displayName(u.getDisplayName())
                .email(u.getEmail()).role(u.getRole())
                .createdAt(u.getCreatedAt()).lastSeenAt(u.getLastSeenAt())
                .wristbandConfig(wb).build();
    }

    private WristbandConfigDto toWristbandDto(WristbandConfigEntity c) {
        return WristbandConfigDto.builder()
                .id(c.getId()).deviceId(c.getDeviceId()).mqttTopic(c.getMqttTopic())
                .heartRateThresholdMin(c.getHeartRateThresholdMin())
                .heartRateThresholdMax(c.getHeartRateThresholdMax())
                .bloodPressureSystolicMax(c.getBloodPressureSystolicMax())
                .spo2Min(c.getSpo2Min()).strokeAlertEnabled(c.isStrokeAlertEnabled())
                .build();
    }
}
