package vn.pckien.inet_auto_login.auth

import org.junit.Assert.*
import org.junit.Test

class ParserAndChapTest {
    @Test fun octalGoldenVectors() {
        assertArrayEquals(byteArrayOf(1, 65, 66, 67, -1), OctalParser.decode("\\001ABC\\377"))
        assertArrayEquals(byteArrayOf(92, 'x'.code.toByte()), OctalParser.decode("\\x"))
        assertArrayEquals(byteArrayOf(), OctalParser.decode("\\"))
        assertArrayEquals(byteArrayOf(-128), OctalParser.decode("\\200"))
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsOutOfRangeOctal() { OctalParser.decode("\\777") }
    @Test fun parsesFieldsRegardlessOfAttributeOrder() {
        val html = javaClass.getResource("/fixtures/mikrotik_login.html")!!.readText()
        val p = PortalPageParser.parse(html)
        assertEquals("SERIAL-TEST", p.serial)
        assertEquals("02:00:00:00:00:00", p.clientMac)
        assertArrayEquals(byteArrayOf(1), p.chapIdBytes)
        assertArrayEquals(byteArrayOf(-128, 65, 66, 67, -1), p.chapChallengeBytes)
    }
    @Test(expected = PortalParseException::class) fun missingFieldIsTyped() { PortalPageParser.parse("<html/>") }
    @Test fun chapMatchesKnownMd5Golden() {
        assertEquals("5f4dcc3b5aa765d61d8327deb882cf99", ChapCalculator.calculate(byteArrayOf(), "password", byteArrayOf()))
        assertEquals(32, ChapCalculator.calculate(byteArrayOf(1), "päss", byteArrayOf(-128, 2)).length)
    }
}
