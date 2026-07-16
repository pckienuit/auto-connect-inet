package vn.pckien.inet_auto_login.bridge

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings

import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.collectLatest
import vn.pckien.inet_auto_login.logging.RotatingLogger
import vn.pckien.inet_auto_login.service.ServiceController

class AutoLoginBridge(private val activity: Activity) : MethodChannel.MethodCallHandler, EventChannel.StreamHandler {
    companion object {
        const val METHOD_CHANNEL = "vn.pckien.inet_auto_login/control"
        const val EVENT_CHANNEL = "vn.pckien.inet_auto_login/events"
    }
    private var eventJob: Job? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val logger by lazy { RotatingLogger(activity.filesDir.resolve("logs")) }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        try {
            when (call.method) {
                "start" -> {
                    val missing = missingPermissions()
                    if (missing.isNotEmpty()) result.error("PERMISSION_REQUIRED", "Required Android permissions have not been granted", mapOf("permissions" to missing))
                    else { ServiceController.start(activity); result.success(null) }
                }
                "stop" -> { ServiceController.stop(activity); result.success(null) }
                "retryNow" -> { ServiceController.retry(activity); result.success(null) }
                "getSnapshot" -> {
                    val snapshot = ServiceController.snapshot(activity)
                    val bootError = ServiceController.consumeBootError(activity)
                    result.success(if (bootError == null) snapshot.toMap() else snapshot.copy(lastError = bootError).toMap())
                }
                "getRecentLogs" -> {
                    val limit = (call.argument<Number>("limit")?.toInt() ?: 200).coerceIn(1, 500)
                    result.success(logger.recentLines(limit))
                }
                "openBatterySettings" -> {
                    activity.startActivity(
                        Intent(
                            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            Uri.parse("package:${activity.packageName}"),
                        ),
                    )
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        } catch (e: Exception) {
            logger.log("error", "Native bridge method ${call.method} failed", e)
            result.error(if (call.method == "start") "SERVICE_START_FAILED" else "INTERNAL_ERROR", e.message ?: "Native operation failed", null)
        }
    }

    override fun onListen(arguments: Any?, events: EventChannel.EventSink) {
        eventJob?.cancel()
        eventJob = scope.launch { ServiceController.snapshots.collectLatest { events.success(it.toMap()) } }
    }
    override fun onCancel(arguments: Any?) { eventJob?.cancel(); eventJob = null }
    fun dispose() { eventJob?.cancel(); scope.cancel() }

    private fun missingPermissions(): List<String> = buildList {
        if (Build.VERSION.SDK_INT >= 33) {
            if (!granted(Manifest.permission.NEARBY_WIFI_DEVICES)) add(Manifest.permission.NEARBY_WIFI_DEVICES)
            if (!granted(Manifest.permission.POST_NOTIFICATIONS)) add(Manifest.permission.POST_NOTIFICATIONS)
        } else if (!granted(Manifest.permission.ACCESS_FINE_LOCATION)) add(Manifest.permission.ACCESS_FINE_LOCATION)
    }
    private fun granted(permission: String) = activity.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED
}