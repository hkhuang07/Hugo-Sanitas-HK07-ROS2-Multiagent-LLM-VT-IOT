/**
 * MockSensorService.ts
 *
 * Mock telemetry generator disabled.
 * Zero mock data writing to Pinia telemetry store.
 */

export const MockSensorService = {
  start(): void {
    // Mock sensor simulation is fully deactivated
    console.warn('[MockSensorService] Simulation is disabled. Only live telemetry allowed.')
  },
  stop(): void {
    // No-op
  },
  get isRunning(): boolean {
    return false
  }
}

