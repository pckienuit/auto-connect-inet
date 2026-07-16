import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:inet_auto_login/app.dart';
import 'package:inet_auto_login/src/models/daemon_snapshot.dart';
import 'package:inet_auto_login/src/models/stability_snapshot.dart';
import 'package:inet_auto_login/src/platform/auto_login_platform.dart';

class FakePlatform implements AutoLoginApi {
  final controller = StreamController<DaemonSnapshot>.broadcast();
  DaemonSnapshot snapshot = const DaemonSnapshot.disabled();
  bool permissionGranted = true;
  int starts = 0, stops = 0, retries = 0;
  @override Stream<DaemonSnapshot> get snapshots => controller.stream;
  @override Future<DaemonSnapshot> getSnapshot() async => snapshot;
  @override Future<PermissionResult> requestPermissions() async => PermissionResult(granted: permissionGranted, missing: permissionGranted ? const [] : const ['permission']);
  @override Future<void> start() async { starts++; }
  @override Future<void> stop() async { stops++; }
  @override Future<void> retryNow() async { retries++; }
  @override Future<List<String>> getRecentLogs({int limit = 200}) async => ['safe log'];
  @override Future<void> openBatterySettings() async {}
  final stabilityController = StreamController<StabilitySnapshot>.broadcast();
  int stabilityStarts = 0, stabilityStops = 0, stabilityDuration = 0;
  @override Stream<StabilitySnapshot> get stabilitySnapshots => stabilityController.stream;
  @override Future<void> startStabilityTest({int durationSeconds = 60}) async { stabilityStarts++; stabilityDuration = durationSeconds; }
  @override Future<void> stopStabilityTest() async { stabilityStops++; }
}

DaemonSnapshot state(DaemonState value, {bool enabled = true, DateTime? retryAt}) => DaemonSnapshot(
  serviceEnabled: enabled, state: value, stateMessage: 'Thông tin trạng thái', ssid: 'INET - Free WiFi', gatewayIp: '192.0.2.1', localIp: '192.0.2.2', isWifiTarget: true, lastCheckAt: null, lastAuthAt: null, retryAt: retryAt, failureCount: 0, lastError: null,
);

void main() {
  testWidgets('renders online details and receives event update', (tester) async {
    final fake = FakePlatform()..snapshot = state(DaemonState.waitingWifi);
    await tester.pumpWidget(InetAutoLoginApp(platform: fake));
    await tester.pumpAndSettle();
    expect(find.text('Đang chờ WiFi INET'), findsOneWidget);
    fake.controller.add(state(DaemonState.online));
    await tester.pumpAndSettle();
    expect(find.text('Đã đăng nhập'), findsOneWidget);
    expect(find.text('192.0.2.1'), findsOneWidget);
  });

  testWidgets('toggle requests permission before start', (tester) async {
    final fake = FakePlatform();
    await tester.pumpWidget(InetAutoLoginApp(platform: fake)); await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('masterSwitch'))); await tester.pumpAndSettle();
    await tester.tap(find.text('Tiếp tục')); await tester.pumpAndSettle();
    expect(fake.starts, 1);
  });

  testWidgets('permission denial does not start service', (tester) async {
    final fake = FakePlatform()..permissionGranted = false;
    await tester.pumpWidget(InetAutoLoginApp(platform: fake)); await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('masterSwitch'))); await tester.pumpAndSettle();
    await tester.tap(find.text('Tiếp tục')); await tester.pumpAndSettle();
    expect(fake.starts, 0);
    expect(find.textContaining('Chưa cấp đủ quyền'), findsOneWidget);
  });

  testWidgets('stability section starts selected duration and renders metrics', (tester) async {
    final fake = FakePlatform();
    await tester.pumpWidget(InetAutoLoginApp(platform: fake)); await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const Key('stabilityToggle')),
      300,
      scrollable: find.descendant(
        of: find.byKey(const Key('dashboardList')),
        matching: find.byType(Scrollable),
      ).first,
    );
    await tester.tap(find.text('120 giây')); await tester.pump();
    await tester.tap(find.byKey(const Key('stabilityToggle'))); await tester.pump();
    expect(fake.stabilityStarts, 1); expect(fake.stabilityDuration, 120);
    fake.stabilityController.add(const StabilitySnapshot(
      running: true, elapsedMs: 1500, durationMs: 120000, sent: 3, received: 2,
      lossPercent: 33.3, latestLatencyMs: 20, minLatencyMs: 10,
      averageLatencyMs: 15, maxLatencyMs: 20, jitterMs: 10,
      outageCount: 1, currentOutageMs: 0, maxOutageMs: 500,
      rating: StabilityRating.jittery, networkLabel: 'Mạng đang hoạt động (dự phòng)',
    ));
    await tester.pump();
    expect(find.text('Đánh giá: Dao động'), findsOneWidget);
    expect(find.text('Mạng đang hoạt động (dự phòng)'), findsOneWidget);
  });

  testWidgets('backoff countdown never displays negative number', (tester) async {
    final fake = FakePlatform()..snapshot = state(DaemonState.backoff, retryAt: DateTime.now().subtract(const Duration(seconds: 10)));
    await tester.pumpWidget(InetAutoLoginApp(platform: fake)); await tester.pumpAndSettle();
    expect(find.text('Sẵn sàng thử lại'), findsOneWidget);
  });

  testWidgets('fits at 320 dp and landscape without overflow', (tester) async {
    tester.view.physicalSize = const Size(320, 600); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(InetAutoLoginApp(platform: FakePlatform())); await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    tester.view.physicalSize = const Size(600, 320); await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
