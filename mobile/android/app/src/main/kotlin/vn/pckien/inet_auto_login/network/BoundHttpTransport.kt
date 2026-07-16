package vn.pckien.inet_auto_login.network

import android.net.Network
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.URLEncoder

data class HttpRequest(
    val url: String,
    val method: String = "GET",
    val headers: Map<String, String> = emptyMap(),
    val form: Map<String, String>? = null,
    val body: ByteArray? = null,
    val connectTimeoutMs: Int = 3_000,
    val readTimeoutMs: Int = 3_000,
)
data class HttpResponse(val status: Int, val headers: Map<String, List<String>>, val body: ByteArray) {
    fun header(name: String): String? = headers.entries.firstOrNull { it.key.equals(name, true) }?.value?.firstOrNull()
    fun headers(name: String): List<String> = headers.entries.filter { it.key.equals(name, true) }.flatMap { it.value }
    fun text(): String = body.toString(Charsets.UTF_8)
}
sealed class TransportException(message: String, cause: Throwable? = null) : IOException(message, cause) {
    class Timeout(cause: Throwable) : TransportException("HTTP request timed out", cause)
    class BodyTooLarge(val limit: Int) : TransportException("HTTP response exceeds $limit bytes")
    class Connection(cause: Throwable) : TransportException("HTTP connection failed", cause)
}
interface BoundHttpTransport { suspend fun execute(network: Network?, request: HttpRequest): HttpResponse }
class UrlConnectionTransport(private val maxBodyBytes: Int = 512 * 1024) : BoundHttpTransport {
    override suspend fun execute(network: Network?, request: HttpRequest): HttpResponse = withContext(Dispatchers.IO) {
        val url = URL(request.url)
        val connection = ((network?.openConnection(url) ?: url.openConnection()) as HttpURLConnection)
        try {
            connection.instanceFollowRedirects = false
            connection.requestMethod = request.method
            connection.connectTimeout = request.connectTimeoutMs
            connection.readTimeout = request.readTimeoutMs
            request.headers.forEach(connection::setRequestProperty)
            val payload = request.form?.entries?.joinToString("&") {
                "${URLEncoder.encode(it.key, "UTF-8")}=${URLEncoder.encode(it.value, "UTF-8")}"
            }?.toByteArray() ?: request.body
            if (payload != null) {
                connection.doOutput = true
                if (request.form != null) connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
                connection.outputStream.use { it.write(payload) }
            }
            val status = connection.responseCode
            val stream = if (status >= 400) connection.errorStream else connection.inputStream
            val output = java.io.ByteArrayOutputStream()
            stream?.use { input ->
                val buffer = ByteArray(8192)
                while (true) {
                    val count = input.read(buffer); if (count < 0) break
                    if (output.size() + count > maxBodyBytes) throw TransportException.BodyTooLarge(maxBodyBytes)
                    output.write(buffer, 0, count)
                }
            }
            val headers = connection.headerFields.entries
                .filter { it.key != null }
                .associate { it.key!! to it.value.toList() }
            HttpResponse(status, headers, output.toByteArray())
        } catch (e: SocketTimeoutException) { throw TransportException.Timeout(e) }
        catch (e: TransportException) { throw e }
        catch (e: IOException) { throw TransportException.Connection(e) }
        finally { connection.disconnect() }
    }
}
