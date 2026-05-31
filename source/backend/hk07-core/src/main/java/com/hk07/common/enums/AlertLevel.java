package com.hk07.common.enums;

/** Alert severity level for health and safety events */
public enum AlertLevel {
    /** All vitals within normal range */
    NORMAL,
    /** Informational — no immediate action required */
    INFO,
    /** Attention needed — notify owner */
    WARNING,
    /** Dangerous — activate emergency protocol */
    CRITICAL,
    /** Extreme — suspected stroke / fall / cardiac event */
    STROKE
}
