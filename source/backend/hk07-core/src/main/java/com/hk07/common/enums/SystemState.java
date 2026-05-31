package com.hk07.common.enums;

/** Overall robot system state — drives HUD color and operator actions */
public enum SystemState {
    INITIALIZING,
    ACTIVE,
    PATROL,
    SAFE_HOLD,
    EMERGENCY,
    MAINTENANCE,
    SHUTDOWN
}
