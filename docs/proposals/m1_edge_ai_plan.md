# KẾ HOẠCH TRIỂN KHAI MILESTONE 1: EDGE AI / OFFLINE COGNITION
**Mã tài liệu:** HK07-M1-EDGEAI-V1
**Mục tiêu:** Chuyển đổi hệ thống từ phụ thuộc Cloud API (Groq/OpenRouter/Gemini) sang chạy OFFLINE tại biên (Edge AI) với ràng buộc RAM ~3.3GB.

---

## 1. PHÂN TÍCH HIỆN TRẠNG CLOUD API

### 1.1. Cloud API Usage trong `agents/medical_agent.py`

**Primary API (Groq):**
- Endpoint: `https://api.groq.com/openai/v1/chat/completions`
- Model: `llama-3.1-8b-instant`
- Usage: Chẩn đoán y tế proactive (background) và text interaction
- Method: `_call_groq()`, `_call_groq_text()`

**Fallback API (OpenRouter):**
- Endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Model: `openrouter/free`
- Usage: Khi Groq thất bại
- Method: `_call_openrouter()`, `_call_openrouter_text()`

**Final Fallback (Local Rule-based):**
- Đã tồn tại: `_generate_rule_based_diagnosis()`, `_generate_local_first_aid_plan()`
- Chỉ hoạt động khi cả 2 Cloud API đều thất bại

### 1.2. Cloud API Usage trong `main.py`

- `main.py` không gọi trực tiếp Cloud API
- Chỉ đóng vai trò orchestrator, delegate cho các agent
- Endpoint `/api/v1/memory/sync_profile` chỉ sync dữ liệu nội bộ

### 1.3. Cloud API Usage trong Vision (tài liệu specs)

- Gemini 1.5 Pro/Flash Vision API cho chẩn đoán hình ảnh
- Endpoint: (chưa hiện trong code, chỉ trong spec)

---

## 2. ĐỀ XUẤT EDGE AI LIBRARY (PHÙ HỢP 3.3GB RAM)

### 2.1. Thư viện đề xuất: `llama-cpp-python`

**Lý do chọn:**
- Hỗ trợ quantization (Q4_K_M, Q5_K_S) giảm RAM usage 60-70%
- Tương thích Python, dễ tích hợp vào FastAPI
- Hỗ trợ multi-threading và GPU acceleration (nếu có)
- Active community, nhiều model hỗ trợ

**Cài đặt:**
```bash
pip install llama-cpp-python
# Hoặc với CPU optimization:
CMAKE_ARGS="-DLLAMA_CUBLAS=off" pip install llama-cpp-python
```

### 2.2. Model đề xuất (sắp xếp theo ưu tiên)

#### **Option 1: Phi-3-mini-4k-instruct (Khuyên dùng)**
- **Size:** ~2GB (Q4_K_M quantization)
- **Parameters:** 3.8B
- **Context:** 4K tokens
- **Ưu điểm:** Microsoft phát triển, chất lượng cao, tối ưu cho medical reasoning
- **Download:** `https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4_k_m.gguf`

#### **Option 2: Qwen-1.5B-Chat**
- **Size:** ~1GB (Q4_K_M quantization)
- **Parameters:** 1.5B
- **Context:** 8K tokens
- **Ưu điểm:** Alibaba phát triển, hỗ trợ tiếng Việt tốt, rất nhẹ
- **Download:** `https://huggingface.co/Qwen/Qwen1.5-1.5B-Chat-GGUF/resolve/main/qwen1.5-1.5b-chat-q4_k_m.gguf`

#### **Option 3: TinyLlama-1.1B-Chat**
- **Size:** ~0.8GB (Q4_K_M quantization)
- **Parameters:** 1.1B
- **Context:** 2K tokens
- **Ưu điểm:** Nhẹ nhất, phù hợp nếu RAM cực kỳ hạn chế
- **Download:** `https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/TinyLlama-1.1B-Chat-v1.0.Q4_K_M.gguf`

### 2.3. RAM Estimation (3.3GB constraint)

| Component | Estimation |
|-----------|------------|
| OS + System | ~500MB |
| Python Runtime + FastAPI | ~300MB |
| LanceDB (Vector DB) | ~200MB |
| MQTT Client | ~50MB |
| **Edge AI Model (Phi-3-mini Q4)** | ~2GB |
| **Buffer + Overhead** | ~250MB |
| **Total** | **~3.3GB** |

**Kết luận:** Phi-3-mini-4k-instruct (Q4) là lựa chọn tối ưu nhất.

---

## 3. SƠ ĐỒ LUỒNG ĐI KHI MẤT MẠNG WI-FI

### 3.1. Flowchart (Text-based)

```
┌─────────────────────────────────────────────────────────────┐
│                     USER REQUEST                             │
│              (Text / Voice / Medical Vitals)                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  NETWORK CHECK PING  │
              │  (localhost:8889)    │
              └───────────┬───────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
      ONLINE (Wi-Fi OK)          OFFLINE (No Wi-Fi)
            │                           │
            ▼                           ▼
    ┌───────────────┐         ┌───────────────────────┐
    │  CLOUD API    │         │   EDGE AI (LOCAL)     │
    │  - Groq       │         │   - llama-cpp-python  │
    │  - OpenRouter │         │   - Phi-3-mini Q4     │
    └───────┬───────┘         └───────────┬───────────┘
            │                             │
            ▼                             ▼
    ┌───────────────┐         ┌───────────────────────┐
    │   LLM OUTPUT  │         │   LLM OUTPUT          │
    │   (JSON)      │         │   (JSON)              │
    └───────┬───────┘         └───────────┬───────────┘
            │                             │
            └─────────────┬───────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   RESPONSE TO USER   │
              │   (Text + TTS Audio) │
              └───────────────────────┘
```

### 3.2. Luồng chi tiết cho Medical Agent

**Trạng thái ONLINE:**
```
MQTT Vitals → MedicalAgent Buffer → Aggregation
                                        │
                                        ▼
                              State Change Check
                                        │
                          ┌─────────────┴─────────────┐
                          │                           │
                    NORMAL/CRITICAL              No Change
                          │                           │
                          ▼                           │
                    Call Groq API ◄───────────────────┘
                          │
                    [Success?] ──No──► Call OpenRouter
                          │                   │
                         Yes                  │
                          │                   │
                          ▼                   ▼
                    Return JSON         [Success?] ──No──► Local Rules
                          │                   │              │
                          └─────────┬─────────┘              │
                                    │                        │
                                    ▼                        │
                              MQTT Publish ◄────────────────┘
```

**Trạng thái OFFLINE (M1 Implementation):**
```
MQTT Vitals → MedicalAgent Buffer → Aggregation
                                        │
                                        ▼
                              State Change Check
                                        │
                          ┌─────────────┴─────────────┐
                          │                           │
                    NORMAL/CRITICAL              No Change
                          │                           │
                          ▼                           │
                    Call Edge AI ◄────────────────────┘
                    (llama-cpp-python)
                          │
                    [Success?] ──No──► Local Rules
                          │              │
                         Yes             │
                          │              │
                          ▼              │
                              MQTT Publish ◀──┘
```

### 3.3. Luồng chi tiết cho Vision (Milestone tương lai)

**Trạng thái OFFLINE (Vision):**
```
Camera Frame → Sensor Fusion Buffer
                    │
                    ▼
          User Request: "Quét tôi ngay"
                    │
                    ▼
         Extract Base64 Image
                    │
                    ▼
    ┌───────────────────────────────┐
    │  EDGE VISION MODEL (TBD)      │
    │  - CLIP / BLIP / MobileViT    │
    │  - Hoặc rule-based detection  │
    └───────────────┬───────────────┘
                    │
                    ▼
         Return Diagnosis JSON
```

---

## 4. KẾ HOẠCH TRIỂN KHAI (IMPLEMENTATION PLAN)

### Phase 1: Setup Edge AI Infrastructure (Week 1)
1. Cài đặt `llama-cpp-python` với CPU optimization
2. Download model Phi-3-mini-4k-instruct Q4_K_M
3. Tạo module `services/edge_llm.py` để wrapper llama-cpp-python
4. Test inference với medical prompts

### Phase 2: Refactor MedicalAgent (Week 2)
1. Thêm method `_call_edge_llm()` trong `medical_agent.py`
2. Cập nhật `_call_llm_with_fallback()` để check network status
3. Thêm network health check (ping test)
4. Update circuit breaker để handle Edge AI failures

### Phase 3: Update System Prompts (Week 2)
1. Điều chỉnh prompts để phù hợp với model nhỏ hơn
2. Test JSON output consistency với Edge AI
3. Benchmark latency: Cloud vs Edge

### Phase 4: Testing & Validation (Week 3)
1. Test offline mode (disconnect Wi-Fi)
2. Test proactive medical monitoring offline
3. Test memory sync (LanceDB) offline
4. Performance profiling (RAM usage)

### Phase 5: Documentation & Handoff (Week 4)
1. Update README với Edge AI setup instructions
2. Create troubleshooting guide
3. Document model switching mechanism

---

## 5. RỦI RO & GIẢI PHÁP

| Rủi ro | Giải pháp |
|--------|-----------|
| Edge AI chất lượng thấp hơn Cloud | Giữ rule-based fallback, tuning prompts |
| RAM vượt 3.3GB | Switch sang Qwen-1.5B (nhẹ hơn), disable unused features |
| Model load time chậm | Pre-load model at startup, keep in memory |
| Vision không hỗ trợ offline | Tạm giữ Vision online-only, M1 tập trung text/vitals |

---

## 6. THÔNG SỐ KỸ THUẬT ĐỀ XUẤT

```yaml
edge_ai:
  library: "llama-cpp-python==0.2.0"
  model: "Phi-3-mini-4k-instruct-q4_k_m.gguf"
  model_path: "./models/edge/"
  context_length: 4096
  n_threads: 4
  n_batch: 512
  temperature: 0.1
  max_tokens: 512

network_check:
  ping_target: "8.8.8.8"
  ping_timeout: 2.0
  fallback_threshold: 3  # số lần fail trước khi switch offline

ram_budget:
  total_available: 3300  # MB
  model_allocation: 2000
  system_overhead: 1300
```

---

## 7. KẾT LUẬN

Milestone 1 tập trung chuyển đổi MedicalAgent từ Cloud API sang Edge AI với:
- **Library:** llama-cpp-python
- **Model:** Phi-3-mini-4k-instruct (Q4_K_M, ~2GB)
- **RAM:** Tổng ~3.3GB (phù hợp ràng buộc)
- **Fallback:** Local rule-based (đã tồn tại)
- **Vision:** Giữ online-only (Milestone tương lai)

Sau khi triển khai, hệ thống có thể hoạt động hoàn toàn offline cho các chức năng:
- Chẩn đoán y tế proactive
- Trả lời câu hỏi y tế
- Theo dõi sinh tồn
- Lưu trữ memory (LanceDB)

**Chờ chủ nhân review duyệt trước khi bắt đầu implementation.**
