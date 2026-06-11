package com.hk07.domain.agent.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.agent.dto.AgentLogRequest;
import com.hk07.domain.agent.entity.AgentLogEntity;
import com.hk07.domain.agent.service.AgentLogService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.reactive.function.client.WebClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.Map;

/**
 * Agent Log Controller — Phase 09
 *
 * Two concerns:
 * 1. POST /api/v1/agents/log — called by Python hk07-agent (internal service)
 *    Accepts agent decision logs and broadcasts them via WebSocket.
 *
 * 2. GET  /api/v1/agents/logs — called by Vue Dashboard
 *    Returns paginated log history for AgentsView.vue.
 *
 * Security: POST endpoint requires a valid JWT (internal service token).
 * The Python agent authenticates using the default owner JWT.
 */
@RestController
@RequestMapping("/api/v1/agents")
@Slf4j
public class AgentLogController {

    private final AgentLogService agentLogService;
    private final WebClient pythonAgentClient;

    public AgentLogController(AgentLogService agentLogService,
                              @Value("${hk07.ai.agent-url:http://127.0.0.1:8889}") String agentUrl) {
        this.agentLogService = agentLogService;
        this.pythonAgentClient = WebClient.builder().baseUrl(agentUrl).build();
        log.info("[AGENT_CONTROLLER] Initialized pythonAgentClient pointing to: {}", agentUrl);
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
        // Hard cap size at 50 to prevent memory overload
        int cappedSize = Math.min(size, 50);
        return ResponseEntity.ok(ApiResponse.ok(agentLogService.getRecentLogs(page, cappedSize)));
    }

    /** Decision count stats per agent (for AgentsView.vue metrics panel) */
    @GetMapping("/stats")
    public ResponseEntity<ApiResponse<Map<String, Long>>> getStats() {
        return ResponseEntity.ok(ApiResponse.ok(agentLogService.getDecisionCounts()));
    }

    /** Forward empathetic text interaction to Python agent engine */
    @PostMapping("/empathetic/interact")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, String>>>> interact(@RequestBody Map<String, String> body) {
        org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        String userId = (auth != null) ? auth.getName() : "owner@hk07.local";

        java.util.Map<String, Object> mutableBody = new java.util.HashMap<>(body);
        mutableBody.put("userId", userId);

        return pythonAgentClient.post()
                .uri("/agents/empathetic/interact")
                .bodyValue(mutableBody)
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> {
                    Map<String, String> response = Map.of("response", (String) map.get("response"));
                    return ResponseEntity.ok(ApiResponse.ok(response));
                })
                .timeout(java.time.Duration.ofSeconds(30))
                .onErrorResume(e -> {
                    log.warn("[AGENT_CONTROLLER] Empathetic interaction failed or timed out: {}", e.getMessage());
                    String message = body.getOrDefault("message", "");
                    String fallbackResponse = "[FALLBACK_BRIDGE] Empathetic Agent offline. Echo: '" +
                            (message.length() > 30 ? message.substring(0, 30) + "..." : message) + "'";
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(Map.of("response", fallbackResponse))));
                });
    }

    /** Proxy latest action plan retrieval to Python agent engine */
    @GetMapping("/action/plan/latest")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, Object>>>> getLatestActionPlan() {
        return pythonAgentClient.get()
                .uri("/api/v1/agents/action/plan/latest")
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> (Map<String, Object>) map)
                .map(response -> ResponseEntity.ok(ApiResponse.ok(response)))
                .timeout(java.time.Duration.ofSeconds(5))
                .onErrorResume(e -> {
                    log.warn("[AGENT_CONTROLLER] Failed to retrieve latest action plan from Python agent: {}", e.getMessage());
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(Map.of("status", "error", "message", "Python agent offline"))));
                });
    }

    /** Proxy action plan confirmation to Python agent engine */
    @PostMapping("/action/confirm")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, Object>>>> confirmActionPlan(@RequestBody Map<String, Object> body) {
        return pythonAgentClient.post()
                .uri("/api/v1/agents/action/confirm")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> (Map<String, Object>) map)
                .map(response -> ResponseEntity.ok(ApiResponse.ok(response)))
                .timeout(java.time.Duration.ofSeconds(10))
                .onErrorResume(e -> {
                    log.warn("[AGENT_CONTROLLER] Action plan confirmation failed: {}", e.getMessage());
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(Map.of("status", "error", "message", "Python agent offline"))));
                });
    }

    /** Proxy full-body perception scan to Python agent engine */
    @PostMapping("/perception/scan")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, Object>>>> perceptionScan(@RequestBody(required = false) Map<String, Object> body) {
        org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        String userId = (auth != null) ? auth.getName() : "owner@hk07.local";

        java.util.Map<String, Object> mutableBody = new java.util.HashMap<>();
        if (body != null) {
            mutableBody.putAll(body);
        }
        mutableBody.put("userId", userId);

        return pythonAgentClient.post()
                .uri("/api/v1/agents/perception/scan")
                .bodyValue(mutableBody)
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> (Map<String, Object>) map)
                .map(response -> ResponseEntity.ok(ApiResponse.ok(response)))
                .timeout(java.time.Duration.ofSeconds(30))
                .onErrorResume(e -> {
                    log.warn("[AGENT_CONTROLLER] Perception scan failed: {}", e.getMessage());
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(Map.of("status", "error", "message", "Python agent offline"))));
                });
    }

    /** Proxy latest perception scan retrieval to Python agent engine */
    @GetMapping("/perception/latest")
    @SuppressWarnings("unchecked")
    public Mono<ResponseEntity<ApiResponse<Map<String, Object>>>> getLatestPerceptionScan() {
        return pythonAgentClient.get()
                .uri("/api/v1/agents/perception/latest")
                .retrieve()
                .bodyToMono(Map.class)
                .map(map -> (Map<String, Object>) map)
                .map(response -> ResponseEntity.ok(ApiResponse.ok(response)))
                .timeout(java.time.Duration.ofSeconds(5))
                .onErrorResume(e -> {
                    log.warn("[AGENT_CONTROLLER] Timeout or error retrieving latest perception scan: {}", e.getMessage());
                    return Mono.just(ResponseEntity.ok(ApiResponse.ok(Map.of("status", "error", "message", "Python agent offline"))));
                });
    }
}
