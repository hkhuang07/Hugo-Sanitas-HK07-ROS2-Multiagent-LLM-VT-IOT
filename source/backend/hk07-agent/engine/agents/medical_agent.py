# Backwards compatibility compatibility redirect for CareAgent
from engine.agents.care_agent import CareAgent, safe_extract_json

# Alias
MedicalAgent = CareAgent

class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_time_s=1.0, recovery_time=1.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_s = recovery_time_s or recovery_time
        self.state = "CLOSED"
        self.failures = 0
        self.last_failure_time = 0.0

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            import time
            self.last_failure_time = time.time()

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        import time
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_time_s:
                self.state = "HALF_OPEN"
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False
