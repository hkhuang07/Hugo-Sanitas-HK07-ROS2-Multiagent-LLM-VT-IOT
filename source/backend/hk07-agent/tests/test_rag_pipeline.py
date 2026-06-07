"""
test_rag_pipeline.py — Integration Test Suite for Phase 4 (RAG / Internet Knowledge)
"""

import sys
import os
import asyncio
import logging

# Reconfigure stdout to support UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import warnings
warnings.filterwarnings("ignore", message='Field "model_name" has conflict with protected namespace "model_"')

# Add agent package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.lance_memory import LanceMemory
from services.knowledge_ingestion import KnowledgeIngestionService
from agents.agent_orchestrator_v2 import AgentOrchestratorV2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("hk07.test_rag")

GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def _pass(msg: str):
    print(f"{GREEN}  ✅ PASS{RESET} — {msg}")


def _fail(msg: str):
    print(f"{RED}  ❌ FAIL{RESET} — {msg}")


def _info(msg: str):
    print(f"{CYAN}  ℹ  {RESET}{msg}")


class RAGPipelineTestSuite:
    def __init__(self):
        self.memory = LanceMemory()
        self.ingest_service = None
        self.orchestrator = None
        self.results = []

    async def setup(self):
        await self.memory.initialize()
        self.ingest_service = KnowledgeIngestionService(self.memory)
        self.orchestrator = AgentOrchestratorV2(self.memory)
        _info("Test setup completed (LanceDB initialized).")

    async def run_all(self):
        print(f"\n{BOLD}{CYAN}+==================================================+{RESET}")
        print(f"{BOLD}{CYAN}|  HK-07 RAG / Knowledge Pipeline Integration Test |{RESET}")
        print(f"{BOLD}{CYAN}+==================================================+{RESET}\n")

        await self.setup()

        tests = [
            self.test_domain_validation,
            self.test_ingest_url_blocked,
            self.test_text_ingestion_and_search,
            self.test_orchestrator_guidelines_tool,
        ]

        for test_fn in tests:
            print(f"\n{BOLD}-- {test_fn.__name__} --{RESET}")
            try:
                await test_fn()
            except Exception as exc:
                _fail(f"Unexpected exception: {exc}")
                self.results.append({"test": test_fn.__name__, "status": "ERROR"})

        self._print_summary()

    async def test_domain_validation(self):
        """Test that whitelist domains are correctly allowed and others blocked."""
        allowed = [
            "https://who.int/news-room",
            "http://www.cdc.gov/diseases",
            "https://moh.gov.vn/web/guest/home",
            "https://sub.moh.gov.vn/some-guideline"
        ]
        blocked = [
            "https://google.com",
            "https://wikipedia.org",
            "https://example.com/medical-fake-news"
        ]

        all_ok = True
        for url in allowed:
            if KnowledgeIngestionService.validate_url(url):
                _pass(f"Allowed: {url}")
            else:
                _fail(f"Blocked (should be allowed): {url}")
                all_ok = False

        for url in blocked:
            if not KnowledgeIngestionService.validate_url(url):
                _pass(f"Blocked: {url}")
            else:
                _fail(f"Allowed (should be blocked): {url}")
                all_ok = False

        self.results.append({
            "test": "domain_validation",
            "status": "PASS" if all_ok else "FAIL"
        })

    async def test_ingest_url_blocked(self):
        """Test URL ingestion blocks unauthorized domains."""
        url = "https://untrusted-site.com/fake-stroke-guide"
        res = await self.ingest_service.ingest_url(url)
        if res.get("status") == "blocked":
            _pass(f"Correctly blocked ingestion of: {url}")
            self.results.append({"test": "ingest_url_blocked", "status": "PASS"})
        else:
            _fail(f"Failed to block ingestion of untrusted URL. Result: {res}")
            self.results.append({"test": "ingest_url_blocked", "status": "FAIL"})

    async def test_text_ingestion_and_search(self):
        """Test direct text ingestion, automatic chunking, and keyword matching."""
        source = "https://who.int/cardiovascular-diseases"
        title = "WHO Guidelines on Hypertension Management"
        content = (
            "WHO RECOMMENDATIONS FOR HYPERTENSION CONTROL:\n"
            "This document presents guidelines for managing hypertension in adults.\n"
            "High blood pressure is defined as systolic blood pressure equal to or above 140 mmHg "
            "or diastolic blood pressure equal to or above 90 mmHg.\n"
            "Standard treatment involves lifestyle modifications, reduced salt intake, "
            "regular physical activity, and pharmacological therapies like ACE inhibitors or calcium channel blockers."
        )

        # Ingest text (should split into chunks and save to guidelines table)
        chunks = await self.ingest_service.ingest_text(source, title, content)
        if chunks > 0:
            _pass(f"Successfully ingested content as {chunks} chunks.")
        else:
            _fail("Failed to ingest content chunks.")
            self.results.append({"test": "text_ingestion_and_search", "status": "FAIL"})
            return

        # Perform guideline search
        # Query with overlapping keywords
        results = await self.memory.search_medical_guidelines("hypertension control blood pressure", limit=3)
        if results:
            _pass(f"Guideline search succeeded. Found {len(results)} matches.")
            first_match = results[0]
            _info(f"Match Title: {first_match.get('title')}")
            _info(f"Match Content: {first_match.get('content')[:120]}...")
            
            checks = [
                ("Source matches", first_match.get("source") == source),
                ("Title matches", first_match.get("title") == title),
                ("Content contains keyword", "hypertension" in first_match.get("content").lower()),
            ]
            all_ok = True
            for label, ok in checks:
                if ok:
                    _pass(label)
                else:
                    _fail(label)
                    all_ok = False
            self.results.append({
                "test": "text_ingestion_and_search",
                "status": "PASS" if all_ok else "FAIL"
            })
        else:
            _fail("Guideline search returned no results.")
            self.results.append({"test": "text_ingestion_and_search", "status": "FAIL"})

    async def test_orchestrator_guidelines_tool(self):
        """Test search_medical_guidelines tool execution in Orchestrator V2."""
        # Query that maps to guidelines search
        result = await self.orchestrator._execute_tool(
            tool_name="search_medical_guidelines",
            parameters={"query": "Đột quỵ FAST"},
            vitals={}
        )
        if "Bộ Y Tế VN" in result or "Nguồn:" in result:
            _pass(f"Orchestrator Guidelines tool returned citation. Response:\n{result[:160]}...")
            self.results.append({"test": "orchestrator_guidelines_tool", "status": "PASS"})
        else:
            _fail(f"Orchestrator guidelines search did not return expected citation. Response: {result}")
            self.results.append({"test": "orchestrator_guidelines_tool", "status": "FAIL"})

    def _print_summary(self):
        print(f"\n{BOLD}{'='*52}{RESET}")
        print(f"{BOLD}  TEST SUMMARY{RESET}")
        print(f"{'='*52}")

        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        total = len(self.results)

        icons = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥"}
        for r in self.results:
            icon = icons.get(r["status"], "?")
            print(f"  {icon} {r['test']:<40} [{r['status']}]")

        print(f"{'─'*52}")
        print(f"  {GREEN}{passed} PASS{RESET} / {RED}{failed} FAIL{RESET}  (total {total})")
        print(f"{'='*52}")


if __name__ == "__main__":
    suite = RAGPipelineTestSuite()
    asyncio.run(suite.run_all())
