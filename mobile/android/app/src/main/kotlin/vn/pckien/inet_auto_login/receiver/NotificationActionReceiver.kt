package vn.pckien.inet_auto_login.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import vn.pckien.inet_auto_login.service.ServiceController

class NotificationActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) = when (intent.action) {
        ServiceController.ACTION_STOP -> ServiceController.stop(context)
        ServiceController.ACTION_RETRY -> ServiceController.retry(context)
        else -> Unit
    }
}