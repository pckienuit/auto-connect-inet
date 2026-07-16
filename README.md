# Auto-Connect INET - Free WiFi

Bộ công cụ tự động duy trì phiên đăng nhập captive portal cho WiFi `INET - Free WiFi`. Repo gồm hai ứng dụng độc lập:

| Nền tảng | Mã nguồn | Cách hoạt động |
| --- | --- | --- |
| Windows 10/11 | `auto_connect_inet.py` | Tiến trình nền theo dõi card WiFi, kiểm tra gateway và đăng nhập lại khi cần. |
| Android 8.0+ | [`mobile/`](mobile/README.md) | Flutter UI điều khiển Kotlin foreground service, bind request vào đúng Android `Network`. |

Ứng dụng không thay thế trình quản lý WiFi của hệ điều hành. Thiết bị vẫn phải kết nối vào `INET - Free WiFi` trước khi công cụ có thể kiểm tra hoặc đăng nhập captive portal.

## Tính năng chính

### Windows

- Theo dõi nhiều card mạng và nhận diện đúng SSID mục tiêu.
- Kiểm tra phiên trực tiếp qua `/status` và `/login` của gateway thay vì dựa vào ping WAN.
- Bind socket vào IP của card WiFi để tránh sai route khi máy có nhiều NIC, VPN hoặc Tailscale.
- Lưu credential cache cục bộ để rút ngắn lần đăng nhập tiếp theo.
- Ghi log vào `auto_connect_inet.log` và ngăn chạy nhiều instance bằng local lock.
- Có thể đăng ký chạy cùng Windows qua `HKCU\Run`, không cần quyền Administrator.

### Android

- Foreground service tiếp tục theo dõi mạng khi đóng màn hình Flutter.
- Nhận diện SSID, IP cục bộ và gateway trên Android 8–15.
- Đăng nhập bằng cache mã hóa trong Android Keystore hoặc lấy phiên mới qua AWING.
- Dashboard hiển thị trạng thái, lịch retry, log đã che dữ liệu nhạy cảm và công cụ đo độ ổn định TCP.
- Khôi phục sau reboot ở mức best effort, tùy chính sách nền của từng hãng.

## Cấu trúc repo

```text
.
├── auto_connect_inet.py      # Ứng dụng Windows dạng Python
├── auto_connect_inet.exe     # Bản Windows đã đóng gói
├── install.bat               # Đăng ký startup và chạy bản Windows
├── test_download.py          # Tiện ích đo tải xuống
├── test_stability.py         # Tiện ích đo loss, latency và jitter
└── mobile/                   # Ứng dụng Flutter/Kotlin cho Android
```

## Windows

### Cài bản đóng gói

Đặt `install.bat` và `auto_connect_inet.exe` cùng thư mục, sau đó chạy:

```bat
install.bat
```

Script đăng ký executable vào `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, dừng instance cũ và chạy lại trong nền.

### Chạy từ mã nguồn

Project chỉ dùng Python standard library:

```powershell
python .\auto_connect_inet.py
```

Dữ liệu runtime được tạo cạnh executable/script và đã được Git bỏ qua:

- `.creds_cache.json`: credential cache; không chia sẻ file này.
- `auto_connect_inet.log`: log chẩn đoán.

### Gỡ startup

```bat
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v AutoConnectINET /f
taskkill /f /im auto_connect_inet.exe
```

## Android

Flutter project nằm trong `mobile`, vì vậy mọi lệnh Flutter phải chạy từ thư mục đó:

```powershell
cd mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

Build APK release tách theo CPU để giảm dung lượng:

```powershell
flutter build apk --release --split-per-abi
```

Với phần lớn điện thoại hiện nay, dùng:

```text
mobile/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk
```

Hướng dẫn quyền Android, cài APK, trạng thái daemon và xử lý sự cố nằm tại [`mobile/README.md`](mobile/README.md).

## Kiểm thử

```powershell
cd mobile
flutter analyze
flutter test
.\android\gradlew.bat -p android testDebugUnitTest
```

## Bảo mật và giới hạn

- Captive portal hiện vẫn dùng HTTP cleartext ở một phần luồng gateway/AWING; bên kiểm soát mạng có thể quan sát hoặc sửa lưu lượng này.
- Không commit credential cache, log, keystore hoặc mật khẩu ký APK.
- Android service, receiver và bridge không cung cấp API điều khiển công khai cho ứng dụng khác.
- Portal thay đổi schema hoặc chính sách có thể yêu cầu cập nhật parser/authenticator.

## Repository

- GitHub: https://github.com/pckienuit/auto-connect-inet
