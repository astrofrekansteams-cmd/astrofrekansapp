# Presence and typing

## Why Realtime Database and not Firestore

Presence needs `onDisconnect`, and only a connected client can arm it. The
backend cannot know that a phone went into a tunnel - no request arrives to tell
it, and a heartbeat that has to fail three times before it believes the user has
gone leaves somebody looking online for a minute after they left. The client's
own socket knows immediately.

So RTDB owns presence, and the backend never writes it. Which is also why
presence is the one thing in this phase a client writes directly.

## The layout

```
presence/{uid}
  state: "online" | "offline"
  lastChanged: <server timestamp>

typing/{conversationId}/{uid}
  typing: true | false
  updatedAt: <number>

conversationMembers/{conversationId}/{uid}: true        # backend-written
presenceVisibility/{targetUid}/{readerUid}/{conversationId}: true   # backend-written
```

Everything ephemeral. None of it reaches Postgres - "was this user online at
14:32" is not a fact the product needs, and storing it would be building a
movement log nobody asked for.

## The three rules

**A user writes only their own presence.** `auth.uid === $uid`. Otherwise anybody
could mark a stranger online, or mark them offline to make them look
unresponsive.

**Presence is readable only by a conversation partner.** A global presence list
would let any account watch when any other account is using the app. That is
surveillance, not a feature.

**Typing is scoped to a conversation and to one's own uid**, and only for a
member of it.

## Two projections, because they answer different questions

Both are written by the Admin SDK and are unwritable by any client - a client
that could add itself to `conversationMembers` would have granted itself access.

`conversationMembers/{conversationId}` answers "is this uid in this thread". That
is enough for typing, which is always read per-conversation.

`presenceVisibility/{uid}` answers "may this reader see this user". Presence is
read *per-user*: a client subscribes to `presence/{partnerUid}` and the path names
no conversation, so the rules have nothing to look a membership up by. Without
this second projection every partner listener is denied and nobody ever appears
online - while `GET /conversations/{id}/presence` keeps working, because the
Admin SDK bypasses rules. That is a failure mode that hides from the backend
tests, so `test_presence_visibility_is_projected_for_the_rtdb_rules` asserts the
projection itself.

Grants are stored per conversation:

```
presenceVisibility/{alice}/{bob}/{conversationA}: true
```

The rule checks whether `presenceVisibility/{alice}/{bob}` exists. The backend
adds and removes conversation keys transactionally, so revoking one thread does
not blind Alice to Bob when they still share another. The last removal deletes
the reader node and the rule denies access.

If the old `{targetUid}/{conversationId}/{readerUid}` projection has already
been deployed, the old nodes cannot satisfy the new reader-keyed rule. After
deploying these rules, run once:

```
python -m scripts.rebuild_presence_visibility --dry-run
python -m scripts.rebuild_presence_visibility
```

It rebuilds both directions for every conversation the chat policy grants
(`grants_presence`), is idempotent, and removes nothing unless given
`--prune-stale` / `--prune-legacy`. See
[firebase_backend.md](firebase_backend.md#deployment-presence-visibility-backfill).

### Who is granted

One rule, `grants_presence` in `app/services/chat/policy.py`, used by both
normal provisioning (`ConversationService.provision`: publish if it grants,
revoke otherwise) and the backfill command:

| Conversation | Presence grant |
| --- | --- |
| `active` | yes |
| `read_only` | **yes - current product policy** (see below) |
| `suspended` | no |
| `closed` | no |
| order no longer readable, or conversation/order deleted | no |

**Current product policy:** a `read_only` thread - completion grace period
over, or a cancelled/refunded order - keeps presence visibility between its
two members. This is the existing behaviour, kept deliberately; narrowing it
is a product decision.

A `suspended` thread publishes nothing. Grants it already had are withdrawn
when it is reprovisioned: moderation sets `status=suspended` and
`provisioning_status=pending`, and `reconcile_pending` revokes them. The
backfill command's `--prune-stale` removes any that remain. Suspension does
not change the Firestore conversation or its history policy.

`revoke_membership` removes every visibility grant that conversation issued,
then the membership and typing nodes. Closing a conversation calls it; failed
projections can be retried without re-granting a closed thread. Access ends
when the last relationship does.

## The server-side read

`GET /api/v1/conversations/{id}/presence` returns each participant's state.

It exists for a client that wants presence without an RTDB listener - a cold
open, a web client, a screen that shows it once. It is scoped to a conversation
the caller is a member of and it reads through the Admin SDK.

There is deliberately **no endpoint that reads presence by uid.** That endpoint
would be a way for any account to watch any other, whatever the RTDB rules say.

## Typing is not persisted or notified

No Postgres row, no push notification. It is UI state with a lifetime measured in
seconds. Closing a conversation revokes its RTDB membership and deletes its
typing node, so a stale "typing…" does not outlive the thread.

## Failure modes worth knowing

* **A killed app never fires `onDisconnect`'s local write, but the server-side
  one still runs** - that is the point of arming it on the server. A user who
  loses power goes offline when RTDB notices the socket is gone.
* **A client that reconnects re-arms `onDisconnect`.** Doing it once at startup
  leaves the user permanently online after the first reconnect.
* **Presence is not delivery confirmation.** Online means a socket is open, not
  that anybody is reading. The chat does not use it to decide whether to send a
  push; the push outbox does not consult presence at all.
