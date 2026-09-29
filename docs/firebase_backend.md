# Firebase in the backend

The single decision everything else in B9 follows from:

> **FastAPI + PostgreSQL is the source of truth. Firebase is a transport and a
> credential.**

Firebase carries identity, realtime delivery, blobs and push. It does not decide
who may do what. That stays in Postgres, because authorisation here is not "is
this person a member of this thread" - it is "does an order in a writable state,
for a service the catalogue says supports chat, with an expert who is not
suspended, inside a grace period, entitle this person to speak right now". None
of that is visible to a security rule without mirroring the entire marketplace
into Firestore, and a mirror that can drift is a permission bug waiting to
happen.

## What runs where

| Concern | Firebase | Postgres |
|---|---|---|
| Sign-in credential | Firebase Auth issues the ID token | `users.firebase_uid` maps it to an account |
| Message storage | Firestore, canonical | membership, audit metadata, counters |
| Presence and typing | RTDB, ephemeral | the membership the rules consult |
| Attachment bytes | Storage | the attachment row, status and verified type |
| Push delivery | FCM | the device table and the outbox |
| **Every authorisation decision** | – | **here** |

Business tables reference the local `users.id`. No foreign key anywhere points
at a Firebase uid, so a rotated project, a lost project or a migration away from
Firebase orphans nothing.

## Degraded, never broken

A missing service account is a supported configuration. The process boots,
`/health` and `/ready` stay green, and astrology, horary, divination, the
marketplace and Astro AI all work normally. Only the Firebase-backed endpoints
answer:

```json
{"error": {"code": "firebase_not_configured", "message": "..."}}
```

with `503`. `GET /api/v1/auth/capabilities` says so up front, so a client knows
whether to initialise Firebase at all rather than discovering it from a failed
request:

```json
{
  "auth_mode": "hybrid",
  "accepts_local_jwt": true,
  "accepts_firebase_token": true,
  "firebase_configured": false,
  "firebase_project_id": null
}
```

`firebase_project_id` is public configuration a client needs to initialise. No
key of any kind is ever returned.

`log_startup_diagnostic()` says at boot which of the two states the process is
in, and names the missing variables when it is the second. It is a local check:
a boot that calls a third party is a boot that fails when the third party is
having a bad morning, after the load balancer has already been told the process
is up.

## SDK surface

`firebase-admin==7.6.0`, verified against the current documentation rather than
recalled. Two things worth writing down because guessing them would have been
wrong:

* `send_multicast()` and `send_all()` were **removed in 7.x**. The replacements
  are `send_each()` and `send_each_for_multicast()`, which report per-token
  outcomes - which is what token retirement needs anyway.
* `firebase-admin` pins `httpx[http2]==0.28.1`. That is already this project's
  version, so nothing was forced to move.

The SDK is synchronous. Every call is wrapped in `asyncio.to_thread`, so a slow
Firestore write occupies a thread rather than blocking the event loop.

## The provider seam

Five protocols in `app/services/firebase/provider.py`: identity, chat, presence,
storage, push. Two implementations behind each - the real SDK, and an in-memory
double.

The doubles exist so the suite needs no service account. A test that requires
real credentials is a test that does not run in CI, on a new laptop, or for a
contributor - and a phase whose security properties are only checked by hand is
a phase whose security properties are not checked. They can be told to misbehave
on purpose: expire a token, revoke it, disable an account, fail a push
transiently, report a token dead, return a bucket object that is not what the
client promised.

`FIREBASE_PROVIDER=fake` is refused in production by `assert_production_ready`.

## Configuration

`.env.example` carries placeholders only. A service-account JSON never enters
the repository; it arrives as `FIREBASE_CREDENTIALS_JSON` from the deployment's
secret store, or as a file `FIREBASE_CREDENTIALS_PATH` points at. The emulator
hosts exist for local development and are empty by default.

## Deployment: presence visibility backfill

**Run once after deploying the presence contract fix** (the reader-keyed
`presenceVisibility/{targetUid}/{readerUid}/{conversationId}` layout and the
matching `database.rules.json`). Conversations provisioned before it carry no
grant the new rule can see, so their partners' presence listeners are denied
until this runs:

```
python -m scripts.rebuild_presence_visibility --dry-run   # counts only
python -m scripts.rebuild_presence_visibility             # add missing grants
```

Order: deploy the backend, deploy the RTDB rules, run the command. It is
idempotent - a second run writes nothing - and safe to repeat.

* Which conversations are granted is the B9 chat policy
  (`grants_presence` in `app/services/chat/policy.py`) - the same rule normal
  provisioning uses, so the two cannot disagree. Closed, suspended, unpaid and
  failed threads get nothing; read-only threads keep presence (current product
  policy, see [presence.md](presence.md#who-is-granted)).
* By default it **only adds**. `--prune-stale` removes grants of conversations
  Postgres knows and says grant nothing; `--prune-legacy` removes the old
  `{targetUid}/{conversationId}/{readerUid}` nodes. Grants naming a
  conversation Postgres does not know are counted and never removed.
* Output is counts only (no uid, email, name or conversation id). Exit `2`
  with `firebase_not_configured` when credentials or `FIREBASE_DATABASE_URL`
  are missing, or when `FIREBASE_PROVIDER=fake`. Boot behaviour is unchanged.
* It reads the whole `presenceVisibility` tree once; fine for a one-off pass.
  A conversation closed while the command runs can be re-granted by it; a
  later `--prune-stale` run removes that.

## Call pushes

FCM still carries every ordinary notification. Call lifecycle events use it
differently: **data-only, HIGH priority, short TTL** on Android (no
`notification` block; the app's receiver presents and dismisses the ringing
UI), and only background updates or plain alerts for an iPhone's FCM token -
iOS rings through APNs PushKit VoIP, which is not Firebase at all. See
[mobile_call_delivery.md](mobile_call_delivery.md).

## What is not here

Voice and video media. Those are LiveKit (B10) - see
[call_architecture.md](call_architecture.md). B10 only added three events to
the push vocabulary. `expert_conversations.call_session_id` stays unwritten:
`call_sessions.conversation_id` is the source of truth, because one
conversation can see several calls.

## Related

* [firebase_auth.md](firebase_auth.md) - identity mapping and account linking
* [chat_architecture.md](chat_architecture.md) - conversations and messages
* [presence.md](presence.md) - RTDB presence and typing
* [media_attachments.md](media_attachments.md) - Storage uploads
* [push_notifications.md](push_notifications.md) - the outbox and FCM
