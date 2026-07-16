package vn.pckien.inet_auto_login.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import vn.pckien.inet_auto_login.logging.RotatingLogger
import vn.pckien.inet_auto_login.service.ServiceController

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED || !ServiceController.isEnabled(context)) return
        try { ServiceController.start(context) } catch (e: RuntimeException) {
            // A rejected best-effort boot start must not erase the user's preference.
            ServiceController.setEnabled(context, true)
            ServiceController.recordBootError(context, "Foreground service start was rejected after boot: ${e.javaClass.simpleName}")
            RotatingLogger(context.filesDir.resolve("logs")).log("warn", "Boot recovery rejected", e)
        }
    }
}