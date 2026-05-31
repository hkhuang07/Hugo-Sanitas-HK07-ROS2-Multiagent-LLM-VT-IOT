package com.hk07.domain.user.dto;

import com.hk07.common.enums.UserRole;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

@Data @Builder
public class UserDto {
    private UUID id;
    private String displayName;
    private String email;
    private UserRole role;
    private LocalDateTime createdAt;
    private LocalDateTime lastSeenAt;
    private WristbandConfigDto wristbandConfig;
}
