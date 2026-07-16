# INET Auto Login cho Android

Ứng dụng Flutter điều khiển dịch vụ nền Android để theo dõi `INET - Free WiFi` và đăng nhập captive portal AWING/MikroTik. Daemon chạy bằng foreground service, độc lập với màn hình Flutter.

## Yêu cầu

- Android 8.0 trở lên.
- Flutter SDK và Android SDK để tự build.
- Thiết bị đã kết nối vật lý với `INET - Free WiFi`.

Ứng dụng không tự bật WiFi, không tự chọn hoặc kết nối WiFi, không dùng VPN và không cần root.

## Build APK

Từ thư mục `mobile`:

```bash
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

APK debug nằm tại `build/app/outputs/flutter-apk/app-debug.apk`. Cài qua ADB:

```bash
adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

Muốn phát hành nội bộ, cấu hình khóa ký Android riêng và chạy `flutter build apk --release`. Không đưa keystore hoặc mật khẩu ký vào Git.

## Cấp quyền và bật dịch vụ

1. Mở ứng dụng và bật `Tự động đăng nhập`.
2. Đọc giải thích rồi chấp nhận hộp thoại Android.
3. Android 13 trở lên cần quyền thiết bị WiFi ở gần và thông báo.
4. Android 12 trở xuống cần quyền vị trí để Android cho phép đọc SSID.
5. Nếu SSID vẫn không đọc được, bật dịch vụ Vị trí của thiết bị rồi thử lại.
6. Giữ thông báo foreground của ứng dụng được phép hiển thị.

Ứng dụng chỉ khởi động daemon sau khi các quyền bắt buộc đã được cấp. Nút `Cài đặt pin` mở trang thông tin ứng dụng để người dùng tự điều chỉnh mức sử dụng pin.

## Trạng thái

- `Đã tắt`: daemon không chạy.
- `Đang khởi động`: foreground service đang chuẩn bị.
- `Đang chờ cấp quyền`: Android chưa cho phép đọc WiFi hoặc hiển thị thông báo.
- `Đang chờ WiFi INET`: chưa kết nối đúng SSID mục tiêu.
- `Đang kiểm tra kết nối`: đang hỏi gateway về phiên đăng nhập.
- `Đang đăng nhập bằng dữ liệu đã lưu`: đang thử credential được mã hóa trong Android Keystore.
- `Đang đăng nhập qua AWING`: đang lấy credential mới.
- `Đã đăng nhập`: gateway xác nhận phiên hợp lệ.
- `Đang chờ thử lại`: lỗi tạm thời và daemon đang backoff.
- `Có lỗi`: lỗi cần xem chi tiết hoặc nhật ký.

Kéo xuống để làm mới. `Thử lại ngay` bỏ thời gian backoff hiện tại. Mục `Nhật ký gần đây` hiển thị tối đa số dòng giới hạn và logger đã che dữ liệu nhạy cảm.

## Kiểm tra ổn định mạng

Dashboard có mục `Kiểm tra ổn định` độc lập với dịch vụ tự động đăng nhập. Chọn 30, 60 hoặc 120 giây rồi bấm bắt đầu. Android ưu tiên đúng Network của `INET - Free WiFi` mà bộ theo dõi mạng nhận diện; nếu chưa nhận diện được, giao diện ghi rõ đang dùng mạng hoạt động làm dự phòng.

Mỗi 500 ms, công cụ mở TCP socket bằng `Android Network.socketFactory` tới `1.1.1.1:53`, timeout 1000 ms và luôn đóng socket. Kết quả thời gian thực gồm tỷ lệ mất gói, độ trễ mới nhất/nhỏ nhất/trung bình/lớn nhất, jitter, số lần và thời gian gián đoạn, cùng đánh giá chất lượng. Chỉ một bài kiểm tra được chạy tại một thời điểm và có thể dừng an toàn. Đây là phép đo TCP, không phải kiểm tra băng thông, không dùng proxy và không dùng VPN.

## Pin, Auto Start và OEM

Android chuẩn có thể khôi phục daemon sau reboot ở mức best effort. Một số hãng áp giới hạn riêng:

- Xiaomi, Redmi, Poco: bật Auto Start và đặt Battery saver thành No restrictions.
- Oppo, Realme, OnePlus: cho phép Auto launch và Background activity.
- Vivo: bật Autostart và High background power consumption.
- Samsung: bỏ ứng dụng khỏi Sleeping apps hoặc Deep sleeping apps, có thể thêm vào Never sleeping apps.

Tên menu thay đổi theo phiên bản hệ điều hành. Luôn giữ notification foreground. Vuốt ứng dụng khỏi màn hình gần đây thường không dừng service, nhưng OEM có thể xử lý khác.

## Force Stop và giới hạn nền

`Buộc dừng` trong Settings là lệnh mạnh của Android. Sau Force Stop, service và boot receiver không được chạy lại cho đến khi người dùng mở ứng dụng thủ công. Ứng dụng không thể vượt qua giới hạn này. Reboot recovery cũng là best effort và phụ thuộc chính sách OEM.

## Bảo mật và giới hạn giao thức

Captive portal hiện yêu cầu HTTP cleartext tới gateway và một phần luồng AWING. Lưu lượng HTTP có thể bị quan sát hoặc sửa đổi bởi bên kiểm soát mạng. Ứng dụng giảm rủi ro bằng cách bind request vào đúng Android Network, không log username, password, cookie hoặc CHAP material, không export service điều khiển, và lưu credential cache bằng Android Keystore.

Không xem nhật ký là bằng chứng tuyệt đối rằng mạng an toàn. Ứng dụng chỉ hỗ trợ portal AWING/MikroTik hiện tại, không tự kết nối WiFi vật lý, không đảm bảo chạy sau Force Stop và không thể khắc phục portal đổi schema nếu chưa cập nhật ứng dụng.

## Chẩn đoán

Mở dashboard để xem SSID, gateway, IP cục bộ, lần kiểm tra, lần đăng nhập, thời gian retry và nhật ký đã redact. Khi báo sai WiFi hoặc SSID không xác định, kiểm tra quyền, Location và kết nối WiFi trước. Khi OEM dừng nền, bật Auto Start, bỏ giới hạn pin rồi mở lại ứng dụng.
