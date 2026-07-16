import 'package:flutter_test/flutter_test.dart';
import 'package:inet_auto_login/src/models/daemon_snapshot.dart';

void main() {
  test('parses the complete native schema', () {
    final snapshot = DaemonSnapshot.fromMap({
      'serviceEnabled': true, 'state': 'ONLINE', 'stateMessage': 'ok',
      'ssid': 'INET - Free WiFi', 'gatewayIp': '192.0.2.1', 'localIp': '192.0.2.2',
      'isWifiTarget': true, 'lastCheckAt': 1000, 'lastAuthAt': 2000,
      'retryAt': 3000, 'failureCount': 2, 'lastError': 'safe error',
    });
    expect(snapshot.state, DaemonState.online);
    expect(snapshot.gatewayIp, '192.0.2.1');
    expect(snapshot.lastAuthAt?.millisecondsSinceEpoch, 2000);
    expect(snapshot.failureCount, 2);
  });

  test('uses safe defaults and unknown state fallback', () {
    final snapshot = DaemonSnapshot.fromMap({'state': 'NEW_NATIVE_STATE'});
    expect(snapshot.state, DaemonState.unknown);
    expect(snapshot.serviceEnabled, isFalse);
    expect(snapshot.ssid, isNull);
  });
}
