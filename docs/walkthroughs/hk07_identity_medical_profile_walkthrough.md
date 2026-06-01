# HK-07 Identity & Medical Profile System Integration Walkthrough

This document outlines the complete implementation of the Patient Onboarding Wizard, self-service security management, and real-time AI Memory synchronization under the **Baymax Standard** for secure patient-robot interaction.

---

## 1. System Architecture Overview

The identity and medical baseline management flow follows a secure, high-integrity pipeline connecting the Java core backend, Vue frontend dashboard, and Python AI agent:

```
[Vue 3 Frontend]
       |
       |-- 1. Onboarding Wizard / Password Update / Recovery
       v
[Java Spring Boot Backend (Source of Truth)]
       |
       |-- 2. Validate & Persist (PostgreSQL)
       |-- 3. Generate Recovery Codes
       |-- 4. Push Real-time Webhook
       v
[Python FastAPI AI Agent Engine]
       |
       |-- 5. Embed Medical Profile Baseline
       |-- 6. Upsert Context to Vector Store (LanceDB)
       v
[Medical & Empathetic Agents]
       |
       |-- 7. Recall Super Context from LanceDB
       |-- 8. Incorporate into LLM Prompting
```

---

## 2. Completed Implementations

### A. Frontend Patient Onboarding Wizard (`LoginView.vue`)
- Implemented as a 4-step medical enrollment process:
  1. **Account Setup**: Captures display name, email, and secure credentials.
  2. **Medical Baseline**: Collects demographic indices (Age, Gender, Height, Weight, Blood Type) along with clinical history and allergies.
  3. **Emergency Contacts**: Captures critical guardian details for emergency notification routing.
  4. **Security Passphrase Recovery**: Generates and displays 5 secure recovery codes (8-characters) that users must copy and acknowledge saving before finishing.
- Automatic session sign-in is triggered upon completing the onboarding.

### B. Patient Self-Service Security (`LoginView.vue` & `ProfileSettingsView.vue`)
- **Passphrase Reset Flow**: Allows lost password recovery using the email and any of the unused recovery codes.
- **Passphrase Mutation**: Located in the Profile Settings panel, allowing active sessions to rotate password credentials securely.

### C. Live Medical Profile Sync (`ProfileSettingsView.vue`)
- A tactical settings panel mapping to `/profile`.
- Enables operators to review and modify their body metrics and medical baseline context on the fly.
- Syncs asynchronously with the backend database, automatically triggering the Python agent's memory update hook.

### D. AI Memory & Super Context Sync (`lance_memory.py` & `main.py`)
- FastAPI receives the profile sync hook at `/api/v1/memory/sync_profile`.
- Synchronizes health history vectors into LanceDB and configures database compaction predicates to exclude baseline medical records from the 24-hour cleanup cycle.
- System prompts in both `MedicalAgent` and `EmpatheticAgent` retrieve this permanent baseline vector on text-interaction or vitals-alerts to ensure tailored, personalized advice.

---

## 3. UI/UX Style Conformance
- Shipped standard color configurations aligning with the **Cinematic Cyber-DarkBlue** styling requirements:
  - **Base Background**: `#000624` (Deep Space DarkBlue)
  - **Surface Container**: `#000000` (Pure Black contrast)
  - **Primary Accent**: `#0052FF` (Cobalt Blue active outlines)
  - **Secondary Accent**: `#00D2FF` (Electric Blue data highlights)
  - **Typography**: `#F0F8FF` (Alice Blue readability)
  - **Success / Valid State**: `#00FF66` (Emerald Green for verified cryptographic signals)

---

## 4. Verification and Compilation
- Validated via local TypeScript syntax type checks (`vue-tsc --noEmit`):
  - **Result**: `Exit code: 0` (Clean compilation, type safe).
