package vn.pckien.inet_auto_login.stability

import org.junit.Assert.*
import org.junit.Test

class StabilityAccumulatorTest {
    @Test fun `calculates loss latency and jitter`() {
        val subject = StabilityAccumulator()
        subject.record(10.0, 0); subject.record(30.0, 500); subject.record(null, 1_000)
        val result = subject.snapshot(1_500)
        assertEquals(3, result.sent); assertEquals(2, result.received)
        assertEquals(100.0 / 3.0, result.lossPercent, 0.001)
        assertEquals(20.0, result.averageLatencyMs!!, 0.001)
        assertEquals(20.0, result.jitterMs, 0.001)
    }

    @Test fun `counts consecutive failures as one outage and tracks durations`() {
        val subject = StabilityAccumulator()
        subject.record(null, 100); subject.record(null, 600)
        assertEquals(500, subject.snapshot(600).currentOutageMs)
        subject.record(12.0, 1_100)
        val result = subject.snapshot(1_200)
        assertEquals(1, result.outageCount); assertEquals(0, result.currentOutageMs)
        assertEquals(1_000, result.maxOutageMs)
    }

    @Test fun `rates representative quality levels`() {
        assertEquals(StabilityRating.NO_CONNECTION, StabilityAccumulator.rate(2, 0, 100.0, null, 0.0, 500))
        assertEquals(StabilityRating.BAD, StabilityAccumulator.rate(10, 8, 20.0, 100.0, 5.0, 500))
        assertEquals(StabilityRating.LAGGY, StabilityAccumulator.rate(10, 10, 0.0, 250.0, 5.0, 0))
        assertEquals(StabilityRating.JITTERY, StabilityAccumulator.rate(10, 10, 0.0, 30.0, 45.0, 0))
        assertEquals(StabilityRating.EXCELLENT, StabilityAccumulator.rate(10, 10, 0.0, 30.0, 5.0, 0))
    }
}
