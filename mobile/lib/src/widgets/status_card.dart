import 'package:flutter/material.dart';

import '../models/daemon_snapshot.dart';

class StatusCard extends StatelessWidget {
  const StatusCard({super.key, required this.snapshot});
  final DaemonSnapshot snapshot;

  static String stateLabel(DaemonState state) => switch (state) {
    DaemonState.disabled => 'Đã tắt',
    DaemonState.starting => 'Đang khởi động',
    DaemonState.waitingPermission => 'Đang chờ cấp quyền',
    DaemonState.waitingWifi => 'Đang chờ WiFi INET',
    DaemonState.checking => 'Đang kiểm tra kết nối',
    DaemonState.online => 'Đã đăng nhập',
    DaemonState.authenticatingCache => 'Đang đăng nhập bằng dữ liệu đã lưu',
    DaemonState.authenticatingCloud => 'Đang đăng nhập qua AWING',
    DaemonState.backoff => 'Đang chờ thử lại',
    DaemonState.error => 'Có lỗi',
    DaemonState.unknown => 'Trạng thái chưa xác định',
  };

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isGood = snapshot.state == DaemonState.online;
    final isError = snapshot.state == DaemonState.error;
    final color = isError
        ? scheme.error
        : isGood
        ? const Color(0xff08a878)
        : const Color(0xff315bd8);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: color.withValues(alpha: .1),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(
                isError
                    ? Icons.error_outline_rounded
                    : isGood
                    ? Icons.check_rounded
                    : Icons.wifi_find_rounded,
                color: color,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'TRẠNG THÁI',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: const Color(0xff7b8197),
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.1,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    stateLabel(snapshot.state),
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: color,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  if (snapshot.stateMessage.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      snapshot.stateMessage,
                      style: const TextStyle(color: Color(0xff5d6275)),
                    ),
                  ],
                  if (snapshot.lastError != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Chi tiết lỗi: ${snapshot.lastError}',
                      style: TextStyle(color: scheme.error),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
