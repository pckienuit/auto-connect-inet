package vn.pckien.inet_auto_login.auth

data class PortalParameters(
    val serial: String, val clientMac: String, val clientIp: String, val loginUrl: String,
    val chapIdBytes: ByteArray, val chapChallengeBytes: ByteArray,
)
class PortalParseException(val field: String) : IllegalArgumentException("Missing or malformed portal field: $field")
object PortalPageParser {
    private fun field(html: String, id: String): String {
        val tag = Regex("<input\\b[^>]*\\bid\\s*=\\s*(['\"])${Regex.escape(id)}\\1[^>]*>", RegexOption.IGNORE_CASE).find(html)?.value
            ?: throw PortalParseException(id)
        return Regex("\\bvalue\\s*=\\s*(['\"])(.*?)\\1", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
            .find(tag)?.groupValues?.get(2) ?: throw PortalParseException(id)
    }
    fun parse(html: String): PortalParameters = try {
        PortalParameters(field(html,"serial"), field(html,"client_mac"), field(html,"client_ip"), field(html,"login_url"),
            OctalParser.decode(field(html,"chap-id")), OctalParser.decode(field(html,"chap-challenge")))
    } catch (e: PortalParseException) { throw e } catch (e: IllegalArgumentException) { throw PortalParseException("octal") }
}
