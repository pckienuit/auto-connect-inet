import 'package:flutter/services.dart';

import '../models/daemon_snapshot.dart';
import '../models/stability_snapshot.dart';

class PermissionResult {
  const PermissionResult({required this.granted, required this.missing});

  factory PermissionResult.fromMap(Map<Object?, Object?> map) => PermissionResult(
        granted: map['granted'] == true,
        missing: (map['missing'] as List<Object?>? ?? const [])
            .map((value) => '$value')
            .toList(growable: false),
      );

  final bool granted;
  final List<String> missing;
}

abstract interface class AutoLoginApi {
  Stream<DaemonSnapshot> get snapshots;
  Future<DaemonSnapshot> getSnapshot();
  Future<PermissionResult> requestPermissions();
  Future<void> start();
  Future<void> stop();
  Future<void> retryNow();
  Future<List<String>> getRecentLogs({int limit = 200});
  Future<void> openBatterySettings();
  Stream<StabilitySnapshot> get stabilitySnapshots;
  Future<void> startStabilityTest({int durationSeconds = 60});
  Future<void> stopStabilityTest();
}

class AutoLoginPlatform implements AutoLoginApi {
  AutoLoginPlatform({MethodChannel? methodChannel, EventChannel? eventChannel,
    MethodChannel? stabilityMethodChannel, EventChannel? stabilityEventChannel})
      : _method = methodChannel ?? const MethodChannel(methodChannelName),
        _event = eventChannel ?? const EventChannel(eventChannelName),
        _stabilityMethod = stabilityMethodChannel ?? const MethodChannel(stabilityMethodChannelName),
        _stabilityEvent = stabilityEventChannel ?? const EventChannel(stabilityEventChannelName);

  static const methodChannelName = 'vn.pckien.inet_auto_login/control';
  static const eventChannelName = 'vn.pckien.inet_auto_login/events';
  static const stabilityMethodChannelName = 'vn.pckien.inet_auto_login/stability_control';
  static const stabilityEventChannelName = 'vn.pckien.inet_auto_login/stability';
  final MethodChannel _method;
  final EventChannel _event;
  final MethodChannel _stabilityMethod;
  final EventChannel _stabilityEvent;

  @override
  Stream<StabilitySnapshot> get stabilitySnapshots => _stabilityEvent
      .receiveBroadcastStream()
      .where((event) => event is Map)
      .map((event) => StabilitySnapshot.fromMap((event as Map).cast<Object?, Object?>()));

  @override
  Future<void> startStabilityTest({int durationSeconds = 60}) => _stabilityMethod
      .invokeMethod<void>('startStabilityTest', {'durationSeconds': durationSeconds});

  @override
  Future<void> stopStabilityTest() => _stabilityMethod.invokeMethod<void>('stopStabilityTest');

  @override
  Stream<DaemonSnapshot> get snapshots => _event
      .receiveBroadcastStream()
      .where((event) => event is Map)
      .map((event) => DaemonSnapshot.fromMap((event as Map).cast<Object?, Object?>()));

  @override
  Future<DaemonSnapshot> getSnapshot() async {
    final map = await _method.invokeMapMethod<Object?, Object?>('getSnapshot');
    return DaemonSnapshot.fromMap(map ?? const {});
  }

  @override
  Future<PermissionResult> requestPermissions() async {
    final map = await _method.invokeMapMethod<Object?, Object?>('requestPermissions');
    return PermissionResult.fromMap(map ?? const {});
  }

  @override
  Future<void> start() => _method.invokeMethod<void>('start');
  @override
  Future<void> stop() => _method.invokeMethod<void>('stop');
  @override
  Future<void> retryNow() => _method.invokeMethod<void>('retryNow');
  @override
  Future<void> openBatterySettings() => _method.invokeMethod<void>('openBatterySettings');

  @override
  Future<List<String>> getRecentLogs({int limit = 200}) async {
    final lines = await _method.invokeListMethod<Object?>('getRecentLogs', {'limit': limit});
    return (lines ?? const []).map((line) => '$line').toList(growable: false);
  }
}
