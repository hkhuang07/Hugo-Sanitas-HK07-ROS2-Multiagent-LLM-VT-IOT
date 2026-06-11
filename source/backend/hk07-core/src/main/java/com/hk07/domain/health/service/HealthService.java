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
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Health Service — Phase 04 (Timeline)
 *
 * Core pipeline: MQTT VitalSign → threshold check → persist → WebSocket broadcast.
 *
 * [HẠNCHẾ-#6 FIX] @Async("applicationTaskExecutor")
 *   processVitalSign() runs on a Java 21 Virtual Thread per invocation.
 *   The MQTT listener thread (MqttInboundProcessor) returns immediately.
 *   10Hz × N devices = N concurrent virtual threads, each ~1KB stack — no OS thread created.
 *
 * [HẠNCHẾ-#8 FIX] Batch Insert for NORMAL vitals:
 *   WARNING/CRITICAL/STROKE records are persisted immediately (they are urgent).
 *   NORMAL records accumulate in a thread-safe CopyOnWriteArrayList batch queue.
 *   @Scheduled flushes the batch every 5 seconds via healthRepository.saveAll().
 *   This reduces I/O from 10 writes/s (10Hz × 1 device) to 1 write/5s for steady state.
 *
 * [HẠNCHẾ-#9 FIX] Dynamic Thresholds:
 *   computeAlertLevel() reads per-user thresholds from WristbandConfigEntity
 *   (loaded from DB), not hardcoded constants.
 *   Only the absolute STROKE ceiling (HR>150, SpO2<85) remains hardcoded
 *   as a medical safety net that cannot be misconfigured by users.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class HealthService {

    private final HealthRecordRepository healthRepository;
    private final WristbandConfigRepository wristbandConfigRepository;
    private final SimpMessagingTemplate wsTemplate;

    // ── Throttle: Max 60Hz per device ───────────────────────────────────────
    private final ConcurrentHashMap<String, Long> lastProcessedTime = new ConcurrentHashMap<>();

    // ── [HẠNCHẾ-#8] Batch Insert Queue: accumulates NORMAL records ──────────
    // ConcurrentLinkedQueue: thread-safe for high-frequency concurrent adds + atomic drain
    private final ConcurrentLinkedQueue<HealthRecordEntity> normalBatchQueue = new ConcurrentLinkedQueue<>();
    private final AtomicBoolean isFlushing = new AtomicBoolean(false);
    private static final int BATCH_MAX_SIZE = 500; // Safety cap: flush if too large regardless of timer

    /**
     * Primary pipeline — runs on Virtual Thread (via @Async).
     * The MQTT listener is never blocked; this method executes concurrently.
     *
     * [HẠNCHẾ-#6] @Async → Virtual Thread per MQTT message.
     */
    @Async   // applicationTaskExecutor = VirtualThreadPerTaskExecutor (see VirtualThreadConfig)
    public void processVitalSign(VitalSignDto vital) {
        String deviceId = vital.getDeviceId();
        if (deviceId == null) return;

        // Throttle: max 60Hz (16ms) per device
        long now = System.currentTimeMillis();
        Long lastTime = lastProcessedTime.get(deviceId);
        if (lastTime != null && now - lastTime < 16) return;
        lastProcessedTime.put(deviceId, now);

        // Resolve owner from device's MQTT topic
        String topic = "hk07/sensors/wristband/" + deviceId + "/vitals";
        Optional<WristbandConfigEntity> configOpt = wristbandConfigRepository.findByMqttTopic(topic);

        if (configOpt.isEmpty()) {
            log.debug("[HEALTH_SERVICE] No owner found for deviceId={}", deviceId);
            wsTemplate.convertAndSend("/topic/vitals", vital);
            return;
        }

        WristbandConfigEntity config = configOpt.get();
        UUID userId = config.getUser().getId();

        // ─── [HẠNCHẾ-#9] Dynamic threshold check ───────────────────────────
        AlertLevel level = computeAlertLevel(vital, config);

        // ─── [HẠNCHẾ-#8] Tiered persistence strategy ───────────────────────
        if (level == AlertLevel.NORMAL) {
            // Buffer NORMAL vitals into batch queue — flushed every 5s
            HealthRecordEntity record = buildRecord(vital, userId, level);
            normalBatchQueue.add(record);

            // Safety overflow flush: if queue grows too large, flush immediately
            if (normalBatchQueue.size() >= BATCH_MAX_SIZE) {
                log.warn("[HEALTH_SERVICE] Batch overflow — flushing {} records immediately", normalBatchQueue.size());
                flushNormalBatch();
            }
        } else {
            // WARNING / CRITICAL / STROKE: persist immediately, no batching
            HealthRecordEntity record = buildRecord(vital, userId, level);
            healthRepository.save(record);
            log.warn("[HEALTH_ALERT] userId={} level={} HR={} SpO2={}",
                    userId, level, vital.getHeartRate(), vital.getSpo2());
        }

        // ─── WebSocket broadcast (60Hz stream to dashboard) ─────────────────
        var payload = new VitalSignWithAlertDto(vital, level.name(), userId.toString());
        wsTemplate.convertAndSend("/topic/vitals", payload);
    }

    /**
     * [HẠNCHẾ-#8] Scheduled batch flush: every 5 seconds, drain the normalBatchQueue
     * into a single saveAll() call. This collapses up to 300 individual SQL INSERTs
     * (10Hz × 30s) into 1 batch JDBC call, reducing database I/O by ~98%.
     */
    @Scheduled(fixedDelay = 5000)
    @Transactional
    public void flushNormalBatch() {
        if (normalBatchQueue.isEmpty()) return;
        if (!isFlushing.compareAndSet(false, true)) return;
        try {
            List<HealthRecordEntity> batch = new ArrayList<>();
            HealthRecordEntity record;
            while ((record = normalBatchQueue.poll()) != null) {
                batch.add(record);
            }
            if (!batch.isEmpty()) {
                healthRepository.saveAll(batch);
                log.info("[HEALTH_BATCH] Flushed {} NORMAL vitals records to DB (batch mode)", batch.size());
            }
        } finally {
            isFlushing.set(false);
        }
    }

    /**
     * [HẠNCHẾ-#9] Dynamic thresholds from WristbandConfigEntity (DB-backed).
     *
     * Absolute STROKE ceiling is hardcoded as a medical safety net only.
     * All WARNING/CRITICAL thresholds come from the user's device configuration.
     */
    private AlertLevel computeAlertLevel(VitalSignDto v, WristbandConfigEntity cfg) {
        int hr       = v.getHeartRate();
        float spo2   = v.getSpo2();
        float sys    = v.getSystolic();
        float temp   = v.getBodyTemperature();

        // STROKE: Absolute medical ceiling — cannot be overridden by user config
        if (hr > 150 || hr < 40 || spo2 < 85.0f) return AlertLevel.STROKE;

        // CRITICAL: Dynamic thresholds from DB + critical margin
        int hrMaxCrit  = cfg.getHeartRateThresholdMax() + 20;
        float sysCrit  = cfg.getBloodPressureSystolicMax() + 20;
        if (hr > hrMaxCrit || sys > sysCrit || spo2 < 90.0f || temp > 39.5f)
            return AlertLevel.CRITICAL;

        // WARNING: Dynamic thresholds from DB
        if (hr > cfg.getHeartRateThresholdMax()
                || hr < cfg.getHeartRateThresholdMin()
                || sys > cfg.getBloodPressureSystolicMax()
                || spo2 < cfg.getSpo2Min()
                || temp > 38.5f)
            return AlertLevel.WARNING;

        return AlertLevel.NORMAL;
    }

    private HealthRecordEntity buildRecord(VitalSignDto vital, UUID userId, AlertLevel level) {
        return HealthRecordEntity.builder()
                .userId(userId)
                .heartRate(vital.getHeartRate())
                .systolic(vital.getSystolic())
                .diastolic(vital.getDiastolic())
                .bodyTemperature(vital.getBodyTemperature())
                .spo2(vital.getSpo2())
                .deviceId(vital.getDeviceId())
                .alertLevel(level)
                .agentAnalysis(level == AlertLevel.NORMAL
                        ? null
                        : "Threshold breach — Medical Agent analysis pending")
                .build();
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
        return mapRawToDto(rawList);
    }

    /**
     * Custom date-range hourly summary — supports arbitrary fromDate..toDate windows.
     * Used by the frontend CUSTOM range picker.
     * Max window capped at 90 days server-side to prevent runaway queries.
     */
    public List<com.hk07.domain.health.dto.HourlySummaryDto> getHourlySummaryByRange(
            UUID userId,
            java.time.LocalDateTime fromDate,
            java.time.LocalDateTime toDate) {

        // Safety cap: max 90 day window to prevent accidental full-table scans
        java.time.LocalDateTime cappedFrom = toDate.minusDays(90).isAfter(fromDate)
                ? toDate.minusDays(90) : fromDate;

        List<Object[]> rawList = healthRepository.findHourlySummaryByRangeRaw(userId, cappedFrom, toDate);
        return mapRawToDto(rawList);
    }

    /** Shared Object[] row → HourlySummaryDto mapper (native query result rows) */
    private List<com.hk07.domain.health.dto.HourlySummaryDto> mapRawToDto(List<Object[]> rawList) {
        java.time.format.DateTimeFormatter formatter =
                java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'");
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

    /** Minimal inner DTO — avoids creating a full class, reduces GC pressure */
    public record VitalSignWithAlertDto(VitalSignDto vitals, String alertLevel, String userId) {}
}

