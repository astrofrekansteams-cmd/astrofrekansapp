package com.astrofrekans.astrofrekans

import android.content.Intent
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.UUID

class MainActivity : FlutterActivity() {
    private var channel: MethodChannel? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        NotificationChannels.ensureDefault(this)
        receiveAction(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        receiveAction(intent)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "astrofrekans/incoming_calls")
        channel?.setMethodCallHandler { call, result ->
            val id = (call.arguments as? Map<*, *>)?.get("callId") as? String
            when (call.method) {
                "consumeAction" -> result.success(NativeCallDelivery.consumePending(this))
                "clearPending" -> {
                    NativeCallDelivery.clearPending(this)
                    result.success(null)
                }
                "show" -> {
                    if (!validId(id)) {
                        result.error("invalid_call_id", "Invalid call ID", null)
                    } else {
                        val expiry = NativeCallDelivery.expiresAt(this, id!!)
                        if (expiry > System.currentTimeMillis() / 1000 &&
                            NativeCallDelivery.show(this, id, expiry)) result.success(null)
                        else result.error("call_not_presentable", "No valid incoming event", null)
                    }
                }
                "dismiss" -> {
                    if (!validId(id)) result.error("invalid_call_id", "Invalid call ID", null)
                    else {
                        NativeCallDelivery.dismiss(this, id!!)
                        result.success(null)
                    }
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun validId(id: String?): Boolean = try {
        id != null && UUID.fromString(id).toString().equals(id, ignoreCase = true)
    } catch (_: IllegalArgumentException) { false }

    private fun receiveAction(intent: Intent?) {
        val id = intent?.getStringExtra("callId")
        val action = intent?.getStringExtra("action")
        val nonce = intent?.getStringExtra("nonce")
        if (!validId(id) || action !in setOf("open", "answer", "decline") ||
            !NativeCallDelivery.validNonce(this, id!!, nonce)) return
        NativeCallDelivery.savePending(this, id, action!!)
        NativeCallDelivery.actionTaken(this, id)
        // The event is only a hint. Flutter consumes the persisted action once
        // after its auth session/router are ready; no backend call occurs here.
        channel?.invokeMethod("action", mapOf("callId" to id))
        intent.removeExtra("callId")
        intent.removeExtra("action")
        intent.removeExtra("nonce")
    }
}
