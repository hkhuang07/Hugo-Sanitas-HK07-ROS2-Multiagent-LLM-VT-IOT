# BAO CAO PHAN TICH TOAN DIEN -- HugoSanitas HK-07 Agent System
**Phien ban:** v2.1 -- Cap nhat dua tren Log Session 19:25-19:32 ngay 08/07/2026
**Tac gia:** Antigravity AI -- Software & Robotics Architecture Analysis
**Phan loai:** CRITICAL DIAGNOSTIC -- PRODUCTION READINESS REVIEW

---

## MUC LUC
1. Phan tich Chi tiet Log Tung Dong
2. Phan loai Loi va Canh bao
3. Danh gia So sanh voi Hinh mau Baymax
4. De xuat Cai tien Production
5. Lo trinh Trien khai

---

## 1. PHAN TICH CHI TIET LOG TUNG DONG

### 1.1. Frontend /companion -- Hoi thoai

| Thoi diem | Su kien | Phan tich |
|-----------|---------|-----------|
| 19:25:42 | User: Hi Hugo, are you there | Request tieng Anh don gian |
| 19:25:47 | Hugo phan hoi OK | OK - Agent doc duoc light=134.5lux, battery=45%. Empathetic response tot |
| 19:26:16 | User: Chao ban Hugo, ban co o do khong? | Request tieng Viet |
| 19:26:29 | Hugo phan hoi OK | OK - Da ngon ngu tot. light=111.5lux, battery=45% tu sensor that |
| 19:27:20 | User: cho toi biet du lieu cam bien cua ban | LOI -- Xem ERROR-01 |
| 19:27:22 | Hugo: Khong nhan duoc cau tra loi hop le tu Agent | FAIL: tool succeeded nhung response null |
| 19:28:37 | User: anh sang hien tai the nao | |
| 19:28:39 | Hugo: Khong nhan duoc cau tra loi hop le | FAIL: Tuong tu, aggregation null |
| 19:28:51 | [ENVIRONMENT_SCAN] No Camera vision data in Blackboard | FAIL: IPWebcam khong co trong Blackboard |
| 19:30:04 | Hugo bao 'vet thuong hoac tu mau do' | CRITICAL FALSE POSITIVE: OpenCV sai |
| 19:30:33 | User: toi khong co vet thuong nay | User phu nhan -- mat niem tin vao he thong |
| 19:31:38 | User: scan me -- REGEX_INTERCEPT bat | OK: bypass LLM, force execute_full_body_scan |
| 19:31:55 | IP_SCANNER All discovery phases failed. CB 60s | FAIL: IPWebcam khong tim thay qua WiFi scan |
| 19:31:55 | Disk fallback latest_frame.jpg | WARNING: Dung anh cu, khong phai realtime |
| 19:32:14 | GEMINI_VISION_T2 timeout 4.5s | FAIL: Gemini khong tra loi kip |
| 19:32:20 | OLLAMA_PROBE timeout 3.0s | FAIL: Ollama khong chay |
| 19:32:22 | LOCAL_OPENCV_AI: Risk CRITICAL, Injuries 1 | FAIL: False positive -- anh cu + sai logic color |
| 19:32:23 | Vision resolved in 27408ms | CRITICAL: 27 GIAY -- khong chap nhan duoc cho production |
| 19:32:25 | Gemini 429 -- Global CB OPEN 1800s | CRITICAL DESIGN FLAW: Lock toan he thong 30 phut |

### 1.2. Log Backend Python WSL -- Phan tich tung dong

**19:26:40** `[CARE_ROUTER] Published action=COMPANION_CHAT priority=NORMAL gesture=NONE`
OK -- Router phan loai dung. Greeting = COMPANION_CHAT.

**19:27:20** `[GROQ_MITIGATION] Truncating message from 3037 to 2000 chars.`
WARNING -- Context history 3037 chars qua lon cho Groq free tier. Viec truncate tuy tien cat mat tool_results
quan trong, dan den response null o frontend.

**19:27:20** `Tier GROQ_TIER_1 hit hard budget timeout. Rotating... Attempt 1/3 timed out.`
WARNING -- Groq rate limit. Attempt 1 fail, attempt 2 thanh cong nhung context bi cut. Tool_results khong
duoc inject dung vao LLM synthesis prompt lan 2.

**19:27:22** `Tool fetch_sensor_telemetry completed successfully`
INFO -- Tool chay OK. Sensor data doc duoc. Nhung LLM synthesis sau do fail -> frontend nhan null message.

**19:30:36** `LLM decided to invoke tools: [analyze_clinical_symptoms, speak_empathetic_response]`
INFO -- Orchestrator V2 chay 2 tools song song. Kien truc dung.

**19:30:40** `[CARE_AGENT] Querying local qwen2.5 LLM for companion advice`
INFO -- Care agent dung local Ollama qwen2.5. Thanh cong.

**19:30:48** `[LANCE_MEMORY] Skipped ingest_chat_cycle -- table not initialized`
WARNING -- LanceDB chua init xong. Hoi thoai khong duoc luu vao long-term memory. Hugo khong nho context.

**19:31:38** `[REGEX_INTERCEPT] Scan keyword detected -- bypassing LLM tier.`
OK -- Fast-path intercept hoat dong dung. Scan bat truoc khi LLM timeout.

**19:31:55** `[IP_SCANNER] All discovery phases failed. Tripping circuit breaker for 60.0s.`
FAIL -- WiFi scan khong tim duoc IP cua IPWebcam app. Nguyen nhan: IP dong thay doi khi reconnect hotspot.

**19:31:55** `[AGENT_LOG_CLIENT] Backend core is offline. Reconnecting in 60.0s...`
WARNING -- hk07-core Spring Boot khong chay hoac khong accessible tu WSL. Mat observability.

**19:31:56** `[VISION_GROUPED/T2] Firing concurrent cluster: ['OPENAI_VISION_T2', 'GEMINI_VISION_T2'] (budget=4.5s)`
INFO -- Grouped vision cluster kien truc tot. Budget 4.5s qua thap cho network latency thuc te.

**19:32:14** `GEMINI_VISION_T2 hit hard budget timeout. Fail count GEMINI incremented to 1/3.`
FAIL -- Gemini khong tra loi trong 4.5s.

**RuntimeWarning: coroutine 'VertexLLM.async_completion' was never awaited**
BUG CODE -- Coroutine async khong duoc await dung trong Gemini/VertexLLM. Memory leak tiem nang.

**19:32:20** `[OLLAMA_PROBE] Probing timed out after 3.0s.` x2
FAIL -- Ollama tai localhost:11434 khong phan hoi. Model chua pull hoac port 11434 chua expose tu WSL.

**19:32:22** `[LOCAL_OPENCV_AI] Completed. Risk: CRITICAL, Tone: normal, Injuries: 1`
FAIL -- OpenCV local fallback T4 bao CRITICAL nhung la false positive. Dung anh cu tu disk fallback.

**19:32:23** `Vision resolved via LOCAL_EDGE_VLM in 27408ms -- risk=CRITICAL`
CRITICAL FAIL -- 27 giay cho 1 scan tu T4 fallback. 44 giay tong the. Khong the chap nhan cho production.

**19:32:25** `[CIRCUIT_BREAKER] 429 on GEMINI_VISION_T2! Tripping global circuit breaker.`
`[LLM_CLIENT_CB] Circuit Breaker tripped to OPEN. Routing to LocalOfflineFallback for 1800.0s.`
CRITICAL DESIGN FLAW -- 1 global circuit breaker khoa TOAN BO he thong khi Gemini 429.
Groq va OpenAI van hoat dong tot nhung bi khoa theo. Nguyen nhan: LLMClientCircuitBreaker la singleton global.

---

## 2. PHAN LOAI LOI VA CANH BAO

### ERROR-01 [CRITICAL]: LLM Tool Response Null sau Retry
- **Vi tri:** `agents/agent_orchestrator_v2.py` -- ham synthesis sau tool execution
- **Root cause:** GROQ timeout lan 1, retry lan 2 thanh cong nhung context 3037 chars bi truncate xuong 2000
  chars. Tool_results khong duoc inject dung vao synthesis prompt. LLM synthesis tra ve empty/null.
- **Fix:** Implement `_synthesize_with_fallback()` voi `_local_aggregate_tool_results()` lam du phong.

### ERROR-02 [HIGH]: IPWebcam Discovery Failed -- Disk Fallback voi Anh Cu
- **Vi tri:** `utils/ip_scanner.py`, `agents/perception_agent.py`
- **Root cause:** IP dong cua dien thoai thay doi khi reconnect hotspot WiFi. Khong co static IP override.
- **Hau qua:** Moi vision analysis deu dung `latest_frame.jpg` -- anh cu, khong phai realtime.
- **Fix:** Them `IPWEBCAM_STATIC_IP` vao `.env`, implement IP persistence cache TTL 30 phut.

### ERROR-03 [CRITICAL]: OpenCV False Positive Injury Detection
- **Vi tri:** `utils/vision_pipeline.py` -- `LOCAL_VLM_OPENCV_FALLBACK`
- **Root cause:** HSV color range (red: 0-10 degree) match mau nen/trang phuc. Dung tren anh cu tu disk.
- **Hau qua:** Hugo bao 'vet thuong CRITICAL' sai -> User mat niem tin vao he thong.
- **Fix:** Multi-frame confirmation (>=3/5 frames), confidence gate >0.75, cross-validate voi pain_score user.

### ERROR-04 [CRITICAL]: Global Circuit Breaker Lock Toan He Thong 30 Phut
- **Vi tri:** `services/llm_client.py` -- `LLMClientCircuitBreaker` singleton toan cuc
- **Root cause:** 1 global CB (`_circuit_breaker`) trip khi bat ky provider nao gap 429.
- **Hau qua:** Hugo offline hoan toan 30 phut. Groq va OpenAI van OK nhung bi khoa theo.
- **Fix:** Chuyen sang `ProviderCircuitBreaker` doc lap per-provider.

### ERROR-05 [HIGH]: Ollama Khong Hoat Dong (T3 Vision Tier)
- **Vi tri:** WSL Docker Compose, `services/llm_client.py`
- **Root cause:** Model `moondream` chua pull, port `11434` chua expose tu WSL ra Windows host.
- **Hau qua:** T3 local vision khong co, chi con T4 OpenCV (27s latency).
- **Fix:** Xem Section 4.5.

### ERROR-06 [CRITICAL]: Vision Latency 27-44 Giay
- **Root cause:** CPU-only inference. OpenCV chi chay o cuoi chain (T4) sau khi T1/T2/T3 da fail.
- **Fix:** Khoi dong OpenCV analysis song song ngay tu T0 (khong cho cloud fail). Giam T2 budget 4.5s->3s.

### WARN-01 [MEDIUM]: IMU Sensor Nham Lan Owner vs Robot
- **Trieu chung:** Dien thoai owner nam ngang -> he thong bao robot dang bi nga.
- **Root cause:** Thieu metadata `entity` phan biet nguon IMU (owner phone vs robot hardware).
- **Fix:** Them `entity: owner_device | robot_hardware` vao sensor payload schema.

### WARN-02 [MEDIUM]: GROQ Timeout Lien Tuc (Attempt 1 luon fail)
- **Root cause:** `llama-3.3-70b-versatile` qua lon cho Groq free tier rate limit.
- **Fix:** Dung `llama-3.1-8b-instant` cho routing layer (nhe va nhanh hon), giu 70b cho medical analysis.

### WARN-03 [HIGH]: LanceDB Memory Khong Khoi Tao
- **Hau qua:** Moi hoi thoai khong duoc luu. Hugo khong co long-term memory qua cac session.
- **Fix:** Implement in-memory queue buffer chat cycles, flush vao LanceDB khi ready.

### WARN-04 [MEDIUM]: Duplicate Vision Scan (3 requests song song)
- **Root cause:** Duplicate HTTP requests tu frontend khi reconnect.
- **Fix:** Idempotency key tren endpoint `/agents/empathetic/interact`, deduplicate trong window 5s.

### WARN-05 [LOW]: RuntimeWarning coroutine Never Awaited (Gemini)
- **Fix:** Review va them `await` dung trong Gemini/VertexLLM integration.

---

## 3. DANH GIA SO SANH VOI HINH MAU BAYMAX

### Scorecard Doi chieu

| Tieu chi | Baymax BigHero6 | HK-07 Hien tai | Gap |
|----------|-----------------|----------------|-----|
| Thi giac Vision | Real-time 360 + thermal | IPWebcam 1 camera, latency 27s | CRITICAL |
| Chan doan chu dong | Tu chay scan khong can lenh | Chi khi user ra lenh | CRITICAL |
| Pain Scale 0-10 | Hoi tu dong sau chao | Khong co workflow nay | MISSING |
| Nhan dien cam xuc | Facial expression + voice tone | OpenCV color-based (kem) | PARTIAL |
| Neurotransmitter inference | Tich hop biometric da nguon | Chua co | MISSING |
| So luong phan he | Hang tram ky nang chuyen biet | Fixed 3: Safety/Medical/Empathetic | SEVERE GAP |
| Phan xa thoi gian thuc | < 1 giay | 2-27 giay | CRITICAL |
| Voice proactive | Tu noi khi phat hien bat thuong | Chi phan hoi text khi duoc nhan tin | CRITICAL |
| Multi-sensor fusion | Tich hop toan bo realtime | Sensor phan manh, thieu time-sync | PARTIAL |
| Long-term memory | Nho lich su Owner preferences | LanceDB chua hoat dong | PARTIAL |
| Injury detection | Nano-scan cell-level | Color segmentation false positive | CRITICAL |
| Proactive care workflow | Auto SCAN-DIAGNOSE-ACT | 100% reactive | MISSING |
| Medical knowledge | Tu dong cap nhat tu internet | Kien thuc co dinh trong prompt | MISSING |

### Han che Kien truc Cot loi

**A. Fixed 3-Agent Architecture -- Khong Scalable**
He thong hardcode 3 agent: Safety, Medical, Empathetic. Baymax xu ly vo so boi canh:
chien dau, tam ly, dinh duong, giac ngu, van dong, cap cuu, dong hanh...
Can chuyen sang Dynamic Plugin/Expert System.

**B. Thieu Sensor Fusion Thong nhat**
Sensor doc doc lap, khong co time-sync. Khong the suy ra:
HR tang + IMU bat thuong + facial grimace = stress/pain cong don.

**C. Voice-First Architecture Hoan Toan Thieu**
Baymax chu dong noi khi phat hien van de. HK-07 chi phan hoi text khi duoc nhan tin.
Chua co: continuous wake-word detection, proactive voice, global voice listener.

**D. Thieu Proactive Initiative**
Hugo 100% reactive. Baymax luon chu dong chao hoi, scan, chan doan, hanh dong.

---

## 4. DE XUAT CAI TIEN PRODUCTION

### 4.1. Dynamic Expert Plugin System -- Thay the Fixed 3-Agent

```
[Router Agent V3 -- Semantic Intent + Context Aware]
           |
           v
[Expert Registry -- Dynamic Plugin Loader]
    +-- ExpertPain          (pain scale 0-10, injury assessment)
    +-- ExpertCardiology    (HR, BP, SpO2, ECG, arrhythmia)
    +-- ExpertPsychology    (emotion, stress, mood therapy)
    +-- ExpertEnvironment   (ambient, thermal, obstacle mapping)
    +-- ExpertMobility      (gait analysis, balance, fall detection)
    +-- ExpertNutrition     (hydration reminder, eating habits)
    +-- ExpertSleep         (sleep quality monitoring, fatigue)
    +-- ExpertEmergency     (SOS, cardiac arrest, seizure protocol)
    +-- ExpertCompanion     (small talk, encouragement, humor)
    +-- ExpertNeuro         (neurotransmitter state inference)
    +-- ExpertTherapy       (breathing exercises, warm compress)
    +-- ... (them Expert moi chi can them 1 file -- khong gioi han)
```

Interface `IExpert`:
- `can_handle(context) -> float`  (confidence 0.0-1.0)
- `execute(state) -> ExpertOutput`
- `requires_sensors: List[str]`
- `priority: int`

### 4.2. Fix ERROR-01: LLM Tool Response Null

```python
# agents/agent_orchestrator_v2.py -- them 2 ham nay

async def _synthesize_with_fallback(self, tool_results, state):
    try:
        response = await asyncio.wait_for(
            self._llm_synthesize(tool_results, state), timeout=8.0
        )
        if response and response.strip():
            return response
    except Exception as e:
        log.warning('[ORCHESTRATOR_V2] LLM synthesis failed: %s. Falling back to local aggregate.', e)

    # Fallback: aggregate thu cong tu tool results
    return self._local_aggregate_tool_results(tool_results)

def _local_aggregate_tool_results(self, results):
    parts = []
    for r in results:
        if not r or not isinstance(r, dict):
            continue
        if r.get('sensor_summary'):
            parts.append(r['sensor_summary'])
        elif r.get('response'):
            parts.append(r['response'])
        elif r.get('diagnosis'):
            parts.append(r['diagnosis'])
    if parts:
        return ' '.join(parts)
    return '[SYSTEM] Du lieu cam bien da duoc xu ly. Vui long thu lai.'
```

### 4.3. Fix ERROR-02: IPWebcam IP Persistence

Them vao `.env`:
```
IPWEBCAM_STATIC_IP=192.168.x.x
IPWEBCAM_PORT=8080
IPWEBCAM_CACHE_TTL_MINUTES=30
```

Tao `utils/ip_cache.py`:
```python
import json, time, os

CACHE_FILE = '/tmp/hk07_ipwebcam_cache.json'

def get_cached_ip():
    # Doc IP da luu tu cache neu con han
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        if time.time() - data['ts'] < data['ttl_s']:
            return data['ip']
    except Exception:
        pass
    return None

def save_ip_cache(ip, ttl_minutes=30):
    with open(CACHE_FILE, 'w') as f:
        json.dump({'ip': ip, 'ts': time.time(), 'ttl_s': ttl_minutes * 60}, f)
```

### 4.4. Fix ERROR-03: OpenCV False Positive Injury

```python
# utils/vision_pipeline.py

class InjuryDetector:
    def __init__(self):
        self._frame_buffer = []   # Rolling buffer 5 frames
        self._min_confirm_frames = 3
        self._confidence_gate = 0.75

    def analyze_frame(self, frame, ambient_lux=None, user_reported_pain=0):
        if ambient_lux and ambient_lux > 0:
            frame = self._apply_light_correction(frame, ambient_lux)

        raw_detections = self._detect_red_regions(frame)
        self._frame_buffer.append(raw_detections)
        if len(self._frame_buffer) > 5:
            self._frame_buffer.pop(0)

        if len(self._frame_buffer) < self._min_confirm_frames:
            return []   # Chua du frame de xac nhan

        confirmed = []
        for det in raw_detections:
            appearances = sum(
                1 for fb in self._frame_buffer
                if any(self._is_same_region(det, d) for d in fb)
            )
            if appearances >= self._min_confirm_frames and det.confidence >= self._confidence_gate:
                if user_reported_pain == 0:
                    det.severity = 'UNCERTAIN'  # Khong CRITICAL khi user khong bao dau
                confirmed.append(det)
        return confirmed
```

### 4.5. Huong dan Fix Ollama trong WSL

**Buoc 1** -- Kiem tra Ollama dang chay:
```bash
curl -s http://localhost:11434/api/tags
```

**Buoc 2** -- Khoi dong va pull model:
```bash
ollama serve &
sleep 3
ollama pull moondream      # Vision model ~1.7GB
ollama pull qwen2.5:3b    # Text routing model nhe hon llama-70b
```

**Buoc 3** -- docker-compose.yml (expose port):
```yaml
services:
  ollama:
    image: ollama/ollama
    ports:
      - '11434:11434'
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_KEEP_ALIVE=5m
```

**Buoc 4** -- Cap nhat `.env` cua hk07-agent:
```
OLLAMA_HOST=http://172.x.x.x:11434
OLLAMA_VISION_MODEL=moondream
OLLAMA_TEXT_MODEL=qwen2.5:3b
```

**Buoc 5** -- Tang probe timeout trong `llm_client.py`:
```python
OLLAMA_PROBE_TIMEOUT = 8.0     # Tang tu 3.0s -- CPU-only cham hon
OLLAMA_INFERENCE_TIMEOUT = 60.0
```

### 4.6. Fix ERROR-04: Per-Provider Circuit Breaker

```python
# services/llm_client.py -- thay the LLMClientCircuitBreaker singleton

class ProviderCircuitBreaker:
    def __init__(self, name, threshold=3, base_cooldown_s=300):
        self.name = name
        self.state = 'CLOSED'   # CLOSED | OPEN | HALF_OPEN
        self.fail_count = 0
        self.threshold = threshold
        self.base_cooldown_s = base_cooldown_s
        self.reset_time = 0.0

    def record_success(self):
        self.fail_count = 0
        self.state = 'CLOSED'

    def record_failure(self, is_rate_limit=False):
        self.fail_count += 1
        cooldown = self.base_cooldown_s * 2 if is_rate_limit else self.base_cooldown_s
        if self.fail_count >= self.threshold:
            self.state = 'OPEN'
            self.reset_time = time.monotonic() + cooldown
            log.error('[CB] %s tripped OPEN for %.0fs', self.name, cooldown)

    def is_available(self):
        if self.state == 'OPEN':
            if time.monotonic() >= self.reset_time:
                self.state = 'HALF_OPEN'
                self.fail_count = 0
            else:
                return False
        return True

# Registry per-provider -- KHONG dung 1 global CB nua
_provider_cb = {
    'GROQ':   ProviderCircuitBreaker('GROQ',   threshold=5, base_cooldown_s=120),
    'OPENAI': ProviderCircuitBreaker('OPENAI', threshold=3, base_cooldown_s=300),
    'GEMINI': ProviderCircuitBreaker('GEMINI', threshold=3, base_cooldown_s=600),
    'OLLAMA': ProviderCircuitBreaker('OLLAMA', threshold=5, base_cooldown_s=60),
}
```

### 4.7. Proactive Baymax Care Protocol -- State Machine

File moi: `agents/proactive_care_engine.py`

```
STATES:
  IDLE       -> Neu va theo doi lien tuc sensor + vision
  GREETING   -> 'Xin chao, toi la Hugo. Toi o day voi ban...'
  ASSESSMENT -> 'Tu 1 den 10, ban danh gia con dau hien tai the nao?'
  SCANNING   -> [Song song: vision scan + sensor analysis + emotion detection]
  DIAGNOSIS  -> [Tong hop ket qua tu tat ca nguon]
  ACTING     -> [De xuat: om, lam am, loi khuyen, goi cap cuu...]
  MONITORING -> [Theo doi sau hanh dong, check-in moi 30 giay]

AUTO-TRIGGERS (Hugo chu dong -- khong can user input):
  - HR > 120 hoac < 45 BPM
  - SpO2 < 92%
  - Robot IMU: fall_detected = True  (KHONG dung phone IMU)
  - vision.facial_pain_score > 0.7
  - vision.emotional_state in [sad, fearful, stressed, pain]
  - Khong hoat dong > 120 phut (pedometer khong thay doi)
  - Micro VAD: tieng khoc, ren, goi ten 'Hugo'
  - battery_temp > 45°C
  - Khong tuong tac > 4 gio (proactive check-in)
```

### 4.8. Xoa LiDAR Mock 12ms -- Do Latency That

```python
# XOA: lidar_latency = 12  (hardcoded mock -- nghiem cam)

# THAY BANG:
async def measure_device_latency(endpoint):
    start = time.monotonic()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2.0)) as session:
            async with session.get(endpoint) as resp:
                if resp.status < 500:
                    return round((time.monotonic() - start) * 1000, 1)
    except Exception:
        pass
    return None   # Frontend hien thi '--' thay vi '12ms'
```

### 4.9. IMU Entity Tagging -- Phan biet Owner vs Robot

Schema sensor payload tu phone can them field `entity`:
```json
{
  "entity": "owner_device",
  "sensor_type": "imu",
  "data": {"accel_x": 0.12, "accel_y": 9.81, "orientation_pitch": 0},
  "source": "phone_hotspot_sensorlog"
}
```

Logic trong `safety_agent.py`:
```python
entity = sensor_payload.get('entity', 'unknown')
if entity == 'robot_hardware':
    # Cam bien that cua robot -- dung cho fall detection
    _check_robot_balance_and_fall(sensor_payload['data'])
elif entity == 'owner_device':
    # Dien thoai cua owner -- danh gia CHUYEN DONG cua owner
    # TUYET DOI KHONG dung orientation=0/180 de bao 'robot nga'
    _assess_owner_physical_activity(sensor_payload['data'])
```

### 4.10. Micro Audio VAD + Speech-to-Text

Kien truc:
```
Phone Mic Audio Stream
       |
  [VAD -- silero-vad CPU-only, 10ms latency]
       | silence -> bo qua
       | voice detected
       v
  [faster-whisper STT -- CPU optimized]
  Model: small (RAM 256GB -- dung duoc)
  Latency: 0.5-2s tren CPU
       | confidence < 0.7 -> bo qua
       v
  [Language Detection vi/en]
       |
  [Agent Command Processor]
       |
  [Response TTS Voice -> Frontend]
```

Cai dat WSL:
```bash
pip install faster-whisper
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

---

## 5. LO TRINH TRIEN KHAI

### Sprint 1 -- Hotfix Critical (~13h tong the, uu tien ngay lap tuc)

| # | Task | File | Uoc tinh |
|---|------|------|----------|
| 1 | Fix Per-Provider Circuit Breaker | services/llm_client.py | 2h |
| 2 | Fix Tool Response Null -- Local Aggregate Fallback | agents/agent_orchestrator_v2.py | 2h |
| 3 | IPWEBCAM_STATIC_IP env + IP persistence cache | .env + utils/ip_cache.py | 1h |
| 4 | IMU entity tagging (owner_device vs robot_hardware) | agents/safety_agent.py | 1h |
| 5 | Xoa hardcode LiDAR 12ms + do latency that | grep all agents/ + fix | 1h |
| 6 | OpenCV multi-frame confirmation + confidence gate | utils/vision_pipeline.py | 3h |
| 7 | Fix RuntimeWarning coroutine never awaited | services/llm_client.py | 1h |
| 8 | Idempotency key tren /agents/empathetic/interact | main.py | 1h |

### Sprint 2 -- Architecture Upgrade (Trong 1 tuan)

| # | Task | File | Uoc tinh |
|---|------|------|----------|
| 9 | IExpert interface + Expert Registry | plugins/expert_base.py + expert_registry.py | 4h |
| 10 | ExpertPain, ExpertCardiology, ExpertPsychology | plugins/experts/ | 2 ngay |
| 11 | Fix Ollama WSL (pull moondream + qwen2.5:3b) | Docker Compose + .env | 3h |
| 12 | LanceDB in-memory buffer queue | memory/lance_memory.py | 4h |
| 13 | Router V3 -- semantic routing sang Expert Registry | agents/router_agent_v3.py | 1 ngay |
| 14 | LLM downgrade GROQ: llama-70b -> llama-8b-instant | services/llm_client.py | 30m |

### Sprint 3 -- Proactive Intelligence (Trong 1 thang)

| # | Task | File | Uoc tinh |
|---|------|------|----------|
| 15 | Proactive Care Engine State Machine | agents/proactive_care_engine.py | 3 ngay |
| 16 | Micro Audio VAD + faster-whisper STT | services/audio_pipeline.py | 2 ngay |
| 17 | Sensor Fusion Time-Synchronizer | services/sensor_fusion_buffer.py | 2 ngay |
| 18 | Neurotransmitter state inference | plugins/experts/neuro_expert.py | 3 ngay |
| 19 | Medical Knowledge self-learning crawler | services/knowledge_ingestion.py | 2 ngay |
| 20 | Global Voice Service (bat ky route nao) | frontend GlobalVoiceWidget.vue | 1 ngay |
| 21 | OpenCV parallel pipeline chay song song T2 cloud | utils/vision_pipeline.py | 1 ngay |

---

## TONG KET DANH GIA HE THONG

| Hang muc | Trang thai hien tai | Muc tieu sau Sprint 1 |
|----------|--------------------|-----------------------|
| Tinh on dinh Agent Core | PARTIAL -- LLM timeout thuong xuyen | STABLE -- per-provider CB |
| Do chinh xac Vision | FAIL -- false positive, 27s | PARTIAL -- multi-frame gate |
| Tinh chu dong Proactive | FAIL -- 0% Baymax | FAIL -- can Sprint 3 |
| Sensor Integration | PARTIAL -- entity confusion | GOOD -- entity tagging fix |
| Voice System | PARTIAL -- chi /companion | PARTIAL -- global Sprint 2 |
| Memory Continuity | FAIL -- LanceDB chua chay | PARTIAL -- buffer queue |
| Kha nang mo rong | FAIL -- Fixed 3-agent | GOOD -- Expert System Sprint 2 |
| LLM Reliability | PARTIAL -- global CB sai logic | GOOD -- per-provider CB |
| **Production Readiness** | **35 / 100** | **~60 / 100 sau Sprint 1** |

**Ket luan cuoi:**
HK-07 co nen tang kien truc tot (Orchestrator V2, Blackboard, Tool Calling, Tiered LLM) nhung dang gap
6 loi CRITICAL can xu ly ngay. Loi nghiem trong nhat la Global Circuit Breaker khoa toan he thong khi
Gemini 429. Sprint 1 se giai quyet trong khoang 1 ngay lam viec. Sprint 2-3 nang cap HK-07 len muc
Baymax-inspired production robot companion that su (muc tieu 60-70% benchmark Baymax, CPU only, no GPU).

---
*Tai lieu: docs/bao_cao_phan_tich_loi_hugo_agent.md*
*Cap nhat lan cuoi: 2026-07-08 19:47 ICT*