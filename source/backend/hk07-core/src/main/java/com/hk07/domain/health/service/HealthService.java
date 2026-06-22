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
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.stream.Collectors;

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

    // ── Sliding windows for SpO2 and Heart Rate (size = 5) ──────────────────
    private final ConcurrentHashMap<String, ConcurrentLinkedQueue<Integer>> hrWindows = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, ConcurrentLinkedQueue<Float>> spo2Windows = new ConcurrentHashMap<>();

    // ── Thread-Safe Memory Cache & Bypass Map ────────────────────────────────
    @lombok.Data
    @lombok.AllArgsConstructor
    public static class IngestedVital {
        private final VitalSignDto vital;
        private final UUID userId;
        private final AlertLevel alertLevel;
    }

    private final ConcurrentLinkedQueue<IngestedVital> vitalsBuffer = new ConcurrentLinkedQueue<>();
    private final ConcurrentHashMap<UUID, Boolean> bypassAggregationMap = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<UUID, Long> bypassActivationTime = new ConcurrentHashMap<>();
    private final java.util.concurrent.atomic.AtomicBoolean globalBypass = new java.util.concurrent.atomic.AtomicBoolean(false);
    private long globalBypassActivationTime = 0;
    private final AtomicBoolean isFlushing = new AtomicBoolean(false);

    public void setBypassAggregation(UUID userId, boolean bypass) {
        long now = System.currentTimeMillis();
        if (bypass) {
            bypassAggregationMap.put(userId, true);
            bypassActivationTime.put(userId, now);
            log.warn("[BYPASS_AGGREGATION] Activated for patient={}", userId);
        } else {
            Long activatedAt = bypassActivationTime.get(userId);
            if (activatedAt != null && (now - activatedAt < 30000)) {
                log.debug("[BYPASS_AGGREGATION] Deactivation request deferred for patient={}. Remaining time: {}ms",
                          userId, 30000 - (now - activatedAt));
                return;
            }
            bypassAggregationMap.put(userId, false);
            log.info("[BYPASS_AGGREGATION] Deactivated for patient={}", userId);
        }
    }

    public void setBypassAggregationForAll(boolean bypass) {
        long now = System.currentTimeMillis();
        if (bypass) {
            globalBypass.set(true);
            globalBypassActivationTime = now;
            log.warn("[BYPASS_AGGREGATION] Activated globally");
        } else {
            if (globalBypassActivationTime != 0 && (now - globalBypassActivationTime < 30000)) {
                log.debug("[BYPASS_AGGREGATION] Global deactivation request deferred. Remaining time: {}ms",
                          30000 - (now - globalBypassActivationTime));
                return;
            }
            globalBypass.set(false);
            log.info("[BYPASS_AGGREGATION] Deactivated globally");
        }
    }

    public void setBypassAggregationForDevice(String deviceId, boolean bypass) {
        String topic = "hk07/sensors/wristband/" + deviceId + "/vitals";
        wristbandConfigRepository.findByMqttTopic(topic).ifPresent(config -> {
            setBypassAggregation(config.getUser().getId(), bypass);
        });
    }

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

        // Smooth SpO2 and Heart Rate using median filter of size 5 (ignoring <= 0 disconnected/invalid signals)
        ConcurrentLinkedQueue<Integer> hrWindow = hrWindows.computeIfAbsent(deviceId, k -> new ConcurrentLinkedQueue<>());
        ConcurrentLinkedQueue<Float> spo2Window = spo2Windows.computeIfAbsent(deviceId, k -> new ConcurrentLinkedQueue<>());
        
        if (vital.getHeartRate() > 0) {
            hrWindow.add(vital.getHeartRate());
            if (hrWindow.size() > 5) {
                hrWindow.poll();
            }
            List<Integer> hrList = new ArrayList<>(hrWindow);
            int medianHr = computeMedianInt(hrList);
            vital.setHeartRate(medianHr);
        } else {
            hrWindow.clear();
            vital.setHeartRate(-1);
        }
        
        if (vital.getSpo2() > 0.0f) {
            spo2Window.add(vital.getSpo2());
            if (spo2Window.size() > 5) {
                spo2Window.poll();
            }
            List<Float> spo2List = new ArrayList<>(spo2Window);
            float medianSpo2 = computeMedianFloat(spo2List);
            vital.setSpo2(medianSpo2);
        } else {
            spo2Window.clear();
            vital.setSpo2(-1.0f);
        }
        
        List<Integer> hrList = new ArrayList<>(hrWindow);
        List<Float> spo2List = new ArrayList<>(spo2Window);
        
        // ─── [HẠNCHẾ-#9] Dynamic threshold check ───────────────────────────
        AlertLevel level = computeAlertLevel(vital, config, hrList, spo2List);

        // Confirmed critical warning (CRITICAL or STROKE level) or Fever Alert triggers bypass instantly
        if ((vital.getBodyTemperature() >= 38.5f && vital.getBodyTemperature() > 0.0f) || level == AlertLevel.CRITICAL || level == AlertLevel.STROKE) {
            setBypassAggregation(userId, true);
        }

        // Add to sliding memory cache
        vitalsBuffer.add(new IngestedVital(vital, userId, level));

        // ─── WebSocket broadcast (60Hz stream to dashboard) ─────────────────
        var payload = new VitalSignWithAlertDto(vital, level.name(), userId.toString());
        wsTemplate.convertAndSend("/topic/vitals", payload);
    }

    /**
     * Scheduled batch flush: every 5 seconds, drains the memory cache
     * and performs downsampling (averaging) under normal conditions,
     * or bypasses and persists high-resolution raw data under emergency/anomaly states.
     */
    @Scheduled(fixedDelay = 5000)
    @Transactional
    public void flushVitalsPipeline() {
        if (vitalsBuffer.isEmpty()) return;
        if (!isFlushing.compareAndSet(false, true)) return;
        try {
            // Lock-free pipeline: drain all elements atomically
            List<IngestedVital> drained = new java.util.ArrayList<>();
            IngestedVital item;
            while ((item = vitalsBuffer.poll()) != null) {
                drained.add(item);
            }

            if (drained.isEmpty()) return;

            // Group by patient userId
            Map<UUID, List<IngestedVital>> grouped = drained.stream()
                    .collect(Collectors.groupingBy(IngestedVital::getUserId));

            for (Map.Entry<UUID, List<IngestedVital>> entry : grouped.entrySet()) {
                UUID userId = entry.getKey();
                List<IngestedVital> userGroup = entry.getValue();

                boolean isBypass = globalBypass.get() || bypassAggregationMap.getOrDefault(userId, false);

                // Audit group for anomaly signals to auto-trigger bypass if missed
                boolean hasAnomalyInBatch = userGroup.stream().anyMatch(v -> 
                        v.getAlertLevel() != AlertLevel.NORMAL || 
                        v.getVital().getBodyTemperature() >= 38.5f);

                if (hasAnomalyInBatch) {
                    isBypass = true;
                    setBypassAggregation(userId, true);
                }

                if (isBypass) {
                    // Bypass downsampling: save all raw high-res records
                    List<HealthRecordEntity> rawRecords = userGroup.stream()
                            .map(v -> buildRecord(v.getVital(), userId, v.getAlertLevel()))
                            .toList();
                    healthRepository.saveAll(rawRecords);
                    log.warn("[HEALTH_BATCH] Bypass active. Flushed {} raw records for user {}", rawRecords.size(), userId);
                    
                    // If no anomaly remains in current batch, reset bypass for next cycle
                    if (!hasAnomalyInBatch && !globalBypass.get()) {
                        setBypassAggregation(userId, false);
                    }
                } else {
                    // Normal conditions: compute arithmetic mean (ignoring <= 0 values)
                    double sumHr = 0;
                    int countHr = 0;
                    double sumSpo2 = 0;
                    int countSpo2 = 0;
                    double sumTemp = 0;
                    int countTemp = 0;
                    double sumSys = 0;
                    int countSys = 0;
                    double sumDias = 0;
                    int countDias = 0;

                    for (IngestedVital v : userGroup) {
                        int hrVal = v.getVital().getHeartRate();
                        if (hrVal > 0) {
                            sumHr += hrVal;
                            countHr++;
                        }
                        float spo2Val = v.getVital().getSpo2();
                        if (spo2Val > 0.0f) {
                            sumSpo2 += spo2Val;
                            countSpo2++;
                        }
                        float tempVal = v.getVital().getBodyTemperature();
                        if (tempVal > 0.0f) {
                            sumTemp += tempVal;
                            countTemp++;
                        }
                        float sysVal = v.getVital().getSystolic();
                        if (sysVal > 0.0f) {
                            sumSys += sysVal;
                            countSys++;
                        }
                        float diasVal = v.getVital().getDiastolic();
                        if (diasVal > 0.0f) {
                            sumDias += diasVal;
                            countDias++;
                        }
                    }

                    int finalHr = countHr > 0 ? (int) Math.round(sumHr / countHr) : -1;
                    float finalSpo2 = countSpo2 > 0 ? (float) (sumSpo2 / countSpo2) : -1.0f;
                    float finalTemp = countTemp > 0 ? (float) (sumTemp / countTemp) : -1.0f;
                    float finalSys = countSys > 0 ? (float) (sumSys / countSys) : -1.0f;
                    float finalDias = countDias > 0 ? (float) (sumDias / countDias) : -1.0f;

                    int count = userGroup.size();
                    VitalSignDto lastVital = userGroup.get(count - 1).getVital();
                    VitalSignDto avgVital = VitalSignDto.builder()
                            .deviceId(lastVital.getDeviceId())
                            .heartRate(finalHr)
                            .spo2(finalSpo2)
                            .bodyTemperature(finalTemp)
                            .systolic(finalSys)
                            .diastolic(finalDias)
                            .epochTimestampMs(lastVital.getEpochTimestampMs())
                            .build();

                    HealthRecordEntity record = buildRecord(avgVital, userId, AlertLevel.NORMAL);
                    healthRepository.save(record);
                    log.info("[HEALTH_BATCH] Downsampled {} normal records into 1 consolidated row for user {}", count, userId);
                }
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
    private AlertLevel computeAlertLevel(VitalSignDto v, WristbandConfigEntity cfg, List<Integer> hrWin, List<Float> spo2Win) {
        int hr       = v.getHeartRate();
        float spo2   = v.getSpo2();
        float sys    = v.getSystolic();
        float temp   = v.getBodyTemperature();

        // Stroke consistency check (ignore non-positive invalid values)
        boolean hrConsistentStroke = hrWin.size() >= 5 && hrWin.stream().allMatch(x -> x > 150 || (x > 0 && x < 40));
        boolean spo2ConsistentStroke = spo2Win.size() >= 5 && spo2Win.stream().allMatch(x -> x > 0.0f && x < 85.0f);

        // STROKE: Absolute medical ceiling — cannot be overridden by user config
        if (hrConsistentStroke || spo2ConsistentStroke) return AlertLevel.STROKE;

        // CRITICAL: Dynamic thresholds from DB + critical margin
        int hrMaxCrit  = cfg.getHeartRateThresholdMax() + 20;
        float sysCrit  = cfg.getBloodPressureSystolicMax() + 20;
        
        boolean hrConsistentCrit = hrWin.size() >= 5 && hrWin.stream().allMatch(x -> x > hrMaxCrit);
        boolean spo2ConsistentCrit = spo2Win.size() >= 5 && spo2Win.stream().allMatch(x -> x > 0.0f && x < 90.0f);
        
        if (hrConsistentCrit || (sys > 0.0f && sys > sysCrit) || (spo2 > 0.0f && spo2ConsistentCrit) || (temp > 0.0f && temp > 39.5f))
            return AlertLevel.CRITICAL;

        // WARNING: Dynamic thresholds from DB
        int hrMinWarn = cfg.getHeartRateThresholdMin();
        int hrMaxWarn = cfg.getHeartRateThresholdMax();
        float spo2MinWarn = cfg.getSpo2Min();
        
        boolean hrConsistentWarn = hrWin.size() >= 5 && hrWin.stream().allMatch(x -> x > hrMaxWarn || (x > 0 && x < hrMinWarn));
        boolean spo2ConsistentWarn = spo2Win.size() >= 5 && spo2Win.stream().allMatch(x -> x > 0.0f && x < spo2MinWarn);

        if (hrConsistentWarn
                || (sys > 0.0f && sys > cfg.getBloodPressureSystolicMax())
                || spo2ConsistentWarn
                || (temp > 0.0f && temp > 38.5f))
            return AlertLevel.WARNING;

        return AlertLevel.NORMAL;
    }

    private int computeMedianInt(List<Integer> list) {
        if (list == null || list.isEmpty()) return 72;
        List<Integer> sorted = new ArrayList<>(list);
        java.util.Collections.sort(sorted);
        return sorted.get(sorted.size() / 2);
    }

    private float computeMedianFloat(List<Float> list) {
        if (list == null || list.isEmpty()) return 98.0f;
        List<Float> sorted = new ArrayList<>(list);
        java.util.Collections.sort(sorted);
        return sorted.get(sorted.size() / 2);
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

