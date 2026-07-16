package vn.pckien.inet_auto_login.service

import org.junit.Assert.assertEquals
import org.junit.Test

class BackoffPolicyTest {
    @Test fun followsSequenceAndCapsAtFiveMinutes() {
        val policy = BackoffPolicy()
        assertEquals(listOf(15_000L,30_000L,60_000L,120_000L,240_000L,300_000L,300_000L), (1..7).map(policy::delayFor))
    }
}
