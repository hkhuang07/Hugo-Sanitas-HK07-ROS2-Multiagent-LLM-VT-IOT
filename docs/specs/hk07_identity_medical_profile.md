# ĐẶC TẢ KIẾN TRÚC QUẢN LÝ DANH TÍNH & HỒ SƠ Y TẾ TỰ TRỊ
**Mã tài liệu:** HK07-IAM-MEDICAL-V1
**Mục tiêu:** Xây dựng hệ thống quản lý định danh (Identity) và hồ sơ y tế (Medical Profile) cho bệnh nhân. Cho phép người dùng tự quản lý bảo mật, cập nhật tình trạng sức khỏe và tự động đồng bộ hóa những thay đổi này vào "Trí nhớ" của AI (LanceDB) để cá nhân hóa quá trình chăm sóc.

## 1. NGHI THỨC KHỞI TẠO BỆNH NHÂN (PATIENT ONBOARDING WIZARD)
Thay vì form đăng ký thông thường, hệ thống sử dụng Multi-step Wizard (Tiến trình đa bước) dành cho thiết bị y tế.
* **Bước 1 - Account Setup (Tài khoản):** Nhập Email, Password (có validate độ mạnh), Confirm Password.
* **Bước 2 - Medical Baseline (Hồ sơ gốc):** Nhập Họ tên, Tuổi, Giới tính, Chiều cao (cm), Cân nặng (kg), Nhóm máu, Tiền sử bệnh lý (bệnh nền), Tiền sử dị ứng.
* **Bước 3 - Emergency Contacts (Người liên hệ):** Nhập Tên và Số điện thoại của người thân/bác sĩ.
* **Kết quả (System Output):** Sau khi hoàn tất, Backend tự động sinh ra **5 Mã Khôi Phục (Recovery Codes)** (mỗi mã 8 ký tự ngẫu nhiên) hiển thị lên màn hình, yêu cầu người dùng lưu lại để khôi phục mật khẩu khi cần.

## 2. QUẢN LÝ BẢO MẬT & QUYỀN TRUY CẬP (SELF-SERVICE SECURITY)
* **Change Password (Đổi mật khẩu):** API và Giao diện cho phép người dùng đang đăng nhập đổi mật khẩu (Yêu cầu nhập mật khẩu cũ).
* **Forgot Password (Quên mật khẩu bằng Recovery Codes):**
    * Người dùng nhập Email + 1 Mã Khôi Phục chưa sử dụng.
    * Hệ thống xác thực và cho phép đặt lại mật khẩu mới, đồng thời vô hiệu hóa mã khôi phục vừa dùng.

## 3. QUẢN LÝ HỒ SƠ Y TẾ (MEDICAL PROFILE MANAGEMENT)
* Tạo trang "Settings / My Profile" trên Dashboard.
* Cho phép người dùng xem và cập nhật lại thông tin cá nhân, chỉ số cơ thể (cân nặng, chiều cao) và tiền sử bệnh lý.
* Cung cấp API CRUD (Create, Read, Update) cho Entity `MedicalProfile` trong Spring Boot.

## 4. ĐỈNH CAO: ĐỒNG BỘ HÓA TRÍ NHỚ AI (AI MEMORY SYNC)
Mọi thay đổi của bệnh nhân phải được AI "học" ngay lập tức.
* **Java Backend (Webhook Trigger):** Bất cứ khi nào API Cập nhật Hồ sơ Y tế (Update Profile) được gọi thành công, Spring Boot phải tự động gửi một HTTP POST Request (chứa dữ liệu profile mới) đến Endpoint nội bộ của Python Agent.
* **Python AI Engine (FastAPI Receiver):** * Tạo một endpoint `/api/v1/memory/sync_profile`.
    * Khi nhận được JSON chứa thông tin y tế mới, nó gọi module `lance_memory.py` để cập nhật/ghi đè (upsert) vector ngữ cảnh bệnh nhân vào LanceDB.
    * Kết quả: Nếu User vừa cập nhật "Tôi bị cao huyết áp", 5 phút sau khi họ chat, `MedicalAgent` đã biết thông tin này để tư vấn cẩn thận hơn.