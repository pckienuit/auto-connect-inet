import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:inet_auto_login/src/platform/auto_login_platform.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('test/control');
  const stabilityChannel = MethodChannel('test/stability_control');
  final calls = <MethodCall>[];

  setUp(() {
    calls.clear();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          calls.add(call);
          if (call.method == 'getSnapshot') return {'state': 'DISABLED'};
          if (call.method == 'getRecentLogs') return ['one'];
          if (call.method == 'requestPermissions') {
            return {'granted': true, 'missing': <String>[]};
          }
          return null;
        });
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(stabilityChannel, (call) async {
          calls.add(call);
          return null;
        });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(stabilityChannel, null);
  });

  test('invokes contract methods and arguments', () async {
    final platform = AutoLoginPlatform(
      methodChannel: channel,
      eventChannel: const EventChannel('test/events'),
      stabilityMethodChannel: stabilityChannel,
      stabilityEventChannel: const EventChannel('test/stability'),
    );
    await platform.start();
    await platform.stop();
    await platform.retryNow();
    await platform.getSnapshot();
    await platform.getRecentLogs(limit: 42);
    await platform.openBatterySettings();
    await platform.requestPermissions();
    await platform.startStabilityTest(durationSeconds: 120);
    await platform.stopStabilityTest();
    expect(calls.map((c) => c.method), [
      'start',
      'stop',
      'retryNow',
      'getSnapshot',
      'getRecentLogs',
      'openBatterySettings',
      'requestPermissions',
      'startStabilityTest',
      'stopStabilityTest',
    ]);
    expect(calls[4].arguments, {'limit': 42});
    expect(calls[7].arguments, {'durationSeconds': 120});
  });
}
