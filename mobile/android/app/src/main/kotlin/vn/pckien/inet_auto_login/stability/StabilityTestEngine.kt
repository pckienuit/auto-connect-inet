package vn.pckien.inet_auto_login.stability

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.os.SystemClock
import kotlinx.coroutines.*
import vn.pckien.inet_auto_login.network.AndroidNetworkRepository
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.atomic.AtomicReference

class StabilityTestEngine(context: Context) {
    companion object {
        const val DEFAULT_DURATION_SECONDS = 60
        const val INTERVAL_MS = 500L
        const val TIMEOUT_MS = 1_000
        private const val HOST = "1.1.1.1"
        private const val PORT = 53

        fun normalizeDurationSeconds(value: Int): Int = when {
            value == 0 -> 0
            value < 0 -> 1
            else -> value.coerceAtMost(600)
        }
    }

    private val appContext = context.applicationContext
    private val connectivity = appContext.getSystemService(ConnectivityManager::class.java)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val runningSocket = AtomicReference<Socket?>()
    private var job: Job? = null
    @Volatile private var sink: ((Map<String, Any?>) -> Unit)? = null

    @Synchronized
    fun setSink(value: ((Map<String, Any?>) -> Unit)?) { sink = value }

    @Synchronized
    fun start(durationSeconds: Int = DEFAULT_DURATION_SECONDS): Boolean {
        if (job?.isActive == true) return false
        val duration = normalizeDurationSeconds(durationSeconds)
        job = scope.launch { run(duration) }
        return true
    }

    @Synchronized
    fun stop() {
        job?.cancel()
        runningSocket.getAndSet(null)?.closeQuietly()
    }

    fun dispose() {
        stop()
        sink = null
        scope.cancel()
    }

    private suspend fun run(durationSeconds: Int) {
        val repository = AndroidNetworkRepository(appContext)
        try { repository.start { } } catch (_: SecurityException) { /* Active network remains a valid fallback. */ }
        delay(100) // Allow the callback to publish an already available target WiFi.
        val target = repository.current()
        val network: Network? = target?.network ?: connectivity.activeNetwork
        val label = if (target != null) "INET WiFi: ${target.ssid}" else when {
            network != null -> "Mạng đang hoạt động (dự phòng)"
            else -> "Không có mạng đang hoạt động"
        }
        val accumulator = StabilityAccumulator()
        val startedAt = SystemClock.elapsedRealtime()
        val durationMs = durationSeconds * 1_000L
        emit(true, 0, durationMs, accumulator, label, null)
        try {
            while (currentCoroutineContext().isActive && (durationMs == 0L || SystemClock.elapsedRealtime() - startedAt < durationMs)) {
                val iterationAt = SystemClock.elapsedRealtime()
                val latency = if (network == null) null else connect(network)
                accumulator.record(latency, SystemClock.elapsedRealtime())
                emit(true, SystemClock.elapsedRealtime() - startedAt, durationMs, accumulator, label, null)
                delay((INTERVAL_MS - (SystemClock.elapsedRealtime() - iterationAt)).coerceAtLeast(0))
            }
            emit(false, elapsedForEvent(startedAt, durationMs), durationMs, accumulator, label, null)
        } catch (_: CancellationException) {
            emit(false, elapsedForEvent(startedAt, durationMs), durationMs, accumulator, label, null)
        } catch (error: Exception) {
            emit(false, SystemClock.elapsedRealtime() - startedAt, durationMs, accumulator, label, error.message ?: error.javaClass.simpleName)
        } finally {
            runningSocket.getAndSet(null)?.closeQuietly()
            repository.stop()
        }
    }

    private fun elapsedForEvent(startedAt: Long, durationMs: Long): Long {
        val elapsed = SystemClock.elapsedRealtime() - startedAt
        return if (durationMs == 0L) elapsed else elapsed.coerceAtMost(durationMs)
    }

    private fun connect(network: Network): Double? {
        val socket = try { network.socketFactory.createSocket() } catch (_: Exception) { return null }
        runningSocket.set(socket)
        return try {
            val start = SystemClock.elapsedRealtimeNanos()
            socket.connect(InetSocketAddress(HOST, PORT), TIMEOUT_MS)
            (SystemClock.elapsedRealtimeNanos() - start) / 1_000_000.0
        } catch (_: Exception) {
            null
        } finally {
            runningSocket.compareAndSet(socket, null)
            socket.closeQuietly()
        }
    }

    private fun emit(running: Boolean, elapsedMs: Long, durationMs: Long, accumulator: StabilityAccumulator, networkLabel: String, error: String?) {
        val m = accumulator.snapshot(SystemClock.elapsedRealtime())
        sink?.invoke(mapOf(
            "running" to running, "elapsedMs" to elapsedMs, "durationMs" to durationMs,
            "sent" to m.sent, "received" to m.received, "lossPercent" to m.lossPercent,
            "latestLatencyMs" to m.latestLatencyMs, "minLatencyMs" to m.minLatencyMs,
            "averageLatencyMs" to m.averageLatencyMs, "maxLatencyMs" to m.maxLatencyMs,
            "jitterMs" to m.jitterMs, "outageCount" to m.outageCount,
            "currentOutageMs" to m.currentOutageMs, "maxOutageMs" to m.maxOutageMs,
            "rating" to m.rating.wireName, "error" to error, "networkLabel" to networkLabel,
        ))
    }

    private fun Socket.closeQuietly() { try { close() } catch (_: Exception) {} }
}
