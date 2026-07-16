import 'dart:async';

import 'package:flutter/material.dart';

import '../models/stability_snapshot.dart';
import '../platform/auto_login_platform.dart';

class StabilityTestSection extends StatefulWidget {
  const StabilityTestSection({super.key, required this.platform});
  final AutoLoginApi platform;

  @override
  State<StabilityTestSection> createState() => _StabilityTestSectionState();
}

class _StabilityTestSectionState extends State<StabilityTestSection> {
  StreamSubscription<StabilitySnapshot>? _subscription;
  StabilitySnapshot? _snapshot;
  int _duration = 60;
  bool _starting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _subscription = widget.platform.stabilitySnapshots.listen(
      (value) => mounted ? setState(() { _snapshot = value; _starting = false; _error = value.error; }) : null,
      onError: (Object error) => mounted ? setState(() { _error = '$error'; _starting = false; }) : null,
    );
  }

  @override
  void dispose() { _subscription?.cancel(); super.dispose(); }

  String _ms(double? value) => value == null ? 'Chưa có' : '${value.toStringAsFixed(1)} ms';
  String _durationMs(int value) => '${(value / 1000).toStringAsFixed(1)} giây';
  String get _ratingLabel => switch (_snapshot?.rating) {
    StabilityRating.excellent => 'Xuất sắc',
    StabilityRating.jittery => 'Dao động',
    StabilityRating.laggy => 'Có độ trễ',
    StabilityRating.bad => 'Kém',
    _ => 'Không kết nối',
  };
  String get _ratingHelp => switch (_snapshot?.rating) {
    StabilityRating.excellent => 'Độ trễ thấp, ít mất gói và ổn định.',
    StabilityRating.jittery => 'Độ trễ thay đổi, có thể ảnh hưởng gọi thoại.',
    StabilityRating.laggy => 'Độ trễ hoặc mất gói đáng kể.',
    StabilityRating.bad => 'Mất gói, độ trễ hoặc gián đoạn ở mức cao.',
    _ => 'Chưa nhận được kết nối TCP thành công.',
  };

  Future<void> _toggle() async {
    try {
      setState(() { _starting = true; _error = null; });
      if (_snapshot?.running == true) {
        await widget.platform.stopStabilityTest();
      } else {
        await widget.platform.startStabilityTest(durationSeconds: _duration);
      }
    } catch (error) {
      if (mounted) setState(() { _starting = false; _error = '$error'; });
    }
  }

  Widget _metric(String label, String value) => SizedBox(
    width: 145,
    child: Card(color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(padding: const EdgeInsets.all(10), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 3), Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
      ]))),
  );

  @override
  Widget build(BuildContext context) {
    final value = _snapshot;
    return Card(key: const Key('stabilitySection'), child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Kiểm tra ổn định', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 4),
        const Text('Đo kết nối TCP qua đúng Android Network tới 1.1.1.1:53. Không dùng proxy hoặc VPN.'),
        const SizedBox(height: 12),
        SegmentedButton<int>(
          segments: const [30, 60, 120].map((seconds) => ButtonSegment(value: seconds, label: Text('$seconds giây'))).toList(),
          selected: {_duration}, onSelectionChanged: value?.running == true ? null : (values) => setState(() => _duration = values.first),
        ),
        const SizedBox(height: 12),
        if (value != null) ...[
          Text(value.networkLabel, key: const Key('stabilityNetworkLabel'), style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          LinearProgressIndicator(value: value.progress),
          const SizedBox(height: 4),
          Text('${(value.elapsedMs / 1000).floor()} / ${(value.durationMs / 1000).floor()} giây'),
          const SizedBox(height: 8),
          Text('Đánh giá: $_ratingLabel', key: const Key('stabilityRating'), style: Theme.of(context).textTheme.titleMedium),
          Text(_ratingHelp),
          const SizedBox(height: 10),
          Wrap(spacing: 4, runSpacing: 4, children: [
            _metric('Đã gửi / nhận', '${value.sent} / ${value.received}'),
            _metric('Mất gói', '${value.lossPercent.toStringAsFixed(1)}%'),
            _metric('Độ trễ mới nhất', _ms(value.latestLatencyMs)),
            _metric('Nhỏ nhất / trung bình', 'Min ${_ms(value.minLatencyMs)}\nTB ${_ms(value.averageLatencyMs)}'),
            _metric('Lớn nhất', _ms(value.maxLatencyMs)),
            _metric('Jitter trung bình', _ms(value.jitterMs)),
            _metric('Số lần gián đoạn', '${value.outageCount}'),
            _metric('Gián đoạn hiện tại', _durationMs(value.currentOutageMs)),
            _metric('Gián đoạn dài nhất', _durationMs(value.maxOutageMs)),
          ]),
        ] else
          const Text('Chọn thời lượng và bắt đầu để xem số liệu theo thời gian thực.'),
        if (_error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 12),
        FilledButton.icon(
          key: const Key('stabilityToggle'), onPressed: _starting ? null : _toggle,
          icon: Icon(value?.running == true ? Icons.stop : Icons.play_arrow),
          label: Text(value?.running == true ? 'Dừng kiểm tra' : 'Bắt đầu kiểm tra'),
        ),
      ]),
    ));
  }
}
