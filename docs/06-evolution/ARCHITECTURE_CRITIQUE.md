# SYSTEM EVOLUTION & ARCHITECTURE CRITIQUE
**Date**: 2026-05-31
**Context**: HK-07 Robotics Companion
**Phase**: Red Teaming & Self-Critique

## 1. Memory Leaks (Frontend Vue 3 Canvas)
**Vulnerability**: Trong `DashboardView.vue` và `SafetyView.vue`, vòng lặp `requestAnimationFrame` được khởi tạo bằng cách gọi đệ quy. Khi component bị unmount, `cancelAnimationFrame` chỉ hủy frame cuối cùng đang chờ. Nếu callback của frame trước đó vẫn đang thực thi, nó sẽ tiếp tục gọi đệ quy `requestAnimationFrame`, tạo ra vòng lặp vô hạn chạy ngầm (Ghost Loop) ngay cả khi đã chuyển trang.
**Impact**: Chạy 24/7 sẽ gây rò rỉ bộ nhớ, làm Crash tab trình duyệt trên máy có RAM thấp.
**Solution**: Bổ sung cờ `isUnmounted` và kiểm tra `if (isUnmounted) return` ngay đầu hàm `drawEcg()` và `drawRadar()`.

## 2. Race Conditions & Connection Bottleneck (Agent Log Pipeline)
**Vulnerability**: `AgentLogService.java` sử dụng `@Async` cho từng Log riêng lẻ. Khi Python Agent Client xả (flush) 10 logs cùng lúc, Spring Boot sinh ra 10 Virtual Threads đồng thời truy cập DB. Với connection pool giới hạn của MariaDB (HikariCP), nếu nhiều Agents cùng xả rác, pool sẽ cạn kiệt, gây thắt cổ chai và Transaction Timeout. 
Thêm vào đó, ở phía Python, `_flush_buffer` đang dùng vòng lặp `for entry in batch: await self._http.post(...)` tuần tự, làm tắc nghẽn luồng Async Event Loop nếu backend chậm.
**Solution**: 
- (Spring Boot) Thay thế lưu đơn lẻ bằng `saveAll(logs)` theo Batch. 
- (Python) Dùng `asyncio.gather` để xả batch nhanh hơn hoặc gộp payload thành array JSON (tuy nhiên để tuân thủ kiến trúc hiện tại, ta sẽ dùng `asyncio.gather` để tăng tốc HTTP Client).

## 3. Message Flooding & OOM (MQTT Subsumption)
**Vulnerability**: Nếu cảm biến LiDAR vật lý bị nhiễu (Glitch) và đẩy 10,000 gói tin/giây lên MQTT topic `hk07/sensors/lidar/scan`, `SafetyAgent.py` sẽ bị trigger liên tục. Hàm callback MQTT sẽ đẩy hàng vạn tác vụ vào ThreadPool, gây tràn RAM (OOM) và sập tiến trình Subsumption. Tương tự với vòng lặp xử lý Vitals trong `HealthService`.
**Solution**: Áp dụng thuật toán **Throttling/Debounce**. 
- Trong `SafetyAgent.py`: Ghi nhớ timestamp cuối cùng (`self._last_process_time`), bỏ qua các tin nhắn đến quá nhanh (ví dụ: giới hạn xử lý tối đa 20Hz - 50ms/tin).
- Trong `HealthService.java`: Dùng ConcurrentHashMap để Throttle tín hiệu Vitals từ MQTT inbound channel, chỉ xử lý tối đa 60Hz.

## LỆNH TỰ ĐỘNG VÁ LỖI (AUTO-PATCHING SEQUENCE)
Động cơ tự trị sẽ tiến hành refactor các file sau:
1. `SafetyView.vue` & `DashboardView.vue` (Fix Canvas memory leak).
2. `agent_log_client.py` (Áp dụng `asyncio.gather` tránh block I/O tuần tự).
3. `safety_agent.py` (Áp dụng Throttle 50ms cho LiDAR stream).
