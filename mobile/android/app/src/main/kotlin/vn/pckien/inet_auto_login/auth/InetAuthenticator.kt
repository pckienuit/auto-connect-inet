package vn.pckien.inet_auto_login.auth

import android.net.Network
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeout
import vn.pckien.inet_auto_login.network.NetworkContext
import vn.pckien.inet_auto_login.storage.CredentialStore

enum class AuthOutcome { ONLINE, FAILED, STALE_NETWORK }
enum class AuthPhase { STATUS, PORTAL, CACHE, CLOUD, VERIFY }
data class AuthResult(val outcome: AuthOutcome, val phase: AuthPhase, val recoverable: Boolean, val message: String)
fun interface AuthenticationAttempt { suspend fun authenticate(context: NetworkContext): AuthResult }
fun interface CloudNetworkProvider { fun validatedNetwork(): Network? }

class InetAuthenticator(
    private val gateway: GatewayAccess,
    private val awing: AwingAccess,
    private val store: CredentialStore,
    private val cloudNetwork: CloudNetworkProvider,
    private val generationIsCurrent: (Long) -> Boolean,
    private val verifyDelayMs: Long = 1_000,
    private val timeoutMs: Long = 15_000,
) : AuthenticationAttempt {
    override suspend fun authenticate(context: NetworkContext): AuthResult = try {
        withTimeout(timeoutMs) { authenticateWithinTimeout(context) }
    } catch (_: kotlinx.coroutines.TimeoutCancellationException) {
        AuthResult(AuthOutcome.FAILED, AuthPhase.STATUS, true, "Authentication timed out")
    } catch (e: Exception) {
        AuthResult(AuthOutcome.FAILED, AuthPhase.CLOUD, true, e.message ?: "Authentication failed")
    }
    private suspend fun authenticateWithinTimeout(context: NetworkContext): AuthResult {
        fun stale() = !generationIsCurrent(context.generation)
        if (stale()) return AuthResult(AuthOutcome.STALE_NETWORK, AuthPhase.STATUS, true, "Network changed")
        when (gateway.checkStatus(context.network, context.gatewayIp)) {
            GatewayStatus.ONLINE -> return AuthResult(AuthOutcome.ONLINE, AuthPhase.STATUS, true, "Already online")
            GatewayStatus.UNREACHABLE -> return AuthResult(AuthOutcome.FAILED, AuthPhase.STATUS, true, "Gateway unreachable")
            else -> Unit
        }
        val portal = gateway.fetchLoginPage(context.network, context.gatewayIp)
        suspend fun login(username: String, password: String, phase: AuthPhase): AuthResult? {
            if (stale()) return AuthResult(AuthOutcome.STALE_NETWORK, phase, true, "Network changed")
            gateway.login(context.network, context.gatewayIp, username, ChapCalculator.calculate(portal.chapIdBytes, password, portal.chapChallengeBytes))
            delay(verifyDelayMs)
            if (stale()) return AuthResult(AuthOutcome.STALE_NETWORK, phase, true, "Network changed")
            return if (gateway.checkStatus(context.network, context.gatewayIp) == GatewayStatus.ONLINE)
                AuthResult(AuthOutcome.ONLINE, phase, true, "Authenticated") else null
        }
        store.load()?.let { login(it.username, it.password, AuthPhase.CACHE)?.let { result -> return result } }
        val credential = awing.fetch(cloudNetwork.validatedNetwork() ?: context.network, portal)
        val result = login(credential.username, credential.password, AuthPhase.CLOUD)
            ?: return AuthResult(AuthOutcome.FAILED, AuthPhase.VERIFY, true, "Gateway did not verify login")
        if (result.outcome == AuthOutcome.ONLINE) store.save(credential)
        return result
    }
}
