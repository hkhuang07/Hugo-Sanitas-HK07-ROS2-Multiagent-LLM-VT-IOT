# [STATUS: DONE] CHANGELOG — Phase 01-02: Foundation + Auth
**Phase:** 03-frontend/phase-01-setup  
**Hoàn thành:** 2026-05-31

## Công việc đã hoàn thành

### Frontend (Vue 3 + Vite)
- [x] `package.json` — Vue 3.4, Vite 5, TypeScript, STOMP WS, Chart.js
- [x] `vite.config.ts` — API proxy + manual chunking
- [x] `index.html` — Cyber fonts (Orbitron, Roboto Mono, Share Tech Mono)
- [x] `cyber.css` — Complete Cyber-Cinematic design system:
  - Scanlines effect (GPU-accelerated)
  - Corner reticles
  - 30/70 asymmetric grid
  - Terminal cards, vital displays
  - Segmented progress bar
  - Neon glow utilities
- [x] `main.ts` — Vue 3 + Pinia + Router init
- [x] `router/index.ts` — Protected routes with auth guard
- [x] `DashboardView.vue` — Full dashboard: ECG 60Hz canvas, vitals, agent log, Subsumption status, chat
- [x] `LoginView.vue` — Boot sequence animation + JWT auth

### Backend Security (Phase 02)
- [x] `SecurityConfig.java` — JWT + RBAC stateless
- [x] `JwtService.java` — Access/Refresh token generation
- [x] `JwtAuthFilter.java` — Bearer token extraction + Spring Security context

## Phase tiếp theo
**Phase 02 Backend:** `phase-02-auth/` — AuthController + User entity + complete JWT flow
**Phase 03 Frontend:** `phase-02-auth/` — AgentsView + SafetyView
