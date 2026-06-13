package com.hk07.infrastructure.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * JWT Authentication Filter — runs once per request.
 *
 * PRODUCTION HARDENING (Phase 09):
 *   1. Structural pre-validation: rejects empty/malformed tokens BEFORE they reach
 *      the JwtService parser, eliminating IllegalArgumentException overhead and
 *      "Found: 0 periods" log spam on every unauthenticated request.
 *   2. Strict compact JWT format check: must contain exactly 2 period separators
 *      (header.payload.signature) before attempting cryptographic validation.
 *   3. Minimum length guard: bare "Bearer " prefix or whitespace-only values are
 *      discarded without incurring CPU cost from parser instantiation.
 *
 * Runs on Virtual Threads — no blocking I/O (pure CPU JWT verification).
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class JwtAuthFilter extends OncePerRequestFilter {

    private static final int JWT_MIN_LENGTH = 20;  // Minimum viable JWT string length
    private static final int JWT_PERIOD_COUNT = 2;  // header.payload.signature = 2 dots

    private final JwtService jwtService;

    @Value("${hk07.security.internal-api-key:hk07-internal-api-key-bypass}")
    private String internalApiKey;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        // ── Service-to-Service API Key Bypass ──
        String apiKeyHeader = request.getHeader("X-Internal-API-Key");
        if (StringUtils.hasText(apiKeyHeader) && apiKeyHeader.equals(internalApiKey)) {
            var auth = new UsernamePasswordAuthenticationToken(
                "internal-service", null,
                List.of(new SimpleGrantedAuthority("ROLE_OWNER"))
            );
            SecurityContextHolder.getContext().setAuthentication(auth);
            log.debug("[API_KEY_BYPASS] Service-to-service auth successful for path={}", request.getRequestURI());
            filterChain.doFilter(request, response);
            return;
        }

        // ── Public Path Bypass (never hijack public paths with 401 responses) ──
        String uri = request.getRequestURI();
        boolean isPublicPath = uri.contains("/api/v1/auth/") ||
                               uri.startsWith("/ws/") ||
                               uri.equals("/health") ||
                               uri.equals("/error") ||
                               uri.contains("/actuator/");
        if (isPublicPath) {
            log.debug("[JWT_SKIP] Public path '{}' detected. Letting Spring Security evaluate.", uri);
            filterChain.doFilter(request, response);
            return;
        }

        String token = extractToken(request);

        if (token == null || token.equalsIgnoreCase("undefined") || token.equalsIgnoreCase("null")) {
            log.debug("[JWT_SKIP] No token or literal undefined/null found for path={}. Letting Spring Security evaluate.", uri);
            filterChain.doFilter(request, response);
            return;
        }

        // ── GUARD 1: Structural pre-validation ──
        if (!isStructurallyValid(token)) {
            log.warn("[JWT_REJECTED] Malformed token structure detected: token='{}' for path={}", token, uri);
            writeUnauthorizedResponse(response, "Malformed JWT structure");
            return;
        }

            // ── GUARD 2: Cryptographic validation ──
            try {
                if (jwtService.isTokenValid(token)) {
                    String userId = jwtService.extractUserId(token);
                    String role = jwtService.extractRole(token);

                    var auth = new UsernamePasswordAuthenticationToken(
                        userId, null,
                        List.of(new SimpleGrantedAuthority("ROLE_" + role))
                    );
                    SecurityContextHolder.getContext().setAuthentication(auth);
                    log.debug("[JWT_AUTH] userId={} role={} path={}", userId, role, request.getRequestURI());
                } else {
                    log.warn("[JWT_INVALID] Cryptographic validation failed for path={}", request.getRequestURI());
                    writeUnauthorizedResponse(response, "Invalid or expired JWT token");
                    return;
                }
            } catch (Exception e) {
                log.error("[JWT_ERROR] Exception parsing token for path={}: {}", request.getRequestURI(), e.getMessage());
                writeUnauthorizedResponse(response, "Token validation failed: " + e.getMessage());
                return;
            }

        filterChain.doFilter(request, response);
    }

    private void writeUnauthorizedResponse(HttpServletResponse response, String message) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(String.format(
            "{\"status\":\"error\",\"error\":\"UNAUTHORIZED\",\"message\":\"%s\",\"authError\":true}",
            message
        ));
    }

    /**
     * Extracts raw token string from Authorization header.
     * Returns null if header is absent or not a Bearer scheme.
     */
    private String extractToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (StringUtils.hasText(header) && header.startsWith("Bearer ")) {
            String token = header.substring(7).trim();
            return token.isEmpty() ? null : token;
        }
        return null;
    }

    /**
     * Structural pre-validation: checks compact JWT format without cryptographic cost.
     * A valid compact JWT must have exactly 2 period characters (3 Base64URL segments).
     */
    private boolean isStructurallyValid(String token) {
        if (token.length() < JWT_MIN_LENGTH) {
            return false;
        }
        return countOccurrences(token, '.') == JWT_PERIOD_COUNT;
    }

    private int countOccurrences(String str, char ch) {
        int count = 0;
        for (int i = 0; i < str.length(); i++) {
            if (str.charAt(i) == ch) count++;
        }
        return count;
    }

    @Override
    protected boolean shouldNotFilterAsyncDispatch() {
        return false;
    }

    @Override
    protected boolean shouldNotFilterErrorDispatch() {
        return false;
    }
}
