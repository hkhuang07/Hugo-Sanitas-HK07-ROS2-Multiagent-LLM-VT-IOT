package com.hk07.domain.health.repository;

import com.hk07.common.enums.AlertLevel;
import com.hk07.domain.health.entity.HealthRecordEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface HealthRecordRepository extends JpaRepository<HealthRecordEntity, UUID> {

    /** Latest record for a user — for the real-time HUD */
    Optional<HealthRecordEntity> findTopByUserIdOrderByRecordedAtDesc(UUID userId);

    /** Paginated history */
    Page<HealthRecordEntity> findByUserIdOrderByRecordedAtDesc(UUID userId, Pageable pageable);

    /** Active alerts (WARNING+) for dashboard alert panel */
    @Query("SELECT h FROM HealthRecordEntity h WHERE h.userId = :userId " +
           "AND h.alertLevel IN :levels ORDER BY h.recordedAt DESC")
    List<HealthRecordEntity> findActiveAlerts(UUID userId, List<AlertLevel> levels);

    @Query(value = 
        "SELECT bucket_hour, avg_hr, max_hr, min_hr, avg_systolic, avg_spo2, avg_temp, sample_count, worst_alert " +
        "FROM v_health_hourly_summary " +
        "WHERE user_id = :userId " +
        "AND bucket_hour >= NOW() - INTERVAL :hours HOUR " +
        "ORDER BY bucket_hour ASC", 
        nativeQuery = true)
    List<Object[]> findHourlySummaryRaw(
        @org.springframework.data.repository.query.Param("userId") UUID userId, 
        @org.springframework.data.repository.query.Param("hours") int hours
    );
}
