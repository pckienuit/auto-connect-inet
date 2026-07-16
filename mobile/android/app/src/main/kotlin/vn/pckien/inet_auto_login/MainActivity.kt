package vn.pckien.inet_auto_login

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import vn.pckien.inet_auto_login.bridge.AutoLoginBridge

class MainActivity : FlutterActivity() {
    private var bridge: AutoLoginBridge? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        bridge?.dispose()
        bridge = AutoLoginBridge(this).also {
            MethodChannel(flutterEngine.dartExecutor.binaryMessenger, AutoLoginBridge.METHOD_CHANNEL).setMethodCallHandler(it)
            EventChannel(flutterEngine.dartExecutor.binaryMessenger, AutoLoginBridge.EVENT_CHANNEL).setStreamHandler(it)
        }
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        bridge?.dispose(); bridge = null
        super.cleanUpFlutterEngine(flutterEngine)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        if (bridge?.onRequestPermissionsResult(requestCode) == true) return
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
    }
}
