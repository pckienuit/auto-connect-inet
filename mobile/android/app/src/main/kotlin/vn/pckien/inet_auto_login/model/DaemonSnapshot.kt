package vn.pckien.inet_auto_login.model

data class DaemonSnapshot(
    val serviceEnabled: Boolean = false,
    val state: DaemonState = DaemonState.DISABLED,
    val stateMessage: String = "",
    val ssid: String? = null,
    val gatewayIp: String? = null,
    val localIp: String? = null,
    val isWifiTarget: Boolean = false,
    val lastCheckAt: Long? = null,
    val lastAuthAt: Long? = null,
    val retryAt: Long? = null,
    val failureCount: Int = 0,
    val lastError: String? = null,
) {
    fun toMap(): Map<String, Any?> = mapOf(
        "serviceEnabled" to serviceEnabled, "state" to state.name,
        "stateMessage" to stateMessage, "ssid" to ssid, "gatewayIp" to gatewayIp,
        "localIp" to localIp, "isWifiTarget" to isWifiTarget,
        "lastCheckAt" to lastCheckAt, "lastAuthAt" to lastAuthAt,
        "retryAt" to retryAt, "failureCount" to failureCount, "lastError" to lastError,
    )
}
