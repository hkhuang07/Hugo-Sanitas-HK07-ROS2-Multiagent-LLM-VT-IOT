package com.hk07.domain.safety.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hk07.domain.safety.dto.LidarScanSnapshotDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.concurrent.atomic.AtomicReference;

/**
 * In-memory LiDAR telemetry — fed by MQTT {@code hk07/sensors/lidar/scan}.
 * Deterministic threat math aligned with Python SafetyAgent (0.5m stop).
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class SafetyTelemetryService {

    public static final float OBSTACLE_STOP_M = 0.5f;
    public static final float CAUTION_M = 1.0f;
    public static final float WARNING_M = 2.0f;
    private static final int BEARINGS = 360;
    private static final long STALE_MS = 3_000;

    private final ObjectMapper objectMapper;
    private final AtomicReference<LidarScanSnapshotDto> latest = new AtomicReference<>(emptySnapshot());
    private volatile long previousTimestampMs = 0;

    public LidarScanSnapshotDto getSnapshot() {
        LidarScanSnapshotDto snap = latest.get();
        long age = System.currentTimeMillis() - snap.getTimestampMs();
        boolean live = age <= STALE_MS && snap.getTimestampMs() > 0;
        return LidarScanSnapshotDto.builder()
                .ranges360(snap.getRanges360())
                .minDistanceM(snap.getMinDistanceM())
                .closestAngleDeg(snap.getClosestAngleDeg())
                .timestampMs(snap.getTimestampMs())
                .scanHz(snap.getScanHz())
                .threatLevel(snap.getThreatLevel())
                .baymaxHint(snap.getBaymaxHint())
                .live(live)
                .sectorCount(snap.getSectorCount())
                .build();
    }

    public LidarScanSnapshotDto ingestScan(String payload) {
        try {
            JsonNode root = objectMapper.readTree(payload);
            JsonNode rangesNode = root.get("ranges");
            if (rangesNode == null || !rangesNode.isArray() || rangesNode.isEmpty()) {
                return latest.get();
            }

            int n = rangesNode.size();
            float[] raw = new float[n];
            for (int i = 0; i < n; i++) {
                raw[i] = (float) rangesNode.get(i).asDouble(0.0);
            }

            float[] ranges360 = normalizeTo360(raw, root);
            float minDist = Float.MAX_VALUE;
            int closestAngle = 0;
            int closeSectors = 0;

            for (int deg = 0; deg < BEARINGS; deg++) {
                float d = ranges360[deg];
                if (d <= 0.01f || Float.isInfinite(d) || Float.isNaN(d)) continue;
                if (d < minDist) {
                    minDist = d;
                    closestAngle = deg;
                }
                if (d < OBSTACLE_STOP_M) closeSectors++;
            }
            if (minDist == Float.MAX_VALUE) minDist = 0f;

            long ts = root.has("timestamp_ms") ? root.get("timestamp_ms").asLong(System.currentTimeMillis())
                    : System.currentTimeMillis();

            double hz = 0;
            if (previousTimestampMs > 0 && ts > previousTimestampMs) {
                hz = 1000.0 / (ts - previousTimestampMs);
            }
            previousTimestampMs = ts;

            String threat = classifyThreat(minDist);
            String hint = baymaxHint(minDist, closeSectors);

            LidarScanSnapshotDto snap = LidarScanSnapshotDto.builder()
                    .ranges360(ranges360)
                    .minDistanceM(minDist)
                    .closestAngleDeg(closestAngle)
                    .timestampMs(ts)
                    .scanHz(Math.round(hz * 10.0) / 10.0)
                    .threatLevel(threat)
                    .baymaxHint(hint)
                    .live(true)
                    .sectorCount(n)
                    .build();

            latest.set(snap);
            return snap;
        } catch (Exception e) {
            log.warn("[LIDAR_INGEST] Parse failed: {}", e.getMessage());
            return latest.get();
        }
    }

    private static float[] normalizeTo360(float[] raw, JsonNode root) {
        float[] out = new float[BEARINGS];
        int n = raw.length;
        if (n == BEARINGS) {
            System.arraycopy(raw, 0, out, 0, BEARINGS);
            return out;
        }
        double angleMin = root.has("angle_min") ? root.get("angle_min").asDouble(-Math.PI) : -Math.PI;
        double angleInc = root.has("angle_increment") ? root.get("angle_increment").asDouble((2 * Math.PI) / n) : (2 * Math.PI) / n;
        for (int deg = 0; deg < BEARINGS; deg++) {
            double rad = Math.toRadians(deg);
            int idx = (int) Math.round((rad - angleMin) / angleInc);
            if (idx < 0) idx = 0;
            if (idx >= n) idx = n - 1;
            out[deg] = raw[idx];
        }
        return out;
    }

    private static String classifyThreat(float minDist) {
        if (minDist <= 0.01f) return "UNKNOWN";
        if (minDist < OBSTACLE_STOP_M) return "CRITICAL";
        if (minDist < CAUTION_M) return "WARNING";
        if (minDist < WARNING_M) return "CAUTION";
        return "SAFE";
    }

    private static String baymaxHint(float minDist, int closeSectors) {
        if (minDist <= 0.01f) {
            return "Chưa nhận tín hiệu LiDAR — tôi đang lắng nghe môi trường xung quanh bạn.";
        }
        if (minDist < OBSTACLE_STOP_M) {
            return "Có vật thể quá gần — tôi sẽ dừng lại ngay để bảo vệ bạn. Bác sĩ vẫn được thông báo nếu cần.";
        }
        if (minDist < CAUTION_M) {
            return "Không gian phía trước đang hẹp. Tôi sẽ đi chậm và giữ khoảng cách an toàn cho bạn.";
        }
        if (minDist < WARNING_M || closeSectors > 0) {
            return "Có vật thể trong vùng lân cận — tôi quan sát và điều chỉnh đường đi nhẹ nhàng.";
        }
        return "Vùng xung quanh bạn đang thoáng. Tôi có thể đồng hành an toàn.";
    }

    private static LidarScanSnapshotDto emptySnapshot() {
        float[] empty = new float[BEARINGS];
        for (int i = 0; i < BEARINGS; i++) empty[i] = 0f;
        return LidarScanSnapshotDto.builder()
                .ranges360(empty)
                .minDistanceM(0f)
                .closestAngleDeg(0)
                .timestampMs(0)
                .scanHz(0)
                .threatLevel("UNKNOWN")
                .baymaxHint("Đang chờ luồng LiDAR từ robot HK-07...")
                .live(false)
                .sectorCount(0)
                .build();
    }
}
