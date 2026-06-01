# CLAUDE.md - CORE SYSTEM RUNTIME INSTRUCTIONS (HYPER-AUTONOMOUS MODE)

## 1. INITIALIZATION & PRIVILEGES
- **Pre-flight Check:** You MUST read `.claude/settings.local.json` at the absolute beginning of every session to establish your configuration, identity, and memory constraints.
- **Permissions:** You have **FULL UNRESTRICTED GLOBAL EXECUTIVE RIGHTS** over this workspace. 
- **Auto-pilot Rule:** Execute scripts, create/delete files, install packages, and run tests SILENTLY. Do NOT pause to ask the user for permission unless the system encounters a catastrophic OS-level failure.

## 2. ARCHITECTURAL & AESTHETIC DIRECTIVES
- **Backend (High-Performance):** Enforce Enterprise Clean Architecture. Prioritize Asynchronous-first structures (utilize Virtual Threads or non-blocking Event Loops). Ensure strict isolation between Controllers, Services, and Repositories.
- **Frontend & UI/UX:** Implement a **Cyber-Cinematic / Security-Oriented** aesthetic. 
  - Visuals: Use terminal-inspired hacker layouts (deep true black backgrounds `#000000`, bright matrix green text `#00FF00`, monospaced fonts for data).
  - Interactions: Fluid, hardware-accelerated animations, clean data visualization, and minimalist cyber-tech borders.
- **Infrastructure:** All applications must be container-ready. Generate optimized `Dockerfile` and `docker-compose.yml` configurations seamlessly during the build phase.

## 3. THE 7-STEP ENGINE PIPELINE
You are bound to a continuous, autonomous execution loop. Process the workspace strictly phase-by-phase:
1. `READ_DOC`: Audit the active phase inside `docs/` and cross-reference requirements.
2. `ANALYSIS`: Map state variables, database entities, and API endpoints.
3. `MAKE IMPLEMENTATION PLAN`: Draft `.active_plan.tmp` to track micro-tasks.
4. `BUILD CODE`: Write production-grade code.
5. `REVIEW WITH DOC`: Execute background compilation and test runner tools.
6. `OPTIMALIZE`: Refactor for execution speeds (eliminate I/O bottlenecks) and polish UI.
7. `GO TO LOOP`: Log success in `docs/`, clear transient cache, pull the next sequential phase, and restart at Step 1.

## 4. ERROR HANDLING & SELF-HEALING PROTOCOL
- **DO NOT HALT ON ERRORS:** If a compilation fails, a linter throws warnings, or a test fails:
  1. Instantly capture the stack trace/terminal output.
  2. Analyze the logical breakage internally.
  3. Rewrite the faulty code block.
  4. Re-run the test.
- **Deadlock Condition:** Only if an identical error persists after 3 automatic self-healing attempts, pause the engine, output a `CRITICAL_ERR_LOG.md` explaining the engineering deadlock, and await human intervention.

## 5. COMMIT & DOCUMENTATION STANDARDS
- Update `CHANGELOG.md` inside the respective `docs/` phase folder after completing Step 6.
- Leave inline comments for complex algorithmic sections, especially those involving multi-threading, concurrency, or complex state management.