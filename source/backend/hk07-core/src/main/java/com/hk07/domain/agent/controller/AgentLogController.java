package com.hk07.domain.agent.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.agent.dto.AgentLogRequest;
import com.hk07.domain.agent.entity.AgentLogEntity;
import com.hk07.domain.agent.service.AgentLogService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.Map;

/**
 * Agent Log Controller — Phase 09 (Production-Hardened)
 *
 * REACTIVE STREAM ARCHITECTURE:
 *   - All Mono<> endpoints use 2500ms timeout gate (halved from 5000ms) to release
 *     reactor-http-nio threads immediately on Python agent slowness.
 *   - switchIfEmpty() pattern: empty Mono (no terminal signal from Python agent)
 *     instantly resolves to a cached SafeState fallback object — zero thread blocking.
 *   - onErrorResume() covers timeout + connection refused + 5xx from Python side.
 *   - Retry is intentionally NOT applied on action-plan polling (high-frequency GET)
 *     to prevent retry storms under load. Only empathetic/interact retries once with
 *     exponential backoff (user-facing latency is acceptable here).
 *
 * SECURITY:
 *   - userId extracted from Servlet-layer Principal (set by JwtAuthFilter before Mono starts).
 *   - No fallback to hardcoded UUIDs — uses "anonymous" sentinel that Python agents
 *     reject cleanly rather than silently routing to wrong user data.
 */
@RestController
@RequestMapping("/api/v1/agents")
@Slf4j
public class AgentLogController {

    // ── Stream timeout constants (tunable via env) ──────────────────────────
    private static final Duration INTERACT_TIMEOUT    = Duration.ofSeconds(10); // LLM can be slow - tuned to 10s to fail fast under agent starvation
    private static final Duration PLAN_POLL_TIMEOUT   = Duration.ofSeconds(15); // High-freq poll — 15s timeout for devmode
    private static final Duration CONFIRM_TIMEOUT     = Duration.ofSeconds(10);
    private static final Duration SCAN_TIMEOUT        = Duration.ofSeconds(30);
    private static final Duration PERCEPTION_TIMEOUT  = Duration.ofSeconds(15); // Background poll — 15s timeout for devmode

    // ── Safe fallback state objects (injected on empty/timeout) ────────────
    private static final Map<String, Object> SAFE_PLAN_STATE = Map.of(
        "status", "NO_PENDING",
        "plan", Map.of(),
        "source", "SAFE_CACHED_STATE"
    );
    private static final Map<String, Object> SAFE_PERCEPTION_STATE = Map.of(
        "status", "OFFLINE",
        "scan", Map.of(
            "overall_risk", "UNKNOWN",
            "posture_risk", "UNKNOWN",
            "facial_distress", 0.0,
            "confidence", 0.0,
            "disclaimer", "[OFFLINE_FALLBACK] Perception module unreachable."
        ),
        "source", "EMPTY_PERCEPTION_FALLBACK"
    );

    private final AgentLogService agentLogService;
    private final WebClient pythonAgentClient;

    public AgentLogController(AgentLogService agentLogService,
                              @Value("${hk07.ai.agent-url:http://127.0.0.1:8889}") String agentUrl) {
        this.agentLogService = agentLogService;
        this.pythonAgentClient = WebClient.builder()
                .baseUrl(agentUrl)
                .codecs(c -> c.defaultCodecs().maxInMemorySize(512 * 1024)) // 512KB cap
                .build();
        log.info("[AGENT_CONTROLLER] Initialized pythonAgentClient → {}", agentUrl);
    }

    /** Called by Python hk07-agent to record a decision */
    @PostMapping("/log")
    public ResponseEntity<ApiResponse<Void>> recordLog(@Valid @RequestBody AgentLogRequest req) {
        agentLogService.recordDecision(req);
        return ResponseEntity.accepted().body(ApiResponse.ok("Agent decision logged", null));
    }

    /** Paginated log history for dashboard */
    @GetMapping("/logs")
    public ResponseEntity<ApiResponse<Page<AgentLogEntity>>> getLogs(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size) {
        int cappedSize = Math.min(size, 50);
        return ResponseEntity.ok(ApiResponse.ok(agentLogService.getRecentLogs(page, cappedSize)));
    }

    /** Decision count stats per agent (for AgentsView.vue metrics panel) */
    @GetMapping("/stats")
    public ResponseEntity<ApiResponse<Map<String, Long>>> getStats() {
        return ResponseEntity.ok(ApiResponse.ok(agentLogService.getDecisionCounts()));
    }

    /**
     * Forward empathetic text interaction to Python agent engine.
     * Timeout: 30s (user-facing — LLM inference can take 10–25s under load).
     * Retry: 1 attempt with 1s backoff on connection errors only (not 4xx).
     */
    @PostMapping("/empathetic/interact")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, String>>>> interact(
            @RequestBody Map<String, String> body,
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            java.security.Principal principal) {
        String userId = (principal != null) ? principal.getName() : "anonymous";
        String userMessage = body.getOrDefault("message", "");

        java.util.Map<String, Object> mutableBody = new java.util.HashMap<>(body);
        mutableBody.put("userId", userId);

        log.debug("[AGENT_CONTROLLER] interact() userId={} msg_len={}", userId, userMessage.length());

        var requestSpec = pythonAgentClient.post().uri("/agents/empathetic/interact");
        if (authHeader != null) {
            requestSpec = requestSpec.header("Authorization", authHeader);
        }

        return requestSpec.bodyValue(mutableBody)
                .retrieve()
                .bodyToMono(Map.class)
                // switchIfEmpty: Python returned 200 with empty body — inject graceful fallback
                .switchIfEmpty(Mono.just(Map.of("response",
                    "[AGENT_BRIDGE] Agent returned empty response. Local fallback active.")))
                .map(map -> {
                    String reply = map.get("response") != null
                        ? map.get("response").toString()
                        : "[AGENT_BRIDGE] No response field in agent payload.";
                    java.util.Map<String, String> response = new java.util.HashMap<>();
                    response.put("response", reply);
                    return ResponseEntity.ok(ApiResponse.ok(response));
                })
                .timeout(INTERACT_TIMEOUT)
                // retryWhen: retry once on connection-refused / network error, NOT on 4xx/5xx
                .retryWhen(Retry.backoff(1, Duration.ofSeconds(1))
                    .filter(e -> !(e instanceof WebClientResponseException)))
                .onErrorResume(e -> {
                    String errType = e.getClass().getSimpleName();
                    log.warn("[AGENT_CONTROLLER] interact() {} — userId={}: {}",
                            errType, userId, e.getMessage() != null ? e.getMessage().substring(0, Math.min(80, e.getMessage().length())) : "null");
                    String fallbackMsg = "[FALLBACK_BRIDGE] Hugo Agent temporarily offline. " +
                            "Echo: '" + (userMessage.length() > 40 ? userMessage.substring(0, 40) + "..." : userMessage) + "'";
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(Map.of("response", fallbackMsg))));
                });
    }

    /**
     * Proxy latest action plan retrieval — high-frequency poll (2s interval).
     * Timeout: 2500ms (fail-fast gate to protect reactor thread pool).
     * NO retry: polling frequency makes retry unnecessary — next poll recovers.
     */
    @GetMapping("/action/plan/latest")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, Object>>>> getLatestActionPlan(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            java.security.Principal principal) {
        String userId = (principal != null) ? principal.getName() : "anonymous";

        var requestSpec = pythonAgentClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/agents/action/plan/latest")
                        .queryParam("userId", userId)
                        .build());
        if (authHeader != null) {
            requestSpec = requestSpec.header("Authorization", authHeader);
        }

        return requestSpec
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> (Map<String, Object>) map)
                // switchIfEmpty: no terminal signal within timeout → inject SafeCachedState instantly
                .switchIfEmpty(Mono.just(SAFE_PLAN_STATE))
                .map(response -> ResponseEntity.ok(ApiResponse.ok(response)))
                .timeout(PLAN_POLL_TIMEOUT)
                .onErrorResume(e -> {
                    // Suppress TimeoutException at DEBUG level — expected under Python agent load
                    if (e instanceof java.util.concurrent.TimeoutException) {
                        log.debug("[AGENT_CONTROLLER] action/plan poll timeout — userId={}", userId);
                    } else {
                        log.warn("[AGENT_CONTROLLER] action/plan error — {}", e.getMessage());
                    }
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(SAFE_PLAN_STATE)));
                });
    }

    /**
     * Proxy action plan confirmation — user-initiated, single-shot.
     * Timeout: 10s (confirmation triggers robot actuation — must not hang).
     */
    @PostMapping("/action/confirm")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, Object>>>> confirmActionPlan(
            @RequestBody Map<String, Object> body,
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            java.security.Principal principal) {
        String userId = (principal != null) ? principal.getName() : "anonymous";

        java.util.Map<String, Object> mutableBody = new java.util.HashMap<>(body);
        mutableBody.put("userId", userId);

        var requestSpec = pythonAgentClient.post().uri("/api/v1/agents/action/confirm");
        if (authHeader != null) {
            requestSpec = requestSpec.header("Authorization", authHeader);
        }

        return requestSpec.bodyValue(mutableBody)
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> (Map<String, Object>) map)
                .switchIfEmpty(Mono.just(Map.of("status", "NO_RESPONSE", "message", "Agent returned empty")))
                .map(response -> ResponseEntity.ok(ApiResponse.ok(response)))
                .timeout(CONFIRM_TIMEOUT)
                .onErrorResume(e -> {
                    log.warn("[AGENT_CONTROLLER] action/confirm failed — userId={}: {}", userId, e.getMessage());
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(
                        Map.of("status", "ERROR", "message", "Action confirmation failed — Python agent offline"))));
                });
    }

    /**
     * Proxy full-body perception scan — triggered by user, long-running.
     * Timeout: 30s (OpenCV + LLM vision inference can take 15–25s).
     */
    @PostMapping("/perception/scan")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, Object>>>> perceptionScan(
            @RequestBody(required = false) Map<String, Object> body,
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            java.security.Principal principal) {
        String userId = (principal != null) ? principal.getName() : "anonymous";

        java.util.Map<String, Object> mutableBody = new java.util.HashMap<>();
        if (body != null) {
            mutableBody.putAll(body);
        }
        mutableBody.put("userId", userId);

        var requestSpec = pythonAgentClient.post().uri("/api/v1/agents/perception/scan");
        if (authHeader != null) {
            requestSpec = requestSpec.header("Authorization", authHeader);
        }

        return requestSpec.bodyValue(mutableBody)
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> (Map<String, Object>) map)
                .switchIfEmpty(Mono.just(SAFE_PERCEPTION_STATE))
                .map(response -> ResponseEntity.ok(ApiResponse.ok(response)))
                .timeout(SCAN_TIMEOUT)
                .onErrorResume(e -> {
                    log.warn("[AGENT_CONTROLLER] perception/scan failed — userId={}: {}", userId, e.getMessage());
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(SAFE_PERCEPTION_STATE)));
                });
    }

    /**
     * Proxy latest perception scan retrieval — background poll.
     * Timeout: 2500ms (fail-fast; returns EmptyPerceptionFallback on timeout).
     */
    @GetMapping("/perception/latest")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, Object>>>> getLatestPerceptionScan(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            java.security.Principal principal) {
        String userId = (principal != null) ? principal.getName() : "anonymous";

        var requestSpec = pythonAgentClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/agents/perception/latest")
                        .queryParam("userId", userId)
                        .build());
        if (authHeader != null) {
            requestSpec = requestSpec.header("Authorization", authHeader);
        }

        return requestSpec
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> (Map<String, Object>) map)
                .switchIfEmpty(Mono.just(SAFE_PERCEPTION_STATE))
                .map(response -> ResponseEntity.ok(ApiResponse.ok(response)))
                .timeout(PERCEPTION_TIMEOUT)
                .onErrorResume(e -> {
                    if (e instanceof java.util.concurrent.TimeoutException) {
                        log.debug("[AGENT_CONTROLLER] perception/latest poll timeout — userId={}", userId);
                    } else {
                        log.warn("[AGENT_CONTROLLER] perception/latest error — {}", e.getMessage());
                    }
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(SAFE_PERCEPTION_STATE)));
                });
    }
}
