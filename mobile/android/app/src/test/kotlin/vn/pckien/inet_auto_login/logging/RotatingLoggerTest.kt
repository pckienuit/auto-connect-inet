package vn.pckien.inet_auto_login.logging

import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files

class RotatingLoggerTest {
    @Test fun redactsSecretsAndIdentifiers() {
        val input = "username=bob password: s3cret Cookie=abc chap-challenge=xyz mac=aa:bb:cc:dd:ee:ff ip=192.168.1.20"
        val output = LogRedactor.redact(input)
        listOf("bob", "s3cret", "abc", "xyz", "aa:bb:cc:dd:ee:ff", "192.168.1.20").forEach { assertFalse(output.contains(it)) }
    }

    @Test fun rotatesAndKeepsOnlyTwoFiles() {
        val dir = Files.createTempDirectory("inet-log").toFile()
        val logger = RotatingLogger(dir, maxBytes = 90) { 0 }
        repeat(20) { logger.log("info", "safe message number $it") }
        assertTrue(dir.resolve("daemon.log").isFile)
        assertTrue(dir.resolve("daemon.log.1").isFile)
        assertEquals(2, dir.listFiles()!!.size)
    }
}