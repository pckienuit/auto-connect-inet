# Auto-Connect INET - Free WiFi

Tự động duy trì phiên captive portal cho WiFi `INET - Free WiFi`. Repo gồm ba ứng dụng:

| Nền tảng | Mã nguồn | Cách hoạt động |
| --- | --- | --- |
| Windows 10/11 x64 | `auto_connect_inet.py`, `auto_connect_inet.exe` | Theo dõi card Wi-Fi, kiểm tra WAN, đăng nhập lại khi có challenge portal. |
| Linux với NetworkManager | `auto_connect_inet_linux.py` | Daemon Python, theo dõi NetworkManager và hỗ trợ systemd user service. |
| Android 8.0+ | [`mobile/`](mobile/README.md) | Flutter UI điều khiển Kotlin foreground service, bind request vào đúng Android `Network`. |

Windows không thay thế trình quản lý Wi-Fi: cần kết nối vào SSID trước. Linux mặc định không đổi mạng khi máy chỉ có một card Wi-Fi; nhánh nhiều card có thể kết nối lại card phụ. Không bảo đảm phục hồi dưới một giây.

## Windows

### Cài bản đóng gói

Đặt `install.bat` và `auto_connect_inet.exe` cùng thư mục có quyền ghi, rồi chạy:

```bat
install.bat
```

Installer đăng ký `.exe` vào `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, dừng instance cũ và khởi chạy lại. Không cần Administrator. Startup chạy sau khi đăng nhập Windows, không phải Windows service.

Binary trong repo đã build lại từ source hiện tại bằng **Windows Python 3.12.10 + PyInstaller 6.16.0 dưới Wine**, dạng **x64 / onefile / noconsole**. Test logic chạy bằng Windows Python dưới Wine; smoke test binary xác minh khởi động và thoát an toàn khi lock đã được giữ. Chưa xác minh captive portal, nhận diện card và startup trên Windows thật.

### Chạy source

Runtime chỉ dùng Python standard library:

```powershell
python .\auto_connect_inet.py
```

### Logic phục hồi

- Nhận diện SSID mục tiêu trên nhiều card qua `netsh` và `ipconfig`; parser hiện dựa vào output tiếng Anh.
- Probe WAN Firefox, dự phòng Microsoft; yêu cầu HTTP `200` và body đúng. Không dùng `200/302` từ gateway làm bằng chứng có Internet.
- Probe thất bại hai lượt mới kiểm tra challenge captive portal. Không POST khi gateway không có bằng chứng portal.
- Ưu tiên cache, tính CHAP mới theo challenge hiện tại. Chỉ xóa cache khi bị từ chối rõ ràng; giữ cache khi timeout hoặc kết quả chưa rõ.
- Bind gateway, WAN probe và AWING vào IP card Wi-Fi; bỏ proxy môi trường cho luồng này.
- Một loop sở hữu probe/auth. Chu kỳ online khoảng 2 giây cộng thời gian gọi mạng; backoff sau lỗi auth là 5, 10, 20, tối đa 30 giây. Deadline dùng đồng hồ monotonic, tính sau request.
- Reset trạng thái khi IP/gateway thay đổi. Cache ghi thay thế nguyên tử; parser HTTP hỗ trợ chunked và giới hạn kích thước body.
- Lock loopback port `49999` ngăn chạy nhiều instance.

### Build lại trên Windows

```powershell
python -m pip install pyinstaller==6.16.0
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name auto_connect_inet auto_connect_inet.py
```

Kết quả: `dist\auto_connect_inet.exe`. Thay binary cũ cạnh `install.bat`, chạy lại installer để dừng bản cũ và nạp bản mới. Đây là build không ký số.

### Gỡ startup

```bat
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v AutoConnectINET /f
taskkill /f /im auto_connect_inet.exe
```

## Linux

### Yêu cầu

Python 3, NetworkManager (`nmcli`), `iproute2` (`ip`), `iw`. Cài daemon cần systemd user session. Python không cần package bên thứ ba.

```bash
# Ubuntu / Debian, nếu chưa có các công cụ hệ thống
sudo apt install python3 network-manager iproute2 iw
```

### Chạy và kiểm tra

```bash
python3 auto_connect_inet_linux.py --status
python3 auto_connect_inet_linux.py --daemon
```

`--status` chỉ kiểm tra. `--once` có thể đăng nhập portal:

```bash
python3 auto_connect_inet_linux.py --once
python3 auto_connect_inet_linux.py --daemon --ssid "INET - Free WiFi"
```

Không chạy `--once` đồng thời với daemon: lock hiện chỉ nằm ở chế độ daemon, chạy cùng lúc có thể gửi auth trùng.

### Tự chạy với systemd

Đặt repo ở đường dẫn ổn định, không có dấu cách, có quyền ghi. Lệnh sau ghi unit cho user hiện tại, enable và start:

```bash
python3 auto_connect_inet_linux.py --install-service
systemctl --user status auto-connect-inet.service
journalctl --user -u auto-connect-inet.service -n 50 --no-pager
```

Unit dùng đường dẫn tuyệt đối tới Python và source lúc cài. Di chuyển repo hoặc đổi Python cần cài lại unit. Service dùng `Restart=always`, `RestartSec=5`; chạy theo user session, không mặc định bảo đảm hoạt động trước đăng nhập. Nếu daemon đã chạy khi cập nhật source, restart riêng để nạp code mới:

```bash
systemctl --user restart auto-connect-inet.service
```

Gỡ tự chạy:

```bash
systemctl --user disable --now auto-connect-inet.service
rm ~/.config/systemd/user/auto-connect-inet.service
systemctl --user daemon-reload
```

### Phạm vi và giới hạn bản Linux

Bản Linux trong repo là source đang được dùng trên máy Linux, kèm test hồi quy. Có dual WAN probe, cache-first CHAP, portal gate, backoff tối đa 30 giây và thread `nmcli device monitor` chỉ đánh thức một loop auth.

Không đồng nhất hoàn toàn với Windows mới; chưa mang các sửa parser Windows sang Linux:

- WAN probe Linux dùng parser socket thủ công, có thể nhận sai response HTTP chunked thành offline.
- Khi có nhiều default route, Linux có fallback theo marker gateway; đó không phải bằng chứng WAN độc lập.
- Nhánh reconnect nhiều card vẫn so tên connection profile và chưa áp dụng allowlist AP đầy đủ trong loop cuối. Thận trọng với profile đổi tên, nhiều card hoặc hotspot AP.
- `--force-connect` cho phép đổi cả Wi-Fi chính. Không dùng khi đang cần giữ uplink khác.

## Android

- Foreground service theo dõi mạng khi đóng màn hình Flutter.
- Nhận diện SSID, IP và gateway trên Android 8–15.
- Cache mã hóa bằng Android Keystore; request bind theo Android `Network`.
- Dashboard có trạng thái daemon, retry, log che dữ liệu nhạy cảm và công cụ đo độ ổn định TCP.
- Khôi phục sau reboot ở mức best effort, tùy chính sách nền từng hãng.

Chạy lệnh Flutter từ `mobile/`:

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

Build APK:

```bash
flutter build apk --release --split-per-abi
```

Điện thoại ARM64 thường dùng `mobile/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk`. Hướng dẫn quyền và chẩn đoán: [`mobile/README.md`](mobile/README.md).

## Cấu trúc repo

```text
.
├── auto_connect_inet.py          # Windows source
├── auto_connect_inet.exe         # Windows x64 binary
├── auto_connect_inet_linux.py    # Linux / NetworkManager daemon
├── install.bat                   # Windows HKCU startup installer
├── test_windows_logic.py         # Windows logic + localhost HTTP fixtures
├── test_linux_logic.py           # Linux logic fixtures
├── test_download.py              # Tiện ích tải xuống, dùng mạng thật
├── test_stability.py             # Tiện ích đo mạng thật
└── mobile/                       # Flutter / Kotlin Android
```

## Kiểm thử

Từ thư mục gốc repo:

```bash
python -B -m unittest test_windows_logic test_linux_logic -v
```

Windows có 27 test, Linux có 29 test. Fixture thay lệnh hệ điều hành và request bên ngoài; test Windows có HTTP server localhost để kiểm cookie AWING, CHAP và source binding thật. Test không đổi Wi-Fi hay đăng nhập portal thật. Không dùng unittest discovery rộng vì các tiện ích đo mạng không thuộc suite offline.

Kết quả kiểm tại bản cập nhật này: 27 test Windows pass trên Linux và Windows Python dưới Wine; 29 test Linux pass trên Linux. Chưa chạy test Linux dưới Windows; chưa smoke test Windows thật. Android không đổi trong bản cập nhật, không chạy lại suite Android.

Android:

```powershell
cd mobile
flutter analyze
flutter test
.\android\gradlew.bat -p android testDebugUnitTest
```

## Dữ liệu runtime và bảo mật

- `.creds_cache.json` và `auto_connect_inet.log` nằm cạnh source/executable, được Git bỏ qua. Không chia sẻ hoặc commit các file này.
- Cache Windows/Linux là JSON plaintext, không mã hóa. Linux ghi mode `0600`; trên Windows quyền đọc phụ thuộc ACL thư mục. Dùng thư mục riêng của user.
- Không chạy hai bản Windows/Linux dùng chung cache hoặc cùng gateway. Lock `49999` ngăn hai daemon trên cùng host, không bảo vệ lệnh Linux `--once`.
- Một phần luồng gateway/AWING dùng HTTP cleartext. Bên kiểm soát mạng có thể quan sát hoặc sửa lưu lượng; source binding không cung cấp mã hóa hay xác thực gateway.
- Không commit keystore, mật khẩu ký APK hoặc log. Android service, receiver và bridge không cung cấp API điều khiển công khai cho app khác.
- Portal đổi schema/chính sách có thể cần cập nhật parser hoặc authenticator.

## Repository

https://github.com/pckienuit/auto-connect-inet
