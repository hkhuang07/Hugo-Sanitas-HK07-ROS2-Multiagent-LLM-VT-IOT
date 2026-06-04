package com.hk07.domain.agent.controller;

import com.hk07.common.dto.ApiResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.Map;

/**
 * AgentDebugController — Phase 01 Completion
 *
 * Provides debug and integration-test endpoints that proxy to the Python
 * hk07-agent engine for blackboard inspection and orchestrator testing.
 *
 * Endpoints:
 *   GET  /api/v1/agents/blackboard/inspect       — dump Blackboard state
 *   POST /api/v1/agents/test/orchestrator         — integration test: message → full MAS state
 *   POST /api/v1/agents/v2/orchestrate            — Orchestrator V2 (parallel tool-calling)
 *   GET  /api/v1/agents/debug/router-status       — last provider used by RouterV2
 *
 * All endpoints proxy requests to the Python FastAPI engine (default :8889).
 * This controller is safe to expose in dev/staging; add @PreAuthorize for production.
 */
@RestController
@RequestMapping("/api/v1/agents")
@Slf4j
public class AgentDebugController {

    private final WebClient agentClient;

    public AgentDebugController(
            @Value("${hk07.ai.agent-url:http://127.0.0.1:8889}") String agentUrl) {
        this.agentClient = WebClient.builder()
                .baseUrl(agentUrl)
                .codecs(c -> c.defaultCodecs().maxInMemorySize(2 * 1024 * 1024)) // 2MB buffer
                .build();
        log.info("[AGENT_DEBUG] AgentDebugController ready — proxying to: {}", agentUrl);
    }

    // ── Blackboard Inspect ────────────────────────────────────────────────────

    /**
     * GET /api/v1/agents/blackboard/inspect
     *
     * Proxies to Python FastAPI GET /api/v1/agents/blackboard/inspect.
     * Returns latest ClinicalEntry, EmotionalEntry, ContextEntry + stats.
     * Useful for debugging Blackboard shared memory state from the Vue dashboard.
     */
    @GetMapping("/blackboard/inspect")
    @SuppressWarnings("unchecked")
    public ResponseEntity<ApiResponse<Map<String, Object>>> inspectBlackboard() {
        try {
            Map<String, Object> payload = agentClient.get()
                    .uri("/api/v1/agents/blackboard/inspect")
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(m -> (Map<String, Object>) m)
                    .block(Duration.ofSeconds(5));

            log.debug("[AGENT_DEBUG] Blackboard inspect: {}", payload);
            return ResponseEntity.ok(ApiResponse.ok(payload));

        } catch (Exception e) {
            log.error("[AGENT_DEBUG] Blackboard inspect failed: {}", e.getMessage());
            return ResponseEntity.ok(ApiResponse.ok(Map.of(
                    "error", "Python agent engine unavailable",
                    "detail", e.getMessage()
            )));
        }
    }

    // ── Orchestrator Integration Test ─────────────────────────────────────────

    /**
     * POST /api/v1/agents/test/orchestrator
     *
     * Feeds a synthetic user message (+ optional vitals) to the agent engine
     * and returns the full orchestration state. Supports both V1 and V2.
     *
     * Body: { "message": "...", "vitals": {...}, "use_v2": true }
     */
    @PostMapping("/test/orchestrator")
    @SuppressWarnings("unchecked")
    public ResponseEntity<ApiResponse<Map<String, Object>>> testOrchestrator(
            @RequestBody(required = false) Map<String, Object> body) {

        if (body == null) {
            body = Map.of("message", "Xin chào Hugo!", "use_v2", true);
        }

        try {
            Map<String, Object> result = agentClient.post()
                    .uri("/api/v1/agents/test/orchestrator")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(m -> (Map<String, Object>) m)
                    .block(Duration.ofSeconds(30));

            log.info("[AGENT_DEBUG] Test orchestrator response: agent={}, alert={}",
                    result != null ? result.get("current_agent") : "null",
                    result != null ? result.get("alert_level") : "null");

            return ResponseEntity.ok(ApiResponse.ok(result));

        } catch (Exception e) {
            log.error("[AGENT_DEBUG] Test orchestrator failed: {}", e.getMessage());
            return ResponseEntity.ok(ApiResponse.ok(Map.of(
                    "error", "Python agent engine unavailable",
                    "detail", e.getMessage()
            )));
        }
    }

    // ── Orchestrator V2 (parallel tool-calling) ───────────────────────────────

    /**
     * POST /api/v1/agents/v2/orchestrate
     *
     * Proxies to Python Orchestrator V2 (parallel tool-calling router).
     * Requires USE_ORCHESTRATOR_V2=true in Python engine .env.
     *
     * Body: { "message": "...", "vitals": {...} }
     */
    @PostMapping("/v2/orchestrate")
    @SuppressWarnings("unchecked")
    public ResponseEntity<ApiResponse<Map<String, Object>>> orchestrateV2(
            @RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> result = agentClient.post()
                    .uri("/api/v1/agents/v2/orchestrate")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(m -> (Map<String, Object>) m)
                    .block(Duration.ofSeconds(30));

            log.info("[AGENT_DEBUG] V2 orchestrate: tools={}, provider={}",
                    result != null ? result.get("tools_invoked") : "null",
                    result != null ? result.get("provider") : "null");

            return ResponseEntity.ok(ApiResponse.ok(result));

        } catch (Exception e) {
            log.error("[AGENT_DEBUG] V2 orchestrate failed: {}", e.getMessage());
            return ResponseEntity.ok(ApiResponse.ok(Map.of(
                    "error", "Python agent V2 unavailable",
                    "detail", e.getMessage()
            )));
        }
    }

    // ── Router Status (lightweight health check) ──────────────────────────────

    /**
     * GET /api/v1/agents/debug/router-status
     *
     * Quick health check: returns Python agent /health response.
     * Useful to confirm which engine version is active.
     */
    @GetMapping("/debug/router-status")
    @SuppressWarnings("unchecked")
    public ResponseEntity<ApiResponse<Map<String, Object>>> routerStatus() {
        try {
            Map<String, Object> health = agentClient.get()
                    .uri("/health")
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(m -> (Map<String, Object>) m)
                    .block(Duration.ofSeconds(3));

            return ResponseEntity.ok(ApiResponse.ok(health));

        } catch (Exception e) {
            log.warn("[AGENT_DEBUG] Router status check failed: {}", e.getMessage());
            return ResponseEntity.ok(ApiResponse.ok(Map.of(
                    "status", "OFFLINE",
                    "error", e.getMessage()
            )));
        }
    }
}
