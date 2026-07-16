import 'dart:async';

import 'package:flutter/material.dart';

import '../models/stability_snapshot.dart';
import '../platform/auto_login_platform.dart';

const _navy = Color(0xff07164f);
const _blue = Color(0xff275bd8);
const _softBlue = Color(0xfff3f6ff);
const _muted = Color(0xff7b8197);
const _orange = Color(0xffff633f);

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
      (value) => mounted
          ? setState(() {
              _snapshot = value;
              _starting = false;
              _error = value.error;
            })
          : null,
      onError: (Object error) => mounted
          ? setState(() {
              _error = '$error';
              _starting = false;
            })
          : null,
    );
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }

  String get _ratingLabel => switch (_snapshot?.rating) {
    StabilityRating.excellent => 'Xuất sắc',
    StabilityRating.jittery => 'Dao động',
    StabilityRating.laggy => 'Có độ trễ',
    StabilityRating.bad => 'Kém',
    _ => 'Không kết nối',
  };

  String get _ratingHelp => switch (_snapshot?.rating) {
    StabilityRating.excellent => 'Độ trễ thấp, ít mất gói và kết nối ổn định.',
    StabilityRating.jittery => 'Độ trễ thay đổi, có thể ảnh hưởng cuộc gọi.',
    StabilityRating.laggy => 'Độ trễ hoặc mất gói đáng kể.',
    StabilityRating.bad => 'Mất gói, độ trễ hoặc gián đoạn ở mức cao.',
    _ => 'Chưa nhận được kết nối TCP thành công.',
  };

  Color get _ratingColor => switch (_snapshot?.rating) {
    StabilityRating.excellent => const Color(0xff08a878),
    StabilityRating.jittery => const Color(0xffff9f1c),
    StabilityRating.laggy => _orange,
    StabilityRating.bad => const Color(0xffd92d4f),
    _ => _muted,
  };

  Future<void> _toggle() async {
    try {
      setState(() {
        _starting = true;
        _error = null;
      });
      if (_snapshot?.running == true) {
        await widget.platform.stopStabilityTest();
      } else {
        await widget.platform.startStabilityTest(durationSeconds: _duration);
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _starting = false;
          _error = '$error';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final value = _snapshot;
    final running = value?.running == true;
    return Card(
      key: const Key('stabilitySection'),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const _Header(),
            const SizedBox(height: 18),
            _DurationPicker(
              duration: _duration,
              enabled: !running,
              onChanged: (duration) => setState(() => _duration = duration),
            ),
            const SizedBox(height: 14),
            if (value == null)
              const _EmptyState()
            else ...[
              _ConnectionSummary(
                value: value,
                ratingLabel: _ratingLabel,
                ratingHelp: _ratingHelp,
                ratingColor: _ratingColor,
              ),
              const SizedBox(height: 12),
              _MetricsGrid(value: value),
            ],
            if (_error != null) ...[
              const SizedBox(height: 12),
              _ErrorMessage(message: _error!),
            ],
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: const Key('stabilityToggle'),
                onPressed: _starting ? null : _toggle,
                style: FilledButton.styleFrom(
                  backgroundColor: running ? _orange : _blue,
                  foregroundColor: Colors.white,
                  disabledBackgroundColor: const Color(0xffdfe3ef),
                  minimumSize: const Size.fromHeight(54),
                ),
                icon: _starting
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: Colors.white,
                        ),
                      )
                    : Icon(
                        running ? Icons.stop_rounded : Icons.play_arrow_rounded,
                      ),
                label: Text(running ? 'Dừng kiểm tra' : 'Bắt đầu kiểm tra'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Container(
        width: 46,
        height: 46,
        decoration: BoxDecoration(
          color: const Color(0xffeaf0ff),
          borderRadius: BorderRadius.circular(15),
        ),
        child: const Icon(Icons.speed_rounded, color: _blue, size: 25),
      ),
      const SizedBox(width: 12),
      const Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Kiểm tra ổn định',
              style: TextStyle(
                color: _navy,
                fontSize: 18,
                fontWeight: FontWeight.w900,
              ),
            ),
            SizedBox(height: 4),
            Text(
              'Đo trực tiếp tới 1.1.1.1 qua đúng mạng Android.',
              style: TextStyle(color: _muted, fontSize: 12, height: 1.35),
            ),
          ],
        ),
      ),
    ],
  );
}

class _DurationPicker extends StatelessWidget {
  const _DurationPicker({
    required this.duration,
    required this.enabled,
    required this.onChanged,
  });

  final int duration;
  final bool enabled;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    const options = <int, String>{
      30: '30 giây',
      60: '60 giây',
      120: '120 giây',
      0: 'Vô hạn',
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'THỜI LƯỢNG KIỂM TRA',
          style: TextStyle(
            color: _muted,
            fontSize: 10,
            fontWeight: FontWeight.w800,
            letterSpacing: .8,
          ),
        ),
        const SizedBox(height: 9),
        LayoutBuilder(
          builder: (context, constraints) {
            final itemWidth = (constraints.maxWidth - 8) / 2;
            return Wrap(
              spacing: 8,
              runSpacing: 8,
              children: options.entries.map((entry) {
                final selected = duration == entry.key;
                return SizedBox(
                  width: itemWidth,
                  height: 42,
                  child: Material(
                    color: selected ? _blue : _softBlue,
                    borderRadius: BorderRadius.circular(14),
                    child: InkWell(
                      onTap: enabled ? () => onChanged(entry.key) : null,
                      borderRadius: BorderRadius.circular(14),
                      child: Center(
                        child: Text(
                          entry.value,
                          style: TextStyle(
                            color: selected
                                ? Colors.white
                                : enabled
                                ? _navy
                                : _muted,
                            fontSize: 12,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            );
          },
        ),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(15),
    decoration: BoxDecoration(
      color: _softBlue,
      borderRadius: BorderRadius.circular(16),
    ),
    child: const Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.info_outline_rounded, color: _blue, size: 20),
        SizedBox(width: 10),
        Expanded(
          child: Text(
            'Chọn thời lượng rồi bắt đầu để theo dõi chất lượng mạng theo thời gian thực.',
            style: TextStyle(color: Color(0xff5d6275), height: 1.4),
          ),
        ),
      ],
    ),
  );
}

class _ConnectionSummary extends StatelessWidget {
  const _ConnectionSummary({
    required this.value,
    required this.ratingLabel,
    required this.ratingHelp,
    required this.ratingColor,
  });

  final StabilitySnapshot value;
  final String ratingLabel;
  final String ratingHelp;
  final Color ratingColor;

  @override
  Widget build(BuildContext context) {
    final elapsed = (value.elapsedMs / 1000).floor();
    final progressLabel = value.isUnlimited
        ? 'Đã chạy $elapsed giây, dừng thủ công khi cần'
        : '$elapsed / ${(value.durationMs / 1000).floor()} giây';
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: _softBlue,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xffe2e9ff)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 9,
                height: 9,
                decoration: BoxDecoration(
                  color: value.running ? const Color(0xff08a878) : _muted,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  value.networkLabel,
                  key: const Key('stabilityNetworkLabel'),
                  style: const TextStyle(
                    color: _navy,
                    fontWeight: FontWeight.w800,
                    fontSize: 12,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
                decoration: BoxDecoration(
                  color: ratingColor.withValues(alpha: .12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  ratingLabel,
                  style: TextStyle(
                    color: ratingColor,
                    fontSize: 10,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 13),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: LinearProgressIndicator(
              minHeight: 7,
              value: value.isUnlimited && value.running ? null : value.progress,
              backgroundColor: const Color(0xffdce4fb),
              color: _blue,
            ),
          ),
          const SizedBox(height: 7),
          Text(
            progressLabel,
            style: const TextStyle(color: _muted, fontSize: 11),
          ),
          const SizedBox(height: 13),
          Text(
            'Đánh giá: $ratingLabel',
            key: const Key('stabilityRating'),
            style: const TextStyle(
              color: _navy,
              fontWeight: FontWeight.w900,
              fontSize: 15,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            ratingHelp,
            style: const TextStyle(
              color: Color(0xff5d6275),
              fontSize: 12,
              height: 1.35,
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricsGrid extends StatelessWidget {
  const _MetricsGrid({required this.value});
  final StabilitySnapshot value;

  String _ms(double? metric) =>
      metric == null ? 'Chưa có' : '${metric.toStringAsFixed(1)} ms';

  String _seconds(int metric) => '${(metric / 1000).toStringAsFixed(1)} giây';

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final width = (constraints.maxWidth - 8) / 2;
      return Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          _MetricTile(
            width: width,
            icon: Icons.swap_vert_rounded,
            label: 'ĐÃ GỬI / NHẬN',
            value: '${value.sent} / ${value.received}',
          ),
          _MetricTile(
            width: width,
            icon: Icons.data_usage_rounded,
            label: 'MẤT GÓI',
            value: '${value.lossPercent.toStringAsFixed(1)}%',
          ),
          _MetricTile(
            width: width,
            icon: Icons.bolt_rounded,
            label: 'ĐỘ TRỄ MỚI NHẤT',
            value: _ms(value.latestLatencyMs),
          ),
          _MetricTile(
            width: width,
            icon: Icons.insights_rounded,
            label: 'NHỎ NHẤT / TB',
            value:
                '${_ms(value.minLatencyMs)} / ${_ms(value.averageLatencyMs)}',
          ),
          _MetricTile(
            width: width,
            icon: Icons.keyboard_double_arrow_up_rounded,
            label: 'LỚN NHẤT',
            value: _ms(value.maxLatencyMs),
          ),
          _MetricTile(
            width: width,
            icon: Icons.graphic_eq_rounded,
            label: 'JITTER TRUNG BÌNH',
            value: _ms(value.jitterMs),
          ),
          _MetricTile(
            width: width,
            icon: Icons.link_off_rounded,
            label: 'SỐ LẦN GIÁN ĐOẠN',
            value: '${value.outageCount}',
          ),
          _MetricTile(
            width: width,
            icon: Icons.timer_outlined,
            label: 'GIÁN ĐOẠN HIỆN TẠI',
            value: _seconds(value.currentOutageMs),
          ),
          _MetricTile(
            width: width,
            icon: Icons.history_rounded,
            label: 'GIÁN ĐOẠN DÀI NHẤT',
            value: _seconds(value.maxOutageMs),
          ),
        ],
      );
    },
  );
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.width,
    required this.icon,
    required this.label,
    required this.value,
  });

  final double width;
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Container(
    width: width,
    constraints: const BoxConstraints(minHeight: 76),
    padding: const EdgeInsets.all(11),
    decoration: BoxDecoration(
      color: const Color(0xfff5f7fc),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Row(
      children: [
        Icon(icon, size: 19, color: _blue),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: _muted,
                  fontSize: 8.5,
                  fontWeight: FontWeight.w800,
                  letterSpacing: .25,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                value,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: _navy,
                  fontSize: 11.5,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _ErrorMessage extends StatelessWidget {
  const _ErrorMessage({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: const Color(0xffffeeee),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          Icons.error_outline_rounded,
          size: 19,
          color: Theme.of(context).colorScheme.error,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            message,
            style: TextStyle(
              color: Theme.of(context).colorScheme.error,
              fontSize: 12,
            ),
          ),
        ),
      ],
    ),
  );
}
