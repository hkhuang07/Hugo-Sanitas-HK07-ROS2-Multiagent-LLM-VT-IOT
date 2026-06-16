package com.hk07.config;

import com.hk07.common.enums.UserRole;
import com.hk07.infrastructure.security.JwtAuthFilter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;

/**
 * Security Configuration — JWT + RBAC (Phase 02)
 *
 * Stateless session (no HttpSession) — scales well with Virtual Threads.
 * RBAC roles: OWNER > OPERATOR > EMERGENCY_CONTACT > TECHNICIAN
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
@Slf4j
public class SecurityConfig {

    private final JwtAuthFilter jwtAuthFilter;

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        return http
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                // ── Public & Infrastructure endpoints ────────────────────────────
                // /error MUST be whitelisted: Spring's DispatcherServlet re-dispatches to /error
                // on any exception. Without this, the error endpoint itself triggers a new 401
                // which creates an Infinite Request Loop, saturating Tomcat handler threads.
                .requestMatchers(org.springframework.http.HttpMethod.OPTIONS, "/**").permitAll()
                .requestMatchers("/api/v1/auth/**", "/ws", "/ws/**", "/health", "/error", "/actuator/health", "/").permitAll()
                // ── Internal service endpoints (Python hk07-agent → hk07-core) ──
                // Agent log POST uses internal JWT — already protected by JWT filter
                // ── Role-Based Access Control ────────────────────────────────────
                .requestMatchers("/api/v1/safety/**", "/api/v1/agents/**")
                    .hasAnyRole(UserRole.OWNER.name(), UserRole.OPERATOR.name())
                // Only OWNER can issue shutdown command
                .requestMatchers("/api/v1/robot/command/shutdown")
                    .hasRole(UserRole.OWNER.name())
                // Everything else requires at minimum a valid JWT
                .anyRequest().authenticated()
            )
            .exceptionHandling(ex -> ex
                .accessDeniedHandler((request, response, accessDeniedException) -> {
                    log.warn("[ACCESS_DENIED] path={} principal={} authorities={} error={}",
                        request.getRequestURI(),
                        request.getUserPrincipal() != null ? request.getUserPrincipal().getName() : "anonymous",
                        org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication() != null 
                            ? org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication().getAuthorities() 
                            : "none",
                        accessDeniedException.getMessage());
                    response.sendError(jakarta.servlet.http.HttpServletResponse.SC_FORBIDDEN, "Access Denied");
                })
                .authenticationEntryPoint((request, response, authException) -> {
                    log.warn("[UNAUTHORIZED] path={} error={}",
                        request.getRequestURI(),
                        authException.getMessage());
                    response.sendError(jakarta.servlet.http.HttpServletResponse.SC_UNAUTHORIZED, "Unauthorized");
                })
            )
            .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class)
            .build();
    }

    @Bean
    public org.springframework.web.cors.CorsConfigurationSource corsConfigurationSource() {
        org.springframework.web.cors.CorsConfiguration configuration = new org.springframework.web.cors.CorsConfiguration();
        configuration.setAllowedOriginPatterns(java.util.List.of("*"));
        configuration.setAllowedMethods(java.util.List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(java.util.List.of("*"));
        configuration.setExposedHeaders(java.util.List.of("x-auth-token", "Set-Cookie"));
        configuration.setAllowCredentials(true);
        configuration.setMaxAge(3600L);
        org.springframework.web.cors.UrlBasedCorsConfigurationSource source = new org.springframework.web.cors.UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }

    @Bean
    public AuthenticationManager authenticationManager(
            AuthenticationConfiguration config) throws Exception {
        return config.getAuthenticationManager();
    }
}
