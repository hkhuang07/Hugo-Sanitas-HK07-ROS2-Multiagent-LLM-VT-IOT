# CHUẨN KIẾN TRÚC VÀ QUY TRÌNH QUẢN LÝ DỰ ÁN (PROJECT ARCHITECTURE TEMPLATE)
**Dự án:** Robot Companion Hugo-Sanitas HK-07  
**Mã hiệu hệ thống:** HK.Huang07  
**Tiêu chuẩn vận hành:** Hyper-Autonomous Engine Mode  

Tài liệu này đóng vai trò là sơ đồ cấu trúc tối cao định nghĩa mối quan hệ giữa phân vùng tài liệu cấu hình (`docs/`) và phân vùng mã nguồn thực thi (`source/`). Tất cả các AI Agent hoặc hệ thống biên dịch tự động khi vận hành dự án bắt buộc phải tuân thủ nghiêm ngặt cấu trúc phân cấp này để đọc hiểu bối cảnh và thực thi mã nguồn chính xác.

---

## I. SƠ ĐỒ CÂY THƯ MỤC TOÀN CỤC (WORKSPACE TREE SYSTEM)

``` 
HK07_WORKSPACE/
├── docs/
│   ├── 00_init/                     # Khởi tạo dự án, yêu cầu hệ thống và phần cứng
│   │   ├── 00_readme.md             # Tầm nhìn cốt lõi và giới hạn hệ thống
│   │   ├── 01_project_requirements.md
│   │   ├── 02_idea_techstack.md
│   │   ├── 03_hardware_environment.md
│   │   ├── 04_startup_and_testing_guide.md
│   │   └── prompts/
│   │       └── CURSOR_BAYMAX_FULL_SYSTEM_BUILD.md # Prompt tối cao khởi tạo hệ thống
│   ├── 01_system_design/            # Bản thiết kế kỹ thuật chi tiết
│   │   ├── 00_multi_agent_architecture.md
│   │   ├── 01_project_architecture_template.md # Tài liệu này
│   │   ├── 02_api_design.md
│   │   ├── 03_dto_definitions.md
│   │   └── 04_enums.md
│   ├── 02_subsystems/               # Hướng dẫn vận hành & Changelog theo tầng
│   │   ├── backend/
│   │   │   ├── operations_manual.md
│   │   │   └── phase_01_foundation_changelog.md
│   │   ├── frontend/
│   │   │   ├── operations_manual.md
│   │   │   ├── ui_ux_design.md
│   │   │   └── phase_01_setup_changelog.md
│   │   ├── testing/
│   │   │   └── readme.md
│   │   └── deployment/
│   │       └── readme.md
│   ├── 03_evolution_specs/          # Đặc tả nâng cấp & Phân tích hệ thống qua các Phase
│   │   ├── 00_gap_analysis_and_evaluation.md
│   │   ├── 01_system_analysis_and_limitations.md
│   │   ├── 02_architecture_critique.md
│   │   ├── 03_auth_upgrade_v2.md
│   │   ├── 04_baymax_multimodal_upgrade.md
│   │   ├── 05_identity_medical_profile.md
│   │   ├── 06_hardware_twin_blueprint.md
│   │   ├── 07_phase13_kinematics_perception.md
│   │   ├── 08_phase14_physics_ik_ros2.md
│   │   ├── 09_phase15_decoupling_slam.md
│   │   ├── 10_phase18_21_multimodal_rtos.md
│   │   └── 11_phase22_real_vision_slm.md
│   ├── 04_walkthroughs/             # Báo cáo kết quả thử nghiệm và vận hành thực tế
│   │   ├── 00_gap_analysis_walkthrough.md
│   │   ├── 01_auth_upgrade_walkthrough.md
│   │   ├── 02_cognitive_upgrade_v2_walkthrough.md
│   │   ├── 03_baymax_multimodal_upgrade_walkthrough.md
│   │   └── 04_identity_medical_profile_walkthrough.md
│   └── MASTER_CHANGELOG.md          # Lịch sử thay đổi hệ thống cốt lõi
├── source/
│   ├── backend/                     # Mã nguồn logic xử lý dịch vụ Backend
│   └── frontend/                    # Mã nguồn giao diện hiển thị Client Dashboard
└── CLAUDE.md                        # Chỉ thị thực thi tối cao (Vòng lặp tự trị)
```

---

## II. ĐỊNH NGHĨA CHỨC NĂNG CÁC ĐẦU NÚT PHÂN TÁN (NODE FUNCTIONALITY)

### 1. Phân vùng Điều phối và Giám sát (`docs/00_init/` & `docs/01_system_design/`)
* **`00_init/`**: Thiết lập biên giới tài nguyên và ràng buộc phần cứng khắt khe.
* **`01_system_design/`**: Bản thiết kế kỹ thuật tổng thể, API, DTOs, Enums dùng chung giữa Backend và Frontend để đảm bảo tính đồng bộ dữ liệu.

### 2. Phân vùng Vận hành Subsystem (`docs/02_subsystems/`)
* Chia theo từng tầng công nghệ (Backend, Frontend, Testing, Deployment) chứa sổ tay vận hành chi tiết (`operations_manual.md`) và nhật ký thay đổi.

### 3. Phân vùng Tiến hóa hệ thống (`docs/03_evolution_specs/` & `docs/04_walkthroughs/`)
* **`03_evolution_specs/`**: Lưu trữ các đặc tả kiến trúc nâng cấp qua các phase từ Robot mô phỏng đến tích hợp ROS 2 DDS, Perception, rPPG, FHIR, Watchdog.
* **`04_walkthroughs/`**: Các file hướng dẫn xác thực và chạy demo kết quả kiểm thử sau khi hoàn thành mỗi phase.

---

## III. QUY TRÌNH PHÂN RÃ VÀ TỰ ĐỘNG HÓA TÁC VỤ (ENGINE PIPELINE RUNTIME)

Khi Động cơ Tự trị (Autonomous Engine) được kích hoạt, luồng xử lý mã nguồn bắt buộc phải tuân thủ nghiêm ngặt chuỗi tuần tự 7 bước không ngắt quãng:

```text
  [READ_DOC] ──> [ANALYSIS] ──> [MAKE PLAN] ──> [BUILD CODE] ──> [REVIEW] ──> [OPTIMALIZE] ──> [LOOP]
```

1. **`READ_DOC`**: Quét toàn bộ tệp tài liệu đặc tả của Phase mục tiêu trong `docs/` để thu thập yêu cầu nghiệp vụ.
2. **`ANALYSIS`**: Phân tích các ràng buộc về mặt kiến trúc, kiểm tra các lỗi biên có thể xảy ra và xác định cấu trúc dữ liệu.
3. **`MAKE_IMPLEMENTATION_PLAN`**: Khởi tạo một tệp kế hoạch tạm thời `.active_plan.tmp` chứa danh sách kiểm tra chi tiết các đoạn mã cần chỉnh sửa hoặc viết mới.
4. **`BUILD_CODE`**: Thực thi viết mã nguồn sạch, áp dụng thiết kế hướng đối tượng (SOLID) trực tiếp vào thư mục `source/`.
5. **`REVIEW_CODE_WITH_DOCUMENT`**: Tự động mở terminal trong nền, khởi chạy trình biên dịch và trình chạy kiểm thử (Unit Test) để xác thực tính đúng đắn của logic so với tài liệu đặc tả.
6. **`OPTIMALIZE`**: Kiểm tra rò rỉ bộ nhớ, tối ưu hóa các dòng lệnh chặn luồng (Blocking I/O), và đánh bóng các hiệu ứng chuyển động phần cứng giao diện.
7. **`GO_TO_LOOP`**: Ghi nhận trạng thái hoàn tất `[STATUS: DONE]`, cập nhật nhật ký thay đổi (`CHANGELOG.md`), giải phóng bộ nhớ đệm bối cảnh và tự động quay lại Bước 1 để tiếp quản Phase tiếp theo.
