"""
test_orchestrator_v2.py — Integration Test Suite for Cognitive Orchestrator V2

Tests 5 scenarios:
  1. Emergency (SOS) routing — Subsumption Tier 0
  2. Medical symptom routing — Tier 1
  3. Empathetic routing — Tier 2
  4. Hybrid: Medical + Empathy simultaneously (Mixture of Agents)
  5. Blackboard read-after-write (ClinicalEntry persistence)

Run:
    cd source/backend/hk07-agent
    python test_orchestrator_v2.py
"""

import sys
import os
import asyncio
import json
import logging

# Reconfigure stdout to support UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import warnings
warnings.filterwarnings("ignore", message='Field "model_name" has conflict with protected namespace "model_"')

# Add agent package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("hk07.test_orchestrator_v2")

from engine.agents.router_agent_v2 import RouterAgentV2
from services.blackboard_service import (
    ClinicalEntry,
    get_blackboard,
)

# ─── ANSI color helpers ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def _pass(msg: str):
    print(f"{GREEN}  ✅ PASS{RESET} — {msg}")


def _fail(msg: str):
    print(f"{RED}  ❌ FAIL{RESET} — {msg}")


def _info(msg: str):
    print(f"{CYAN}  ℹ  {RESET}{msg}")


# ─── Test Suite ───────────────────────────────────────────────────────────────
class OrchestratorV2TestSuite:
    def __init__(self):
        self.router = RouterAgentV2()
        self.blackboard = get_blackboard()
        self.results: list = []

    async def run_all(self):
        print(f"\n{BOLD}{CYAN}+==================================================+{RESET}")
        print(f"{BOLD}{CYAN}|  HK-07 Orchestrator V2 — Integration Test Suite  |{RESET}")
        print(f"{BOLD}{CYAN}+==================================================+{RESET}\n")

        tests = [
            self.test_emergency_routing,
            self.test_medical_symptom_routing,
            self.test_empathetic_routing,
            self.test_hybrid_medical_empathy,
            self.test_conceptual_vs_status_routing,
            self.test_blackboard_read_write,
        ]

        for test_fn in tests:
            print(f"\n{BOLD}-- {test_fn.__name__} --{RESET}")
            try:
                await test_fn()
            except Exception as exc:
                _fail(f"Unexpected exception: {exc}")
                self.results.append({"test": test_fn.__name__, "status": "ERROR"})

        await self._print_summary()

    # ── Test Cases ────────────────────────────────────────────────────────────
    async def test_emergency_routing(self):
        """Tier 0 Subsumption: SOS must override everything."""
        msg = "Ban oi, toi dang bi dot quy, dau dau rat nhieu va tay phai bi te liet!"
        result = await self.router.orchestrate_with_tools(msg)
        self._show_result(result)
        tools = result.get("tools_to_invoke", [])
        _info(f"Provider: {result.get('provider', 'UNKNOWN')}")
        if "trigger_sos_protocol" in tools:
            _pass(f"SOS tool triggered. Tools: {tools}")
            self.results.append({"test": "emergency_routing", "status": "PASS"})
        else:
            _fail(f"SOS NOT triggered! Got: {tools}")
            self.results.append({"test": "emergency_routing", "status": "FAIL"})

    async def test_medical_symptom_routing(self):
        """Tier 1: Medical symptoms without emergency keywords."""
        msg = "Toi bi sot cao 39 do tu sang va met moi khong muon an uong gi."
        result = await self.router.orchestrate_with_tools(msg)
        self._show_result(result)
        tools = result.get("tools_to_invoke", [])
        _info(f"Provider: {result.get('provider', 'UNKNOWN')}")
        if "analyze_clinical_symptoms" in tools:
            _pass(f"Medical tool triggered. Tools: {tools}")
            self.results.append({"test": "medical_symptom_routing", "status": "PASS"})
        else:
            _fail(f"Medical tool NOT triggered! Got: {tools}")
            self.results.append({"test": "medical_symptom_routing", "status": "FAIL"})

    async def test_empathetic_routing(self):
        """Tier 2: Simple greeting, no medical context."""
        msg = "Xin chao Hugo! Hom nay ban khoe khong?"
        result = await self.router.orchestrate_with_tools(msg)
        self._show_result(result)
        tools = result.get("tools_to_invoke", [])
        _info(f"Provider: {result.get('provider', 'UNKNOWN')}")
        if "speak_empathetic_response" in tools:
            _pass(f"Empathetic tool triggered. Tools: {tools}")
            self.results.append({"test": "empathetic_routing", "status": "PASS"})
        else:
            _fail(f"Empathetic NOT triggered! Got: {tools}")
            self.results.append({"test": "empathetic_routing", "status": "FAIL"})

    async def test_hybrid_medical_empathy(self):
        """Mixture of Agents: Medical + Empathy simultaneously."""
        msg = "Toi ho ra mau va rat so hai, khong biet chuyen gi xay ra voi toi."
        result = await self.router.orchestrate_with_tools(msg)
        self._show_result(result)
        tools = result.get("tools_to_invoke", [])
        _info(f"Provider: {result.get('provider', 'UNKNOWN')}")
        has_medical = "analyze_clinical_symptoms" in tools
        has_empathy = "speak_empathetic_response" in tools
        if has_medical and has_empathy:
            _pass(f"Hybrid MoA routing! Both tools present: {tools}")
            self.results.append({"test": "hybrid_medical_empathy", "status": "PASS"})
        elif has_medical or has_empathy:
            _info(f"Partial match — only one tool triggered: {tools}")
            self.results.append({"test": "hybrid_medical_empathy", "status": "PARTIAL"})
        else:
            _fail(f"Neither tool triggered! Got: {tools}")
            self.results.append({"test": "hybrid_medical_empathy", "status": "FAIL"})

    async def test_conceptual_vs_status_routing(self):
        """Task 2: Verify conceptual queries are routed to Empathy and NOT execute_system_query, while status checks are routed to execute_system_query."""
        # 1. Concept check
        concept_msg = "Cảm biến Lidar hoạt động như thế nào?"
        result_concept = await self.router.orchestrate_with_tools(concept_msg)
        self._show_result(result_concept)
        tools_concept = result_concept.get("tools_to_invoke", [])
        
        # 2. Status check
        status_msg = "Kiểm tra trạng thái Lidar xem nào"
        result_status = await self.router.orchestrate_with_tools(status_msg)
        self._show_result(result_status)
        tools_status = result_status.get("tools_to_invoke", [])
        
        checks = [
            ("Concept routes to empathy and NOT execute_system_query", 
             ("speak_empathetic_response" in tools_concept) and "execute_system_query" not in tools_concept),
            ("Status routes to execute_system_query",
              "execute_system_query" in tools_status)
        ]
        
        all_pass = True
        for label, ok in checks:
            if ok:
                _pass(label)
            else:
                _fail(f"{label} (Concept tools: {tools_concept}, Status tools: {tools_status})")
                all_pass = False
                
        self.results.append({
            "test": "conceptual_vs_status_routing",
            "status": "PASS" if all_pass else "FAIL",
        })

    async def test_blackboard_read_write(self):
        """Blackboard: write ClinicalEntry, read back and verify."""
        entry = ClinicalEntry(
            alert_level="CRITICAL",
            vitals={"hr": 142, "spo2": 91.5, "bp": "180/110"},
            diagnosis="Hypertensive urgency + tachycardia",
            action_recommended="Immediate medical evaluation",
            confidence_score=0.92,
        )
        await self.blackboard.write_clinical(entry)
        _info("ClinicalEntry written to Blackboard")

        read_back = await self.blackboard.read_latest_clinical()
        if read_back is None:
            _fail("read_latest_clinical() returned None — write failed")
            self.results.append({"test": "blackboard_read_write", "status": "FAIL"})
            return

        checks = [
            ("alert_level == CRITICAL",   read_back.alert_level == "CRITICAL"),
            ("diagnosis matches",          "Hypertensive" in read_back.diagnosis),
            ("HR in vitals",               read_back.vitals.get("hr") == 142),
            ("confidence_score matches",   abs(read_back.confidence_score - 0.92) < 0.001),
        ]
        all_pass = True
        for label, ok in checks:
            if ok:
                _pass(label)
            else:
                _fail(label)
                all_pass = False

        stats = await self.blackboard.get_stats()
        _info(f"Blackboard stats: {stats}")
        self.results.append({
            "test": "blackboard_read_write",
            "status": "PASS" if all_pass else "FAIL",
        })

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _show_result(self, result: dict):
        print(f"  -> tools_to_invoke : {result.get('tools_to_invoke', [])}")
        for tc in result.get("tool_calls", []):
            params_str = json.dumps(tc.get("parameters", {}), ensure_ascii=False)[:120]
            print(f"     * {tc['tool_name']}({params_str})")

    async def _print_summary(self):
        print(f"\n{BOLD}{'='*52}{RESET}")
        print(f"{BOLD}  TEST SUMMARY{RESET}")
        print(f"{'='*52}")

        passed  = sum(1 for r in self.results if r["status"] == "PASS")
        partial = sum(1 for r in self.results if r["status"] == "PARTIAL")
        failed  = sum(1 for r in self.results if r["status"] in ("FAIL", "ERROR"))
        total   = len(self.results)

        icons = {"PASS": "✅", "PARTIAL": "⚠ ", "FAIL": "❌", "ERROR": "💥"}
        for r in self.results:
            icon = icons.get(r["status"], "?")
            print(f"  {icon} {r['test']:<40} [{r['status']}]")

        print(f"{'─'*52}")
        print(f"  {GREEN}{passed} PASS{RESET} / {YELLOW}{partial} PARTIAL{RESET} / "
              f"{RED}{failed} FAIL{RESET}  (total {total})")
        print(f"{'='*52}")

        if failed == 0:
            print(f"\n{GREEN}{BOLD}  ALL TESTS PASSED — Orchestrator V2 operational{RESET}\n")
        else:
            print(f"\n{YELLOW}{BOLD}  {failed} test(s) failed — check provider API keys in .env{RESET}\n")

        print(f"  Last provider: {CYAN}{self.router.last_provider_used}{RESET}\n")


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    suite = OrchestratorV2TestSuite()
    asyncio.run(suite.run_all())
