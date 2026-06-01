# ĐẶC TẢ KIẾN TRÚC XÁC THỰC & TRẢI NGHIỆM Y TẾ (BAYMAX STANDARD)
**Mã tài liệu:** HK07-AUTH-V2
**Mục tiêu:** Chuyển đổi từ cơ chế xác thực JWT truyền thống sang cơ chế "Silent Authentication" (Xác thực tĩnh lặng), đảm bảo trải nghiệm liền mạch (không văng phiên khi reload), cung cấp quyền truy cập cấp cứu (Emergency) và chuẩn bị nền tảng ghép nối thiết bị sinh trắc học.

## 1. KIẾN TRÚC SILENT REFRESH (HTTP-ONLY COOKIE)
Để chống XSS tuyệt đối nhưng không làm mất UX khi F5/Reload trang, hệ thống sẽ sử dụng cơ chế HttpOnly Cookie cho Refresh Token.

### 1.1. Yêu cầu Backend (Spring Boot)
* **Endpoint `/api/v1/auth/login`**:
    * Vẫn trả về `accessToken` (thời hạn ngắn, vd: 15 phút) trong JSON Body.
    * **KHÔNG** trả `refreshToken` trong JSON Body.
    * Tạo đối tượng `Cookie` chứa `refreshToken` với các cờ bắt buộc: `HttpOnly = true`, `Secure = true` (nếu chạy HTTPS), `SameSite = Strict`, `Path = /api/v1/auth/refresh`. Đính kèm Cookie này vào `HttpServletResponse`.
* **Endpoint `/api/v1/auth/refresh`**:
    * Đọc `refreshToken` trực tiếp từ Cookie thay vì từ Request Body/Header.
    * Nếu hợp lệ, cấp phát và trả về `accessToken` mới trong JSON Body.
* **Endpoint `/api/v1/auth/logout`**:
    * Xóa/Clear Cookie chứa `refreshToken` bằng cách set Max-Age = 0.

### 1.2. Yêu cầu Frontend (Vue 3 / Pinia)
* **Cấu hình Axios/Fetch**: Phải bật `withCredentials: true` trên instance API mặc định để trình duyệt tự động đính kèm Cookie khi gọi API refresh.
* **Store `auth.ts`**:
    * Chỉ lưu `accessToken` in-memory (`ref<string | null>(null)`).
    * Tạo hàm `initAuth()` hoặc `tryAutoLogin()`. Hàm này sẽ gọi ngầm endpoint `/refresh` (không kèm token nào, để trình duyệt tự gửi cookie).
    * Gọi hàm này ở `main.ts` hoặc `App.vue` **trước khi** mount ứng dụng hoặc trước khi Router kiểm tra quyền truy cập.

## 2. CHẾ ĐỘ TRUY CẬP KHẨN CẤP (EMERGENCY OVERRIDE)
Hệ thống y tế không thể đóng sầm cửa trước mặt bác sĩ cấp cứu chỉ vì họ không có mật khẩu.
* **Route mới**: Tạo route `/emergency` ở Frontend. Route này cấu hình `meta: { requiresAuth: false }` (Bypass Router Guard).
* **Giao diện Login**: Thêm một nút kích thước lớn, màu cảnh báo (Đỏ/Cam) mang tên **"EMERGENCY ACCESS (CẤP CỨU)"**. Nút này điều hướng thẳng tới `/emergency`.
* **Quyền hạn tại `/emergency`**: 
    * Được phép kết nối WebSocket để xem sinh hiệu (Vitals: Nhịp tim, SpO2) thời gian thực.
    * **Bị khóa (Disabled)** mọi nút bấm ra lệnh (Action Buttons), không thể thay đổi cài đặt hệ thống hay chat với Agent y tế chuyên sâu.

## 3. GIAO DIỆN GHÉP NỐI THIẾT BỊ (DEVICE PAIRING MOCKUP)
Chuẩn bị UI cho việc đăng nhập không chạm (NFC/QR/Mã định danh).
* Thiết kế lại `LoginView.vue`.
* Chia giao diện thành 2 Tabs hoặc 2 Cột:
    * **Tab 1 (Operator):** Form đăng nhập Email/Password như hiện tại.
    * **Tab 2 (Device Pairing):** Giao diện chờ hiển thị "Quét thiết bị định danh hoặc nhập PIN thiết bị". Hiện tại chỉ cần xây dựng UI tĩnh (Mockup), logic xử lý phần cứng sẽ làm sau.