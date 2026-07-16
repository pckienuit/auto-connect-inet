package vn.pckien.inet_auto_login.auth

import org.junit.Assert.*
import org.junit.Test
import vn.pckien.inet_auto_login.network.*

class GatewayAndAwingTest {
    private val unused = object : BoundHttpTransport { override suspend fun execute(network: android.net.Network?, request: HttpRequest) = error("unused") }
    @Test fun gatewayClassificationIsConservative() {
        val client = GatewayClient(unused)
        fun response(status: Int, body: String = "", location: String? = null) = HttpResponse(status, location?.let { mapOf("Location" to listOf(it)) } ?: emptyMap(), body.toByteArray())
        assertEquals(GatewayStatus.ONLINE, client.classify(response(200, "Welcome inetcenter.vn")))
        assertEquals(GatewayStatus.LOGIN_REQUIRED, client.classify(response(200, "<input name=\"username\">")))
        assertEquals(GatewayStatus.LOGIN_REQUIRED, client.classify(response(302, location = "/login")))
        assertEquals(GatewayStatus.UNKNOWN, client.classify(response(200, "plain response")))
        assertEquals(GatewayStatus.UNKNOWN, client.classify(response(302, location = "/other")))
    }
    @Test fun cookieAndNestedFormParsing() {
        val client = AwingClient(unused)
        assertEquals("abc", client.extractIngressCookie(listOf("other=x; Path=/", "ingresscookie=abc; HttpOnly")))
        val json = """{"captiveContext":{"contentAuthenForm":"<input value='test-user' name='username'><input name='password' value='test-pass'>"}}"""
        val credential = client.parseCredential(json)
        assertEquals("test-user", credential.username); assertEquals("test-pass", credential.password)
    }
    @Test fun queryEncodesHighBytesLikeFormEncoding() {
        val p = PortalParameters("s", "02:00:00:00:00:00", "192.0.2.10", "http://192.0.2.1/login", byteArrayOf(-128), byteArrayOf(-1))
        val query = AwingClient(unused).buildReferer(p)
        assertTrue(query.contains("chap-id=%C2%80")); assertTrue(query.contains("chap-challenge=%C3%BF"))
    }
    @Test(expected = AwingException.InvalidJson::class) fun schemaChangeIsTyped() { AwingClient(unused).parseCredential("{}") }
}
