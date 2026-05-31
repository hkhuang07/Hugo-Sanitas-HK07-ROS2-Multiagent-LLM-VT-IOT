package com.hk07.domain.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

public class AuthDto {

    @Data
    public static class LoginRequest {
        @NotBlank @Email
        private String email;
        @NotBlank @Size(min = 8, max = 128)
        private String password;
    }

    @Data
    public static class RegisterRequest {
        @NotBlank @Size(min = 2, max = 100)
        private String displayName;
        @NotBlank @Email
        private String email;
        @NotBlank @Size(min = 8, max = 128)
        private String password;
    }

    @Data
    public static class RefreshRequest {
        @NotBlank
        private String refreshToken;
    }

    @lombok.Builder
    @Data
    public static class TokenResponse {
        private String accessToken;
        private String refreshToken;
        private long accessTokenExpiresAt;  // Unix epoch ms
        private String userId;
        private String role;
    }
}
