# INET Auto Login cho Android

Ứng dụng Flutter điều khiển Kotlin foreground service để theo dõi `INET - Free WiFi` và duy trì phiên captive portal AWING/MikroTik. Service hoạt động độc lập với màn hình Flutter, không dùng VPN, proxy hoặc root.

## Yêu cầu

- Android 8.0 (API 26) trở lên.
- Thiết bị đã kết nối vào `INET - Free WiFi`.
- Bật dịch vụ Vị trí của Android để hệ thống cho phép đọc SSID.
- Flutter SDK và Android SDK nếu build từ mã nguồn.

Ứng dụng không tự bật WiFi và không tự kết nối/chuyển SSID.

## Chạy khi phát triển

Thư mục này là root của Flutter project:

```powershell
cd D:\auto-connect-inet\mobile
flutter pub get
flutter run
```

Chọn thiết bị cụ thể khi có cả emulator và máy USB:

```powershell
flutter devices
flutter run -d <device-id>
```

Nếu Flutter chưa nằm trong `PATH`:

```powershell
C:\tools\flutter\bin\flutter.bat run -d <device-id>
```

## Build và cài APK

### Debug

```powershell
flutter build apk --debug
adb install -r build\app\outputs\flutter-apk\app-debug.apk
```

Bản debug chứa runtime phục vụ phát triển nên dung lượng lớn.

### Release theo kiến trúc CPU

```powershell
flutter build apk --release --split-per-abi
```

| Thiết bị | APK |
| --- | --- |
| Hầu hết điện thoại Android hiện nay | `build/app/outputs/flutter-apk/app-arm64-v8a-release.apk` |
| Điện thoại ARM 32-bit cũ | `build/app/outputs/flutter-apk/app-armeabi-v7a-release.apk` |
| Emulator/thiết bị x86-64 | `build/app/outputs/flutter-apk/app-x86_64-release.apk` |

Cấu hình hiện tại ký release bằng debug key để cài thử nội bộ. Trước khi phát hành, phải cấu hình release keystore riêng và tuyệt đối không commit keystore hoặc mật khẩu.

## Quyền Android

Khi bật `Tự động đăng nhập`, ứng dụng yêu cầu:

- `ACCESS_FINE_LOCATION`: Android coi SSID là thông tin nhạy cảm vị trí, kể cả trên Android mới.
- `NEARBY_WIFI_DEVICES`: quyền truy cập thông tin WiFi trên Android 13+.
- `POST_NOTIFICATIONS`: hiển thị foreground service trên Android 13+.

Android 12+ mặc định che SSID trong `NetworkCapabilities`. App dùng callback có `FLAG_INCLUDE_LOCATION_INFO` và chỉ xử lý dữ liệu capability/link properties của chính callback. Nếu từ chối quyền vị trí hoặc tắt Location, dashboard có thể hiện `Chưa có` dù thanh trạng thái vẫn báo đang nối WiFi.

## Luồng hoạt động

```text
Android NetworkCallback
        │
        ├─ SSID không phải INET ──► WAITING_WIFI
        │
        └─ INET - Free WiFi
                 │
                 ├─ kiểm tra gateway /status
                 ├─ dùng credential trong Android Keystore nếu cần
                 ├─ lấy phiên mới qua AWING nếu cache không hợp lệ
                 └─ ONLINE hoặc BACKOFF rồi retry
```

Request gateway luôn được bind vào đúng `android.net.Network`, tránh đi nhầm qua mobile data hoặc VPN.

## Trạng thái trên dashboard

- `Đã tắt`: service không chạy.
- `Đang khởi động`: foreground service đang chuẩn bị.
- `Đang chờ cấp quyền`: thiếu quyền Android bắt buộc.
- `Đang chờ WiFi INET`: chưa nhận diện đúng SSID mục tiêu.
- `Đang kiểm tra kết nối`: đang hỏi gateway về phiên hiện tại.
- `Đang đăng nhập bằng dữ liệu đã lưu`: thử credential trong Keystore.
- `Đang đăng nhập qua AWING`: lấy credential/phiên mới.
- `Đã đăng nhập`: gateway xác nhận phiên hợp lệ.
- `Đang chờ thử lại`: lỗi tạm thời và đang backoff.
- `Có lỗi`: xem thông tin chi tiết và nhật ký.

`Thử lại ngay` bỏ thời gian backoff hiện tại. Kéo dashboard xuống hoặc bấm `Làm mới` để đọc snapshot mới nhất.

## Kiểm tra ổn định mạng

Chọn 30, 60, 120 giây hoặc `Vô hạn`. Công cụ mở TCP socket qua đúng Android `Network` tới `1.1.1.1:53`, ghi nhận:

- packet loss;
- latency mới nhất, nhỏ nhất, trung bình và lớn nhất;
- jitter;
- số lần, thời gian hiện tại và thời gian dài nhất của gián đoạn.

Đây là phép đo độ ổn định TCP, không phải kiểm tra băng thông. Chế độ vô hạn chạy đến khi người dùng dừng hoặc đóng màn hình app.

## Chạy nền và OEM

Android chuẩn có thể khôi phục service sau reboot ở mức best effort. Một số hãng cần cấu hình thêm:

- Oppo, Realme, OnePlus: bật Auto launch và Background activity.
- Xiaomi, Redmi, Poco: bật Auto Start và đặt Battery saver thành No restrictions.
- Vivo: bật Autostart và High background power consumption.
- Samsung: đưa ứng dụng ra khỏi Sleeping/Deep sleeping apps.

`Buộc dừng` trong Settings chặn cả service và boot receiver đến khi người dùng mở lại ứng dụng. Không ứng dụng nào có thể tự vượt qua giới hạn này.

Sau khi cài đè APK bằng `adb install -r`, Android có thể dừng foreground service cũ. Hãy mở lại app và tắt/bật công tắc một lần nếu dashboard chỉ đứng ở `Đang khởi động`.

## Chẩn đoán

### Không nhận diện được WiFi hiện tại

1. Kiểm tra đang nối đúng `INET - Free WiFi`.
2. Bật Location của thiết bị.
3. Cấp quyền Vị trí chính xác và Thiết bị WiFi ở gần cho app.
4. Tắt/bật lại `Tự động đăng nhập`.
5. Kiểm tra SSID, gateway, IP cục bộ và `Nhật ký gần đây` trên dashboard.

Qua ADB:

```powershell
adb devices -l
adb shell dumpsys wifi
adb shell dumpsys activity services vn.pckien.inet_auto_login
```

### Service bị OEM dừng

Bật Auto Start, bỏ giới hạn pin, giữ thông báo foreground và mở app lại. Vuốt app khỏi Recent thường không dừng service trên Android chuẩn, nhưng hành vi OEM có thể khác.

## Kiểm thử

```powershell
flutter analyze
flutter test
.\android\gradlew.bat -p android testDebugUnitTest
```

Các test bao phủ model/bridge Flutter, layout 320dp và landscape, parser/authentication, backoff, redaction log, network selector và stability accumulator.

## Bảo mật

- Credential cache được lưu bằng Android Keystore.
- Logger che username, password, cookie, CHAP material, MAC và IPv4.
- Service không export ra ứng dụng khác.
- Gateway/AWING có phần lưu lượng HTTP cleartext; không coi kết nối này tương đương HTTPS end-to-end.
