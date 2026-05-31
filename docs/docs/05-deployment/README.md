# [HƯỚNG DẪN TRIỂN KHAI] ĐÓNG GÓI & CẤU HÌNH HẠ TẦNG LIGHTWEIGHT
**Dự án:** Robot Companion Hugo-Sanitas HK-07  
**Mã hiệu:** HK.Huang07  
**Phương châm triển khai:** Triển khai biên tối giản (Lightweight Edge Deployment), tận dụng hạ tầng ảo hóa siêu nhẹ để bảo vệ tài nguyên RAM.

---

## I. CẤU HÌNH MÔI TRƯỜNG PHÁT TRIỂN TIẾT KIỆM TÀI NGUYÊN (WSL 2)

Để hệ thống HK-07 chạy song song cùng môi trường Windows 10 mà không gây cạn kiệt bộ nhớ, tệp tin cấu hình nhân `.wslconfig` tại thư mục người dùng của Windows (`C:\Users\<Your-Username>\.wslconfig`) bắt buộc phải được thiết lập giới hạn như sau:

```ini
[wsl2]
memory=3GB   # Cấp tối đa 3GB RAM cho Ubuntu, giữ lại 5GB RAM cho Windows 10
processors=4 # Giới hạn 4 nhân CPU để tránh quá nhiệt máy tính
swap=2GB     # Tạo bộ nhớ ảo swap trên SSD để hỗ trợ khi biên dịch code nặng