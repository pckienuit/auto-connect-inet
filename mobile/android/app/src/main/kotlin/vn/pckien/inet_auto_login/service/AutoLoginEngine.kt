package vn.pckien.inet_auto_login.service

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import vn.pckien.inet_auto_login.auth.*
import vn.pckien.inet_auto_login.model.*
import vn.pckien.inet_auto_login.network.*

fun interface EpochClock { fun now(): Long }
class BackoffPolicy(private val delays: LongArray = longArrayOf(15_000, 30_000, 60_000, 120_000, 240_000, 300_000)) {
    init { require(delays.isNotEmpty()) }
    fun delayFor(failureCount: Int): Long = delays[(failureCount.coerceAtLeast(1) - 1).coerceAtMost(delays.lastIndex)]
}
class AutoLoginEngine(
    private val networks: NetworkRepository,
    private val authenticator: AuthenticationAttempt,
    dispatcher: CoroutineDispatcher = Dispatchers.IO,
    private val clock: EpochClock = EpochClock { System.currentTimeMillis() },
    private val onlineIntervalMs: Long = 10_000,
    private val backoffPolicy: BackoffPolicy = BackoffPolicy(),
) {
    private val scope = CoroutineScope(SupervisorJob() + dispatcher)
    private val mutex = Mutex()
    private var enabled = false
    private var scheduled: Job? = null
    private var attempt: Job? = null
    private val mutableSnapshot = MutableStateFlow(DaemonSnapshot())
    val snapshot: StateFlow<DaemonSnapshot> = mutableSnapshot

    fun start() {
        if (enabled) return
        enabled = true
        mutableSnapshot.value = DaemonSnapshot(serviceEnabled = true, state = DaemonState.STARTING)
        networks.start { context -> scope.launch { onNetwork(context) } }
        scope.launch { onNetwork(networks.current()) }
    }
    private suspend fun onNetwork(context: NetworkContext?) {
        mutex.withLock {
            if (!enabled) return
            scheduled?.cancel()
            scheduled = null
            if (context == null) {
                attempt?.cancel()
                attempt = null
                mutableSnapshot.value = mutableSnapshot.value.copy(state = DaemonState.WAITING_WIFI, stateMessage = "Waiting for target WiFi", ssid = null, gatewayIp = null, localIp = null, isWifiTarget = false, retryAt = null)
            } else {
                scheduleLocked(context, 0)
            }
        }
    }
    private fun scheduleLocked(context: NetworkContext, delayMs: Long) {
        scheduled?.cancel()
        scheduled = scope.launch { if (delayMs > 0) delay(delayMs); runAttempt(context) }
    }
    private suspend fun runAttempt(context: NetworkContext) {
        mutex.withLock {
            if (!enabled || attempt?.isActive == true || networks.current()?.generation != context.generation) return
            mutableSnapshot.value = mutableSnapshot.value.copy(state = DaemonState.CHECKING, stateMessage = "Checking gateway", ssid = context.ssid, gatewayIp = context.gatewayIp, localIp = context.localIp, isWifiTarget = true, lastCheckAt = clock.now(), retryAt = null)
            attempt = scope.launch {
                val result = try { authenticator.authenticate(context) } catch (e: CancellationException) { throw e } catch (e: Exception) {
                    AuthResult(AuthOutcome.FAILED, AuthPhase.STATUS, true, e.message ?: "Unexpected authentication error")
                }
                finish(context, result)
            }
        }
    }
    private suspend fun finish(context: NetworkContext, result: AuthResult) {
        mutex.withLock {
            attempt = null
            if (!enabled || networks.current()?.generation != context.generation || result.outcome == AuthOutcome.STALE_NETWORK) return
            if (result.outcome == AuthOutcome.ONLINE) {
                mutableSnapshot.value = mutableSnapshot.value.copy(state = DaemonState.ONLINE, stateMessage = result.message, failureCount = 0, lastAuthAt = if (result.phase == AuthPhase.STATUS) mutableSnapshot.value.lastAuthAt else clock.now(), retryAt = null, lastError = null)
                scheduleLocked(context, onlineIntervalMs)
            } else {
                val failures = mutableSnapshot.value.failureCount + 1
                val delayMs = backoffPolicy.delayFor(failures)
                mutableSnapshot.value = mutableSnapshot.value.copy(state = DaemonState.BACKOFF, stateMessage = result.message, failureCount = failures, retryAt = clock.now() + delayMs, lastError = result.message)
                scheduleLocked(context, delayMs)
            }
        }
    }
    fun retryNow() { scope.launch { mutex.withLock { networks.current()?.let { scheduleLocked(it, 0) } } } }
    fun stop() {
        enabled = false; networks.stop(); scheduled?.cancel(); attempt?.cancel(); scheduled = null; attempt = null
        mutableSnapshot.value = DaemonSnapshot(state = DaemonState.DISABLED)
    }
}
