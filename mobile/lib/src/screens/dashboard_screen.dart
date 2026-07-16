import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/daemon_snapshot.dart';
import '../platform/auto_login_platform.dart';
import '../widgets/stability_test_section.dart';
import '../widgets/status_card.dart';

const _navy = Color(0xff07164f);
const _blue = Color(0xff275bd8);
const _orange = Color(0xffff633f);
const _pink = Color(0xffe91e82);

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
    _subscription = widget.platform.snapshots.listen(
      _accept,
      onError: _showError,
    );
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
    if (mounted) {
      setState(() {
        _snapshot = value;
        _loading = false;
      });
    }
  }

  Future<void> _refresh() async {
    try {
      final values = await Future.wait<Object>([
        widget.platform.getSnapshot(),
        widget.platform.getRecentLogs(),
      ]);
      if (mounted) {
        setState(() {
          _snapshot = values[0] as DaemonSnapshot;
          _logs = values[1] as List<String>;
          _loading = false;
        });
      }
    } catch (error) {
      _showError(error);
    }
  }

  void _showError(Object error) {
    if (!mounted) return;
    final message = error is PlatformException
        ? error.message ?? error.code
        : '$error';
    setState(() {
      _notice = message;
      _loading = false;
      _busy = false;
    });
  }

  Future<void> _toggle(bool enabled) async {
    setState(() {
      _busy = true;
      _notice = null;
    });
    try {
      if (enabled) {
        final proceed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Quyền cần thiết'),
            content: const Text(
              'Android cần quyền đọc WiFi để nhận biết đúng INET - Free WiFi. Quyền thông báo giúp dịch vụ nền hoạt động rõ ràng và ổn định.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Để sau'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Tiếp tục'),
              ),
            ],
          ),
        );
        if (proceed != true) return;
        final permission = await widget.platform.requestPermissions();
        if (!permission.granted) {
          if (mounted) {
            setState(() {
              _notice =
                  'Chưa cấp đủ quyền. Hãy cho phép thiết bị ở gần, vị trí hoặc thông báo khi Android yêu cầu.';
            });
          }
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

  Future<void> _retryNow() async {
    try {
      await widget.platform.retryNow();
      await _refresh();
    } catch (error) {
      _showError(error);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refresh,
              color: _blue,
              child: ListView(
                key: const Key('dashboardList'),
                padding: EdgeInsets.zero,
                children: [
                  _HeroPanel(
                    snapshot: _snapshot,
                    busy: _busy,
                    onToggle: _toggle,
                    onRefresh: _refresh,
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (_notice != null) ...[
                          _NoticeCard(message: _notice!),
                          const SizedBox(height: 12),
                        ],
                        StatusCard(snapshot: _snapshot),
                        const SizedBox(height: 12),
                        _NetworkDetails(
                          snapshot: _snapshot,
                          ssid: _value(_snapshot.ssid),
                          gateway: _value(_snapshot.gatewayIp),
                          localIp: _value(_snapshot.localIp),
                          lastCheck: _time(_snapshot.lastCheckAt),
                          lastAuth: _time(_snapshot.lastAuthAt),
                          retry: _retry,
                        ),
                        const SizedBox(height: 12),
                        _ActionPanel(
                          canRetry: !_busy && _snapshot.serviceEnabled,
                          onRetry: _retryNow,
                          onBatterySettings: () async {
                            try {
                              await widget.platform.openBatterySettings();
                            } catch (error) {
                              _showError(error);
                            }
                          },
                          onRefresh: _refresh,
                        ),
                        const SizedBox(height: 12),
                        StabilityTestSection(platform: widget.platform),
                        const SizedBox(height: 12),
                        _LogsCard(logs: _logs),
                        const SizedBox(height: 16),
                        const Text(
                          'Ứng dụng chỉ theo dõi INET - Free WiFi và không tự kết nối WiFi. Hãy bật thông báo nền để dịch vụ hoạt động ổn định.',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: Color(0xff7b8197),
                            height: 1.45,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _HeroPanel extends StatelessWidget {
  const _HeroPanel({
    required this.snapshot,
    required this.busy,
    required this.onToggle,
    required this.onRefresh,
  });
  final DaemonSnapshot snapshot;
  final bool busy;
  final ValueChanged<bool> onToggle;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final online = snapshot.state == DaemonState.online;
    final enabled = snapshot.serviceEnabled;
    return Container(
      constraints: const BoxConstraints(minHeight: 390),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [_navy, Color(0xff123289), Color(0xff2f6ae6)],
          stops: [0, .48, 1],
        ),
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(34)),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 30),
          child: Column(
            children: [
              Row(
                children: [
                  const _Brand(),
                  const Spacer(),
                  _RoundButton(
                    icon: Icons.refresh_rounded,
                    onPressed: onRefresh,
                  ),
                ],
              ),
              const SizedBox(height: 24),
              const _OrbitMark(),
              const SizedBox(height: 16),
              Text(
                enabled
                    ? (online ? 'CONNECTED' : 'AUTO LOGIN')
                    : 'DISCONNECTED',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                  fontSize: 30,
                  letterSpacing: -.8,
                ),
              ),
              const SizedBox(height: 7),
              Text(
                enabled
                    ? (online
                          ? 'Internet của bạn đã sẵn sàng.'
                          : 'Đang bảo vệ kết nối INET của bạn.')
                    : 'Chạm công tắc để tự động đăng nhập INET.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white.withValues(alpha: .78),
                  fontSize: 15,
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.fromLTRB(18, 10, 10, 10),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'TỰ ĐỘNG ĐĂNG NHẬP',
                            style: TextStyle(
                              color: _navy,
                              fontSize: 13,
                              fontWeight: FontWeight.w900,
                              letterSpacing: .25,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            enabled
                                ? 'Dịch vụ nền đang bật'
                                : 'Dịch vụ nền đang tắt',
                            style: const TextStyle(
                              color: Color(0xff747a8d),
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Switch(
                      key: const Key('masterSwitch'),
                      value: enabled,
                      onChanged: busy ? null : onToggle,
                      activeTrackColor: _pink,
                      activeThumbColor: Colors.white,
                      inactiveTrackColor: const Color(0xffdfe1e9),
                      inactiveThumbColor: Colors.white,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Brand extends StatelessWidget {
  const _Brand();
  @override
  Widget build(BuildContext context) => const Row(
    children: [
      Icon(Icons.bolt_rounded, color: _orange, size: 30),
      SizedBox(width: 6),
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'INET',
            style: TextStyle(
              color: Colors.white,
              fontSize: 19,
              fontWeight: FontWeight.w900,
              letterSpacing: 1.5,
            ),
          ),
          Text(
            'AUTO LOGIN',
            style: TextStyle(
              color: Color(0xff9db8ff),
              fontSize: 9,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.35,
            ),
          ),
        ],
      ),
    ],
  );
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({required this.icon, required this.onPressed});
  final IconData icon;
  final VoidCallback onPressed;
  @override
  Widget build(BuildContext context) => IconButton(
    onPressed: onPressed,
    icon: Icon(icon),
    color: Colors.white,
    style: IconButton.styleFrom(
      backgroundColor: Colors.white.withValues(alpha: .12),
      fixedSize: const Size(44, 44),
    ),
  );
}

class _OrbitMark extends StatelessWidget {
  const _OrbitMark();
  @override
  Widget build(BuildContext context) => Container(
    width: 78,
    height: 78,
    decoration: BoxDecoration(
      shape: BoxShape.circle,
      gradient: const LinearGradient(colors: [_orange, _pink]),
      boxShadow: [
        BoxShadow(
          color: _pink.withValues(alpha: .35),
          blurRadius: 28,
          spreadRadius: 2,
        ),
      ],
    ),
    child: Container(
      margin: const EdgeInsets.all(6),
      decoration: const BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
      ),
      child: const Icon(Icons.wifi_rounded, color: _navy, size: 34),
    ),
  );
}

class _NoticeCard extends StatelessWidget {
  const _NoticeCard({required this.message});
  final String message;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: const Color(0xffffeeee),
      borderRadius: BorderRadius.circular(18),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          Icons.error_outline_rounded,
          color: Theme.of(context).colorScheme.error,
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            message,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ),
      ],
    ),
  );
}

class _NetworkDetails extends StatelessWidget {
  const _NetworkDetails({
    required this.snapshot,
    required this.ssid,
    required this.gateway,
    required this.localIp,
    required this.lastCheck,
    required this.lastAuth,
    required this.retry,
  });
  final DaemonSnapshot snapshot;
  final String ssid;
  final String gateway;
  final String localIp;
  final String lastCheck;
  final String lastAuth;
  final String retry;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle(
            icon: Icons.router_outlined,
            title: 'Chi tiết mạng',
          ),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (context, constraints) {
              final itemWidth = constraints.maxWidth < 410
                  ? constraints.maxWidth
                  : (constraints.maxWidth - 10) / 2;
              return Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  _InfoTile(
                    width: itemWidth,
                    label: 'WIFI HIỆN TẠI',
                    value: ssid,
                    icon: Icons.wifi_rounded,
                  ),
                  _InfoTile(
                    width: itemWidth,
                    label: 'ĐÚNG WIFI INET',
                    value: snapshot.isWifiTarget ? 'Có' : 'Không',
                    icon: snapshot.isWifiTarget
                        ? Icons.check_circle_outline
                        : Icons.highlight_off,
                  ),
                  _InfoTile(
                    width: itemWidth,
                    label: 'GATEWAY',
                    value: gateway,
                    icon: Icons.hub_outlined,
                  ),
                  _InfoTile(
                    width: itemWidth,
                    label: 'IP CỤC BỘ',
                    value: localIp,
                    icon: Icons.phone_android_rounded,
                  ),
                  _InfoTile(
                    width: itemWidth,
                    label: 'LẦN KIỂM TRA',
                    value: lastCheck,
                    icon: Icons.schedule_rounded,
                  ),
                  _InfoTile(
                    width: itemWidth,
                    label: 'LẦN ĐĂNG NHẬP',
                    value: lastAuth,
                    icon: Icons.login_rounded,
                  ),
                  _InfoTile(
                    width: itemWidth,
                    label: 'THỬ LẠI',
                    value: retry,
                    icon: Icons.replay_rounded,
                  ),
                  _InfoTile(
                    width: itemWidth,
                    label: 'SỐ LẦN LỖI',
                    value: '${snapshot.failureCount}',
                    icon: Icons.warning_amber_rounded,
                  ),
                ],
              );
            },
          ),
        ],
      ),
    ),
  );
}

class _InfoTile extends StatelessWidget {
  const _InfoTile({
    required this.width,
    required this.label,
    required this.value,
    required this.icon,
  });
  final double width;
  final String label;
  final String value;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Container(
    width: width,
    constraints: const BoxConstraints(minHeight: 78),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: const Color(0xfff5f7fc),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Row(
      children: [
        Icon(icon, size: 20, color: _blue),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                label,
                style: const TextStyle(
                  color: Color(0xff8a8fa1),
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                  letterSpacing: .55,
                ),
              ),
              const SizedBox(height: 4),
              SelectableText(
                value,
                style: const TextStyle(
                  color: _navy,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.icon, required this.title});
  final IconData icon;
  final String title;
  @override
  Widget build(BuildContext context) => Row(
    children: [
      Icon(icon, color: _blue, size: 21),
      const SizedBox(width: 9),
      Expanded(
        child: Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: _navy,
            fontWeight: FontWeight.w900,
            fontSize: 18,
          ),
        ),
      ),
    ],
  );
}

class _ActionPanel extends StatelessWidget {
  const _ActionPanel({
    required this.canRetry,
    required this.onRetry,
    required this.onBatterySettings,
    required this.onRefresh,
  });
  final bool canRetry;
  final VoidCallback onRetry;
  final VoidCallback onBatterySettings;
  final VoidCallback onRefresh;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _SectionTitle(
            icon: Icons.tune_rounded,
            title: 'Thao tác nhanh',
          ),
          const SizedBox(height: 14),
          FilledButton.icon(
            onPressed: canRetry ? onRetry : null,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Thử lại ngay'),
          ),
          const SizedBox(height: 9),
          LayoutBuilder(
            builder: (context, constraints) {
              final batteryButton = OutlinedButton.icon(
                onPressed: onBatterySettings,
                icon: const Icon(Icons.battery_saver_outlined, size: 19),
                label: const Text('Cài đặt pin'),
              );
              final refreshButton = OutlinedButton.icon(
                onPressed: onRefresh,
                icon: const Icon(Icons.sync_rounded, size: 19),
                label: const Text('Làm mới'),
              );
              if (constraints.maxWidth < 300) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    batteryButton,
                    const SizedBox(height: 9),
                    refreshButton,
                  ],
                );
              }
              return Row(
                children: [
                  Expanded(child: batteryButton),
                  const SizedBox(width: 9),
                  Expanded(child: refreshButton),
                ],
              );
            },
          ),
        ],
      ),
    ),
  );
}

class _LogsCard extends StatelessWidget {
  const _LogsCard({required this.logs});
  final List<String> logs;
  @override
  Widget build(BuildContext context) => Card(
    child: ExpansionTile(
      shape: const Border(),
      collapsedShape: const Border(),
      tilePadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 5),
      leading: const Icon(Icons.receipt_long_outlined, color: _blue),
      title: const Text(
        'Nhật ký gần đây',
        style: TextStyle(color: _navy, fontWeight: FontWeight.w800),
      ),
      subtitle: Text('${logs.length} dòng · đã loại dữ liệu nhạy cảm'),
      children: [
        Container(
          width: double.infinity,
          constraints: const BoxConstraints(maxHeight: 280),
          padding: const EdgeInsets.all(14),
          margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
          decoration: BoxDecoration(
            color: _navy,
            borderRadius: BorderRadius.circular(16),
          ),
          child: logs.isEmpty
              ? const Text(
                  'Chưa có nhật ký',
                  style: TextStyle(color: Colors.white70),
                )
              : SingleChildScrollView(
                  child: SelectableText(
                    logs.join('\n'),
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: Color(0xffdce5ff),
                    ),
                  ),
                ),
        ),
      ],
    ),
  );
}
