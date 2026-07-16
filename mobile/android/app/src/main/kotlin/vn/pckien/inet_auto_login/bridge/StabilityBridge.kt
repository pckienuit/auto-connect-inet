package vn.pckien.inet_auto_login.bridge

import android.content.Context
import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import vn.pckien.inet_auto_login.stability.StabilityTestEngine

class StabilityBridge(context: Context) : MethodChannel.MethodCallHandler, EventChannel.StreamHandler {
    companion object {
        const val METHOD_CHANNEL = "vn.pckien.inet_auto_login/stability_control"
        const val EVENT_CHANNEL = "vn.pckien.inet_auto_login/stability"
    }

    private val engine = StabilityTestEngine(context)
    private val mainHandler = Handler(Looper.getMainLooper())
    @Volatile private var events: EventChannel.EventSink? = null

    init {
        engine.setSink { value -> mainHandler.post { events?.success(value) } }
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "startStabilityTest" -> {
                val duration = call.argument<Int>("durationSeconds") ?: StabilityTestEngine.DEFAULT_DURATION_SECONDS
                if (engine.start(duration)) result.success(null)
                else result.error("already_running", "Một bài kiểm tra đang chạy", null)
            }
            "stopStabilityTest" -> { engine.stop(); result.success(null) }
            else -> result.notImplemented()
        }
    }

    override fun onListen(arguments: Any?, sink: EventChannel.EventSink) { events = sink }
    override fun onCancel(arguments: Any?) { events = null }
    fun dispose() { events = null; engine.dispose() }
}
