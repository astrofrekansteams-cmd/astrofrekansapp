package com.astrofrekans.astrofrekans

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

/**
 * The channel ordinary pushes land in ("Astrofrekans Bildirimleri"), instead
 * of FCM's unnamed "Miscellaneous" fallback. FCM uses it through the
 * `default_notification_channel_id` meta-data, so it must exist before the
 * first notification: created when the app opens and when a push arrives.
 *
 * Default importance: sound and a status-bar icon, no heads-up banner - these
 * are reports, reminders and receipts, not calls (calls have their own channel,
 * see NativeCallDelivery). Creating an existing channel only refreshes its
 * name and description; the importance and sound the person chose are kept.
 */
object NotificationChannels {
    fun ensureDefault(context: Context) {
        if (Build.VERSION.SDK_INT < 26) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        val channel = NotificationChannel(
            context.getString(R.string.default_notification_channel_id),
            context.getString(R.string.default_notification_channel_name),
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = context.getString(R.string.default_notification_channel_description)
            setShowBadge(true)
        }
        manager.createNotificationChannel(channel)
    }
}
