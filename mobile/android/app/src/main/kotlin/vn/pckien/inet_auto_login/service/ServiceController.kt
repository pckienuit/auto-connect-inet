package vn.pckien.inet_auto_login.service

import android.content.Context
import android.content.Intent
import android.os.Build
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import vn.pckien.inet_auto_login.model.DaemonSnapshot
import vn.pckien.inet_auto_login.model.DaemonState

object ServiceController {
    const val ACTION_START = "vn.pckien.inet_auto_login.action.START"
    const val ACTION_STOP = "vn.pckien.inet_auto_login.action.STOP"
    const val ACTION_RETRY = "vn.pckien.inet_auto_login.action.RETRY"
    private const val PREFS = "daemon_control"
    private const val ENABLED = "enabled"
    private const val BOOT_ERROR = "boot_error"
    private val state = MutableStateFlow(DaemonSnapshot())
    val snapshots: StateFlow<DaemonSnapshot> = state

    fun isEnabled(context: Context): Boolean = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(ENABLED, false)
    fun setEnabled(context: Context, value: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(ENABLED, value).apply()
    }
    fun publish(snapshot: DaemonSnapshot) { state.value = snapshot }
    fun snapshot(context: Context): DaemonSnapshot = state.value.let {
        if (it.state == DaemonState.DISABLED && isEnabled(context)) it.copy(serviceEnabled = true, state = DaemonState.STARTING, stateMessage = "Service is starting") else it
    }
    fun start(context: Context) {
        setEnabled(context, true)
        val intent = Intent(context, InetAutoLoginService::class.java).setAction(ACTION_START)
        try {
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent) else context.startService(intent)
        } catch (e: RuntimeException) {
            setEnabled(context, false)
            throw e
        }
    }
    fun stop(context: Context) {
        setEnabled(context, false)
        context.stopService(Intent(context, InetAutoLoginService::class.java))
        publish(DaemonSnapshot())
    }
    fun retry(context: Context) {
        if (!isEnabled(context)) return
        val intent = Intent(context, InetAutoLoginService::class.java).setAction(ACTION_RETRY)
        if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent) else context.startService(intent)
    }
    fun recordBootError(context: Context, message: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(BOOT_ERROR, message.take(300)).apply()
    }
    fun consumeBootError(context: Context): String? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return prefs.getString(BOOT_ERROR, null)?.also { prefs.edit().remove(BOOT_ERROR).apply() }
    }
}