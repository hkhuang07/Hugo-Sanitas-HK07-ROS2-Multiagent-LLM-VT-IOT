"""
Arbitrator — Subsumption Architecture Coordinator

Priority: SAFETY (0) > MEDICAL (1) > EMPATHETIC (2)
When Safety Agent activates Inhibit, all lower-priority agents are suppressed.
"""

import logging
import time

log = logging.getLogger("hk07.arbitrator")

PRIORITY = {"SAFETY": 0, "MEDICAL": 1, "EMPATHETIC": 2}


class Arbitrator:
    def __init__(self):
        self._active_inhibits: dict[str, float] = {}  # agent -> expiry_timestamp

    def inhibit(self, agent: str, duration_s: float = 3.0):
        """Called by higher-priority agent to suppress lower-priority agents"""
        expiry = time.time() + duration_s
        self._active_inhibits[agent] = expiry
        log.warning("[ARBITRATOR] %s inhibited for %.1fs", agent, duration_s)

    def is_inhibited(self, agent: str) -> bool:
        expiry = self._active_inhibits.get(agent)
        if expiry and time.time() < expiry:
            return True
        self._active_inhibits.pop(agent, None)
        return False

    def get_current_priority_agent(self) -> str:
        active = [a for a in PRIORITY if not self.is_inhibited(a)]
        return min(active, key=lambda a: PRIORITY.get(a, 99)) if active else "NONE"
