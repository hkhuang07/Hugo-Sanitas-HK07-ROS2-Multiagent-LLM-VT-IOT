package com.hk07.domain.health.repository;

import com.hk07.domain.health.entity.MedicalThresholdEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/**
 * Repository for MedicalThresholdEntity.
 *
 * Primary lookup: by userId + deviceId — used in HealthService.computeAlertLevel()
 * on every incoming MQTT vital sign (up to 60Hz). Result should be cached in
 * WristbandConfigRepository or a local ConcurrentHashMap for performance.
 */
@Repository
public interface MedicalThresholdRepository extends JpaRepository<MedicalThresholdEntity, UUID> {

    /** Find active threshold profile for a specific user + device combination */
    Optional<MedicalThresholdEntity> findByUser_IdAndDeviceId(UUID userId, String deviceId);

    /** Find all profiles belonging to a user (for profile list API) */
    java.util.List<MedicalThresholdEntity> findAllByUser_Id(UUID userId);

    @Query("SELECT t FROM MedicalThresholdEntity t WHERE t.user.id = :userId AND t.deviceId = :deviceId")
    Optional<MedicalThresholdEntity> findByUserAndDevice(@Param("userId") UUID userId,
                                                          @Param("deviceId") String deviceId);
}
