package vn.pckien.inet_auto_login.auth

import android.net.Network
import vn.pckien.inet_auto_login.network.*

enum class GatewayStatus { ONLINE, LOGIN_REQUIRED, UNKNOWN, UNREACHABLE }
interface GatewayAccess {
    suspend fun checkStatus(network: Network, gateway: String): GatewayStatus
    suspend fun fetchLoginPage(network: Network, gateway: String): PortalParameters
    suspend fun login(network: Network, gateway: String, username: String, chapPassword: String): HttpResponse
}
class GatewayClient(private val transport: BoundHttpTransport) : GatewayAccess {
    fun classify(response: HttpResponse): GatewayStatus {
        val body = response.text().lowercase()
        val location = response.header("Location")?.lowercase().orEmpty()
        if ("inetcenter.vn" in body || Regex("\\bsuccess\\b", RegexOption.IGNORE_CASE).containsMatchIn(body)) return GatewayStatus.ONLINE
        if ("name=\"username\"" in body || "name='username'" in body || "id=\"serial\"" in body || "id='serial'" in body ||
            "login" in location || "awingconnect" in location) return GatewayStatus.LOGIN_REQUIRED
        return GatewayStatus.UNKNOWN
    }
    override suspend fun checkStatus(network: Network, gateway: String): GatewayStatus = try {
        classify(transport.execute(network, HttpRequest("http://$gateway/status")))
    } catch (_: TransportException) { GatewayStatus.UNREACHABLE }
    override suspend fun fetchLoginPage(network: Network, gateway: String): PortalParameters =
        PortalPageParser.parse(transport.execute(network, HttpRequest("http://$gateway/login")).text())
    override suspend fun login(network: Network, gateway: String, username: String, chapPassword: String): HttpResponse =
        transport.execute(network, HttpRequest("http://$gateway/login", "POST", form = linkedMapOf(
            "username" to username, "password" to chapPassword, "dst" to "http://v1.awingconnect.vn/Success", "popup" to "false")))
}
