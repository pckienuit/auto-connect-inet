import 'package:flutter_test/flutter_test.dart';
import 'package:inet_auto_login/src/models/daemon_snapshot.dart';

void main() {
  test('default snapshot is disabled', () {
    expect(const DaemonSnapshot.disabled().state, DaemonState.disabled);
  });
}
