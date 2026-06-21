package com.hk07.domain.agent.controller;

import com.hk07.common.dto.ApiResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

/**
 * SensorCacheController — [v2: Non-blocking cache proxy with stale-while-revalidate]
 *
 * [BUG-FIX] Original implementation used WebClient.block(5s) on a Virtual Thread,
 * saturating Tomcat handler pool when Python FastAPI was slow/busy. This caused
 * cascading AsyncRequestTimeoutException every ~1s.
 *
 * Fix strategy (Stale-While-Revalidate pattern):
 *   1. Keep AtomicReference<Map> as last-known-good cache
 *   2. On Python timeout/error, return stale cache (HTTP 200) instead of throwing
 *   3. Reduce block timeout to 2.5s to prevent thread starvation
 *   4. Log cache hits vs live hits at DEBUG level only (no ERROR spam)
 *
 * Proxies to Python FastAPI Agent Engine (port 8000) via WebClient.
 * Preserves Spring Boot API Gateway auth/RBAC layer.
 */
@RestController
@RequestMapping("/api/v1/sensor-cache")
@Slf4j
public class SensorCacheController {

    private final WebClient agentClient;

    // ── Stale-While-Revalidate cache ─────────────────────────────────────────
    private final AtomicReference<Map<String, Object>> _latestCacheRef = new AtomicReference<>(null);
    private final AtomicLong _cacheUpdatedAt = new AtomicLong(0);
    private static final long STALE_THRESHOLD_MS = 10_000L; // serve stale for up to 10s
    private final AtomicReference<Map<String, Object>> _visionCacheRef = new AtomicReference<>(null);
    private final AtomicLong _visionUpdatedAt = new AtomicLong(0);

    // Suppress repeated timeout error logs (log only first N per minute)
    private final AtomicLong _errorCount = new AtomicLong(0);
    private final AtomicLong _errorWindowStart = new AtomicLong(System.currentTimeMillis());
    private static final long ERROR_LOG_WINDOW_MS = 60_000L;
    private static final long MAX_ERRORS_PER_WINDOW = 3;

    public SensorCacheController(
            @Value("${hk07.ai.agent-url:http://localhost:8000}") String agentUrl) {
        this.agentClient = WebClient.builder()
                .baseUrl(agentUrl)
                .codecs(c -> c.defaultCodecs().maxInMemorySize(10 * 1024 * 1024))
                .build();
        log.info("[SENSOR_CACHE] SensorCacheController v2 initialized — stale-while-revalidate proxy to: {}", agentUrl);
    }

    /**
     * GET /api/v1/sensor-cache/latest
     * [v2] Stale-While-Revalidate: returns cached data on Python timeout.
     * Eliminates AsyncRequestTimeoutException flood. Thread-safe via AtomicReference.
     */
    @GetMapping("/latest")
    @SuppressWarnings("unchecked")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getLatestCache() {
        try {
            Map<String, Object> payload = agentClient.get()
                    .uri("/api/v1/sensor-cache/latest")
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(m -> (Map<String, Object>) m)
                    .block(Duration.ofMillis(2500)); // [FIX] 2.5s timeout (was 5s)

            if (payload != null) {
                // Update the stale cache on successful fetch
                _latestCacheRef.set(payload);
                _cacheUpdatedAt.set(System.currentTimeMillis());
                // Reset error counter on success
                _errorCount.set(0);
            }
            return ResponseEntity.ok(ApiResponse.ok(payload));

        } catch (Exception e) {
            // [FIX] Stale-While-Revalidate: serve last known good data instead of error
            Map<String, Object> stale = _latestCacheRef.get();
            long staleness = System.currentTimeMillis() - _cacheUpdatedAt.get();

            // Rate-limited error logging (max 3 logs per minute to prevent console flood)
            long now = System.currentTimeMillis();
            if (now - _errorWindowStart.get() > ERROR_LOG_WINDOW_MS) {
                _errorWindowStart.set(now);
                _errorCount.set(0);
            }
            if (_errorCount.incrementAndGet() <= MAX_ERRORS_PER_WINDOW) {
                log.warn("[SENSOR_CACHE] Python agent timeout ({}ms stale cache available). Error: {}",
                        staleness, e.getMessage());
            }

            if (stale != null && staleness < STALE_THRESHOLD_MS) {
                // Serve stale cache — annotate with staleness metadata
                Map<String, Object> response = new HashMap<>(stale);
                response.put("_cache_stale", true);
                response.put("_cache_age_ms", staleness);
                return ResponseEntity.ok(ApiResponse.ok(response));
            }

            // No stale data available — return empty-but-valid response
            return ResponseEntity.ok(ApiResponse.ok(Map.of(
                    "status", "agent_unavailable",
                    "daemon_status", "PYTHON_UNREACHABLE",
                    "vitals", Map.of(),
                    "fall_detected", false,
                    "fever_alert", false,
                    "frame_available", false
            )));
        }
    }

    /**
     * GET /api/v1/sensor-cache/frame
     * [v2] Returns raw JPEG frame bytes. Short timeout to prevent thread starvation.
     */
    @GetMapping(value = "/frame", produces = MediaType.IMAGE_JPEG_VALUE)
    public ResponseEntity<byte[]> getCachedFrame() {
        try {
            byte[] frame = agentClient.get()
                    .uri("/api/v1/sensor-cache/frame")
                    .retrieve()
                    .bodyToMono(byte[].class)
                    .block(Duration.ofMillis(2500)); // [FIX] 2.5s timeout (was 5s)

            if (frame == null || frame.length == 0) {
                return ResponseEntity.notFound().build();
            }
            return ResponseEntity.ok(frame);
        } catch (Exception e) {
            log.debug("[SENSOR_CACHE] Frame fetch failed (non-critical): {}", e.getMessage());
            return ResponseEntity.notFound().build();
        }
    }

    /**
     * GET /api/v1/sensor-cache/vision
     * [v2] Stale-While-Revalidate proxy for Python vision endpoint.
     */
    @GetMapping("/vision")
    @SuppressWarnings("unchecked")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getVisionCache() {
        try {
            Map<String, Object> payload = agentClient.get()
                    .uri("/api/v1/sensor-cache/vision")
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(m -> (Map<String, Object>) m)
                    .block(Duration.ofMillis(2500)); // 2.5s timeout

            if (payload != null) {
                _visionCacheRef.set(payload);
                _visionUpdatedAt.set(System.currentTimeMillis());
            }
            return ResponseEntity.ok(ApiResponse.ok(payload));

        } catch (Exception e) {
            Map<String, Object> stale = _visionCacheRef.get();
            long staleness = System.currentTimeMillis() - _visionUpdatedAt.get();

            log.debug("[SENSOR_CACHE] Python vision agent query timeout/error: {}", e.getMessage());

            if (stale != null && staleness < 30_000L) { // serve stale vision for up to 30s
                Map<String, Object> response = new HashMap<>(stale);
                response.put("_cache_stale", true);
                response.put("_cache_age_ms", staleness);
                return ResponseEntity.ok(ApiResponse.ok(response));
            }

            return ResponseEntity.ok(ApiResponse.ok(Map.of(
                    "status", "agent_unavailable",
                    "daemon_status", "PYTHON_UNREACHABLE",
                    "camera_fresh", false,
                    "frame_available", false,
                    "latest_scan", Map.of()
            )));
        }
    }
}
