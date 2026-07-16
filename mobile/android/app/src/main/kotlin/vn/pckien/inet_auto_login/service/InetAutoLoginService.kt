package vn.pckien.inet_auto_login.service

import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.IBinder
import android.os.PowerManager
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.collectLatest
import vn.pckien.inet_auto_login.auth.*
import vn.pckien.inet_auto_login.logging.RotatingLogger
import vn.pckien.inet_auto_login.model.DaemonSnapshot
import vn.pckien.inet_auto_login.network.AndroidNetworkRepository
import vn.pckien.inet_auto_login.network.UrlConnectionTransport
import vn.pckien.inet_auto_login.storage.AndroidCredentialStore

class InetAutoLoginService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private lateinit var engine: AutoLoginEngine
    private lateinit var notifications: NotificationFactory
    private lateinit var logger: RotatingLogger
    private var initialized = false

    override fun onCreate() {
        super.onCreate()
        notifications = NotificationFactory(this)
        logger = RotatingLogger(filesDir.resolve("logs"))
        // Android requires promotion before network/keystore initialization can block.
        startForeground(NotificationFactory.NOTIFICATION_ID, notifications.create(DaemonSnapshot(serviceEnabled = true)))
        initializeEngine()
    }

    private fun initializeEngine() {
        val repository = AndroidNetworkRepository(applicationContext)
        val connectivity = getSystemService(ConnectivityManager::class.java)
        val transport = UrlConnectionTransport()
        val baseAuthenticator = InetAuthenticator(
            GatewayClient(transport), AwingClient(transport), AndroidCredentialStore(applicationContext),
            CloudNetworkProvider {
                connectivity.activeNetwork?.takeIf { network ->
                    connectivity.getNetworkCapabilities(network)
                        ?.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) == true
                }
            },
            generationIsCurrent = { repository.current()?.generation == it },
        )
        val power = getSystemService(PowerManager::class.java)
        val wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "$packageName:authentication").apply { setReferenceCounted(false) }
        val guarded = AuthenticationAttempt { context ->
            wakeLock.acquire(20_000)
            try { baseAuthenticator.authenticate(context) } finally { if (wakeLock.isHeld) wakeLock.release() }
        }
        engine = AutoLoginEngine(repository, guarded, log = { logger.log("info", it) })
        initialized = true
        scope.launch {
            engine.snapshot.collectLatest { snapshot ->
                ServiceController.publish(snapshot)
                logger.log("info", "State=${snapshot.state.name} failures=${snapshot.failureCount}")
                delay(750) // coalesce rapid state transitions
                getSystemService(NotificationManager::class.java).notify(NotificationFactory.NOTIFICATION_ID, notifications.create(snapshot))
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ServiceController.ACTION_STOP -> shutdown()
            ServiceController.ACTION_RETRY -> if (initialized && ServiceController.isEnabled(this)) engine.retryNow()
            else -> if (ServiceController.isEnabled(this)) engine.start() else shutdown()
        }
        return START_STICKY
    }

    private fun shutdown() {
        if (initialized) engine.stop()
        ServiceController.publish(DaemonSnapshot())
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }
    override fun onDestroy() {
        if (initialized) engine.stop()
        scope.cancel()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
    override fun onBind(intent: Intent?): IBinder? = null
}