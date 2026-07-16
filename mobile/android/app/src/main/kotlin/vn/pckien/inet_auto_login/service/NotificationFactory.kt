package vn.pckien.inet_auto_login.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import vn.pckien.inet_auto_login.MainActivity
import vn.pckien.inet_auto_login.R
import vn.pckien.inet_auto_login.model.DaemonSnapshot
import vn.pckien.inet_auto_login.model.DaemonState
import vn.pckien.inet_auto_login.receiver.NotificationActionReceiver

class NotificationFactory(private val context: Context) {
    companion object { const val CHANNEL_ID = "inet_auto_login"; const val NOTIFICATION_ID = 4107 }
    init {
        if (Build.VERSION.SDK_INT >= 26) context.getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL_ID, context.getString(R.string.notification_channel_name), NotificationManager.IMPORTANCE_LOW).apply {
                description = context.getString(R.string.notification_channel_description); setShowBadge(false)
            })
    }
    fun create(snapshot: DaemonSnapshot): Notification {
        val immutable = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        fun action(action: String, code: Int) = PendingIntent.getBroadcast(context, code,
            Intent(context, NotificationActionReceiver::class.java).setAction(action), immutable)
        val content = PendingIntent.getActivity(context, 1, Intent(context, MainActivity::class.java), immutable)
        return Notification.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher).setContentTitle("INET Auto Login")
            .setContentText(text(snapshot)).setContentIntent(content).setOngoing(true).setOnlyAlertOnce(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .addAction(Notification.Action.Builder(null, "Thử lại", action(ServiceController.ACTION_RETRY, 2)).build())
            .addAction(Notification.Action.Builder(null, "Tắt", action(ServiceController.ACTION_STOP, 3)).build())
            .build()
    }
    internal fun text(s: DaemonSnapshot): String = when (s.state) {
        DaemonState.ONLINE -> "Đã đăng nhập INET"
        DaemonState.WAITING_WIFI -> "Đang chờ INET - Free WiFi"
        DaemonState.BACKOFF -> s.retryAt?.let { "Thử lại sau ${((it - System.currentTimeMillis()).coerceAtLeast(0) + 999) / 1000} giây" } ?: "Đang chờ thử lại"
        DaemonState.CHECKING -> "Đang kiểm tra kết nối"
        DaemonState.AUTHENTICATING_CACHE, DaemonState.AUTHENTICATING_CLOUD -> "Đang đăng nhập INET"
        DaemonState.ERROR -> "Lỗi dịch vụ INET"
        else -> "Dịch vụ tự động đăng nhập đang chạy"
    }
}