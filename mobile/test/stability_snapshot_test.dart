import 'package:flutter_test/flutter_test.dart';
import 'package:inet_auto_login/src/models/stability_snapshot.dart';

void main() {
  test('parses complete stability event with numeric coercion', () {
    final value = StabilitySnapshot.fromMap({
      'running': true,
      'elapsedMs': 1500,
      'durationMs': 30000,
      'sent': 3,
      'received': 2,
      'lossPercent': 33,
      'latestLatencyMs': 12,
      'minLatencyMs': 10.5,
      'averageLatencyMs': 11,
      'maxLatencyMs': 12.5,
      'jitterMs': 2,
      'outageCount': 1,
      'currentOutageMs': 0,
      'maxOutageMs': 500,
      'rating': 'jittery',
      'networkLabel': 'INET WiFi: INET - Free WiFi',
    });
    expect(value.running, isTrue);
    expect(value.lossPercent, 33.0);
    expect(value.averageLatencyMs, 11.0);
    expect(value.rating, StabilityRating.jittery);
    expect(value.progress, .05);
  });

  test('uses safe defaults for partial event', () {
    final value = StabilitySnapshot.fromMap(const {});
    expect(value.rating, StabilityRating.noConnection);
    expect(value.networkLabel, 'Chưa xác định mạng');
    expect(value.progress, 0);
  });

  test('zero duration represents an unlimited test', () {
    final value = StabilitySnapshot.fromMap(const {
      'running': true,
      'elapsedMs': 90000,
      'durationMs': 0,
    });
    expect(value.isUnlimited, isTrue);
    expect(value.progress, 0);
  });
}
