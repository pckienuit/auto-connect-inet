# Auto-Connect INET - Free WiFi

Công cụ tự động đăng nhập và duy trì kết nối WiFi **INET - Free WiFi** (captive portal AWING) trên Windows 10/11 — không cần mở trình duyệt, re-auth trong **~0.3 giây**.

## ✨ Tính năng

- **Auto-connect disconnected adapter:** Tự động phát hiện và kết nối lại các card mạng phụ (như USB WiFi) vào SSID `"INET - Free WiFi"` nếu bị ngắt kết nối hoặc lệch SSID.
- **Local Gate-check (Immune Mode):** Giải quyết triệt để lỗi xung đột định tuyến (Routing Metric) và lỗi bị VPN/Tailscale chặn/định tuyến nhầm gói tin kiểm tra mạng. Thay vì check ping WAN (`detectportal`), script V3.3 sẽ trực tiếp kiểm tra trạng thái session cục bộ qua cổng chào (`/status` và `/login`) của router. Nhờ đó, script hoạt động chính xác 100% ngay cả khi đang bật VPN/Tailscale.
- **Keepalive 0.5s (Gaming Mode):** Thread riêng kiểm tra trạng thái cổng chào mỗi 0.5 giây (timeout 300ms) → phát hiện mất mạng cực nhanh, re-auth tức thì để không gây khựng mạng khi chơi game đối kháng.
- **Proactive Refresh (Gia hạn chủ động 14 phút):** Tự động đếm ngược 14 phút kể từ lần xác thực thành công gần nhất. Script sẽ chủ động `/logout` và re-auth cực nhanh (~0.3s) trước khi router đá session ở phút thứ 15.
- **Nút bấm Refresh thủ công:** Bằng việc tích hợp Socket Listener ở cổng `49999`, bạn có thể nhấp đúp file `ProactiveRefresh.bat` ở Desktop để ép daemon chính tái xác thực ngay lập tức trước khi bắt đầu trận đấu (Lobby/Matchmaking).
- **Cached credentials:** Lưu username/password ra file `.creds_cache.json` → re-auth trực tiếp vào gateway cục bộ (~0.3s) không cần gọi cloud API.
- **Hỗ trợ ghi Log:** Xuất nhật ký hoạt động trực tiếp ra file `auto_connect_inet.log` để dễ dàng kiểm tra/debug khi chạy ngầm.
- **Tự động chạy khi bật máy:** Registry HKCU\Run — không cần admin, không dùng Scheduled Task.
- **Chạy ẩn hoàn toàn:** file `.exe` dạng `--noconsole`, RAM ~7MB.
- **Zero Backoff:** Khi chơi game, nếu auth thực sự lỗi (do nhà mạng), script sẽ liên tục thử lại sau mỗi 1 giây thay vì phạt đợi tăng dần, giúp khôi phục mạng nhanh nhất có thể.

## 📂 Cấu trúc

```
├── auto_connect_inet.py    # Source Python v3.3 (Proactive + Precise Gaming Mode)
├── auto_connect_inet.exe   # Compiled binary (chạy ngầm)
├── install.bat             # Cài đặt Registry startup + launch nhanh (Không cần Admin)
├── ProactiveRefresh.bat    # Phím tắt ép re-auth thủ công trước khi find trận
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

## 🔬 Cơ chế kỹ thuật

### V3.1 — Immune Mode & Gaming Mode (Keepalive + Local Gate-check)

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

1. **Auto-connect disconnected adapter:** Khác với V2 chỉ giám sát các interface đang kết nối, V3.1 chủ động gọi `netsh wlan connect` để hồi sinh các card mạng phụ/USB WiFi nếu chúng bị mất kết nối hoặc lệch SSID.

2. **Local Gate-check (Bypass VPN & Multi-NIC):** 
   - Ở bản V2, việc check internet sử dụng ping WAN (`detectportal.firefox.com`) bị lỗi khi chạy song song nhiều card mạng (do sai lệch Metric routing) hoặc khi đang bật VPN/Tailscale (gói tin ping bị VPN bắt đi làm script tưởng đã online).
   - Bản V3.1 chuyển sang truy vấn trực tiếp cổng chào cục bộ (`192.168.200.1` cổng 80). Do thuộc local subnet, gói tin này đi thẳng ra card mạng vật lý tương ứng mà không bị ảnh hưởng bởi VPN hay Metric. Nếu gateway trả về trang `/login` chứa form nhập → Xác định bị block. Nếu gateway trả về redirect `/status` hoặc timeout → Xác định đã ONLINE.

3. **Spam Cached Login (Fast Re-auth):** Khi re-auth, script sẽ gửi liên tiếp 3 request POST thông tin đăng nhập trong cache cách nhau 100ms để ép gateway xử lý lập tức, tăng độ tin cậy khi truyền tải gói tin không dây.

4. **Zero Backoff (Gaming Mode):** Không áp dụng thời gian phạt tăng dần (exponential backoff) khi auth fail. Script sẽ liên tục quét và thử lại sau mỗi 1 giây để khôi phục mạng nhanh nhất khi bác đang chơi game.

### So sánh thời gian re-auth (mất mạng → có mạng lại)

```
Gốc (v0)   ████████████████████████████████████████  20-30s
V1         ██████████████                             5-10s
V2         ███                                        ~1-2s
V3.1 này   █                                          ~0.3s (Gaming Mode) 🏁
```

## 📦 Links

- GitHub: https://github.com/pckienuit/auto-connect-inet
