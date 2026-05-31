package com.hk07.domain.health.service;

import com.hk07.common.enums.AlertLevel;
import com.hk07.domain.health.dto.VitalSignDto;
import com.hk07.domain.health.entity.HealthRecordEntity;
import com.hk07.domain.health.repository.HealthRecordRepository;
import com.hk07.domain.user.entity.WristbandConfigEntity;
import com.hk07.domain.user.repository.WristbandConfigRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Health Service — Phase 04 (Timeline)
 *
 * Core pipeline: MQTT VitalSign → threshold check → persist → WebSocket broadcast.
 *
 * The pipeline runs on Virtual Threads via @Async.
 * Each MQTT message spawns a lightweight virtual thread (< 1KB stack) — no OS thread created.
 *
 * Memory optimization:
 * - Primitives (int, float) used for vital sign fields — no Integer/Float boxing overhead
 * - Single HealthRecordEntity object created per pipeline run (no intermediate DTOs)
 * - SimpMessagingTemplate broadcast is async — does not block the pipeline thread
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class HealthService {

    private final HealthRecordRepository healthRepository;
    private final WristbandConfigRepository wristbandConfigRepository;
    private final SimpMessagingTemplate wsTemplate;

    // Throttling: Max 60Hz (~16ms) per device
    private final ConcurrentHashMap<String, Long> lastProcessedTime = new ConcurrentHashMap<>();

    /**
     * Primary pipeline: process an incoming VitalSignDto from MQTT.
     *
     * 1. Look up user by MQTT topic (wristband config)
     * 2. Perform threshold check (fast, no LLM)
     * 3. Persist to PostgreSQL
     * 4. Broadcast via WebSocket to Dashboard
     *
     * Annotated @Async → runs on Virtual Thread automatically (via VirtualThreadConfig)
     */
    @Async
    public void processVitalSign(VitalSignDto vital) {
        String deviceId = vital.getDeviceId();
        if (deviceId == null) return;
        
        // Throttling (Message Flooding Protection): Max 60Hz (16ms)
        long now = System.currentTimeMillis();
        Long lastTime = lastProcessedTime.get(deviceId);
        if (lastTime != null && now - lastTime < 16) {
            return; // Drop message to prevent flooding
        }
        lastProcessedTime.put(deviceId, now);

        // Resolve owner from device's MQTT topic
        String topic = "hk07/sensors/wristband/" + deviceId + "/vitals";
        Optional<WristbandConfigEntity> configOpt = wristbandConfigRepository.findByMqttTopic(topic);

        if (configOpt.isEmpty()) {
            log.debug("[HEALTH_SERVICE] No owner found for deviceId={}", vital.getDeviceId());
            // Still broadcast to general /topic/vitals for simulation mode
            wsTemplate.convertAndSend("/topic/vitals", vital);
            return;
        }

        WristbandConfigEntity config = configOpt.get();
        UUID userId = config.getUser().getId();

        // ─── Fast threshold check (pure arithmetic — zero GC pressure) ────────
        AlertLevel level = computeAlertLevel(vital, config);

        // ─── Persist (only persist WARNING+ to avoid DB flood at 60Hz) ─────────
        if (level != AlertLevel.NORMAL) {
            HealthRecordEntity record = HealthRecordEntity.builder()
                    .userId(userId)
                    .heartRate(vital.getHeartRate())
                    .systolic(vital.getSystolic())
                    .diastolic(vital.getDiastolic())
                    .bodyTemperature(vital.getBodyTemperature())
                    .spo2(vital.getSpo2())
                    .deviceId(vital.getDeviceId())
                    .alertLevel(level)
                    .agentAnalysis("Threshold breach detected — Medical Agent analysis pending")
                    .build();
            healthRepository.save(record);
            log.warn("[HEALTH_ALERT] userId={} level={} HR={} SpO2={}",
                    userId, level, vital.getHeartRate(), vital.getSpo2());
        }

        // ─── WebSocket broadcast (60Hz stream to dashboard) ─────────────────
        // Include alertLevel in the payload so dashboard HUD can color-code instantly
        var payload = new VitalSignWithAlertDto(vital, level.name(), userId.toString());
        wsTemplate.convertAndSend("/topic/vitals", payload);
    }

    /**
     * Compute AlertLevel using pure arithmetic threshold checks.
     * No LLM call here — this runs at up to 60Hz.
     * LLM analysis happens asynchronously in MedicalAgent for CRITICAL+ cases.
     */
    private AlertLevel computeAlertLevel(VitalSignDto v, WristbandConfigEntity cfg) {
        int hr = v.getHeartRate();
        float spo2 = v.getSpo2();
        float systolic = v.getSystolic();
        float temp = v.getBodyTemperature();

        // STROKE: Extreme out-of-range combination
        if (hr > 150 || hr < 40 || spo2 < 85.0f) return AlertLevel.STROKE;

        // CRITICAL: Single critical threshold breach
        if (hr > cfg.getHeartRateThresholdMax() + 20
                || systolic > cfg.getBloodPressureSystolicMax() + 20
                || spo2 < 90.0f || temp > 39.5f) return AlertLevel.CRITICAL;

        // WARNING: Threshold exceeded
        if (hr > cfg.getHeartRateThresholdMax() || hr < cfg.getHeartRateThresholdMin()
                || systolic > cfg.getBloodPressureSystolicMax()
                || spo2 < cfg.getSpo2Min() || temp > 38.5f) return AlertLevel.WARNING;

        return AlertLevel.NORMAL;
    }

    /** Retrieve latest vital for dashboard initial load */
    public Optional<HealthRecordEntity> getLatestVital(UUID userId) {
        return healthRepository.findTopByUserIdOrderByRecordedAtDesc(userId);
    }

    /** Active alerts for sidebar panel */
    public List<HealthRecordEntity> getActiveAlerts(UUID userId) {
        return healthRepository.findActiveAlerts(userId,
                List.of(AlertLevel.WARNING, AlertLevel.CRITICAL, AlertLevel.STROKE));
    }

    /** Retrieve 24h health summary from database view mapped to DTO */
    public List<com.hk07.domain.health.dto.HourlySummaryDto> getHourlySummary(UUID userId, int hours) {
        List<Object[]> rawList = healthRepository.findHourlySummaryRaw(userId, hours);
        java.time.format.DateTimeFormatter formatter = java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'");
        return rawList.stream().map(row -> {
            String bucketHourStr = null;
            if (row[0] != null) {
                if (row[0] instanceof java.time.LocalDateTime ldt) {
                    bucketHourStr = ldt.format(formatter);
                } else if (row[0] instanceof java.sql.Timestamp ts) {
                    bucketHourStr = ts.toLocalDateTime().format(formatter);
                } else {
                    bucketHourStr = row[0].toString();
                }
            }
            return com.hk07.domain.health.dto.HourlySummaryDto.builder()
                    .bucketHour(bucketHourStr)
                    .avgHr(row[1] != null ? ((Number) row[1]).intValue() : null)
                    .maxHr(row[2] != null ? ((Number) row[2]).intValue() : null)
                    .minHr(row[3] != null ? ((Number) row[3]).intValue() : null)
                    .avgSystolic(row[4] != null ? ((Number) row[4]).doubleValue() : null)
                    .avgSpo2(row[5] != null ? ((Number) row[5]).doubleValue() : null)
                    .avgTemp(row[6] != null ? ((Number) row[6]).doubleValue() : null)
                    .sampleCount(row[7] != null ? ((Number) row[7]).intValue() : null)
                    .worstAlert(row[8] != null ? row[8].toString() : null)
                    .build();
        }).toList();
    }

    /** Minimal inner DTO to avoid creating a full class — reduces GC pressure */
    public record VitalSignWithAlertDto(VitalSignDto vitals, String alertLevel, String userId) {}
}
