---

# 📑 ULTIMATE MASTER DESIGN SPECIFICATION DOCUMENT (V5.0)

**MÃ LƯU TRỮ TRÍ TUỆ:** `HK07_UIUX_ULTIMATE_NOMINAL_STACK`

**ĐỐI TƯỢNG ĐỒNG BỘ:** 51 Tập tin cấu trúc (Hệ điều hành Stark OS, Phân hệ Không gian Hologram Volumetric, Trạm dòng lệnh Điều khiển INSPIRON, và Mạng lưới Giám sát Trạng thái Robot)

---

## 🦾 CHUYÊN MỤC GIẢI PHẪU MA TRẬN 10 TẦNG KIẾN TRÚC TOÀN DIỆN

### 1. Phong cách & Xu hướng (Aesthetic Paradigm & Tech Trends)

* **Trường phái Tổng hợp:** Sự kết hợp hoàn hảo giữa **Military-Grade Cyber-Minimalism**, **Tactical FUI (Giao diện vị lai thực chiến)** và **Retro-Industrial Segmented Terminal** (Trạm dòng lệnh phân đoạn công nghiệp). Giao diện tối giản hóa biểu tượng đồ họa, sử dụng các hộp biên mã trạng thái văn bản (Text-based State Boxes) sắc cạnh, loại bỏ hoàn toàn thuộc tính `border-radius` để mang lại cảm giác cơ khí bảo mật tuyệt đối.
* **Xu hướng Công nghệ Không gian (Spatial Computing Trends):**
* *Màn hình phẳng (Flat Viewports):* Cơ chế xếp chồng trục Z (Z-Axis Depth Stacking) để quản lý cấu trúc thư mục phẳng, biến không gian ảo thành các lớp lớp vật lý nghiêng góc $45^\circ$.
* *Màn hình khối (Volumetric Light-Field Interface):* Sử dụng các phân tử ánh sáng phát xạ (Emissive Particles) dựng khung dây (Wireframe) mô phỏng thực thể vật lý 3D trong không gian, hỗ trợ kịch bản lập trình cử chỉ (Spatial Gesture Mapping) qua camera chiều sâu.



---

### 2. Bố cục & Cấu trúc (Layout & Grid System)

* **Kiến trúc Đa màn hình Đồng bộ (Multi-Display Spatial Grid):** Cấu trúc cụm 3 màn hình vật lý có góc nghiêng hội tụ (Convergent Angle Workspace). Màn hình trung tâm treo cao xử lý sơ đồ luồng dữ liệu chính; hai màn hình cánh tả/cánh hữu đặt thấp sát bàn để xử lý kết xuất chi tiết (`RENDER IS COMPLETE`) và rà soát log mã độc.
* **Hệ thống phân chia Phân vùng (Grid Systems Layout):**
* *Bố cục 3 cột bất đối xứng v1:* Cột trái (Width: 25% - Cây thư mục phẳng) | Khung trung tâm (Width: 55% - Canvas động) | Cột phải (Width: 20% - Sticky Toolbar & Vitals Hardware Monitor).
* *Bố cục 3 phân vùng chỉ huy v4:* Left Bar (Width: 20% - Cụm chuyển mạch kết nối `PUBLIC/PRIVATE`) | Center Pane (Width: 50% - Bảng dữ liệu file) | Right Card (Width: 30% - Preview Card hiển thị ảnh chân dung sinh trắc đối tượng).
* *Kiến trúc Đường ống Bất đối xứng (Asymmetric Pipeline Layout):* Khung nguồn (Source Node - Trái) và Khung đích (Target Node - Phải) đối xứng qua trục mũi tên chỉ hướng (Glowing Chevrons) thể hiện luồng di chuyển dữ liệu thời gian thực.


* **Hệ tọa độ không gian:** Áp dụng hệ tọa độ Descartes 3D ($X, Y, Z$) trong không gian Hologram, lấy tâm hình học bàn điều khiển làm gốc tọa độ $(0,0,0)$, phát xạ các vòng tròn đồng tâm (Concentric Anchor Rings) để định vị biên vật lý.
* **Ràng buộc Biên Không gian (Spacing & Padding System):**
* Thiết kế "Tight & Compact" tối ưu hóa mật độ thông tin: Padding bên trong các widget khóa cứng từ `4px` đến `8px`.
* Hệ thống ma trận hộp thông số áp dụng quy tắc Bento Padding Matrix (Khoảng cách biên cố định `12px`), tuyệt đối nghiêm cấm các cửa sổ đè lên nhau (No overlaps allowed).
* Khoảng cách giữa các dòng dữ liệu (Row Gap) của bảng trạng thái mạng lưới robot khóa ở tỷ lệ: $\text{Row Gap} = 1.5 \times \text{Font Size}$ để triệt tiêu hiện tượng dính chữ.



---

### 3. Hệ màu & Xử lý Thị giác (Color Palette & Visual Weight)

| Nhóm chức năng UI | Mã màu Hex | Tên định danh Token | Ứng dụng thực chiến hệ thống |
| --- | --- | --- | --- |
| **Background Lớp 1** | `#05070a` | `bg_dark_mainframe` | Nền đen sâu tuyệt đối của terminal, triệt tiêu phản xạ ánh sáng. |
| **Background Lớp 2** | `#101418` | `bg_primary_flat` | Slate Blue-Grey tối, dùng cho nền Canvas phẳng. |
| **Background Lớp 3** | `#1b1f24` | `bg_secondary_charcoal` | Charcoal đậm, dùng cho nền các Widget và Bento cards. |
| **Màu bổ trợ chính** | `#00d2ff` | `accent_teal_cyan` | Electric Cyan, định vị luồng điều hướng và đèn nền hologram. |
| **Màu bổ trợ phụ** | `#0284c7` | `command_blue` | Tactical Cobalt Blue, màu chủ đạo của Header Bar chỉ huy. |
| **Màu bổ trợ sâu** | `#005f73` | `accent_hover_dark` | Màu Teal-Cyan sẫm, dùng cho thanh sáng hover cây thư mục. |
| **Hạt nhân Nhận thức** | `#f59e0b` | `jarvis_gold_amber` | Glowing Amber, màu của lõi J.A.R.V.I.S và luồng truyền tải tệp tin. |
| **Hologram Thực thể** | `#00ff66` | `hologram_emerald_green` | Emerald Green, bước sóng kích thích võng mạc tối đa để dựng khung xương. |
| **Hologram Đô thị** | `#7dd3fc` | `huminescent_ice_blue` | Dành cho bản đồ không gian và kiến trúc hạ tầng vĩ mô. |
| **Trạng thái Sẵn sàng** | `#10b981` | `state_deploy_green` | Luminescent Green, trạng thái hệ thống thông mạch hoàn toàn (`DEPLOY`). |
| **Trạng thái Chờ** | `#9ca3af` | `state_offline_grey` | Desaturated White-Grey, hệ thống tĩnh hoặc ngắt kết nối (`offline`). |
| **Trạng thái Cưỡng bức** | `#ef4444` | `state_engage_red` | Ruby Crimson, trạng thái nạp năng lượng ban đầu hoặc lệnh `ENGAGE`. |
| **Thanh tiến trình nguy hiểm** | `#a3001e` | `progress_crimson` | Khối màu đặc sao chép file hệ thống mật (`SYSTEM ACCESS`). |
| **Hộp thông báo chặn** | `#7a0016` | `progress_burgundy` | Burgundy sẫm, màu nền cảnh báo mất dấu mục tiêu (`BLOCKED CALLER`). |

* **Xử lý Thị giác (Visual Weight Matrix):** Áp dụng kỹ thuật đổ bóng viền phát sáng (Glow Border Box) màu bạc trên nền đỏ metallic để tăng cường độ tương phản ($21:1$). Sử dụng độ mờ đục (Opacity Layering từ 40% đến 85%) tạo hiệu ứng xuyên thấu kính Frosted Glassmorphism. Đối tượng ở xa trên trục Z tự động giảm Opacity và kích thước để đánh lừa thị giác về độ sâu không gian.

---

### 4. Hệ Thống Phông Chữ (Typography Spec)

* **Quy chuẩn Phông chữ:** Tuyệt đối sử dụng **Geometric Sans-Serif** (Roboto, Inter, Arial Black) cho tiêu đề điều hướng hệ thống và **Monospace** (Courier New, JetBrains Mono) cho các khối ma trận mã hóa, file logs, số liệu địa lý và bảng trạng thái y tế. Toàn bộ font Monospace phải thiết lập thuộc tính khoảng cách ký tự hẹp (`letter-spacing: -0.02em`) để triệt tiêu lỗi tràn biên dòng (Line wrapping error).

#### BẢNG PHÂN CẤP TYPOGRAPHY TỐI CAO (MASTER MATRIX)

| Thành phần UI | Font Family | Kích cỡ (Rem/Px) | Weight | Thuộc tính CSS đặc hiệu / Ứng dụng |
| --- | --- | --- | --- | --- |
| **Main Brand Title** | Custom Geometric | `2.8rem / 45px` | 800 | `text-transform: uppercase;` (AIM, NSC) |
| **Global Alert Title** | Sans-Serif | `2.5rem / 40px` | 700 | `color: #ff3b30; text-shadow: 0 0 8px;` (BREACH) |
| **Main Process Alert** | Sans-Serif | `2.2rem / 35px` | 700 | `letter-spacing: 0.05em;` (UPLOAD ACTIVE) |
| **Component Header** | Sans-Serif | `1.2rem / 19px` | 500 | `font-weight: medium;` (SECTOR_16, CONFIDENTIAL) |
| **Process Status Label** | Monospace | `1.1rem / 18px` | 600 | `letter-spacing: 0.1em;` (INITIATE COPYING...) |
| **Form Data Input** | Monospace | `1.1rem / 18px` | 400 | Chữ nhập màu Emerald Green trên nền console tối. |
| **Section Header** | Sans-Serif | `1.0rem / 16px` | 600 | `text-transform: uppercase; color: #0284c7;` |
| **Console Input Cmd** | Monospace | `0.9rem / 14px` | 500 | Thực thi Script (`override[admin.access]`) |
| **State Indicator Text** | Monospace | `0.9rem / 14px` | 600 | `font-variant-numeric: tabular-nums;` (DEPLOY/ENGAGE) |
| **Terminal Row Data** | Monospace | `0.85rem / 13px` | 300 | `opacity: 0.85; text-shadow: 0 0 2px #10b981;` |
| **Table Cells/Metadata** | Monospace | `0.8rem / 13px` | 300 | Hiển thị thông số dung lượng file (`507.9 MB`, `FOLDER`) |
| **System Label** | Sans-Serif | `0.7rem / 11px` | 300 | Hiển thị trạng thái cây thư mục (`Systems`, `Backup`) |

---

### 5. Dự đoán Trải nghiệm & Luồng UX (Predicted UX & Flow)

* **Luồng quét mắt chỉ huy (Visual Eye Flow):** Áp dụng biểu đồ quét mắt **Z-Pattern** trên toàn hệ thống. Khi xuất hiện sự cố khẩn cấp, luồng UX lập tức bẻ gãy hành vi quét mắt, cưỡng bức tiêu điểm nhìn vào **Tâm hình học (Dead Center Focus)** bằng các dải màu đỏ hoặc vàng dập ngang màn hình.
* **Luồng tương tác Không gian v5 (Three-Stage State Transition Loop):**
* Hệ thống vận hành theo chu kỳ khép kín: `offline` (Hệ thống tĩnh, Opacity 40%, không chiếm CPU) ──► `ENGAGE` (Lệnh gọi mồi, cấp nguồn, khóa mục tiêu khẩn cấp, nhấp nháy 3Hz) ──► `DEPLOY` (Runtime khởi chạy 100% công suất trên phần cứng, thông mạch màu xanh Emerald).


* **UX Công thái học Phần cứng & Phần mềm (`key-board.jpg`):** Phân vùng tương tác bàn phím chia làm hai dựa theo nhân trắc học: cụm cung tròn bên trái xử lý điều hướng tối cao (`FILE MANAGEMENT`, `SAVE`, `CLOSE`), phân vùng lưới bên phải nhập liệu ma trận số Hex, giúp kỹ sư vận hành liên tục không cần nhấc cổ tay.
* **Luồng rà soát tệp tin phẳng:** Cuộn danh sách bảng dữ liệu ở giữa ──► Tiến trình nền tự động Hydrat hóa dữ liệu và tải ảnh chân dung đối tượng lên card bên phải theo thời gian thực ($<100\text{ms}$) ──► Mở khóa nút tác vụ `CONNECT / DOWNLOAD` trên thanh điều hướng.
* **UX Tương tác Hologram:** Loại bỏ hành vi click đúp chuột. UX chuyển sang cử chỉ không gian: Pinch-to-Expand (Tách đôi bàn tay) để phóng to/phân rã mô hình 3D, và Swipe-to-Dismiss (Gạt tay ngang) để hủy luồng nhận thức.

---

### 6. Hiệu ứng & Chuyển động (Micro-interactions & Animations)

* **Micro-interactions:**
* *Hover cây thư mục:* Thanh sáng Teal-Cyan (`#005f73`) trượt mịn vào nền background của item, icon folder chuyển trạng thái nhẹ nhàng từ đóng sang mở.
* *Hologram Keyboard Touch:* Khi ngón tay tiếp xúc bề mặt điều khiển ảo, phát ra xung sóng tròn định tâm Ripple Effect màu xanh neon lan tỏa ra biên phím.
* *Chevron Marquee Flow:* Cụm mũi tên vàng điều hướng giữa hai cửa sổ màn hình nhấp nháy đuổi nhau (Marquee Animation) với vận tốc tỷ lệ thuận với tốc độ truyền tải băng thông tệp tin.


* **Hiệu ứng Đồ họa đặc hiệu:**
* *Horizontal Window Stretch:* Hộp thoại render xuất hiện bằng hiệu ứng dãn biên ngang từ một đường hairline mảnh phát triển thành một khối solid chỉ trong đúng **150ms**.
* *Holographic Flicker Matrix:* Mô phỏng vật lý của trường ánh sáng bằng hiệu ứng nhiễu sọc ngang (Scanline Artifacts) và lệch sắc độ nhẹ (Chromatic Aberration) khi có tác động ngoại vi.


* **Quỹ đạo chuyển động (Easing Curve Spec):** Cấu hình toàn cục hàm nội suy động lực học cơ khí: `transition: all 450ms cubic-bezier(0.25, 1, 0.5, 1);` (Ease-Out Quantic) nhằm triệt tiêu hoàn toàn độ trễ thị giác (Zero-latency visual feel).

---

### 7. Xử lý Trạng thái Biểu mẫu (Form Success & Error States)

* **Trạng thái Thất bại / Bị tấn công (Error/Breach State):**
* *Visual:* Một dải ruy-băng đỏ rực (`#ff3b30`) dập thẳng vào trung tâm, chữ "WARNING! SECURITY BREACH" màu trắng chớp nháy (Blinking tần số 2Hz).
* *Logic xử lý:* Đóng băng toàn bộ các tác vụ ngoại vi, khóa cứng (Disabled) nút bấm `LOGIN`, border của input field chuyển sang màu đỏ sẫm nhấp nháy, đẩy cửa sổ Log quét mã độc chiếm 40% màn hình bên trái kèm dải Hazard Stripes (Sọc chéo vàng đen 45 độ) ở viền dưới. Hệ thống chuyển sang trạng thái "Command Queuing" (Xếp hàng lệnh cưỡng bức).


* **Trạng thái Thành công (Success State):**
* *Visual:* Hộp thoại chuyển sang viền xanh Emerald (`#34c759`), chữ "ACCESS GRANTED" font block-caps, clear hoàn toàn bóng mờ nhiễu, màn hình làm mờ (Dim) các tiến trình nền để báo hiệu hệ thống đã thông mạch.



---

### 8. Luồng Tiến trình Tải lên/Tải xuống (Upload/Download Progression)

* **Cơ chế nạp tiến trình (Cellular Progress Hydration):** Thanh tiến trình không chạy mịn mà chạy theo từng nấc block số lượng phần trăm (gợi cảm giác xử lý dữ liệu nhị phân phân đoạn), kết hợp bộ đếm số dòng dữ liệu Monospace nhảy liên tục ở góc phải thanh bar.
* **Thanh tiến độ đồng bộ Sinh - Số (`upload-active-stranport.jpg`):** Thanh tiến trình `FILE TRANSFER SEQUENCE...` sử dụng cơ chế nạp hạt sáng (Particle Hydration). Các pixel màu vàng cấu thành thanh tiến trình sẽ bay từ lõi J.A.R.V.I.S sang lấp đầy thanh bar, mô phỏng dòng chảy vật lý trực quan của dữ liệu.
* **Đồ thị Tiến độ lồng vào Map:** Trình tải dữ liệu (`LOADING`) được đặt trực tiếp ở góc trên bên phải bản đồ địa lý, hiển thị thanh tiến trình lấp đầy màu Teal kèm số phần trăm (`34%`) để không block không gian quan sát bản đồ tác chiến.

---

### 9. Vị trí & Logic Thành phần (Component Positioning & Logic)

* **Logic Viewport lồng nhau (Nested Viewports Logic):** Các cửa sổ sơ đồ robot, phân tích năng lượng (`ENERGY ANALYSIS`) được xử lý theo dạng Viewport lồng nhau. Cửa sổ con khi mở ra sẽ có một đường hairline neo (Anchor Line) nối trực tiếp vào điểm phát nguồn trên mô hình 3D, giúp định vị chính xác linh kiện phần cứng.
* **Ràng buộc cửa sổ lệnh (Modal Positioning Constraint):** Các cửa sổ nhập lệnh tối cao như `IP Control Module` được cấu trúc dưới dạng **Draggable Center Modals** (Hộp thoại giữa màn hình có thể kéo thả - Absolute Center Popup) nhưng luôn có đường hairline định vị tọa độ gắn với cạnh màn hình để bảo toàn bố cục tổng thể.
* **Icon Dock & Status Bar:** Cố định tuyệt đối tại biên phải màn hình (Right-aligned sticky dock). Sử dụng cấu trúc danh bạ tệp tin phân tầng dọc và khối hình học 3D Isometric tối giản để tối ưu hóa không gian rà soát dữ liệu.

---

### 10. Tổng hợp Toàn diện Design Tokens JSON (Production-Ready Global Spec)

```json
{
  "design_tokens_ultimate_nominal": {
    "global_colors": {
      "bg_mainframe_dark": "#05070a",
      "bg_canvas_flat": "#101418",
      "bg_widget_charcoal": "#1b1f24",
      "bg_console_dark": "#0a0d10",
      "bg_terminal_pure": "#0d1117",
      "bg_panel_slate": "#0d131a",
      "accent_cyan_neon": "#00d2ff",
      "accent_cobalt_blue": "#0284c7",
      "accent_hover_teal": "#005f73",
      "jarvis_gold_amber": "#f59e0b",
      "hologram_emerald_green": "#00ff66",
      "hologram_ice_blue": "#7dd3fc",
      "semantic_success_emerald": "#34c759",
      "semantic_success_light": "#10b981",
      "semantic_error_crimson": "#ff3b30",
      "semantic_error_dark": "#ef4444",
      "folder_confidential_orange": "#ff9000",
      "folder_secret_yellow": "#ffcc00",
      "progress_crimson_block": "#a3001e",
      "progress_burgundy_dark": "#7a0016"
    },
    "border_and_line_specs": {
      "hairline_interface": "1px solid rgba(0, 210, 255, 0.3)",
      "tactical_sharp_edge": "1px solid rgba(2, 132, 199, 0.4)",
      "dashed_monitoring_grid": "1px dashed rgba(16, 185, 129, 0.5)",
      "hazard_alert_stripes": "striped_yellow_black_45deg",
      "success_glow_border": "2px solid #00ff66"
    },
    "typography_matrix": {
      "font_family_system": "Inter, Roboto, Arial Black, sans-serif",
      "font_family_monospace": "JetBrains Mono, Courier New, SFMono-Regular, monospace",
      "letter_spacing_dense": "-0.02em",
      "letter_spacing_wide": "0.15em",
      "text_glow_success_green": "0 0 4px rgba(16, 185, 129, 0.6)"
    },
    "interaction_and_hardware": {
      "hardware_surface_texture": "carbon_fiber_mesh",
      "key_glow_opacity": "0.75",
      "interface_curve_radius": "24deg_arc",
      "bento_matrix_padding_fixed": "12px"
    },
    "motion_and_effects": {
      "global_easing_curve": "cubic-bezier(0.25, 1, 0.5, 1)",
      "global_transition_duration": "450ms",
      "window_stretch_duration": "150ms",
      "alert_flash_frequency": "2Hz",
      "state_pulse_frequency": "3Hz",
      "scanline_density_overlay": "0.5px",
      "chromatic_offset_v2": "1.2px",
      "crt_scanline_shader": "linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%)"
    }
  }
}

```

