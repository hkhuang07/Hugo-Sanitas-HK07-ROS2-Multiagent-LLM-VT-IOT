package com.hk07.common.enums;

/**
 * AgentType — Identifies which of the 3 MiroFish Agents generated an event.
 * Priority order for Subsumption: SAFETY > MEDICAL > EMPATHETIC
 */
public enum AgentType {
    /** Emotional analysis: voice tone, facial expression, mental state */
    EMPATHETIC,
    /** Medical analysis: vitals monitoring, medication reminders, stroke prediction */
    MEDICAL,
    /**
     * Physical safety: LiDAR obstacle/cliff detection, IMU fall detection.
     * Has HIGHEST Subsumption priority — can inhibit all other agents in < 5ms.
     */
    SAFETY
}
