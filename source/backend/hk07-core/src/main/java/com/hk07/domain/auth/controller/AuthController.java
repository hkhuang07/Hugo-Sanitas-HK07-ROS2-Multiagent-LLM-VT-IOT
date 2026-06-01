package com.hk07.domain.auth.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.common.exception.HK07BusinessException;
import com.hk07.domain.auth.dto.AuthDto;
import com.hk07.domain.auth.service.AuthService;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import java.time.Duration;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.UUID;

/**
 * Auth Controller — Phase 02 (Baymax Standard Auth Upgrade)
 * Endpoints: /api/v1/auth/login | /register | /refresh | /logout
 */
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<AuthDto.TokenResponse>> login(
            @Valid @RequestBody AuthDto.LoginRequest req,
            HttpServletResponse response) {
        AuthDto.TokenResponse tokenResponse = authService.login(req);
        String refreshToken = tokenResponse.getRefreshToken();
        tokenResponse.setRefreshToken(null); // Omit from JSON response body

        ResponseCookie cookie = ResponseCookie.from("hk07_refresh_token", refreshToken)
                .httpOnly(true)
                .secure(false) // Set to true if running over HTTPS in production
                .sameSite("Strict")
                .path("/api/v1/auth")
                .maxAge(Duration.ofDays(7))
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());

        return ResponseEntity.ok(ApiResponse.ok("Authentication successful", tokenResponse));
    }

    @PostMapping("/register")
    public ResponseEntity<ApiResponse<AuthDto.TokenResponse>> register(
            @Valid @RequestBody AuthDto.RegisterRequest req,
            HttpServletResponse response) {
        AuthDto.TokenResponse tokenResponse = authService.register(req);
        String refreshToken = tokenResponse.getRefreshToken();
        tokenResponse.setRefreshToken(null); // Omit from JSON response body

        ResponseCookie cookie = ResponseCookie.from("hk07_refresh_token", refreshToken)
                .httpOnly(true)
                .secure(false)
                .sameSite("Strict")
                .path("/api/v1/auth")
                .maxAge(Duration.ofDays(7))
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());

        return ResponseEntity.ok(ApiResponse.ok("Registration successful", tokenResponse));
    }

    @PostMapping("/refresh")
    public ResponseEntity<ApiResponse<AuthDto.TokenResponse>> refresh(
            @CookieValue(name = "hk07_refresh_token", required = false) String refreshToken,
            HttpServletResponse response) {
        if (refreshToken == null || refreshToken.isBlank()) {
            throw new HK07BusinessException("Missing refresh token cookie");
        }

        AuthDto.RefreshRequest req = new AuthDto.RefreshRequest();
        req.setRefreshToken(refreshToken);
        AuthDto.TokenResponse tokenResponse = authService.refresh(req);
        String newRefreshToken = tokenResponse.getRefreshToken();
        tokenResponse.setRefreshToken(null); // Omit from JSON response body

        ResponseCookie cookie = ResponseCookie.from("hk07_refresh_token", newRefreshToken)
                .httpOnly(true)
                .secure(false)
                .sameSite("Strict")
                .path("/api/v1/auth")
                .maxAge(Duration.ofDays(7))
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());

        return ResponseEntity.ok(ApiResponse.ok("Token refreshed", tokenResponse));
    }

    @PostMapping("/logout")
    public ResponseEntity<ApiResponse<Void>> logout(
            @CookieValue(name = "hk07_refresh_token", required = false) String refreshToken,
            HttpServletResponse response) {
        if (refreshToken != null && !refreshToken.isBlank()) {
            authService.logout(refreshToken);
        }

        ResponseCookie cookie = ResponseCookie.from("hk07_refresh_token", "")
                .httpOnly(true)
                .secure(false)
                .sameSite("Strict")
                .path("/api/v1/auth")
                .maxAge(0) // Immediately expire cookie
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());

        return ResponseEntity.ok(ApiResponse.ok("Logged out successfully", null));
    }

    @PostMapping("/change-password")
    public ResponseEntity<ApiResponse<Void>> changePassword(
            org.springframework.security.core.Authentication auth,
            @Valid @RequestBody AuthDto.ChangePasswordRequest req) {
        if (auth == null) {
            throw new org.springframework.security.authentication.InsufficientAuthenticationException("Authentication required");
        }
        UUID userId = UUID.fromString(auth.getName());
        authService.changePassword(userId, req);
        return ResponseEntity.ok(ApiResponse.ok("Password updated successfully", null));
    }

    @PostMapping("/reset-password")
    public ResponseEntity<ApiResponse<Void>> resetPassword(
            @Valid @RequestBody AuthDto.ResetPasswordRequest req) {
        authService.resetPassword(req);
        return ResponseEntity.ok(ApiResponse.ok("Password reset successful", null));
    }

    /** Health ping for frontend connectivity check */
    @GetMapping("/ping")
    public ResponseEntity<ApiResponse<String>> ping() {
        return ResponseEntity.ok(ApiResponse.ok("pong"));
    }
}
