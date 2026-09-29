# B12C.1 native incoming-call contract issues

Backend was read-only in this phase. These are delivery/capability gaps, not authorization failures and not requests to change `/calls/{id}/join` or `/end` semantics.

| Platform | Current B9 contract | Required before native background incoming can be claimed | Severity |
|---|---|---|---|
| iOS | FCM device token; normal APNs notification + `data.event=incoming_call`, `call_id`, `call_type` | Separate real APNs VoIP token registration/delivery, PushKit/CallKit capability and provisioning, prompt CallKit reporting, cancellation lifecycle, device verification. Do not convert an ordinary FCM token/push into a VoIP token/push. | Release blocker |
| Android | FCM `notification + data`, high priority, generic title/body | A call-specific background delivery design that reaches native call handling in locked/background/killed states, including cancellation/missed, expiration, dedupe and device testing. The current Flutter foreground listener cannot guarantee that for notification payloads. | Release blocker |

Client remains defensive: `call_id` is only a hint; authenticated `GET /calls/{id}` gates presentation/actions, and `/join` alone mints a LiveKit grant. The B10 `/end` contract explicitly cancels a non-active call, so no decline endpoint mismatch was found.

Sources: [Apple PushKit/CallKit](https://developer.apple.com/documentation/pushkit/responding-to-voip-notifications-from-pushkit), [Firebase Android receive behavior](https://firebase.google.com/docs/cloud-messaging/android/receive-messages), [Firebase Flutter background handler](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages).
