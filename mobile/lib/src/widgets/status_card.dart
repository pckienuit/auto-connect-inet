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
    final color = snapshot.state == DaemonState.error
        ? scheme.error
        : isGood
            ? Colors.green.shade700
            : scheme.primary;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(isGood ? Icons.check_circle : Icons.info, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(stateLabel(snapshot.state), style: Theme.of(context).textTheme.titleMedium?.copyWith(color: color, fontWeight: FontWeight.bold)),
              if (snapshot.stateMessage.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(snapshot.stateMessage),
              ],
              if (snapshot.lastError != null) ...[
                const SizedBox(height: 8),
                Text('Chi tiết lỗi: ${snapshot.lastError}', style: TextStyle(color: scheme.error)),
              ],
            ]),
          ),
        ]),
      ),
    );
  }
}
