# Auto-Connect INET - Free WiFi

Công cụ tự động đăng nhập và duy trì kết nối WiFi **INET - Free WiFi** (captive portal AWING) trên Windows 10/11 — không cần mở trình duyệt, re-auth trong **~0.3 giây**.

## ✨ Tính năng

- **Auto-connect disconnected adapter:** Tự động phát hiện và kết nối lại các card mạng phụ (như USB WiFi) vào SSID `"INET - Free WiFi"` nếu bị ngắt kết nối hoặc lệch SSID.
- **Local Gate-check (Immune Mode):** Giải quyết triệt để lỗi xung đột định tuyến (Routing Metric) và lỗi bị VPN/Tailscale chặn/định tuyến nhầm gói tin kiểm tra mạng. Thay vì check ping WAN (`detectportal`), script V3.2 sẽ trực tiếp kiểm tra trạng thái session cục bộ qua cổng chào (`/status` và `/login`) của router. Nhờ đó, script hoạt động chính xác 100% ngay cả khi đang bật VPN/Tailscale.
- **Keepalive 0.5s (Gaming Mode):** Thread riêng kiểm tra trạng thái cổng chào mỗi 0.5 giây (timeout 300ms) → phát hiện mất mạng cực nhanh, re-auth tức thì để không gây khựng mạng khi chơi game đối kháng.
- **Cached credentials:** Lưu username/password ra file `.creds_cache.json` → re-auth trực tiếp vào gateway cục bộ (~0.3s) không cần gọi cloud API.
- **Hỗ trợ ghi Log:** Xuất nhật ký hoạt động trực tiếp ra file `auto_connect_inet.log` để dễ dàng kiểm tra/debug khi chạy ngầm.
- **Tự động chạy khi bật máy:** Registry HKCU\Run — không cần admin, không dùng Scheduled Task.
- **Chạy ẩn hoàn toàn:** file `.exe` dạng `--noconsole`, RAM ~7MB.
- **Zero Backoff:** Khi chơi game, nếu auth thực sự lỗi (do nhà mạng), script sẽ liên tục thử lại sau mỗi 1 giây thay vì phạt đợi tăng dần, giúp khôi phục mạng nhanh nhất có thể.

## 📂 Cấu trúc

```
├── auto_connect_inet.py    # Source Python v3.2 (Precise Gaming Mode)
├── auto_connect_inet.exe   # Compiled binary (chạy ngầm)
├── install.bat             # Cài đặt Registry startup + launch nhanh (Không cần Admin)
├── test_stability.py       # Đo ping jitter, loss và chấm điểm đấu game
├── test_download.py        # Test băng thông
├── README.md
└── .gitignore
```

## 🚀 Cài đặt

### Nhanh: Chạy `install_v2.bat` (nhấp đúp)
→ Tự đăng ký Registry + launch ngay.

### Thủ công (nếu muốn):

```cmd
:: Thêm vào startup
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Run ^
  /v AutoConnectINET /t REG_SZ /d "D:\auto-connect-inet\auto_connect_inet.exe" /f

:: Chạy ngay
start /B "" "D:\auto-connect-inet\auto_connect_inet.exe"
```

## 🗑️ Gỡ cài đặt

```cmd
reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v AutoConnectINET /f
taskkill /f /im auto_connect_inet.exe
rd /s /q D:\auto-connect-inet
```

## 🔬 Cơ chế kỹ thuật qua các phiên bản

### 1. Phiên bản gốc (V1.0 - Single Interface Setup)
* **Check Internet:** Thực hiện request HTTP GET tuần tự đến `neverssl.com` trong vòng lặp chính.
* **Thời gian Re-auth:** Khá chậm (~5-10s) do bị block đồng bộ trong luồng chính và phải đợi cloud API phản hồi mỗi lần.
* **Điểm yếu:** Chỉ theo dõi card mạng đang chạy, nếu card WiFi bị rớt kết nối vật lý thì script hoàn toàn mất tác dụng.

### 2. Phiên bản cải tiến (V2.0 - Keepalive & Credentials Cache)
* **Check Internet:** Sử dụng thread riêng để ping `detectportal.firefox.com` (timeout 0.5s) định kỳ mỗi 1s. Truyền tín hiệu re-auth thông qua `threading.Event`.
* **Đăng nhập nhanh:** Sau lần đầu xác thực với cloud API thành công, credentials được lưu vào `.creds_cache.json` để tự động POST thẳng vào gateway cục bộ ở lần tiếp theo, giảm thiểu thời gian re-auth xuống còn **~1-2s**.
* **Hạn chế:** Bị lỗi báo ONLINE giả nếu bật VPN/Tailscale Exit Node (gói check WAN ping bị định tuyến xuyên qua VPN) hoặc lỗi xung đột định tuyến (Metric) khi cắm 2 card mạng song song.

### 3. Phiên bản Gaming Mode (V3.2 - Precise local checks & Spam auth)
* **Check Internet (Precise local checks):** Loại bỏ ping WAN, chuyển sang check trực tiếp cổng chào cục bộ (`192.168.200.1`). Nhận diện chính xác trạng thái online/offline bằng cách so khớp tên miền thành công (`inetcenter.vn`) và form nhập `/login` (tránh bypass của VPN/Tailscale).
* **Gaming Keepalive (500ms):** Tần suất check tăng lên mỗi 0.5s, timeout 300ms.
* **Spam Auth:** Khi mất mạng, spam POST credentials liên tiếp 3 lần cách nhau 100ms để ép gateway xử lý.
* **Zero Backoff:** Bỏ hoàn toàn án phạt chờ đợi re-auth (exponential backoff) để đảm bảo re-auth liên tục mỗi 1 giây cho đến khi mạng hồi phục. Thời gian re-auth giảm xuống còn **~0.3s**.

### 4. Phiên bản hiện tại (V3.2 - Precise Gaming Mode Restored)
* **Check Internet (Precise local checks):** Loại bỏ hoàn toàn ping WAN, chuyển sang check trực tiếp cổng chào cục bộ (`192.168.200.1`). Nhận diện chính xác trạng thái online/offline bằng cách so khớp tên miền thành công (`inetcenter.vn`) và form nhập `/login` (tránh bypass của VPN/Tailscale).
* **Gaming Keepalive (500ms):** Tần suất check tăng lên mỗi 0.5s, timeout 300ms.
* **Spam Auth:** Khi mất mạng, spam POST credentials liên tiếp 3 lần cách nhau 100ms để ép gateway xử lý.
* **Zero Backoff:** Bỏ hoàn toàn án phạt chờ đợi re-auth (exponential backoff) để đảm bảo re-auth liên tục mỗi 1 giây cho đến khi mạng hồi phục. Thời gian re-auth giảm xuống còn **~0.3s**.

```
keepalive thread (0.5s)          main loop
      │                            │
      ├─ Local gateway check ─────┤ (chờ event)
      │  (/status & /login)        │
      │                            │
      ├─ [MẤT MẠNG / BLOCKED] ────► event!
      │                            ├─ cached creds? → POST gateway (~0.3s) ✅
      │                            │                 (Spam 3 lần để ép auth)
      │                            ├─ không?         → cloud API (~1-3s)
      │                            └─ online lại (Bỏ backoff, retry 1s)
```

### So sánh hiệu năng re-auth qua các phiên bản

```
Gốc (v1.0) ████████████████████████████████████████  20-30s
V2.0       ██████████████                             5-10s
V3.2 này   █                                          ~0.3s (Gaming Mode) 🏁
```

## 📦 Links

- GitHub: https://github.com/pckienuit/auto-connect-inet
