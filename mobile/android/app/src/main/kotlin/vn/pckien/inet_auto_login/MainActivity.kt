package vn.pckien.inet_auto_login

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import vn.pckien.inet_auto_login.bridge.AutoLoginBridge
import vn.pckien.inet_auto_login.bridge.StabilityBridge

class MainActivity : FlutterActivity() {
    private var bridge: AutoLoginBridge? = null
    private var stabilityBridge: StabilityBridge? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        bridge?.dispose()
        bridge = AutoLoginBridge(this).also {
            MethodChannel(flutterEngine.dartExecutor.binaryMessenger, AutoLoginBridge.METHOD_CHANNEL).setMethodCallHandler(it)
            EventChannel(flutterEngine.dartExecutor.binaryMessenger, AutoLoginBridge.EVENT_CHANNEL).setStreamHandler(it)
        }
        stabilityBridge?.dispose()
        stabilityBridge = StabilityBridge(this).also {
            MethodChannel(flutterEngine.dartExecutor.binaryMessenger, StabilityBridge.METHOD_CHANNEL).setMethodCallHandler(it)
            EventChannel(flutterEngine.dartExecutor.binaryMessenger, StabilityBridge.EVENT_CHANNEL).setStreamHandler(it)
        }
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        bridge?.dispose(); bridge = null
        stabilityBridge?.dispose(); stabilityBridge = null
        super.cleanUpFlutterEngine(flutterEngine)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        if (bridge?.onRequestPermissionsResult(requestCode) == true) return
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
    }
}
