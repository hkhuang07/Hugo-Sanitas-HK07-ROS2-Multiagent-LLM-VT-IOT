# BÁO CÁO CẬP NHẬT KIẾN TRÚC XÁC THỰC & TRẢI NGHIỆM Y TẾ (BAYMAX STANDARD)

Chúng ta đã triển khai thành công hệ thống xác thực liền mạch (**Silent Refresh**) sử dụng HttpOnly Cookie nhằm khắc phục hoàn toàn lỗi mất phiên khi reload trang (F5) và thêm giao diện truy cập khẩn cấp cho trạm y tế HK-07.

---

## 1. Danh sách các File đã sửa đổi và tạo mới

### A. Backend (`hk07-core`)
* **[AuthController.java](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/backend/hk07-core/src/main/java/com/hk07/domain/auth/controller/AuthController.java)**:
  * Tách `refreshToken` ra khỏi Response Body trong các API `/login` và `/register`.
  * Thiết lập HttpOnly Cookie `hk07_refresh_token` (`SameSite=Strict`, `Secure=false` cho môi trường phát triển cục bộ, `Path=/api/v1/auth`, thời hạn 7 ngày).
  * Chuyển API `/refresh` và `/logout` sang đọc và xóa Cookie thay vì đọc từ Request Body.

### B. Frontend (`hk07-dashboard`)
* **[api.ts](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/services/api.ts)**:
  * Cấu hình mặc định `axios.defaults.withCredentials = true` và `withCredentials: true` trên Axios instance để trình duyệt tự gửi Cookie.
  * Tinh giản interceptor phản hồi lỗi 401 để tự động gọi API `/refresh` mà không cần truyền body.
* **[auth.ts](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/stores/auth.ts)**:
  * Loại bỏ hoàn toàn biến `refreshToken` khỏi state và local storage.
  * Thêm action `tryAutoLogin()` để thực hiện tự động đăng nhập tĩnh lặng khi người dùng tải lại trang.
* **[websocket.ts](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/services/websocket.ts)**:
  * Thay thế kiểm tra `authStore.refreshToken` bằng `authStore.isAuthenticated` trước khi (re)connect WebSocket.
* **[main.ts](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/main.ts)**:
  * Gọi `await authStore.tryAutoLogin()` trước khi mount ứng dụng lên DOM để khôi phục phiên nếu cookie còn hiệu lực, loại bỏ hiện tượng giật trang đăng nhập.
* **[router/index.ts](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/router/index.ts)**:
  * Khai báo Route `/emergency` với cấu hình `requiresAuth: false` để bỏ qua bộ bảo vệ router guard.
* **[LoginView.vue](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/views/LoginView.vue)**:
  * Thêm nút truy cập khẩn cấp `EMERGENCY ACCESS (CẤP CỨU)` màu đỏ phát sáng.
  * Chia giao diện thành 2 tab: "Operator Login" và "Device Pairing" (với hiệu ứng scan radar và hướng dẫn quét thiết bị).
* **[EmergencyView.vue](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/views/EmergencyView.vue)** *(Tạo mới)*:
  * Giao diện theo phong cách Cyber-DarkBlue hiển thị dòng chữ cảnh báo y tế khẩn cấp, bảng telemetry sinh hiệu (Nhịp tim, SpO2) và nhật ký override không cần đăng nhập.
* **[env.d.ts](file:///d:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/src/env.d.ts)** *(Tạo mới)*:
  * Bổ sung định nghĩa types của Vite Client để trình kiểm thử TypeScript biên dịch thành công `import.meta.env`.

---

## 2. Kết quả kiểm tra biên dịch

* **Frontend Compile**: `npx vue-tsc --noEmit` đạt **Exit Code 0** (không có lỗi TypeScript nào).
* **Backend Compile**: `mvn clean compile` biên dịch thành công toàn bộ dự án (`BUILD SUCCESS`).
