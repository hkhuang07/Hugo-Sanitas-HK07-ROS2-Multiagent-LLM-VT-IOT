package com.hk07.domain.health.repository;

import com.hk07.common.enums.AlertLevel;
import com.hk07.domain.health.entity.HealthRecordEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
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
        "SELECT FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(recorded_at)/3600)*3600) AS bucket_hour, " +
        "CAST(ROUND(AVG(heart_rate)) AS SIGNED) AS avg_hr, " +
        "CAST(MAX(heart_rate) AS SIGNED) AS max_hr, " +
        "CAST(MIN(heart_rate) AS SIGNED) AS min_hr, " +
        "ROUND(AVG(systolic), 1) AS avg_systolic, " +
        "ROUND(AVG(spo2), 1) AS avg_spo2, " +
        "ROUND(AVG(body_temperature), 1) AS avg_temp, " +
        "COUNT(*) AS sample_count, " +
        "MAX(alert_level) AS worst_alert " +
        "FROM health_records " +
        "WHERE user_id = :userId " +
        "AND recorded_at >= NOW() - INTERVAL :hours HOUR " +
        "GROUP BY bucket_hour " +
        "ORDER BY bucket_hour ASC", 
        nativeQuery = true)
    List<Object[]> findHourlySummaryRaw(
        @Param("userId") UUID userId, 
        @Param("hours") int hours
    );

    /** Hourly bucket summary within an explicit date-time range */
    @Query(value =
        "SELECT FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(recorded_at)/3600)*3600) AS bucket_hour, " +
        "CAST(ROUND(AVG(heart_rate)) AS SIGNED) AS avg_hr, " +
        "CAST(MAX(heart_rate) AS SIGNED) AS max_hr, " +
        "CAST(MIN(heart_rate) AS SIGNED) AS min_hr, " +
        "ROUND(AVG(systolic), 1) AS avg_systolic, " +
        "ROUND(AVG(spo2), 1) AS avg_spo2, " +
        "ROUND(AVG(body_temperature), 1) AS avg_temp, " +
        "COUNT(*) AS sample_count, " +
        "MAX(alert_level) AS worst_alert " +
        "FROM health_records " +
        "WHERE user_id = :userId " +
        "AND recorded_at >= :fromDate " +
        "AND recorded_at <= :toDate " +
        "GROUP BY bucket_hour " +
        "ORDER BY bucket_hour ASC",
        nativeQuery = true)
    List<Object[]> findHourlySummaryByRangeRaw(
        @Param("userId") UUID userId,
        @Param("fromDate") LocalDateTime fromDate,
        @Param("toDate") LocalDateTime toDate
    );

    /** Count of records in a range — used for lightweight pagination metadata */
    @Query("SELECT COUNT(h) FROM HealthRecordEntity h WHERE h.userId = :userId " +
           "AND h.recordedAt >= :fromDate AND h.recordedAt <= :toDate")
    long countByUserIdAndRange(
        @Param("userId") UUID userId,
        @Param("fromDate") LocalDateTime fromDate,
        @Param("toDate") LocalDateTime toDate
    );
}
