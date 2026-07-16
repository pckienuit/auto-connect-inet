package vn.pckien.inet_auto_login.auth

import java.security.MessageDigest

object OctalParser {
    fun decode(value: String): ByteArray {
        val out = ArrayList<Byte>()
        var i = 0
        while (i < value.length) {
            val c = value[i]
            if (c != '\\') {
                require(c.code <= 255) { "Non-Latin-1 character" }
                out += c.code.toByte(); i++; continue
            }
            i++
            if (i >= value.length) continue
            var end = i
            while (end < value.length && end - i < 3 && value[end] in '0'..'7') end++
            if (end == i) { out += '\\'.code.toByte(); continue }
            out += value.substring(i, end).toInt(8).also { require(it <= 255) }.toByte()
            i = end
        }
        return out.toByteArray()
    }
}

object ChapCalculator {
    fun calculate(chapId: ByteArray, password: String, challenge: ByteArray): String =
        MessageDigest.getInstance("MD5").digest(chapId + password.toByteArray(Charsets.UTF_8) + challenge)
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
}
