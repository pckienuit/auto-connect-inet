import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:inet_auto_login/src/platform/auto_login_platform.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('test/control');
  final calls = <MethodCall>[];

  setUp(() {
    calls.clear();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      if (call.method == 'getSnapshot') return {'state': 'DISABLED'};
      if (call.method == 'getRecentLogs') return ['one'];
      if (call.method == 'requestPermissions') return {'granted': true, 'missing': <String>[]};
      return null;
    });
  });

  tearDown(() => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(channel, null));

  test('invokes contract methods and arguments', () async {
    final platform = AutoLoginPlatform(methodChannel: channel, eventChannel: const EventChannel('test/events'));
    await platform.start(); await platform.stop(); await platform.retryNow();
    await platform.getSnapshot(); await platform.getRecentLogs(limit: 42);
    await platform.openBatterySettings(); await platform.requestPermissions();
    expect(calls.map((c) => c.method), ['start', 'stop', 'retryNow', 'getSnapshot', 'getRecentLogs', 'openBatterySettings', 'requestPermissions']);
    expect(calls[4].arguments, {'limit': 42});
  });
}
