package vn.pckien.inet_auto_login.network

import android.net.Network

data class NetworkContext(
    val network: Network,
    val generation: Long,
    val ssid: String,
    val localIp: String,
    val gatewayIp: String,
)

interface NetworkRepository {
    fun current(): NetworkContext?
    fun start(listener: (NetworkContext?) -> Unit)
    fun stop()
}

object NetworkSelectors {
    const val TARGET_SSID = "INET - Free WiFi"
    fun normalizeSsid(value: String?): String? {
        val text = value?.trim()?.takeUnless { it.isEmpty() || it.equals("<unknown ssid>", true) } ?: return null
        return if (text.length >= 2 && text.first() == '"' && text.last() == '"') text.substring(1, text.length - 1) else text
    }
    fun isTargetSsid(value: String?): Boolean = normalizeSsid(value)?.equals(TARGET_SSID, true) == true
    data class RouteCandidate(val gateway: String?, val isDefault: Boolean, val isIpv4: Boolean)
    fun selectIpv4Gateway(routes: List<RouteCandidate>): String? =
        routes.firstOrNull { it.isDefault && it.isIpv4 && !it.gateway.isNullOrBlank() }?.gateway
}
