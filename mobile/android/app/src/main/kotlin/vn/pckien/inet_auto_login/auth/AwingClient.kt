package vn.pckien.inet_auto_login.auth

import android.net.Network
import org.json.JSONObject
import vn.pckien.inet_auto_login.network.*
import java.net.URLEncoder

sealed class AwingException(message: String) : Exception(message) {
    class MissingCookie : AwingException("AWING ingress cookie is missing")
    class InvalidJson : AwingException("AWING response schema is invalid")
    class MissingFormField(field: String) : AwingException("AWING form field is missing: $field")
}
fun interface AwingAccess { suspend fun fetch(network: Network?, portal: PortalParameters): vn.pckien.inet_auto_login.storage.Credential }
class AwingClient(private val transport: BoundHttpTransport) : AwingAccess {
    private fun enc(value: String) = URLEncoder.encode(value, "UTF-8")
    fun buildReferer(p: PortalParameters): String {
        fun latin(bytes: ByteArray) = bytes.toString(Charsets.ISO_8859_1)
        val params = linkedMapOf("serial" to p.serial, "client_mac" to p.clientMac, "client_ip" to p.clientIp,
            "userurl" to "http://www.msftconnecttest.com/redirect", "login_url" to p.loginUrl,
            "chap-id" to latin(p.chapIdBytes), "chap-challenge" to latin(p.chapChallengeBytes))
        return "http://v1.awingconnect.vn/login?" + params.entries.joinToString("&") { "${enc(it.key)}=${enc(it.value)}" }
    }
    fun extractIngressCookie(headers: List<String>): String? = headers.asSequence().mapNotNull { header ->
        header.split(';').firstOrNull()?.trim()?.takeIf { it.substringBefore('=').equals("ingresscookie", true) }?.substringAfter('=')
    }.firstOrNull()
    fun parseCredential(json: String): vn.pckien.inet_auto_login.storage.Credential {
        val form = try { JSONObject(json).getJSONObject("captiveContext").getString("contentAuthenForm") } catch (_: Exception) { throw AwingException.InvalidJson() }
        fun input(name: String): String {
            val tag = Regex("<input\\b[^>]*\\bname\\s*=\\s*(['\"])${Regex.escape(name)}\\1[^>]*>", RegexOption.IGNORE_CASE).find(form)?.value
                ?: throw AwingException.MissingFormField(name)
            return Regex("\\bvalue\\s*=\\s*(['\"])(.*?)\\1", RegexOption.IGNORE_CASE).find(tag)?.groupValues?.get(2)
                ?: throw AwingException.MissingFormField(name)
        }
        return vn.pckien.inet_auto_login.storage.Credential(input("username"), input("password"))
    }
    override suspend fun fetch(network: Network?, portal: PortalParameters): vn.pckien.inet_auto_login.storage.Credential {
        val referer = buildReferer(portal)
        val first = transport.execute(network, HttpRequest(referer, connectTimeoutMs = 5_000, readTimeoutMs = 5_000))
        val cookie = extractIngressCookie(first.headers("Set-Cookie")) ?: throw AwingException.MissingCookie()
        val verify = transport.execute(network, HttpRequest("http://v1.awingconnect.vn/Home/VerifyUrl", "POST", mapOf(
            "Referer" to referer, "X-Requested-With" to "XMLHttpRequest", "Cookie" to "ingresscookie=$cookie"), body = ByteArray(0), connectTimeoutMs = 5_000, readTimeoutMs = 5_000))
        return parseCredential(verify.text())
    }
}
