package com.hk07.config;

import com.hk07.infrastructure.security.JwtService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.config.ChannelRegistration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageHeaderAccessor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

import java.security.Principal;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * WebSocket (STOMP) Configuration
 *
 * 1. JWT Authentication Interceptor — Verifies Bearer token on CONNECT.
 *
 * [P2-4] 2. Rate Limiter Interceptor — Limits inbound SEND messages per user:
 *    - Max 30 SEND frames per second per user session (configurable)
 *    - Sliding window implemented with per-user atomic counters + reset ticker
 *    - On breach: message is silently dropped and a WARN log is emitted
 *    - Emergency commands (SUBSCRIBE, CONNECT) are never rate-limited
 *    - This prevents DoS attacks via STOMP message flooding
 */
@Slf4j
@Configuration
@EnableWebSocketMessageBroker
@RequiredArgsConstructor
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    private final JwtService jwtService;

    // ── [P2-4] Rate Limiter State ──────────────────────────────────────────
    /** Max SEND messages per user per 1-second window */
    private static final int RATE_LIMIT_PER_SEC = 30;

    /** Per-user message counts for current 1-second window */
    private final ConcurrentHashMap<String, AtomicInteger> _msgCount = new ConcurrentHashMap<>();

    /** Per-user timestamp of current window start (epoch ms) */
    private final ConcurrentHashMap<String, Long> _windowStart = new ConcurrentHashMap<>();

    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        config.enableSimpleBroker("/topic", "/queue");
        config.setApplicationDestinationPrefixes("/app");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws")
                .setAllowedOriginPatterns("http://localhost:*", "http://127.0.0.1:*")
                .withSockJS();
    }

    @Override
    public void configureClientInboundChannel(ChannelRegistration registration) {
        registration.interceptors(new ChannelInterceptor() {
            @Override
            public Message<?> preSend(Message<?> message, MessageChannel channel) {
                StompHeaderAccessor accessor = MessageHeaderAccessor.getAccessor(message, StompHeaderAccessor.class);
                if (accessor == null) return message;

                // ── JWT Authentication on CONNECT ──────────────────────────
                if (StompCommand.CONNECT.equals(accessor.getCommand())) {
                    String authHeader = accessor.getFirstNativeHeader("Authorization");
                    if (authHeader != null && authHeader.startsWith("Bearer ")) {
                        String token = authHeader.substring(7);
                        if (jwtService.isTokenValid(token)) {
                            String userId = jwtService.extractUserId(token);
                            String role   = jwtService.extractRole(token);
                            UsernamePasswordAuthenticationToken auth = new UsernamePasswordAuthenticationToken(
                                userId, null, List.of(new SimpleGrantedAuthority("ROLE_" + role))
                            );
                            accessor.setUser(auth);
                        } else {
                            throw new IllegalArgumentException("Invalid JWT token for WebSocket connection");
                        }
                    } else {
                        throw new IllegalArgumentException("Missing Authorization header for WebSocket connection");
                    }
                }

                // ── [P2-4] Rate Limiter — Only applied to SEND frames ──────
                if (StompCommand.SEND.equals(accessor.getCommand())) {
                    Principal principal = accessor.getUser();
                    String userId = (principal != null) ? principal.getName() : "anonymous";

                    long now = System.currentTimeMillis();
                    long windowStart = _windowStart.computeIfAbsent(userId, k -> now);
                    AtomicInteger count = _msgCount.computeIfAbsent(userId, k -> new AtomicInteger(0));

                    // Reset window if 1 second has elapsed
                    if (now - windowStart >= 1000) {
                        _windowStart.put(userId, now);
                        count.set(0);
                    }

                    int current = count.incrementAndGet();
                    if (current > RATE_LIMIT_PER_SEC) {
                        log.warn("[WS_RATE_LIMIT] User={} exceeded {} msgs/s — frame DROPPED (count={})",
                                 userId, RATE_LIMIT_PER_SEC, current);
                        return null; // Drop message — Spring interprets null as rejection
                    }
                }

                return message;
            }
        });
    }
}
