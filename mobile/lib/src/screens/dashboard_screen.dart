import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/daemon_snapshot.dart';
import '../platform/auto_login_platform.dart';
import '../widgets/status_card.dart';
import '../widgets/stability_test_section.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key, required this.platform});
  final AutoLoginApi platform;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  DaemonSnapshot _snapshot = const DaemonSnapshot.disabled();
  StreamSubscription<DaemonSnapshot>? _subscription;
  Timer? _clock;
  bool _loading = true;
  bool _busy = false;
  String? _notice;
  List<String> _logs = const [];

  @override
  void initState() {
    super.initState();
    _subscription = widget.platform.snapshots.listen(_accept, onError: _showError);
    _clock = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted && _snapshot.retryAt != null) setState(() {});
    });
    _refresh();
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _clock?.cancel();
    super.dispose();
  }

  void _accept(DaemonSnapshot value) {
    if (mounted) setState(() { _snapshot = value; _loading = false; });
  }

  Future<void> _refresh() async {
    try {
      final values = await Future.wait<Object>([widget.platform.getSnapshot(), widget.platform.getRecentLogs()]);
      if (mounted) setState(() { _snapshot = values[0] as DaemonSnapshot; _logs = values[1] as List<String>; _loading = false; });
    } catch (error) {
      _showError(error);
    }
  }

  void _showError(Object error) {
    if (!mounted) return;
    final message = error is PlatformException ? error.message ?? error.code : '$error';
    setState(() { _notice = message; _loading = false; _busy = false; });
  }

  Future<void> _toggle(bool enabled) async {
    setState(() { _busy = true; _notice = null; });
    try {
      if (enabled) {
        final proceed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Quyền cần thiết'),
            content: const Text('Android cần quyền đọc WiFi để nhận biết đúng INET - Free WiFi. Quyền thông báo giúp foreground service hoạt động rõ ràng và ổn định.'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Để sau')),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Tiếp tục')),
            ],
          ),
        );
        if (proceed != true) return;
        final permission = await widget.platform.requestPermissions();
        if (!permission.granted) {
          if (mounted) setState(() { _notice = 'Chưa cấp đủ quyền. Hãy cho phép thiết bị ở gần, vị trí hoặc thông báo khi Android yêu cầu.'; });
          return;
        }
        await widget.platform.start();
      } else {
        await widget.platform.stop();
      }
      await _refresh();
    } catch (error) {
      _showError(error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _value(String? value) => value ?? 'Chưa có';
  String _time(DateTime? value) {
    if (value == null) return 'Chưa có';
    final local = value.toLocal();
    String two(int number) => number.toString().padLeft(2, '0');
    return '${two(local.hour)}:${two(local.minute)}:${two(local.second)} ${two(local.day)}/${two(local.month)}/${local.year}';
  }

  String get _retry {
    final target = _snapshot.retryAt;
    if (target == null) return 'Không chờ';
    final seconds = target.difference(DateTime.now()).inSeconds;
    return seconds <= 0 ? 'Sẵn sàng thử lại' : 'Còn $seconds giây';
  }

  Widget _detail(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 142, child: Text(label, style: const TextStyle(fontWeight: FontWeight.w600))),
          Expanded(child: SelectableText(value)),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('INET Auto Login')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(key: const Key('dashboardList'), padding: const EdgeInsets.all(12), children: [
                Card(child: SwitchListTile(
                  key: const Key('masterSwitch'),
                  title: const Text('Tự động đăng nhập', style: TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: Text(_snapshot.serviceEnabled ? 'Dịch vụ nền đang bật' : 'Dịch vụ nền đang tắt'),
                  value: _snapshot.serviceEnabled,
                  onChanged: _busy ? null : _toggle,
                )),
                if (_notice != null) Card(color: Theme.of(context).colorScheme.errorContainer, child: Padding(padding: const EdgeInsets.all(12), child: Text(_notice!))),
                StatusCard(snapshot: _snapshot),
                Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
                  _detail('WiFi hiện tại', _value(_snapshot.ssid)),
                  _detail('Đúng WiFi INET', _snapshot.isWifiTarget ? 'Có' : 'Không'),
                  _detail('Gateway', _value(_snapshot.gatewayIp)),
                  _detail('IP cục bộ', _value(_snapshot.localIp)),
                  _detail('Lần kiểm tra', _time(_snapshot.lastCheckAt)),
                  _detail('Lần đăng nhập', _time(_snapshot.lastAuthAt)),
                  _detail('Thử lại', _retry),
                  _detail('Số lần lỗi', '${_snapshot.failureCount}'),
                ]))),
                Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Wrap(spacing: 8, runSpacing: 8, children: [
                  FilledButton.icon(onPressed: _busy || !_snapshot.serviceEnabled ? null : () async { try { await widget.platform.retryNow(); await _refresh(); } catch (e) { _showError(e); } }, icon: const Icon(Icons.refresh), label: const Text('Thử lại ngay')),
                  OutlinedButton.icon(onPressed: () async { try { await widget.platform.openBatterySettings(); } catch (e) { _showError(e); } }, icon: const Icon(Icons.battery_saver), label: const Text('Cài đặt pin')),
                  OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.sync), label: const Text('Làm mới')),
                ])),
                StabilityTestSection(platform: widget.platform),
                Card(child: ExpansionTile(
                  title: const Text('Nhật ký gần đây'),
                  subtitle: Text('${_logs.length} dòng, đã loại dữ liệu nhạy cảm'),
                  children: [Container(width: double.infinity, constraints: const BoxConstraints(maxHeight: 280), padding: const EdgeInsets.all(12), color: Theme.of(context).colorScheme.surfaceContainerHighest, child: _logs.isEmpty ? const Text('Chưa có nhật ký') : SingleChildScrollView(child: SelectableText(_logs.join('\n'), style: const TextStyle(fontFamily: 'monospace', fontSize: 12))))],
                )),
                const Padding(padding: EdgeInsets.all(8), child: Text('Ứng dụng chỉ theo dõi WiFi INET - Free WiFi. Ứng dụng không tự kết nối WiFi. Thông báo nền cần được bật để dịch vụ hoạt động ổn định.')),
              ]),
            ),
    );
  }
}
