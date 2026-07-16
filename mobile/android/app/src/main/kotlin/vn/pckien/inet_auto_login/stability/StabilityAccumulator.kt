package vn.pckien.inet_auto_login.stability

import kotlin.math.abs

enum class StabilityRating(val wireName: String) {
    EXCELLENT("excellent"), JITTERY("jittery"), LAGGY("laggy"), BAD("bad"), NO_CONNECTION("noConnection")
}

data class StabilityMetrics(
    val sent: Int,
    val received: Int,
    val lossPercent: Double,
    val latestLatencyMs: Double?,
    val minLatencyMs: Double?,
    val averageLatencyMs: Double?,
    val maxLatencyMs: Double?,
    val jitterMs: Double,
    val outageCount: Int,
    val currentOutageMs: Long,
    val maxOutageMs: Long,
    val rating: StabilityRating,
)

/** Pure statistics collector. Time values are monotonic milliseconds. */
class StabilityAccumulator {
    private var sent = 0
    private var received = 0
    private var latencyTotal = 0.0
    private var latestLatency: Double? = null
    private var minimumLatency: Double? = null
    private var maximumLatency: Double? = null
    private var previousLatency: Double? = null
    private var jitterTotal = 0.0
    private var jitterSamples = 0
    private var outages = 0
    private var outageStartedAt: Long? = null
    private var maximumOutage = 0L

    fun record(latencyMs: Double?, nowMs: Long) {
        sent++
        if (latencyMs == null) {
            if (outageStartedAt == null) {
                outageStartedAt = nowMs
                outages++
            }
            return
        }

        closeOutage(nowMs)
        received++
        latestLatency = latencyMs
        latencyTotal += latencyMs
        minimumLatency = minimumLatency?.coerceAtMost(latencyMs) ?: latencyMs
        maximumLatency = maximumLatency?.coerceAtLeast(latencyMs) ?: latencyMs
        previousLatency?.let {
            jitterTotal += abs(latencyMs - it)
            jitterSamples++
        }
        previousLatency = latencyMs
    }

    fun snapshot(nowMs: Long): StabilityMetrics {
        val currentOutage = outageStartedAt?.let { (nowMs - it).coerceAtLeast(0) } ?: 0L
        val maxOutage = maxOf(maximumOutage, currentOutage)
        val loss = if (sent == 0) 0.0 else (sent - received) * 100.0 / sent
        val average = if (received == 0) null else latencyTotal / received
        val jitter = if (jitterSamples == 0) 0.0 else jitterTotal / jitterSamples
        return StabilityMetrics(
            sent, received, loss, latestLatency, minimumLatency, average, maximumLatency,
            jitter, outages, currentOutage, maxOutage,
            rate(sent, received, loss, average, jitter, maxOutage),
        )
    }

    private fun closeOutage(nowMs: Long) {
        outageStartedAt?.let { maximumOutage = maxOf(maximumOutage, (nowMs - it).coerceAtLeast(0)) }
        outageStartedAt = null
    }

    companion object {
        fun rate(sent: Int, received: Int, loss: Double, average: Double?, jitter: Double, maxOutageMs: Long): StabilityRating {
            if (sent > 0 && received == 0) return StabilityRating.NO_CONNECTION
            if (loss >= 20 || (average ?: 0.0) >= 500 || maxOutageMs >= 3_000) return StabilityRating.BAD
            if (loss >= 5 || (average ?: 0.0) >= 200 || jitter >= 100) return StabilityRating.LAGGY
            if (loss > 0 || jitter >= 40) return StabilityRating.JITTERY
            return StabilityRating.EXCELLENT
        }
    }
}
