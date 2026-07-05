package com.hk07.domain.user.repository;

import com.hk07.domain.user.entity.WristbandConfigEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface WristbandConfigRepository extends JpaRepository<WristbandConfigEntity, UUID> {
    List<WristbandConfigEntity> findByUserId(UUID userId);
    Optional<WristbandConfigEntity> findFirstByUserId(UUID userId);
    Optional<WristbandConfigEntity> findByUserIdAndDeviceId(UUID userId, String deviceId);
    Optional<WristbandConfigEntity> findByMqttTopic(String mqttTopic);
}
