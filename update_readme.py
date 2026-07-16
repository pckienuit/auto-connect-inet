with open("D:/auto-connect-inet/README.md", "r", encoding="utf-8") as f:
    text = f.read()

import re

updates = """
- **Auto-connect disconnected adapter:** Tự động phát hiện và kết nối lại các card mạng phụ (như USB WiFi) vào SSID `"INET - Free WiFi"` nếu bị ngắt kết nối hoặc lệch SSID.
- **Local Gate-check (Immune Mode):** Giải quyết triệt để lỗi xung đột định tuyến (Routing Metric) và lỗi bị VPN/Tailscale chặn/định tuyến nhầm gói tin kiểm tra mạng. Thay vì check ping WAN (`detectportal`), script V3.2 sẽ trực tiếp kiểm tra trạng thái session cục bộ qua cổng chào (`/status` và `/login`) của router. Nhờ đó, script hoạt động chính xác 100% ngay cả khi đang bật VPN/Tailscale.
- **Bypass Captive Cloud & Survey:** Tự động phát hiện yêu cầu khảo sát tuổi/giới tính và bóc tách địa chỉ Endpoint API động (không fix cứng domain), đảm bảo hoạt động xuyên suốt kể cả khi INET đổi hạ tầng.
- **Bound HTTP Requests:** Vượt lỗi Windows OS Multi-NIC (chặn đường truyền khi cắm 2 card Wi-Fi), script ép toàn bộ quá trình nhận/gửi session đi đúng IP nội bộ thay vì bị drop bởi Metric cao.
- **Keepalive 0.5s (Gaming Mode):** Thread riêng kiểm tra trạng thái cổng chào mỗi 0.5 giây (timeout 300ms) → phát hiện mất mạng cực nhanh, re-auth tức thì để không gây khựng mạng khi chơi game đối kháng.
"""

text = re.sub(
    r'- \*\*Auto-connect disconnected adapter:\*\*.+?(?=\n- \*\*Cached credentials:\*\*)', 
    updates.strip() + '\n', 
    text, 
    flags=re.DOTALL
)

with open("D:/auto-connect-inet/README.md", "w", encoding="utf-8") as f:
    f.write(text)
