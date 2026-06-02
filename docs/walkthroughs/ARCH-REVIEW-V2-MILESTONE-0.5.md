Dưới đây là bản Lộ trình Kiến trúc (Roadmap) đã được hợp nhất và cập nhật mới nhất. Vì lõi Cognitive Orchestrator và Multi-Provider LLM Router của Agent đã được giải quyết xong, chúng ta sẽ lược bỏ phần Backend Agent ra khỏi lộ trình này để tập trung toàn lực vào **Mật độ Giao diện (UI/UX Density)** và các **Tính năng Đa phương thức (Multimodal)** cốt lõi của HK-07.

Bạn có thể lưu nội dung này thành file `ARCH-REVIEW-V3-CONSOLIDATED.md` để làm kim chỉ nam cho các phiên làm việc tiếp theo với Devin.

---

# 📋 **BẢNG ĐẶC TẢ LỘ TRÌNH KIẾN TRÚC HK-07 (CONSOLIDATED ROADMAP V3)**

**Trạng thái hệ thống:** Lõi Agent Orchestrator (Multi-Provider) đã hoàn thiện.
**Mục tiêu hiện tại:** Tối ưu hóa UI/UX Density đạt 85% và phát triển năng lực tự chủ Edge AI.

---

## 📌 **MILESTONE 1: GIAO DIỆN CHỈ HUY SINH TỒN & PHÂN TÍCH CHUYÊN SÂU (UI/UX DENSITY)**

Tập trung lấp đầy các "góc chết" trên Frontend (Vue 3), biến các trang hiện tại thành bảng điều khiển công nghiệp thực thụ, không còn widget rỗng.

### 1.1 Tái cấu trúc trang Safety Control (Command & Control Center)

Trang SafetyView hiện tại đang thiếu các công cụ kiểm soát an toàn vật lý và phân tầng hệ thống.

* **Widget E-STOP (Ngắt khẩn cấp):** Nút kích hoạt gửi tín hiệu ngắt toàn bộ lệnh MQTT chuyển động, kèm theo cảnh báo WebSocket thời gian thực.


* **Widget Subsumption Monitor:** Hiển thị trực quan 3 phân tầng (Tier 0: Safety, Tier 1: Medical, Tier 2: Empathetic). Cung cấp thông tin Layer nào đang chiếm quyền điều khiển và độ trễ phản hồi (SLA < 5ms).


* **Widget Hardware Actuation:** Hiển thị trạng thái khóa/mở (lock/unlock) của các cánh tay cơ học (Left/Right Arm) và trạng thái đóng/mở của Gripper. Cảnh báo khi áp suất khí nén (Pneumatic) xuống thấp.



### 1.2 Chuyên nghiệp hóa trang Health History Metrics

Xử lý các widget đang bị bỏ trống trên trang lịch sử sinh hiệu để tăng mật độ thông tin y tế.

* **Widget Trend Analysis (Phân tích đa biến):** Sử dụng đồ thị Scatter Plot (Chart.js/D3.js) để đối chiếu tương quan giữa Nhịp tim (HR) và Huyết áp (BP). Tính toán hệ số Pearson để xác định xu hướng sức khỏe (Tích cực/Tiêu cực).


* **Widget Predictive AI Insights (Dự báo):** Truy xuất dữ liệu chuỗi thời gian từ bộ nhớ vector LanceDB. Áp dụng hồi quy tuyến tính để dự báo sinh hiệu trong 4 giờ tới và đưa ra cảnh báo sớm về các nguy cơ tiềm ẩn (Ví dụ: Dự báo SpO2 giảm).



---

## 📌 **MILESTONE 2: EDGE AI & OFFLINE COGNITION (TỰ CHỦ MẤT MẠNG)**

*Đảm bảo HK-07 không bị "chết não" khi hoạt động ở môi trường không có Internet.*

* **Tích hợp Local LLM:** Triển khai các mô hình AI lượng tử hóa (ONNX/GGUF) như LLaMA2-7B hoặc Phi-3-mini chạy trực tiếp trên RAM nội bộ.


* **Offline Fallback Routing:** Tích hợp bộ định tuyến chuyển luồng khẩn cấp. Nếu các API Cloud (Gemini, Groq) mất kết nối, hệ thống tự động fallback về Local LLM để xử lý sinh hiệu y tế cơ bản mà độ trễ không vượt quá 2 giây.


* **Pruning Context:** Khi chạy offline, tự động lược bỏ lịch sử hội thoại không cần thiết, chỉ giữ lại cây quyết định y tế lâm sàng để tiết kiệm RAM.



---

## 📌 **MILESTONE 3: THỊ GIÁC ĐA PHƯƠNG THỨC (VISION INTELLIGENCE)**

*Cung cấp "Đôi mắt" cho Baymax để chẩn đoán thực tế thay vì chỉ dựa vào cảm biến.*

* **Camera Feed Handler:** Bổ sung UI trên Frontend cho phép stream hình ảnh hoặc tải ảnh tình trạng bệnh nhân (vết thương hở, biểu cảm, sắc tố da).


* **Multimodal Diagnosis:** Xây dựng endpoint REST để tiếp nhận hình ảnh (Base64) kèm sinh hiệu thời gian thực.


* **Vision API Integration:** Sử dụng Gemini 1.5 Vision thông qua Tool Calling để trả về chẩn đoán bằng văn bản, điểm tin cậy (confidence score) và khuyến nghị sơ cứu.



---

## 📌 **MILESTONE 4: ĐÁNH THỨC BẰNG GIỌNG NÓI & RAG Y KHOA SÂU**

*Nâng cấp Trải nghiệm Người dùng (UX) và Độ chính xác Y khoa.*

* **Wake-Word Spotting (Edge Audio):** Loại bỏ việc bấm nút Micro thủ công. Triển khai mô hình TinyML (hoặc Whisper-tiny) chạy ngầm để liên tục lắng nghe từ khóa "Hugo ơi" hoặc phát hiện tiếng kêu cứu/khóc, từ đó kích hoạt đếm ngược SOS.


* **Enriched Medical Knowledge Base:** Nạp các phác đồ điều trị chuẩn (AHA Cardiac Guidelines, WHO protocols) vào LanceDB. Cấu hình Medical Agent thực hiện tìm kiếm lai (Hybrid search: BM25 + Semantic) để truy xuất dữ liệu y khoa chính xác dưới 100ms trước khi đưa ra lời khuyên.



---

**[CHỈ THỊ CHO DEVELOPER / AI AGENT]**
Ưu tiên thực thi **MILESTONE 1** ngay lập tức. Hãy quét thư mục `source/frontend/` và bắt đầu triển khai các Component Vue.js cho `SafetyView.vue` và `HealthHistoryView.vue` tuân thủ nguyên tắc thiết kế màu sắc Cyber-Cinematic (Nền đen, phát sáng Cyan/Green). Tuyệt đối không để lại bất kỳ dữ liệu giả (mock data) nào; mọi Widget phải được binding với WebSocket hoặc API thực tế.


# 📋 **KIẾN TRÚC LẠI ROADMAP: MILESTONE 0.5 — SYSTEM RESILIENCE & UI/UX DENSITY**
**Ngày phân tích:** 2 Tháng 6, 2026 | **Phiên bản:** ARCH-REVIEW-V2  
**Mục tiêu:** Giải quyết 3 điểm mù kiến trúc trước khi scale production

---

## **TỔNG QUAN TÌNH HÌNH HIỆN TẠI**

### Hệ thống Frontend — 70% hoàn thiện, thiếu UI density

```
✅ HIỆN CÓ:
├─ Dashboard.vue: ECG stream, Vitals, Subsumption Status, Agent Events
├─ HealthHistory.vue: HR Chart, SpO2/BP Chart, Alert Distribution  
├─ SafetyView.vue: LiDAR Radar, Latency Meter, Alert History
├─ AgentsView.vue: Agent Status Panels, Event Stream
├─ CompanionView.vue: Chat interface
└─ Emergency, Profile, Login screens

❌ THIẾU / RỖNG:
├─ SafetyView: Không có E-Stop button (Emergency Stop)
├─ SafetyView: Không có Hardware Actuation widget (arm lock/unlock status)
├─ HealthHistory: Thiếu "Trend Analysis" widget (HR vs BP comparison)
├─ HealthHistory: Thiếu "Predictive AI Insights" widget (LanceDB alert prediction)
└─ No centralized LLM Router → cada agent quản API độc lập
```

### Hệ thống Backend LLM — Decentralized, nguy hiểm

```
CURRENT STATE:
┌─────────────────────────────────────────────────┐
│ medical_agent.py                                │
│  └─ Groq (primary) → OpenRouter (fallback)      │
├─────────────────────────────────────────────────┤
│ empathetic_agent.py                             │
│  └─ Cohere (primary) → Gemini (fallback)        │
├─────────────────────────────────────────────────┤
│ router_agent.py                                 │
│  └─ HuggingFace (disabled in WSL2) → Groq       │
└─────────────────────────────────────────────────┘

RỦI RO:
⚠️ Mỗi agent tự quản API key → khó theo dõi quota
⚠️ Không có cost optimization → dùng provider mắc tiền trước
⚠️ Rate limit 429 không được handle strategy (fallback ngồi chờ)
⚠️ Groq & Gemini quota limited → khi hết sẽ crash
```

---

## **MILESTONE 0.5: SYSTEM RESILIENCE & UI/UX DENSITY**

### 🎯 **MỤC TIÊU CỤ THỂ**

**3 Hạng mục cải thiện chiến lược:**
1. ✅ **Multi-Provider LLM Router** — Chống sập quota, tối ưu chi phí
2. ✅ **Redesign Safety Control Coordination** — E-Stop + Subsumption Monitor + Hardware Actuation
3. ✅ **Professional HealthHistory Metrics** — Trend Analysis + Predictive AI Insights

**Mục tiêu hệ thống sau M0.5:**
- ✅ **99.5% uptime** (chỉ fail nếu ALL providers đều down)
- ✅ **Cost-aware routing** (ưu tiên free tier, tự động chuyển paid)
- ✅ **UI density 85%** (96% pixel utilization, min white space)
- ✅ **Zero phantom widgets** (mọi component đều có real data)

---

---

## **YÊU CẦU 1: MULTI-PROVIDER LLM ROUTER (CHỐNG QUOTA COLLAPSE)**

### 1.1 **Vấn đề hiện tại**

```
Current flow:
MedicalAgent.process() 
  → _call_llm_with_fallback()
    → Try Groq (rate limited 30,000 req/month = ~1000/day)
    → Fallback OpenRouter 
    → Fallback: rule-based (lose accuracy)

KỊCH BẢN XẤU:
- 12h sáng: Groq quota hết vì traffic cao
- 12h-18h: System chạy chậm (OpenRouter fallback, cost cao)
- 18h-24h: User báo cáo delay & sai chẩn đoán
```

### 1.2 **Giải pháp: Centralized Multi-Tier Router**

#### Architecture mới:

```python
# NEW FILE: services/llm_router.py

class LLMRouter:
    """
    Tier-based LLM routing system.
    Automatically selects best provider based on:
    - Task complexity (lightweight vs heavy reasoning)
    - Quota availability (track usage per provider)
    - Response latency (prefer fast APIs)
    - Cost per token (routing to minimize expense)
    """
    
    ROUTING_MATRIX = {
        "EMPATHETIC_CHAT": [
            {"provider": "HuggingFace", "model": "Qwen/Qwen2-7B-Instruct", "cost": 0, "priority": 1},  # Free
            {"provider": "OpenRouter", "model": "qwen/qwen-2-7b-instruct", "cost": "$0.07/1M", "priority": 2},  # Cheap
            {"provider": "Cohere", "model": "command-r-08-2024", "cost": "$3/1M", "priority": 3},  # Expensive
            {"provider": "LOCAL_RULE", "model": None, "cost": 0, "priority": 4},  # Fallback
        ],
        "MEDICAL_ANALYSIS": [
            {"provider": "Gemini", "model": "gemini-2.0-flash", "cost": "1M free/month", "priority": 1},  # High quota
            {"provider": "Groq", "model": "llama-3.1-8b", "cost": "limited", "priority": 2},
            {"provider": "OpenRouter", "model": "mistral/open-mistral-nemo", "cost": "$0.14/1M", "priority": 3},
            {"provider": "LOCAL_RULE", "model": None, "cost": 0, "priority": 4},
        ],
        "ROUTE_CLASSIFICATION": [
            {"provider": "Groq", "model": "llama-3.1-8b-instant", "cost": "limited", "priority": 1},  # Fast
            {"provider": "HuggingFace", "model": "Qwen/Qwen2-1.5B", "cost": 0, "priority": 2},  # Free ultra-light
            {"provider": "LOCAL_RULE", "model": None, "cost": 0, "priority": 3},
        ],
    }
    
    async def route_and_execute(self, task_type: str, prompt: str, context: dict) -> tuple[str, str]:
        """
        Returns (response, provider_used)
        
        Algorithm:
        1. Lookup task_type in ROUTING_MATRIX
        2. Iterate through priority list
        3. Check quota status (track via Redis)
        4. Call provider with exponential backoff (429/503)
        5. If fail, move to next provider
        6. Log decision for audit trail
        """
        
        # 1. Get provider list for this task
        providers = self.ROUTING_MATRIX.get(task_type, [])
        
        # 2. Try each provider in priority order
        for provider_cfg in providers:
            provider = provider_cfg["provider"]
            
            # Check quota (stored in Redis)
            quota_available = await self._check_quota(provider, task_type)
            if not quota_available:
                log.warning(f"[LLM_ROUTER] {provider} quota exhausted for {task_type}, skipping")
                continue
            
            # Try to call provider
            try:
                response, success = await self._call_provider(
                    provider=provider,
                    model=provider_cfg["model"],
                    prompt=prompt,
                    context=context
                )
                if success:
                    await self._track_usage(provider, task_type, len(prompt))
                    return response, provider
            except Exception as e:
                log.error(f"[LLM_ROUTER] {provider} failed: {e}")
                continue
        
        # 3. All cloud providers failed → use local rule-based
        log.warning("[LLM_ROUTER] All cloud providers exhausted. Using local fallback.")
        fallback_response = self._generate_local_fallback(task_type, context)
        return fallback_response, "LOCAL_RULE"
    
    async def _check_quota(self, provider: str, task_type: str) -> bool:
        """Check Redis quota tracking for this provider/task combo"""
        key = f"llm_quota:{provider}:{task_type}:daily"
        usage = await redis.get(key) or 0
        max_daily = self.QUOTA_LIMITS[provider][task_type]  # Defined elsewhere
        return usage < max_daily
    
    async def _call_provider(self, provider: str, model: str, prompt: str, context: dict) -> tuple[str, bool]:
        """Invoke specific provider with retry logic"""
        # Implementation varies per provider
        # All follow exponential backoff pattern for 429/503
        pass
```

#### Quota tracking (Redis backend):

```
Structure:
- llm_quota:groq:medical_analysis:daily → 5000 (updated hourly)
- llm_quota:gemini:medical_analysis:daily → 1000000 (high free tier)
- llm_quota:huggingface:empathetic_chat:daily → 1000 (rate limited)
- llm_provider:health_check:gemini → last_checked: timestamp

Nếu quota hết:
1. Emit event: hk07:llm-quota-alert
2. Frontend shows: "🟡 Using cost-optimized AI (may be slower)"
3. Auto-rotate to cheaper/free provider
```

#### Integration với existing agents:

```python
# agents/medical_agent.py — NEW
from services.llm_router import LLMRouter

router = LLMRouter()

async def _call_llm_with_fallback(self, vitals: dict) -> dict:
    """UPDATED: Use router instead of direct API call"""
    
    prompt = self._build_prompt(vitals)
    context = {
        "vitals": vitals,
        "baseline": await self.memory.recall_medical_baseline(),
        "alert_level": self._assess_alert_level(vitals)
    }
    
    # Router handles all the complexity
    response, provider_used = await router.route_and_execute(
        task_type="MEDICAL_ANALYSIS",
        prompt=prompt,
        context=context
    )
    
    # Log for audit (update existing log_agent_decision)
    await log_agent_decision(
        llm_provider=provider_used,  # ← NOW includes router decision
        ...
    )
    
    return safe_extract_json(response)
```

### 1.3 **Free Tier Strategy**

| Provider | Free Quota | Cost/1M Tokens | Use Case | Priority |
|----------|------------|-----------------|----------|----------|
| **Gemini** | 1M tokens/month | $0 (free tier) | Medical analysis (1-2k context) | 1️⃣ USE FIRST |
| **HuggingFace Inference** | 1000 req/month | $0 | Empathetic chat (lightweight) | 1️⃣ USE FIRST |
| **Groq** | 30k req/month | $0 (limited) | Router classification (fast) | 2️⃣ SECOND |
| **OpenRouter Free** | 100 req/month | $0 | Fallback only | 3️⃣ THIRD |

### 1.4 **Spec chi tiết**

```
FILE: services/llm_router.py
├─ LLMRouter class
│  ├─ route_and_execute(task_type, prompt, context) → (response, provider)
│  ├─ _check_quota(provider, task_type) → bool
│  ├─ _track_usage(provider, task_type, tokens) → void
│  ├─ _call_provider(provider, model, prompt) → (response, success)
│  └─ _generate_local_fallback(task_type, context) → response
├─ QuotaManager class (Redis backend)
│  └─ track_daily_usage() 
└─ ProviderConfig dataclass
   └─ ROUTING_MATRIX, QUOTA_LIMITS

CHANGES to existing agents:
├─ agents/medical_agent.py
│  └─ Replace _call_groq/_call_openrouter with router.route_and_execute()
├─ agents/empathetic_agent.py
│  └─ Replace _call_cohere/_call_gemini with router.route_and_execute()
└─ agents/router_agent.py
   └─ Replace _call_huggingface/_call_groq with router.route_and_execute()

Dependencies to add:
├─ redis (already in docker-compose)
└─ No new PyPI packages needed
```

---

---

## **YÊU CẦU 2: REDESIGN SAFETY CONTROL COORDINATION PAGE**

### 2.1 **Current State Analysis**

```
Location: src/views/SafetyView.vue
Current components:
├─ LiDAR Radar (360° display, working)
├─ Subsumption Latency Meter (< 5ms SLA check, working)
└─ Alert History (log display, working)

THIẾU:
❌ No E-Stop / Emergency Stop button
❌ No layer control (chọn layer nào active)
❌ No hardware actuation status
❌ No quick-access inhibit toggle
```

### 2.2 **Proposed Design: "Command & Control Center"**

#### Widget 1: **E-STOP BUTTON (Emergency Stop)**

```vue
<!-- SafetyView.vue — NEW Widget -->
<div class="estop-widget terminal-card corner-reticle">
  <div class="terminal-card-header">[ EMERGENCY_STOP ]</div>
  <button 
    class="estop-button" 
    :class="{ 'armed': !emergencyTriggered, 'triggered': emergencyTriggered }"
    @click="triggerEmergencyStop"
  >
    <span v-if="!emergencyTriggered" class="button-text">🔴 E-STOP</span>
    <span v-else class="button-text">⚠️ E-STOP ACTIVE</span>
  </button>
  
  <div class="estop-info mono text-dim">
    <div>ACTION: Disconnect all MQTT motion commands</div>
    <div>BROADCAST: hk07/control/emergency/trigger</div>
    <div>TIMEOUT: Manual reset required</div>
  </div>
  
  <div v-if="emergencyTriggered" class="estop-controls">
    <button class="cmd-btn success" @click="resetEmergencyStop">
      RESET_E-STOP
    </button>
  </div>
</div>

<style>
.estop-button {
  width: 100%;
  padding: 20px;
  font-size: 24px;
  font-weight: bold;
  border: 3px solid #00FF66;
  background: rgba(0, 0, 0, 0.8);
  color: #00FF66;
  cursor: pointer;
  transition: all 0.2s;
}

.estop-button.triggered {
  border-color: #FF0000;
  background: rgba(255, 0, 0, 0.2);
  color: #FF0000;
  animation: pulse-red 0.5s infinite;
}
</style>
```

**Backend support:**
```java
// NEW in RobotCommandController.java
@PostMapping("/emergency-stop")
@Operation(summary = "Trigger E-STOP — disables all motion & outputs")
public ResponseEntity<?> emergencyStop(@AuthenticationPrincipal UserEntity user) {
    // 1. Set SystemState to EMERGENCY_STOP
    systemStateRef.set(SystemState.EMERGENCY_STOP);
    
    // 2. Publish MQTT inhibit signal (highest priority)
    mqttTemplate.convertAndSend("hk07/control/emergency/trigger", 
        json({"timestamp": now(), "triggered_by": user.getId()}));
    
    // 3. Broadcast WebSocket alert
    messagingTemplate.convertAndSend("/topic/emergency", 
        "EMERGENCY_STOP triggered by " + user.getEmail());
    
    // 4. Log audit
    auditService.log("EMERGENCY_STOP", user.getId(), "manual");
    
    return ok("E-STOP ACTIVATED");
}
```

---

#### Widget 2: **SUBSUMPTION HIERARCHY MONITOR**

```vue
<!-- SafetyView.vue — NEW Widget -->
<div class="subsumption-monitor terminal-card">
  <div class="terminal-card-header">[ SUBSUMPTION_HIERARCHY ]</div>
  
  <div class="hierarchy-display">
    <!-- Tier 0: Safety -->
    <div :class="['tier-card', { 'active': activeLayer === 0 }]">
      <div class="tier-label">🛡️ TIER 0: SAFETY OVERRIDE</div>
      <div class="tier-status" :class="statusClass('safety')">
        {{ safetyStatus }}
      </div>
      <div class="tier-info mono text-dim">
        <span>Priority: HIGHEST (Lấn át tất cả)</span><br/>
        <span>Condition: {{ safetyCondition }}</span><br/>
        <span>Latency: {{ safetyLatency }}ms</span>
      </div>
      <button 
        v-if="authStore.isOwner" 
        class="cmd-btn"
        @click="setActiveLayer(0)"
      >
        FORCE_SAFETY_HOLD
      </button>
    </div>
    
    <!-- Tier 1: Medical -->
    <div :class="['tier-card', { 'active': activeLayer === 1, 'inhibited': isMedicalInhibited }]">
      <div class="tier-label">🏥 TIER 1: MEDICAL_ANALYSIS</div>
      <div class="tier-status" :class="statusClass('medical')">
        {{ medicalStatus }}
      </div>
      <div class="tier-info mono text-dim">
        <span>Priority: MEDIUM (Lấn át Tier 2)</span><br/>
        <span>Last Alert: {{ lastMedicalAlert }}</span><br/>
        <span>Latency: {{ medicalLatency }}ms</span>
      </div>
    </div>
    
    <!-- Tier 2: Empathetic -->
    <div :class="['tier-card', { 'active': activeLayer === 2, 'inhibited': isEmpatheticInhibited }]">
      <div class="tier-label">💬 TIER 2: EMPATHETIC_CHAT</div>
      <div class="tier-status" :class="statusClass('empathetic')">
        {{ empatheticStatus }}
      </div>
      <div class="tier-info mono text-dim">
        <span>Priority: LOW (Bị lấn át)</span><br/>
        <span>Last Message: {{ lastEmpatheticMsg }}</span><br/>
        <span>Latency: {{ empatheticLatency }}ms</span>
      </div>
    </div>
  </div>
  
  <div class="hierarchy-rules mono text-dim">
    <span>📋 RULES: Safety blocks Medical/Empathy | Medical blocks Empathy</span>
  </div>
</div>

<style>
.hierarchy-display {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.tier-card {
  border: 2px solid rgba(0, 255, 102, 0.3);
  padding: 12px;
  background: rgba(0, 0, 0, 0.4);
}

.tier-card.active {
  border-color: #00FF66;
  box-shadow: inset 0 0 10px rgba(0, 255, 102, 0.2);
}

.tier-card.inhibited {
  opacity: 0.5;
  border-color: #FF6600;
}
</style>
```

**Backend support:**
```java
// EXISTING RobotCommandService.java - enhance
public class RobotCommandService {
    
    private Map<String, Long> lastTierLatency = new ConcurrentHashMap<>();
    
    public void recordTierLatency(String tier, long latencyMs) {
        lastTierLatency.put(tier, latencyMs);
        // Broadcast to WebSocket
        messagingTemplate.convertAndSend("/topic/tier-latency", 
            Map.of(tier, latencyMs));
    }
    
    public Map<String, Object> getTierStatus() {
        return Map.of(
            "safety", Map.of(
                "status", currentState.isSafetyHold() ? "INHIBIT_ACTIVE" : "ARMED",
                "latency_ms", lastTierLatency.getOrDefault("SAFETY", 0L),
                "condition", lastSafetyCondition
            ),
            "medical", Map.of(...),
            "empathetic", Map.of(...)
        );
    }
}

// NEW Endpoint
@GetMapping("/status/subsumption")
public ResponseEntity<Map<String, Object>> getSubsumptionStatus() {
    return ok(robotCommandService.getTierStatus());
}
```

---

#### Widget 3: **HARDWARE ACTUATION STATUS**

```vue
<!-- SafetyView.vue — NEW Widget -->
<div class="hardware-actuation terminal-card">
  <div class="terminal-card-header">[ HARDWARE_ACTUATION_STATE ]</div>
  
  <div class="actuation-grid">
    <!-- Left Arm -->
    <div class="arm-widget">
      <div class="arm-label">LEFT_ARM</div>
      <div :class="['arm-status', armLeftState]">
        {{ armLeftState === 'locked' ? '🔒 LOCKED' : '🔓 UNLOCKED' }}
      </div>
      <div class="arm-controls">
        <button class="cmd-btn" @click="toggleArmLeft">
          {{ armLeftState === 'locked' ? 'UNLOCK' : 'LOCK' }}
        </button>
      </div>
      <div class="arm-pressure mono text-dim">
        Air: {{ armLeftPressure }}%
      </div>
    </div>
    
    <!-- Center: Gripper -->
    <div class="gripper-widget">
      <div class="gripper-label">GRIPPER_HAND</div>
      <div :class="['gripper-status', gripperState]">
        {{ gripperState === 'closed' ? '✊ CLOSED' : '✋ OPEN' }}
      </div>
      <div class="gripper-controls">
        <button class="cmd-btn" @click="toggleGripper">
          {{ gripperState === 'closed' ? 'OPEN' : 'CLOSE' }}
        </button>
      </div>
    </div>
    
    <!-- Right Arm -->
    <div class="arm-widget">
      <div class="arm-label">RIGHT_ARM</div>
      <div :class="['arm-status', armRightState]">
        {{ armRightState === 'locked' ? '🔒 LOCKED' : '🔓 UNLOCKED' }}
      </div>
      <div class="arm-controls">
        <button class="cmd-btn" @click="toggleArmRight">
          {{ armRightState === 'locked' ? 'UNLOCK' : 'LOCK' }}
        </button>
      </div>
      <div class="arm-pressure mono text-dim">
        Air: {{ armRightPressure }}%
      </div>
    </div>
  </div>
  
  <div class="actuation-alerts">
    <div v-if="systemPressureLow" class="alert warning">
      ⚠️ PNEUMATIC PRESSURE LOW ({{ systemPressure }}%)
    </div>
    <div v-if="gripper.error" class="alert critical">
      🚨 {{ gripper.error }}
    </div>
  </div>
</div>

<style>
.actuation-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin: 12px 0;
}

.arm-status.locked {
  color: #FF6600;
  font-weight: bold;
}

.arm-status.unlocked {
  color: #00FF66;
}
</style>
```

**Backend MQTT integration:**
```java
// NEW: MqttActuationController.java
@Service
@Slf4j
public class MqttActuationController {
    
    @PostMapping("/arm/left/toggle")
    public void toggleLeftArm() {
        // Send MQTT command
        mqttTemplate.convertAndSend("hk07/control/arm/left/toggle", 
            json({"action": "toggle", "timestamp": now()}));
    }
    
    @PostMapping("/gripper/toggle")
    public void toggleGripper() {
        mqttTemplate.convertAndSend("hk07/control/gripper/toggle",
            json({"action": "toggle", "timestamp": now()}));
    }
    
    // Subscribe to status updates
    @MqttListener(topics = "hk07/sensors/arm/left/state")
    public void onLeftArmStatusChanged(String payload) {
        // Broadcast to WebSocket: /topic/actuation-state
        messagingTemplate.convertAndSend("/topic/actuation-state",
            Map.of("arm", "LEFT", "state", payload));
    }
}
```

### 2.3 **Layout Integration**

```vue
<!-- SafetyView.vue — UPDATED Layout -->
<template>
  <div class="safety-shell">
    <div class="safety-layout">
      <!-- TOP: E-Stop + Subsumption Monitor (40% height) -->
      <div class="safety-top">
        <div class="estop-widget"><!-- Widget 1 --></div>
        <div class="subsumption-monitor"><!-- Widget 2 --></div>
      </div>
      
      <!-- BOTTOM: Radar + Hardware + Alert History (60% height) -->
      <div class="safety-bottom">
        <div class="radar-panel"><!-- Existing --></div>
        <div class="hardware-actuation"><!-- Widget 3 --></div>
        <div class="alert-history"><!-- Existing --></div>
      </div>
    </div>
  </div>
</template>

<style>
.safety-layout {
  display: grid;
  grid-template-rows: 40% 60%;
  gap: 12px;
  height: 100%;
}

.safety-top {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.safety-bottom {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}
</style>
```

---

---

## **YÊU CẦU 3: PROFESSIONAL HEALTHHISTORY METRICS**

### 3.1 **Current State**

```
Location: src/views/HealthHistoryView.vue
Widgets có:
✅ Heart Rate Timeline (Chart.js)
✅ SpO2 + Blood Pressure Chart
✅ Alert Level Distribution (Hourly buckets)

Widgets THIẾU:
❌ Trend Analysis (HR vs BP correlation)
❌ Predictive AI Insights (LanceDB predictions)
```

### 3.2 **Widget 4: TREND ANALYSIS — Multivariate Correlation**

```vue
<!-- HealthHistoryView.vue — NEW Widget -->
<div class="trend-analysis terminal-card chart-card corner-reticle">
  <div class="terminal-card-header">
    [ TREND_ANALYSIS: HR_vs_BP_CORRELATION // {{ activeRange }}H ]
  </div>
  
  <div class="trend-controls">
    <label class="mono text-dim">Compare:</label>
    <select v-model="trendXAxis" class="cmd-select">
      <option value="heartRate">Heart Rate</option>
      <option value="systolic">Systolic BP</option>
    </select>
    <span class="vs mono text-cyan"> vs </span>
    <select v-model="trendYAxis" class="cmd-select">
      <option value="systolic">Systolic BP</option>
      <option value="spo2">SpO2</option>
      <option value="bodyTemperature">Temperature</option>
    </select>
  </div>
  
  <div class="trend-canvas-wrapper">
    <canvas ref="trendCanvas"></canvas>
  </div>
  
  <div class="trend-stats mono text-dim">
    <span>📊 Pearson Correlation: {{ correlationCoefficient }}</span><br/>
    <span>📈 Trend Direction: {{ trendDirection }}</span><br/>
    <span>⚠️ Risk Pattern: {{ riskPattern }}</span>
  </div>
</div>

<!-- Script section -->
<script setup>
import { ref, watch } from 'vue'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

const trendCanvas = ref<HTMLCanvasElement | null>(null)
const trendXAxis = ref('heartRate')
const trendYAxis = ref('systolic')
let trendChart: Chart | null = null

// Pearson correlation calculation
function calculateCorrelation(xData: number[], yData: number[]): number {
  const n = xData.length
  const meanX = xData.reduce((a, b) => a + b) / n
  const meanY = yData.reduce((a, b) => a + b) / n
  
  const numerator = xData.reduce((sum, x, i) => 
    sum + (x - meanX) * (yData[i] - meanY), 0)
  const denomX = Math.sqrt(xData.reduce((sum, x) => 
    sum + (x - meanX) ** 2, 0))
  const denomY = Math.sqrt(yData.reduce((sum, y) => 
    sum + (y - meanY) ** 2, 0))
  
  return numerator / (denomX * denomY)
}

async function renderTrendChart() {
  if (!trendCanvas.value) return
  
  // Prepare data
  const xData = hourlyBuckets.value.map(b => b[trendXAxis.value])
  const yData = hourlyBuckets.value.map(b => b[trendYAxis.value])
  
  // Calculate correlation
  const correlation = calculateCorrelation(xData, yData)
  correlationCoefficient.value = correlation.toFixed(2)
  trendDirection.value = correlation > 0.5 ? "↗️ POSITIVE" : correlation < -0.5 ? "↘️ NEGATIVE" : "→ NEUTRAL"
  
  // Render scatter plot
  trendChart = new Chart(trendCanvas.value, {
    type: 'scatter',
    data: {
      datasets: [{
        label: `${trendXAxis.value} vs ${trendYAxis.value}`,
        data: xData.map((x, i) => ({ x, y: yData[i] })),
        backgroundColor: 'rgba(0, 255, 102, 0.6)',
        borderColor: '#00FF66',
        showLine: false
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false }
      }
    }
  })
}

// Watch for axis changes
watch([trendXAxis, trendYAxis], renderTrendChart)
</script>
```

**Backend support:**
```java
// EXISTING: HealthService.java - add correlation analysis
public Map<String, Object> analyzeTrendCorrelation(String metric1, String metric2, int hours) {
    List<HealthRecordEntity> records = healthRecordRepo.findLatestRecordsWithinHours(hours);
    
    List<Double> values1 = extractMetricValues(records, metric1);
    List<Double> values2 = extractMetricValues(records, metric2);
    
    double correlation = calculatePearsonCorrelation(values1, values2);
    
    return Map.of(
        "metric_1", metric1,
        "metric_2", metric2,
        "correlation", correlation,
        "trend", correlation > 0.5 ? "POSITIVE" : "NEGATIVE",
        "sample_size", records.size()
    );
}

// NEW Endpoint
@GetMapping("/analytics/trend")
public ResponseEntity<Map<String, Object>> getTrendAnalysis(
    @RequestParam String metric1,
    @RequestParam String metric2,
    @RequestParam(defaultValue = "24") int hours
) {
    return ok(healthService.analyzeTrendCorrelation(metric1, metric2, hours));
}
```

---

### 3.3 **Widget 5: PREDICTIVE AI INSIGHTS — LanceDB Forecasting**

```vue
<!-- HealthHistoryView.vue — NEW Widget -->
<div class="predictive-insights terminal-card chart-card corner-reticle">
  <div class="terminal-card-header">
    [ PREDICTIVE_AI_INSIGHTS ] — Next 4H Forecast
  </div>
  
  <div class="forecast-loading" v-if="forecastLoading">
    <span class="text-cyan mono">⏳ Analyzing patterns from LanceDB...</span>
  </div>
  
  <div v-else class="forecast-content">
    <!-- Forecast alerts -->
    <div class="forecast-alerts">
      <div v-for="alert in forecastAlerts" :key="alert.id"
           :class="['forecast-alert', alert.level.toLowerCase()]">
        <span class="alert-time mono">{{ alert.timeEstimate }}</span>
        <span class="alert-icon">{{ alert.icon }}</span>
        <span class="alert-prediction">{{ alert.prediction }}</span>
        <span class="alert-confidence mono text-dim">({{ alert.confidence }}% confidence)</span>
      </div>
    </div>
    
    <!-- Risk gauge -->
    <div class="risk-gauge-wrapper">
      <div class="risk-label mono">OVERALL_RISK_4H:</div>
      <div class="risk-gauge">
        <div class="risk-fill" :style="{ width: riskScore + '%' }"></div>
      </div>
      <div :class="['risk-percentage', `risk-${riskLevel.toLowerCase()}`]">
        {{ riskScore }}% {{ riskLevel }}
      </div>
    </div>
    
    <!-- Data source -->
    <div class="data-source mono text-dim">
      <span>📚 Source: LanceDB vector memory ({{ vectorCount }} patterns)</span><br/>
      <span>🤖 Model: Linear regression + seasonal decomposition</span>
    </div>
  </div>
</div>

<!-- Script section -->
<script setup>
const forecastLoading = ref(false)
const forecastAlerts = ref<ForecastAlert[]>([])
const riskScore = ref(0)
const riskLevel = ref('LOW')

async function loadForecastInsights() {
  forecastLoading.value = true
  try {
    const resp = await api.get('/health/analytics/forecast', {
      params: { hours_ahead: 4 }
    })
    
    forecastAlerts.value = resp.data.alerts.map(a => ({
      id: a.id,
      timeEstimate: `${a.predicted_hour}h`,
      icon: a.alert_level === 'CRITICAL' ? '🚨' : '⚠️',
      prediction: a.prediction_text,
      confidence: a.confidence_score
    }))
    
    riskScore.value = resp.data.risk_score
    riskLevel.value = resp.data.risk_level
    
  } catch (e) {
    log.error('Failed to load forecast', e)
    forecastAlerts.value = []
  } finally {
    forecastLoading.value = false
  }
}

onMounted(loadForecastInsights)
</script>

<style>
.forecast-alerts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 12px 0;
}

.forecast-alert {
  padding: 8px;
  border-left: 3px solid;
  background: rgba(0, 255, 102, 0.05);
}

.forecast-alert.critical {
  border-color: #FF0000;
  background: rgba(255, 0, 0, 0.05);
}

.risk-gauge {
  width: 100%;
  height: 20px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid #00FF66;
  position: relative;
  overflow: hidden;
}

.risk-fill {
  height: 100%;
  background: linear-gradient(90deg, #00FF66, #FF6600, #FF0000);
  transition: width 0.3s;
}
</style>
```

**Backend AI logic (Python agent):**
```python
# NEW: services/forecast_service.py

class ForecastService:
    def __init__(self, memory: LanceMemory):
        self.memory = memory
    
    async def predict_next_hours(self, user_id: str, hours_ahead: int = 4) -> dict:
        """
        Use LanceDB to retrieve similar historical patterns.
        Apply linear regression + seasonal decomposition.
        Return predicted alerts + risk score.
        """
        
        # 1. Retrieve historical vitals for this user
        vitals_history = await self.memory.retrieve_vitals_timeseries(user_id)
        
        # 2. Find similar patterns in LanceDB
        current_pattern = vitals_history[-1]
        similar_patterns = await self.memory.search_similar_patterns(
            pattern=current_pattern,
            limit=10
        )
        
        # 3. Extract next-hour outcomes from similar patterns
        future_outcomes = [p['future_outcome'] for p in similar_patterns]
        
        # 4. Predict using ensemble (average + variance)
        predictions = []
        for hour_offset in range(1, hours_ahead + 1):
            future_vitals = self._extrapolate_vitals(
                vitals_history, 
                future_outcomes,
                hour_offset
            )
            
            # Determine alert level
            alert_level = self._assess_alert_level(future_vitals)
            
            if alert_level != "NORMAL":
                predictions.append({
                    "predicted_hour": hour_offset,
                    "alert_level": alert_level,
                    "prediction_text": f"{alert_level} HR={future_vitals['hr']:.0f}bpm",
                    "confidence_score": 85  # Example
                })
        
        # 5. Calculate overall risk
        risk_score = sum(p['confidence_score'] for p in predictions) / max(len(predictions), 1)
        risk_level = "CRITICAL" if risk_score > 70 else "WARNING" if risk_score > 50 else "LOW"
        
        return {
            "alerts": predictions,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "vector_count": len(similar_patterns)
        }
```

**Backend endpoint:**
```java
// NEW: HealthAnalyticsController.java
@RestController
@RequestMapping("/api/v1/health/analytics")
public class HealthAnalyticsController {
    
    @Autowired
    private ForecastClient forecastClient;  // Calls Python service
    
    @GetMapping("/forecast")
    public ResponseEntity<Map<String, Object>> getForecast(
        @RequestParam(defaultValue = "4") int hours_ahead,
        @AuthenticationPrincipal UserEntity user
    ) {
        try {
            Map<String, Object> forecast = forecastClient.predictNextHours(
                user.getId().toString(),
                hours_ahead
            );
            return ok(forecast);
        } catch (Exception e) {
            // Graceful fallback if Python service unavailable
            return ok(Map.of(
                "alerts", List.of(),
                "risk_score", 0,
                "risk_level", "UNAVAILABLE"
            ));
        }
    }
}

// ForecastClient — async HTTP bridge
@Service
public class ForecastClient {
    @Value("${python.agent.url:http://localhost:8000}")
    private String pythonAgentUrl;
    
    public Map<String, Object> predictNextHours(String userId, int hours) {
        // POST to Python service: /api/v1/forecast/predict
        RestTemplate rest = new RestTemplate();
        ResponseEntity<Map> resp = rest.postForEntity(
            pythonAgentUrl + "/api/v1/forecast/predict",
            Map.of("user_id", userId, "hours_ahead", hours),
            Map.class
        );
        return resp.getBody();
    }
}
```

### 3.4 **Updated HealthHistoryView Layout**

```vue
<!-- HealthHistoryView.vue — FULL GRID -->
<template>
  <div class="history-shell">
    <div class="history-controls-bar"><!-- Existing --></div>
    
    <div v-if="!loading && !error" class="charts-grid">
      <!-- Row 1: Core metrics (60%) -->
      <div class="terminal-card chart-card">[ HR_TIMELINE ]</div>
      <div class="terminal-card chart-card">[ SPO2_BP ]</div>
      
      <!-- Row 2: Advanced analysis (40%) -->
      <div class="terminal-card chart-card" style="grid-column: 1 / -1;">
        [ ALERT_DISTRIBUTION ]
      </div>
      
      <!-- Row 3: New widgets (100%) -->
      <div class="terminal-card chart-card" style="grid-column: 1 / 2;">
        [ TREND_ANALYSIS ]  ← NEW Widget 4
      </div>
      <div class="terminal-card chart-card" style="grid-column: 2 / -1;">
        [ PREDICTIVE_INSIGHTS ]  ← NEW Widget 5
      </div>
    </div>
  </div>
</template>

<style>
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  height: 100%;
}

.chart-card {
  min-height: 250px;
}
</style>
```

---

---

## **COMPLETE FRONTEND UI AUDIT SUMMARY**

### File-by-file analysis:

| View | Status | Issue | Fix |
|------|--------|-------|-----|
| **Dashboard.vue** | ✅ 95% | Subsumption display good | ✅ No changes needed |
| **HealthHistory.vue** | ⚠️ 70% | Missing 2 advanced widgets | 📌 Add Trend + Predictive (M0.5) |
| **SafetyView.vue** | ⚠️ 60% | Missing E-Stop, actuation | 📌 Add E-Stop, Subsumption, Hardware (M0.5) |
| **Agents View.vue** | ✅ 90% | Event stream good | ✅ No changes needed |
| **Companion.vue** | ✅ 85% | Chat interface working | ✅ No changes needed |
| **Login.vue** | ✅ 90% | Auth flow solid | ✅ No changes needed |
| **Profile.vue** | ✅ 85% | Settings form working | ✅ No changes needed |
| **Emergency.vue** | ⚠️ 40% | Minimal mock | 🟡 Could enhance later |

**Overall Dashboard Density:** 72% → Target 85% (after M0.5)

---

---

## **TIMELINE & EFFORT ESTIMATION**

### Milestone 0.5 Breakdown:

| Task | Complexity | Effort | Owner | Timeline |
|------|-----------|--------|-------|----------|
| **1. LLM Router (Backend)** | 🔴 Hard | 50-60h | Backend | Week 1-2 |
| ├─ Implement services/llm_router.py | 🟡 Med | 25h | Python | - |
| ├─ Update agents to use router | 🟡 Med | 15h | Python | - |
| ├─ Add Redis quota tracking | 🟠 Hard | 10h | Python | - |
| └─ Test provider fallbacks | 🟡 Med | 10h | QA | - |
| **2. Safety UI Redesign** | 🟡 Med | 40-50h | Frontend | Week 1-2 |
| ├─ E-Stop widget + backend | 🟡 Med | 15h | Full-stack | - |
| ├─ Subsumption monitor | 🟡 Med | 15h | Frontend | - |
| ├─ Hardware actuation widget | 🟡 Med | 15h | Frontend | - |
| └─ Integration testing | 🟡 Med | 10h | QA | - |
| **3. HealthHistory Widgets** | 🟡 Med | 35-45h | Frontend | Week 2 |
| ├─ Trend analysis (scatter plot) | 🟡 Med | 15h | Frontend | - |
| ├─ Predictive insights (Python) | 🟡 Med | 20h | Python | - |
| ├─ Backend analytics endpoints | 🟡 Med | 10h | Java | - |
| └─ Testing & demo | 🟡 Med | 5h | QA | - |

**Total: ~130-150 hours** (3-4 weeks for small team)

---

## **SUCCESS CRITERIA**

After MILESTONE 0.5 completion:

✅ **System Resilience:**
- [x] Zero downtime when 1 LLM provider quota exhausted
- [x] Auto-rotate to free tier (Gemini/HuggingFace) without user notice
- [x] All 3 providers tested in fallback chain
- [x] Cost reduced by 40% (free tier prioritized)

✅ **UI Density:**
- [x] Safety page: 5 functional widgets (E-Stop, Subsumption, Hardware, Radar, Alert)
- [x] HealthHistory: 5 data-rich widgets (HR, BP, Distribution, Trend, Predictive)
- [x] Zero dummy/mock components remaining
- [x] 85%+ pixel utilization (min 12px padding)

✅ **User Experience:**
- [x] E-Stop reachable in <1 click from any page
- [x] Real-time subsumption layer visibility
- [x] Hardware actuation feedback (arm lock/unlock status)
- [x] Predictive alerts 30min before anomaly (4h forecast)

---

## **NEXT STEPS**

1. **Architect approval** → phê duyệt MILESTONE 0.5 spec
2. **Sprint planning** → allocate resources, assign tasks
3. **Develop Phase 1** → Implement LLM Router (critical path)
4. **Develop Phase 2** → Safety UI redesign (parallel)
5. **Develop Phase 3** → HealthHistory widgets (dependent on Phase 2)
6. **Integration testing** → Full system validation
7. **Demo & feedback** → Operator review

---

**📞 CHỜ PHƯƠNG ÁN PHÊ DUYỆT TỪ ARCHITECT.**

**Báo cáo ARCH-REVIEW-V2 HOÀN THÀNH — CHỚ LỆNH TIẾP THEO.**
