package vn.pckien.inet_auto_login.logging

import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object LogRedactor {
    private const val MASK = "[REDACTED]"
    private val namedSecret = Regex("(?i)(username|password|cookie|set-cookie|chap-id|chap-challenge)(\\s*[=:]\\s*|%3[dD])([^\\s&,;]+)")
    private val querySecret = Regex("(?i)([?&](?:challenge|chap-id|chap-challenge|password|username)=)[^&#\\s]+")
    private val mac = Regex("(?i)\\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\\b")
    private val ipv4 = Regex("\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b")

    fun redact(message: String): String = message
        .replace(namedSecret) { "${it.groupValues[1]}${it.groupValues[2]}$MASK" }
        .replace(querySecret) { "${it.groupValues[1]}$MASK" }
        .replace(mac, MASK)
        .replace(ipv4, "[IP_REDACTED]")
        .replace(Regex("[\\r\\n]+"), " ")
}

class RotatingLogger(
    directory: File,
    private val maxBytes: Long = 512L * 1024,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    private val active = File(directory.apply { mkdirs() }, "daemon.log")
    private val previous = File(directory, "daemon.log.1")
    private val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US)

    @Synchronized fun log(level: String, message: String, error: Throwable? = null) {
        val safe = LogRedactor.redact(buildString {
            append(message)
            error?.let { append(" (").append(it.javaClass.simpleName).append(": ").append(it.message.orEmpty()).append(')') }
        })
        val prefix = "${format.format(Date(clock()))} ${level.uppercase(Locale.US)} "
        val maximumMessageBytes = (maxBytes - prefix.toByteArray().size - 1).coerceAtLeast(0).toInt()
        val bounded = safe.toByteArray().let { bytes ->
            if (bytes.size <= maximumMessageBytes) safe else bytes.copyOf(maximumMessageBytes).toString(Charsets.UTF_8)
        }
        val line = "$prefix$bounded\n"
        if (active.length() + line.toByteArray().size > maxBytes) rotate()
        active.appendText(line)
    }

    @Synchronized fun recentLines(limit: Int = 200, maxChars: Int = 64 * 1024): List<String> {
        val safeLimit = limit.coerceIn(1, 500)
        val lines = sequenceOf(previous, active).filter { it.isFile }.flatMap { it.readLines().asSequence() }.toList()
        var chars = 0
        val result = ArrayDeque<String>()
        for (line in lines.asReversed()) {
            if (result.size >= safeLimit || chars + line.length > maxChars) break
            result.addFirst(LogRedactor.redact(line)); chars += line.length
        }
        return result.toList()
    }

    private fun rotate() {
        if (previous.exists()) previous.delete()
        if (active.exists()) active.renameTo(previous)
    }
}