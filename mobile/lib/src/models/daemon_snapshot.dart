enum DaemonState {
  disabled,
  starting,
  waitingPermission,
  waitingWifi,
  checking,
  online,
  authenticatingCache,
  authenticatingCloud,
  backoff,
  error,
  unknown;

  static DaemonState parse(Object? value) {
    final normalized = value?.toString().toUpperCase();
    return switch (normalized) {
      'DISABLED' => disabled,
      'STARTING' => starting,
      'WAITING_PERMISSION' => waitingPermission,
      'WAITING_WIFI' => waitingWifi,
      'CHECKING' => checking,
      'ONLINE' => online,
      'AUTHENTICATING_CACHE' => authenticatingCache,
      'AUTHENTICATING_CLOUD' => authenticatingCloud,
      'BACKOFF' => backoff,
      'ERROR' => error,
      _ => unknown,
    };
  }
}

class DaemonSnapshot {
  const DaemonSnapshot({
    required this.serviceEnabled,
    required this.state,
    required this.stateMessage,
    required this.ssid,
    required this.gatewayIp,
    required this.localIp,
    required this.isWifiTarget,
    required this.lastCheckAt,
    required this.lastAuthAt,
    required this.retryAt,
    required this.failureCount,
    required this.lastError,
  });

  const DaemonSnapshot.disabled()
      : serviceEnabled = false,
        state = DaemonState.disabled,
        stateMessage = '',
        ssid = null,
        gatewayIp = null,
        localIp = null,
        isWifiTarget = false,
        lastCheckAt = null,
        lastAuthAt = null,
        retryAt = null,
        failureCount = 0,
        lastError = null;

  factory DaemonSnapshot.fromMap(Map<Object?, Object?> map) {
    String? text(String key) {
      final value = map[key];
      return value is String && value.trim().isNotEmpty ? value : null;
    }

    DateTime? time(String key) {
      final value = map[key];
      final millis = value is num ? value.toInt() : int.tryParse('$value');
      return millis == null || millis <= 0
          ? null
          : DateTime.fromMillisecondsSinceEpoch(millis);
    }

    return DaemonSnapshot(
      serviceEnabled: map['serviceEnabled'] == true,
      state: DaemonState.parse(map['state']),
      stateMessage: text('stateMessage') ?? '',
      ssid: text('ssid'),
      gatewayIp: text('gatewayIp'),
      localIp: text('localIp'),
      isWifiTarget: map['isWifiTarget'] == true,
      lastCheckAt: time('lastCheckAt'),
      lastAuthAt: time('lastAuthAt'),
      retryAt: time('retryAt'),
      failureCount: map['failureCount'] is num
          ? (map['failureCount'] as num).toInt()
          : 0,
      lastError: text('lastError'),
    );
  }

  final bool serviceEnabled;
  final DaemonState state;
  final String stateMessage;
  final String? ssid;
  final String? gatewayIp;
  final String? localIp;
  final bool isWifiTarget;
  final DateTime? lastCheckAt;
  final DateTime? lastAuthAt;
  final DateTime? retryAt;
  final int failureCount;
  final String? lastError;
}
