package com.hk07.domain.user.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.user.dto.UserDto;
import com.hk07.domain.user.dto.WristbandConfigDto;
import com.hk07.domain.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping("/me")
    public ResponseEntity<ApiResponse<UserDto>> getMe(Authentication auth) {
        UUID userId = UUID.fromString(auth.getName());
        return ResponseEntity.ok(ApiResponse.ok(userService.getById(userId)));
    }

    @PutMapping("/me/wristband")
    public ResponseEntity<ApiResponse<WristbandConfigDto>> updateWristband(
            Authentication auth,
            @RequestBody WristbandConfigDto dto) {
        UUID userId = UUID.fromString(auth.getName());
        return ResponseEntity.ok(ApiResponse.ok("Wristband configured",
                userService.upsertWristbandConfig(userId, dto)));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<UserDto>> getUser(@PathVariable UUID id) {
        return ResponseEntity.ok(ApiResponse.ok(userService.getById(id)));
    }
}
