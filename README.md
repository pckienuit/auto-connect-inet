# Auto-Connect INET - Free WiFi

Công cụ tự động đăng nhập và duy trì kết nối WiFi **INET - Free WiFi** (captive portal AWING) trên Windows 10/11 — không cần mở trình duyệt, re-auth trong **~1-2 giây**.

## ✨ Tính năng

- **Auto-connect disconnected adapter:** Tự động phát hiện và kết nối lại các card mạng phụ (như USB WiFi) vào SSID `"INET - Free WiFi"` nếu bị ngắt kết nối hoặc lệch SSID.
- **Local Gate-check (Multi-NIC Bypass):** Giải quyết triệt để lỗi xung đột định tuyến (Routing Metric) trên Windows khi cắm song song card mạng chính (Pikachu) và card phụ (INET). Thay vì ping WAN (`detectportal`), script sẽ tự động kiểm tra trạng thái xác thực cục bộ qua cổng chào (`/status` và `/login`) của router.
- **Keepalive 1s:** Thread riêng ping/check trạng thái cổng chào mỗi 1 giây → phát hiện mất mạng cực nhanh.
- **Cached credentials:** Lưu username/password ra file `.creds_cache.json` → re-auth trực tiếp vào gateway cục bộ (~0.3s) không cần gọi cloud API.
- **Hỗ trợ ghi Log:** Xuất nhật ký hoạt động trực tiếp ra file `auto_connect_inet.log` để dễ dàng kiểm tra/debug khi chạy ngầm.
- **Tự động chạy khi bật máy:** Registry HKCU\Run — không cần admin, không dùng Scheduled Task.
- **Chạy ẩn hoàn toàn:** file `.exe` dạng `--noconsole`, RAM ~7MB.
- **Exponential backoff:** Nếu auth thực sự lỗi (do nhà mạng), tăng dần thời gian retry lên để tránh spam gateway.

## 📂 Cấu trúc

```
├── auto_connect_inet.py    # Source Python v3 (auto-reconnect + local gateway checks)
├── auto_connect_inet.exe   # Compiled binary (chạy ngầm)
├── install_v2.bat          # Cài đặt: Registry startup + launch
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

### V2 — Keepalive + Cached Credentials

```
keepalive thread (1s)           main loop
      │                            │
      ├─ ping detectportal ───────┤ (chờ event)
      │                            │
      ├─ [MẤT MẠNG!] ──────► event!
      │                            ├─ cached creds? → POST gateway (~0.3s) ✅
      │                            ├─ không?         → cloud API (~1-3s)
      │                            └─ online lại
```

1. **Cached credentials:** Sau lần login cloud đầu tiên, lưu username/password vào `.creds_cache.json`. Lần bị block kế tiếp POST thẳng vào gateway local — không cần chạm cloud.

2. **Background keepalive:** Thread riêng ping detectportal.firefox.com mỗi 1s (timeout 0.5s). Dùng `threading.Event` để đánh thức main loop ngay khi phát hiện mất mạng.

3. **Cloud API fallback:** Nếu cached creds hết hạn, gọi `v1.awingconnect.vn/Home/VerifyUrl` timeout 3s, parse form, lấy creds mới, cache lại.

### So sánh thời gian re-auth (mất mạng → có mạng lại)

```
Gốc (v0)   ████████████████████████████████████████  20-30s
V1         ██████████████                             5-10s
V2 này     ███                                        ~1-2s 🏁
```

## 📦 Links

- GitHub: https://github.com/pckienuit/auto-connect-inet
