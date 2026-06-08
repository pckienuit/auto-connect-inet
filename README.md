# Auto-Connect INET - Free WiFi

Công cụ tự động hóa quá trình đăng nhập và duy trì kết nối mạng WiFi **INET - Free WiFi** (hệ thống cổng chào captive portal của **AWING**) trên Windows 10/11 mà không cần mở trình duyệt hay chờ đợi 5 giây quảng cáo.

## ✨ Tính năng nổi bật

- **Tự động đăng nhập:** Tự động mô phỏng luồng đăng nhập (Bypass Captive Portal) ngay khi phát hiện card mạng kết nối vào SSID mục tiêu.
- **Không hiện cửa sổ CMD (Tàng hình):** Tiến trình hoạt động ẩn hoàn toàn dưới nền hệ thống thông qua `pythonw.exe` (chỉ tiêu thụ ~10MB RAM).
- **Nhận diện đa card mạng (Universal Guard):** Tự động nhận diện mọi giao diện mạng không dây (WiFi onboard, USB Realtek WiFi...) kết nối vào mạng INET để quản lý và bảo vệ song song.
- **Cơ chế chống spam (Exponential Backoff):** Tự động kéo giãn thời gian quét khi mạng bị lỗi hoặc router quá tải (10s -> 20s -> 40s ... tối đa 5 phút) để tránh lãng phí tài nguyên và tránh bị Gateway block IP.
- **Trải nghiệm liền mạch (Seamless):** Tự động quét kiểm tra mỗi 10 giây. Khi phiên 15 phút hết hạn, script lập tức đăng nhập lại giúp duy trì internet liên tục.
- **Watchdog Tự hồi sinh:** Sử dụng Windows Scheduled Task làm watchdog, tự khởi chạy lại script khi máy sleep/wake up hoặc bị tắt.
- **Cài đặt 1-Click:** Chỉ cần chạy file `.bat` để thiết lập trọn gói trên bất kỳ máy tính Windows nào.

## 📂 Cấu trúc thư mục Project

```text
├── auto_connect_inet.py  # Script chính (giám sát, xử lý đăng nhập captive portal)
├── test_download.py      # Script phụ để test độ ổn định băng thông (tải file thử nghiệm)
├── install.bat           # File cài đặt 1-click tự động đăng ký với Windows Task Scheduler
└── auto_connect_inet.exe # File thực thi đã biên dịch chạy ẩn (onefile, noconsole)
```

## 🚀 Hướng dẫn cài đặt (1-Click)

1. Tải toàn bộ thư mục này về máy.
2. Nhấp đúp chuột vào file `install.bat`.
3. Quá trình cài đặt sẽ tự động sao chép file thực thi vào thư mục hệ thống `%LOCALAPPDATA%\AutoConnectINET` và đăng ký lịch chạy ngầm vĩnh viễn với Windows.

## 🛠️ Hướng dẫn gỡ cài đặt (Uninstall)

Nếu bạn không muốn sử dụng công cụ tự động đăng nhập nữa, hãy mở CMD với quyền Administrator hoặc Terminal thường và chạy lần lượt các lệnh sau:

```cmd
:: Tắt tiến trình chạy ngầm hiện tại
taskkill /F /FI "CommandLine eq *auto_connect_inet.exe*"

:: Xóa lịch khởi chạy tự động của Windows
schtasks /delete /tn AutoConnectINET /f

:: Xóa thư mục cài đặt
rd /s /q "%LOCALAPPDATA%\AutoConnectINET"
```

## 📝 Cơ chế kỹ thuật (Technical Overview)

1. **Phát hiện mạng:** Sử dụng `netsh wlan show interfaces` để lọc các adapter đang kết nối với SSID `INET - Free WiFi`.
2. **Cô lập socket:** Khởi tạo Socket TCP thủ công và gọi hàm `s.bind((interface_ip, 0))` để ép dữ liệu đi qua chính xác card mạng đích, tránh xung đột định tuyến khi máy dùng nhiều mạng song song.
3. **Phát hiện cổng chào:** Gửi yêu cầu HTTP GET đến `http://detectportal.firefox.com/success.txt`. Nếu trả về chuỗi `success` thì bỏ qua, ngược lại (bị chuyển hướng) sẽ kích hoạt đăng nhập.
4. **Vượt rào cản:** Lấy mã thử thách `chap-challenge` từ gateway nội bộ (`192.168.200.1`), gửi xác thực lên server cloud của nhà mạng (`v1.awingconnect.vn`) thông qua kết nối internet chính đang hoạt động để lấy tài khoản đăng nhập một lần, sau đó POST ngược lại để gateway nội bộ mở băng thông cho địa chỉ MAC của card.
