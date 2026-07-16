enum StabilityRating { excellent, jittery, laggy, bad, noConnection }

class StabilitySnapshot {
  const StabilitySnapshot({
    required this.running,
    required this.elapsedMs,
    required this.durationMs,
    required this.sent,
    required this.received,
    required this.lossPercent,
    this.latestLatencyMs,
    this.minLatencyMs,
    this.averageLatencyMs,
    this.maxLatencyMs,
    required this.jitterMs,
    required this.outageCount,
    required this.currentOutageMs,
    required this.maxOutageMs,
    required this.rating,
    this.error,
    required this.networkLabel,
  });

  factory StabilitySnapshot.fromMap(Map<Object?, Object?> map) {
    int integer(String key) => (map[key] as num?)?.toInt() ?? 0;
    double decimal(String key) => (map[key] as num?)?.toDouble() ?? 0;
    double? nullableDecimal(String key) => (map[key] as num?)?.toDouble();
    final ratingName = '${map['rating'] ?? 'noConnection'}';
    return StabilitySnapshot(
      running: map['running'] == true,
      elapsedMs: integer('elapsedMs'), durationMs: integer('durationMs'),
      sent: integer('sent'), received: integer('received'),
      lossPercent: decimal('lossPercent'), latestLatencyMs: nullableDecimal('latestLatencyMs'),
      minLatencyMs: nullableDecimal('minLatencyMs'), averageLatencyMs: nullableDecimal('averageLatencyMs'),
      maxLatencyMs: nullableDecimal('maxLatencyMs'), jitterMs: decimal('jitterMs'),
      outageCount: integer('outageCount'), currentOutageMs: integer('currentOutageMs'),
      maxOutageMs: integer('maxOutageMs'),
      rating: StabilityRating.values.firstWhere(
        (value) => value.name == ratingName,
        orElse: () => StabilityRating.noConnection,
      ),
      error: map['error'] == null ? null : '${map['error']}',
      networkLabel: '${map['networkLabel'] ?? 'Chưa xác định mạng'}',
    );
  }

  final bool running;
  final int elapsedMs, durationMs, sent, received, outageCount, currentOutageMs, maxOutageMs;
  final double lossPercent, jitterMs;
  final double? latestLatencyMs, minLatencyMs, averageLatencyMs, maxLatencyMs;
  final StabilityRating rating;
  final String? error;
  final String networkLabel;
  bool get isUnlimited => durationMs == 0;
  double get progress => durationMs <= 0 ? 0 : (elapsedMs / durationMs).clamp(0.0, 1.0).toDouble();
}
