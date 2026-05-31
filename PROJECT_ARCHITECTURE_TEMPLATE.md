Nội dung chi tiết và hoàn chỉnh của tệp **`PROJECT_ARCHITECTURE_TEMPLATE.md`** được thiết kế để định hình toàn bộ sơ đồ thư mục, phân cấp tính năng và quy trình điều phối cho hệ thống tự trị của robot **Hugo-Sanitas HK-07**.

Bạn có thể lưu nội dung này trực tiếp vào tệp ở thư mục gốc của dự án:

```markdown
# CHUẨN KIẾN TRÚC VÀ QUY TRÌNH QUẢN LÝ DỰ ÁN (PROJECT ARCHITECTURE TEMPLATE)
**Dự án:** Robot Companion Hugo-Sanitas HK-07  
**Mã hiệu hệ thống:** HK.Huang07  
**Tiêu chuẩn vận hành:** Hyper-Autonomous Engine Mode  

Tài liệu này đóng vai trò là sơ đồ cấu trúc tối cao định nghĩa mối quan hệ giữa phân vùng tài liệu cấu hình (`docs/`) và phân vùng mã nguồn thực thi (`source/`). Tất cả các AI Agent hoặc hệ thống biên dịch tự động khi vận hành dự án bắt buộc phải tuân thủ nghiêm ngặt cấu trúc phân cấp này để đọc hiểu bối cảnh và thực thi mã nguồn chính xác.

---

## I. SƠ ĐỒ CÂY THƯ MỤC TOÀN CỤC (WORKSPACE TREE SYSTEM)

``` 
HK07_WORKSPACE/
├── .claude/
│   └── settings.local.json          # Cấu hình siêu quyền lực và quy tắc tự trị của Agent
├── access/
│   └── logo.jpg                     # Tài nguyên đồ họa tĩnh, nhận diện thương hiệu
├── docs/
│   ├── 00-project-init/
│   │   ├── README.md                # Biên bản khởi tạo dự án, tầm nhìn cốt lõi
│   │   └── hardware-environment.md  # Định mức giới hạn phần cứng (RAM 8GB, CPU 1.6GHz)
│   ├── 01-system-design/
│   │   ├── backend/                 # Thiết kế cơ sở dữ liệu, sơ đồ luồng dữ liệu API
│   │   ├── frontend/                # Bản đặc tả hệ thống UI/UX Cyber-Cinematic
│   │   └── shared/                  # Định nghĩa các cấu trúc dữ liệu dùng chung (DTOs, Enums)
│   ├── 02-backend/
│   │   ├── phase-01-foundation/     # Khởi tạo khung mã nguồn và bộ lọc lỗi tập trung
│   │   ├── phase-02-auth/           # Hệ thống xác thực an toàn (JWT, phân quyền RBAC)
│   │   ├── phase-03-user-management/# Quản lý hồ sơ chủ nhân và cấu hình kết nối
│   │   ├── phase-04-timeline/       # Xử lý luồng bất đồng bộ dòng thời gian sức khỏe
│   │   ├── phase-05-announcements/  # Logic tạo và phê duyệt cảnh báo hệ thống
│   │   ├── phase-06-survey/         # Biểu mẫu khảo sát ý kiến và đánh giá tương tác
│   │   ├── phase-07-notifications/  # Quản lý thông báo thời gian thực qua MQTT
│   │   ├── phase-08-file-service/   # Xử lý lưu trữ hình ảnh và nhật ký tại biên
│   │   └── operations-manual.md     # Hướng dẫn vận hành luồng xử lý ngầm (RAM Wiping)
│   ├── 03-frontend/
│   │   ├── phase-01-setup/          # Khởi tạo Next.js/React và thư viện giao diện
│   │   ├── phase-02-auth/           # Màn hình xác thực sinh trắc học giả lập Terminal
│   │   ├── phase-03-layout/         # Khung giao diện chuẩn, Sidebar, thanh HUD không gian
│   │   ├── phase-04-timeline/       # Đồ thị sóng sinh tồn liên tục (ECG Canvas 60Hz)
│   │   ├── phase-05-announcements/  # Màn hình hiển thị danh sách cảnh báo khẩn cấp
│   │   ├── phase-06-survey/         # Giao diện biểu đồ đánh giá tâm lý người dùng
│   │   ├── phase-07-my-page/        # Trang cá nhân kết nối cấu hình robot
│   │   └── operations-manual.md     # Sổ tay kiểm soát hiệu năng hiển thị 60FPS
│   ├── 04-testing/
│   │   └── README.md                # Kịch bản Subsumption, Netcode và Stress Test RAM
│   ├── 05-deployment/
│   │   └── README.md                # Hướng dẫn Docker Multi-stage, Bootrom Read-Only
│   └── features/
│       ├── ai-features/             # Tích hợp tác nhân thông minh, tóm tắt dữ liệu y tế
│       ├── gamification/            # Cơ chế điểm thưởng thúc đẩy tương tác đồng hành
│       └── teams-integration/       # Đồng bộ thông báo sang các nền tảng công việc
├── source/
│   ├── backend/                     # Mã nguồn logic xử lý dịch vụ Backend
│   └── frontend/                    # Mã nguồn giao diện hiển thị Client Dashboard
├── .gitignore                       # Chặn rò rỉ token bí mật và file rác biên dịch
├── CLAUDE.md                        # Chỉ thị thực thi tối cao (Vòng lặp tự trị 7 bước)
├── PROJECT_ARCHITECTURE_TEMPLATE.md # Tài liệu kiến trúc này
└── PROJECT_REQUIREMENTS.md          # Đặc tả yêu cầu nghiệp vụ và kỹ thuật cốt lõi (PRD)

```
```
---

## II. ĐỊNH NGHĨA CHỨC NĂNG CÁC ĐẦU NÚT PHÂN TÁN (NODE FUNCTIONALITY)

Hệ thống được thiết kế theo nguyên lý **Microservices thu nhỏ**, trong đó mỗi thư mục trong cấu trúc đại diện cho một nút xử lý độc lập có ranh giới dữ liệu rõ ràng:

### 1. Phân vùng Điều phối và Giám sát (`docs/00-` & `docs/01-`)

* **`00-project-init/`**: Thiết lập biên giới tài nguyên. Ép hệ thống phải ghi nhớ ranh giới RAM vật lý còn lại rất thấp (`~3.3GB Khả dụng`) để tự động tối ưu hóa thuật toán biên dịch và quản lý luồng đệm.
* **`01-system-design/`**: Bản thiết kế kỹ thuật tổng thể. Nút `shared/` chứa toàn bộ các định nghĩa TypeScript Interfaces hoặc Java DTOs dùng chung để đảm bảo hai đầu hệ thống không bị lệch pha dữ liệu khi truyền tải qua các giao thức bất đồng bộ.

### 2. Phân vùng Triển khai Logic Nghiệp vụ (`docs/02-backend/` & `source/backend/`)

Chịu trách nhiệm thực thi các tác vụ xử lý nặng, điều phối AI và quản lý phần cứng qua 8 Phase độc lập. Tất cả dữ liệu ngắn hạn thu thập từ môi trường công cộng (như quét mạng Wi-Fi, lịch sử hội thoại tức thời tại quán cà phê) chỉ được phép lưu trữ trên RAM (`Volatile Memory`) và phải đăng ký tiến trình ngầm tại `operations-manual.md` để luồng dọn dẹp bộ nhớ (`RAM Wiping Job`) tự động giải phóng tài nguyên sau mỗi chu kỳ.

### 3. Phân vùng Giao diện Tương tác (`docs/03-frontend/` & `source/frontend/`)

Xây dựng bảng điều khiển giám sát sinh tồn theo phong cách **Cyber-Cinematic (Hacker-style)**. Sử dụng nền tối tuyệt đối (`#000000`) và văn bản đơn sắc phát sáng nhằm mô phỏng màn hình HUD không gian. Mọi module hiển thị phải áp dụng kỹ thuật ảo hóa danh sách (`List Virtualization`) tại Phase 04 để duy trì tốc độ khung hình ổn định 60 FPS trên máy trạm cấu hình thấp.

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
7. **`GO_TO_LOOP`**: Ghi nhận trạng thái hoàn tất `[STATUS: DONE]`, cập nhật nhật ký thay đổi (`CHANGELOG.md`), giải phóng bộ nhớ đệm bối cảnh và tự động quay lại Bước 1 để tiếp quản Phase tiếp theo trong danh sách.

---

## IV. NGUYÊN TẮC BẢO VỆ VÀ AN TOÀN KIẾN TRÚC

* **Tính cô lập tuyệt đối (Isolation Privilege):** Các Agent phát triển tính năng ở một Phase cụ thể không được tự ý can thiệp vào tệp tin của các Phase khác khi chưa có sự cho phép của Node điều phối trung tâm.
* **Cơ chế Tự chữa lành (Self-Healing Protocol):** Nếu bước `REVIEW_CODE_WITH_DOCUMENT` phát hiện lỗi biên dịch hoặc kiểm thử thất bại, hệ thống không được dừng lại. Nó phải tự động phân tích vết lỗi (Stack Trace) trong terminal, sửa lại mã nguồn và chạy lại quy trình kiểm tra tối đa 3 lần trước khi đưa ra cảnh báo bế tắc kỹ thuật.

```

```

### PROJECT_ARCHITECTURE_TEMPLATE.md

```markdown
# CHUẨN KIẾN TRÚC VÀ QUY TRÌNH QUẢN LÝ TÀI LIỆU DỰ ÁN (INTERNAL_SOCIAL)

Tài liệu này định nghĩa cấu trúc phân rã thư mục tài liệu (`docs/`) và mã nguồn (`source/`) nhằm phục vụ quy trình tự động hóa giao việc cho AI Agent. Tất cả các Agent khi tiếp nhận tác vụ bắt buộc phải tuân thủ nghiêm ngặt cấu trúc phân cấp này để đọc ngữ cảnh và ghi nhận trạng thái báo cáo (Logs).

---

## I. CẤU TRÚC ĐỒ THỊ THƯ MỤC TỔNG QUAN (TREE SYSTEM)

```text
INTERNAL_SOCIAL/
├── .claude/
│   └── settings.local.json
├── access/
│   └── logo.jpg
├── docs/
│   ├── 00-project-init/
│   │   └── README.md
│   ├── 01-system-design/
│   │   ├── backend/
│   │   ├── frontend/
│   │   └── shared/
│   ├── 02-backend/
│   │   ├── phase-01-foundation/
│   │   ├── phase-02-auth/
│   │   ├── phase-03-user-management/
│   │   ├── phase-04-timeline/
│   │   ├── phase-05-announcements/
│   │   ├── phase-06-survey/
│   │   ├── phase-07-notifications/
│   │   ├── phase-08-file-service/
│   │   └── operations-manual.md
│   ├── 03-frontend/
│   │   ├── phase-01-setup/
│   │   ├── phase-02-auth/
│   │   ├── phase-03-layout/
│   │   ├── phase-04-timeline/
│   │   ├── phase-05-announcements/
│   │   ├── phase-06-survey/
│   │   └── phase-07-my-page/
│   │   └── operations-manual.md
│   ├── 04-testing/
│   │   └── README.md
│   ├── 05-deployment/
│   │   └── README.md
│   └── features/
│       ├── ai-features/
│       ├── gamification/
│       └── teams-integration/
├── source/
│   ├── backend/
│   └── frontend/
├── .gitignore
├── CLAUDE.md
├── PROJECT_ARCHITECTURE_TEMPLATE.md
└── PROJECT_REQUIREMENTS.md

```
```
---

## II. ĐỊNH NGHĨA CHI TIẾT CHỨC NĂNG TỪNG NODE (DANH CHO AI AGENT)

### 1. Phân vùng Quản lý Cấu hình Hệ thống (`.claude/` & Gốc)

* `.claude/settings.local.json`: Lưu trữ các biến môi trường tại biên (Local Environment Settings) và quyền hạn (permissions) của Agent khi thao tác trên máy trạm.
* `CLAUDE.md`: File chỉ thị tối cao cho AI Coding Assistant, chứa các lệnh build, test nhanh và các quy tắc đặc thù của dự án (Coding Guidelines).
* `PROJECT_REQUIREMENTS.md`: Tài liệu đặc tả yêu cầu nghiệp vụ gốc từ khách hàng/người dùng.

### 2. Phân vùng Tài liệu Khởi tạo và Thiết kế hệ thống (`docs/00-` & `docs/01-`)

* `00-project-init/README.md`: Ghi lại biên bản khởi tạo dự án, thông tin công nghệ (Tech Stack) tổng quan và sơ đồ phân chia nhân sự/Agent.
* `01-system-design/`: Kiến trúc hệ thống chi tiết (System Architecture) chia làm 3 node phụ độc lập hoàn toàn:
* `backend/`: Thiết kế cơ sở dữ liệu (ERD), sơ đồ luồng dữ liệu (Data Flow Diagram), kiến trúc API Endpoint (Swagger/OpenAPI).
* `frontend/`: Sơ đồ luồng màn hình (Screen Flow), giải pháp quản lý trạng thái toàn cục (State Management).
* `shared/`: Định nghĩa các cấu trúc dữ liệu dùng chung (DTOs, Types, Enums) giữa hai đầu hệ thống để đảm bảo tính đồng bộ tuyệt đối.



### 3. Phân vùng Triển khai Logic Nghiệp vụ Backend (`docs/02-backend/`)

Chia nhỏ thành 8 giai đoạn phát triển độc lập (Phân rã dạng Micro-tasks):

* `phase-01-foundation`: Khởi tạo khung mã nguồn (Boilerplate), cấu hình cơ sở dữ liệu, bộ lọc lỗi tập trung (Global Exception Handler).
* `phase-02-auth`: Thiết lập hệ thống xác thực an toàn (JWT, mã hóa bảo mật, phân quyền RBAC).
* `phase-03-user-management`: Quản lý thông tin tài khoản, cập nhật hồ sơ, phân chia vai trò người dùng.
* `phase-04-timeline`: Xử lý thuật toán bất đồng bộ hiển thị dòng thời gian (Bảng tin mạng nội bộ).
* `phase-05-announcements`: Logic tạo, duyệt và phát hành các thông báo chính thức từ ban quản trị.
* `phase-06-survey`: Hệ thống khảo sát ý kiến trực tuyến, xử lý biểu mẫu động.
* `phase-07-notifications`: Module quản lý thông báo thời gian thực (Real-time Push Notifications).
* `phase-08-file-service`: Hệ thống lưu trữ, xử lý tải lên/xuống (Upload/Download) hình ảnh, tài liệu.
* `operations-manual.md`: Sổ tay hướng dẫn vận hành, khởi chạy các luồng xử lý ngầm (Background Jobs) của Backend.

### 4. Phân vùng Triển khai Giao diện Người dùng (`docs/03-frontend/`)

Chia nhỏ thành 7 giai đoạn độc lập tương ứng:

* `phase-01-setup`: Khởi tạo mã nguồn Frontend, cấu hình thư viện UI, cài đặt Router và bộ lọc HTTP Client.
* `phase-02-auth`: Giao diện trang Đăng nhập, Đăng ký, Đổi mật khẩu và các Router bảo vệ (Protected Routes).
* `phase-03-layout`: Thiết lập khung giao diện chuẩn (Sidebar, Navbar, Footer, cấu trúc Layout thích ứng).
* `phase-04-timeline`: Giao diện bảng tin nội bộ, các tương tác cuộn vô hạn (Infinite Scroll).
* `phase-05-announcements`: Giao diện danh sách và chi tiết các bảng thông báo quan trọng.
* `phase-06-survey`: Biểu mẫu hiển thị câu hỏi khảo sát và đồ thị trực quan hóa kết quả.
* `phase-07-my-page`: Giao diện trang cá nhân của người dùng, tích hợp quản lý thông tin riêng tư.

### 5. Phân vùng Kiểm thử, Đóng gói & Tính năng mở rộng (`04-`, `05-` & `features/`)

* `04-testing/README.md`: Quản lý kịch bản kiểm thử tự động (Unit Test, Integration Test, End-to-End Test).
* `05-deployment/README.md`: Hướng dẫn đóng gói ứng dụng (Dockerfile/Docker-Compose) và quy trình thiết lập tự động hóa CI/CD.
* `features/`: Các Module nâng cao chạy độc lập, sẵn sàng tích hợp khi các Phase cốt lõi hoàn thành:
* `ai-features/`: Module tích hợp Trí tuệ nhân tạo (Tự động tóm tắt thông báo, đề xuất nội dung).
* `gamification/`: Cơ chế tính điểm thưởng, huy hiệu thúc đẩy tương tác nội bộ.
* `teams-integration/`: Đồng bộ thông báo và dữ liệu sang các nền tảng làm việc nhóm như Microsoft Teams / Slack.



---

## III. QUY TRÌNH TỰ ĐỘNG HÓA GIAO VIỆC VÀ PHÂN RÃ TÁC VỤ (AI AGENT WORKFLOW)

Khi phân việc cho AI Agent, quy trình xử lý bắt buộc phải tuân theo 3 bước tuần tự sau để tránh xung đột hệ thống:

```text
[BƯỚC 1: Đọc tài liệu thiết kế tổng quan (docs/01-system-design/)]
                   │
                   ▼
[BƯỚC 2: Kiểm tra Phase mục tiêu cần triển khai (docs/02- hoặc docs/03-)]
                   │
                   ▼
[BƯỚC 3: Viết mã nguồn vào thư mục đích (source/) và cập nhật kết quả vào Phase tương ứng]

```

1. **Quy tắc cập nhật tài liệu:** Trước khi tiến hành viết code trong thư mục `source/`, Agent phải cập nhật một file `CHANGELOG.md` hoặc thêm phần trạng thái `[STATUS: IN PROGRESS / DONE]` vào file `README.md` của chính thư mục Phase đó.
2. **Quy tắc độc lập:** Mỗi Agent khi được giao một Phase cụ thể (Ví dụ: `docs/02-backend/phase-02-auth/`) không được tự ý sửa đổi tệp tin thuộc các thư mục Phase khác trừ khi có chỉ thị từ Node điều phối trung tâm.

```

---

## IV. CÁCH LỆNH PROMPT ĐỂ THÍCH KÍCH HOẠT VÀ RA LỆNH CHO AI AGENT

Khi bạn bắt đầu một phiên làm việc mới trên một IDE như **Cursor**, **VS Code (với Cline/Roo Code)** hoặc giao tiếp với **Claude**, hãy paste câu lệnh sau cùng với file mẫu ở trên để AI tự động thiết lập tư duy:

> *"Hãy đọc file `PROJECT_ARCHITECTURE_TEMPLATE.md` tôi vừa cung cấp để nắm toàn bộ cấu trúc phân rã thư mục của dự án này. Từ bây giờ, bạn đóng vai trò là một AI Agent Lead. Khi tôi giao bất kỳ nhiệm vụ nào, bạn phải tự động xác định xem nhiệm vụ đó thuộc về **Phase số mấy** của **Backend** hay **Frontend**, kiểm tra thiết kế trong `docs/01-system-design/`, sau đó mới triển khai code vào thư mục `source/`. Sau khi hoàn thành, bạn phải tự động ghi lại báo cáo tiến độ vào file tài liệu của Phase đó để bàn giao cho Agent tiếp theo. Bạn đã hiểu rõ quy trình chưa?"*

Tư duy phân rã tài liệu cực kỳ ngăn nắp này của bạn chính là nền tảng cốt lõi của các hệ thống doanh nghiệp chuẩn **Clean Architecture** và cũng là môi trường lý tưởng nhất để các AI Agent vận hành mượt mà mà không lo bị quá tải hay "lạc hướng" ngữ cảnh (lost in context).

```