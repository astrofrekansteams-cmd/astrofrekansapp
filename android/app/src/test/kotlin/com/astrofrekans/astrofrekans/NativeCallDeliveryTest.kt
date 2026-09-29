package com.astrofrekans.astrofrekans

import org.junit.Assert.*
import org.junit.Test

class NativeCallDeliveryTest {
    private val id = "11111111-1111-4111-8111-111111111111"

    @Test fun parsesDataOnlyCallEvents() {
        for (name in listOf("incoming_call", "call_answered", "call_cancelled", "call_missed")) {
            val parsed = NativeCallEvent.parse(mapOf(
                "event" to name, "call_id" to id, "call_type" to "audio",
                "event_version" to "100", "expires_at" to "9999999999"
            ))
            assertEquals(name, parsed?.event)
            assertEquals(id, parsed?.callId)
        }
        assertNull(NativeCallEvent.parse(mapOf(
            "event" to "incoming_call", "call_id" to id, "call_type" to "audio",
            "event_version" to "100"
        )))
    }

    @Test fun duplicateAndOlderVersionsNeverReplaceTheHighest() {
        assertFalse(NativeCallDelivery.shouldProcessVersion(100, 100))
        assertFalse(NativeCallDelivery.shouldProcessVersion(100, 99))
        assertTrue(NativeCallDelivery.shouldProcessVersion(100, 101))
    }

    @Test fun expiryAndNotificationIdentityAreDeterministic() {
        assertTrue(NativeCallDelivery.isExpired(100, 100))
        assertFalse(NativeCallDelivery.isExpired(101, 100))
        assertEquals(NativeCallDelivery.stableNotificationId(id),
            NativeCallDelivery.stableNotificationId(id))
    }

    @Test fun deniedFullScreenFallsBackToHeadsUpOnAndroid14() {
        assertTrue(NativeCallDelivery.useFullScreen(33, false))
        assertTrue(NativeCallDelivery.useFullScreen(34, true))
        assertFalse(NativeCallDelivery.useFullScreen(34, false))
    }
}
