package com.astrofrekans.astrofrekans

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.drawable.Icon
import android.os.Build
import java.util.UUID

/** Data-only call events are presentation hints, never authorization. */
internal data class NativeCallEvent(
    val event: String,
    val callId: String,
    val callType: String,
    val version: Long,
    val expiresAt: Long?
) {
    companion object {
        fun parse(data: Map<String, String>): NativeCallEvent? {
            val event = data["event"] ?: return null
            if (event !in setOf("incoming_call", "call_answered", "call_cancelled", "call_missed")) return null
            val id = data["call_id"] ?: return null
            try {
                if (!UUID.fromString(id).toString().equals(id, ignoreCase = true)) return null
            } catch (_: IllegalArgumentException) { return null }
            val type = data["call_type"] ?: return null
            if (type != "audio" && type != "video") return null
            val version = data["event_version"]?.toLongOrNull() ?: return null
            if (version <= 0) return null
            val expiry = data["expires_at"]?.toLongOrNull()
            if (event == "incoming_call" && expiry == null) return null
            return NativeCallEvent(event, id.lowercase(), type, version, expiry)
        }
    }
}

internal object NativeCallDelivery {
    private const val channelId = "astrofrekans_calls"
    private const val stateName = "astrofrekans_call_delivery"
    private const val actionName = "astrofrekans_call_actions"

    private fun state(context: Context) = context.getSharedPreferences(stateName, Context.MODE_PRIVATE)
    private fun actions(context: Context) = context.getSharedPreferences(actionName, Context.MODE_PRIVATE)
    private fun manager(context: Context) =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    fun stableNotificationId(callId: String): Int = callId.hashCode()
    fun shouldProcessVersion(stored: Long, incoming: Long): Boolean = incoming > stored
    fun isExpired(expiry: Long, nowSeconds: Long): Boolean = expiry <= nowSeconds
    fun useFullScreen(sdk: Int, allowed: Boolean): Boolean = sdk < 34 || allowed
    fun highestVersion(context: Context, callId: String): Long =
        state(context).getLong("v:$callId", 0L)
    fun expiresAt(context: Context, callId: String): Long =
        state(context).getLong("e:$callId", 0L)

    @Synchronized
    fun process(context: Context, event: NativeCallEvent): Boolean {
        if (!shouldProcessVersion(highestVersion(context, event.callId), event.version)) return false
        // commit(): process death immediately after onMessageReceived must not
        // let an older retry resurrect a call.
        state(context).edit()
            .putLong("v:${event.callId}", event.version)
            .putLong("e:${event.callId}", event.expiresAt ?: 0L)
            .commit()
        if (event.event == "incoming_call") {
            val expiry = event.expiresAt ?: return false
            if (isExpired(expiry, System.currentTimeMillis() / 1000)) {
                dismiss(context, event.callId)
                return false
            }
            return show(context, event.callId, expiry)
        }
        dismiss(context, event.callId)
        return true
    }

    fun show(context: Context, callId: String, expiresAt: Long): Boolean {
        val notificationManager = manager(context)
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED) return false
        if (!notificationManager.areNotificationsEnabled()) return false
        if (Build.VERSION.SDK_INT >= 26) {
            notificationManager.createNotificationChannel(
                NotificationChannel(channelId, "Gelen görüşmeler", NotificationManager.IMPORTANCE_HIGH)
                    .apply { description = "Astrofrekans canlı görüşme davetleri" }
            )
            if (notificationManager.getNotificationChannel(channelId)?.importance ==
                NotificationManager.IMPORTANCE_NONE) return false
        }
        val nonce = UUID.randomUUID().toString()
        actions(context).edit().putString(callId, nonce).commit()
        val open = actionIntent(context, callId, "open", nonce, 0)
        val answer = actionIntent(context, callId, "answer", nonce, 0x11)
        val decline = actionIntent(context, callId, "decline", nonce, 0x22)
        val builder = if (Build.VERSION.SDK_INT >= 26)
            Notification.Builder(context, channelId) else Notification.Builder(context)
        builder.setSmallIcon(context.applicationInfo.icon)
            .setContentTitle("Astrofrekans")
            .setContentText("Gelen görüşme")
            .setCategory(Notification.CATEGORY_CALL)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .setPriority(Notification.PRIORITY_HIGH)
            .setContentIntent(open)
            .setAutoCancel(true)
            .addAction(Notification.Action.Builder(
                Icon.createWithResource(context, android.R.drawable.ic_menu_close_clear_cancel),
                "Reddet", decline
            ).build())
            .addAction(Notification.Action.Builder(
                Icon.createWithResource(context, android.R.drawable.ic_menu_call),
                "Kabul et", answer
            ).build())
        if (Build.VERSION.SDK_INT >= 26) {
            builder.setTimeoutAfter(((expiresAt - System.currentTimeMillis() / 1000) * 1000).coerceAtLeast(1))
        }
        if (useFullScreen(Build.VERSION.SDK_INT,
                Build.VERSION.SDK_INT < 34 || notificationManager.canUseFullScreenIntent())) {
            builder.setFullScreenIntent(fullScreenIntent(context, callId, nonce), true)
        }
        notificationManager.notify(stableNotificationId(callId), builder.build())
        return true
    }

    fun dismiss(context: Context, callId: String) {
        manager(context).cancel(stableNotificationId(callId))
        actions(context).edit().remove(callId).commit()
        IncomingCallActivity.dismiss(callId)
    }

    fun validNonce(context: Context, callId: String, nonce: String?): Boolean =
        nonce != null && nonce == actions(context).getString(callId, null)

    fun actionTaken(context: Context, callId: String) {
        actions(context).edit().remove(callId).commit()
        manager(context).cancel(stableNotificationId(callId))
        IncomingCallActivity.dismiss(callId)
    }

    private fun actionIntent(
        context: Context, callId: String, action: String, nonce: String, suffix: Int
    ): PendingIntent {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("callId", callId)
            putExtra("action", action)
            putExtra("nonce", nonce)
        }
        return PendingIntent.getActivity(
            context, stableNotificationId(callId) xor suffix, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun fullScreenIntent(context: Context, callId: String, nonce: String): PendingIntent {
        val intent = Intent(context, IncomingCallActivity::class.java).apply {
            putExtra("callId", callId)
            putExtra("nonce", nonce)
        }
        return PendingIntent.getActivity(
            context, stableNotificationId(callId) xor 0x33, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    fun savePending(context: Context, callId: String, action: String) {
        state(context).edit()
            .putString("pending_id", callId)
            .putString("pending_action", action)
            .putLong("pending_version", highestVersion(context, callId))
            .putLong("pending_expiry", expiresAt(context, callId))
            .commit()
    }

    @Synchronized
    fun consumePending(context: Context): Map<String, Any>? {
        val prefs = state(context)
        val id = prefs.getString("pending_id", null)
        val action = prefs.getString("pending_action", null)
        val version = prefs.getLong("pending_version", 0L)
        val expiry = prefs.getLong("pending_expiry", 0L)
        clearPending(context)
        if (id == null || action == null || version <= 0L ||
            version != highestVersion(context, id) ||
            expiry <= System.currentTimeMillis() / 1000) return null
        return mapOf("callId" to id, "action" to action,
            "eventVersion" to version, "expiresAt" to expiry)
    }

    fun clearPending(context: Context) {
        state(context).edit().remove("pending_id").remove("pending_action")
            .remove("pending_version").remove("pending_expiry").commit()
    }
}
