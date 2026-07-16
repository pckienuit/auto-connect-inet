package vn.pckien.inet_auto_login.network

import org.junit.Assert.*
import org.junit.Test

class NetworkSelectorsTest {
    @Test fun normalizesOnlyOuterQuotesAndMatchesCaseInsensitive() {
        assertEquals("INET - Free WiFi", NetworkSelectors.normalizeSsid("\"INET - Free WiFi\""))
        assertTrue(NetworkSelectors.isTargetSsid("inet - free wifi"))
        assertNull(NetworkSelectors.normalizeSsid("<unknown ssid>"))
        assertFalse(NetworkSelectors.isTargetSsid("INET-Free WiFi"))
    }
    @Test fun selectsOnlyDefaultIpv4Gateway() {
        val routes = listOf(NetworkSelectors.RouteCandidate("2001:db8::1", true, false), NetworkSelectors.RouteCandidate("192.0.2.1", false, true), NetworkSelectors.RouteCandidate("192.0.2.254", true, true))
        assertEquals("192.0.2.254", NetworkSelectors.selectIpv4Gateway(routes))
    }
}
