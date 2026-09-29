package com.astrofrekans.astrofrekans

import com.google.firebase.messaging.RemoteMessage
import io.flutter.plugins.firebase.messaging.FlutterFirebaseMessagingService

/** Sole MESSAGING_EVENT service; the FlutterFire receiver still handles normal FCM. */
class AstroCallMessagingService : FlutterFirebaseMessagingService() {
    override fun onCreate() {
        super.onCreate()
        // A push can arrive before the app has ever been opened since install.
        NotificationChannels.ensureDefault(this)
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        val event = NativeCallEvent.parse(remoteMessage.data)
        if (event != null) {
            NativeCallDelivery.process(this, event)
        } else {
            super.onMessageReceived(remoteMessage)
        }
    }
}
