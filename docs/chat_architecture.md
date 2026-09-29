# Expert chat

## The shape

```
send:     client ──HTTPS──> FastAPI ──> Firestore
receive:  client <──listener── Firestore
```

Clients **read** Firestore directly through a listener and **write** nothing.
Every message goes through `POST /conversations/{id}/messages`.

## Why writes are backend-mediated

This is the phase's main architectural decision, and it costs a round trip on
send, so it is worth defending.

Letting the client write straight to Firestore would be one fewer hop. But the
security rule would have to answer "does an order in a writable state, for a
service the catalogue says supports chat, with an expert who is not suspended,
inside the post-completion grace period, entitle this person to speak right
now". Firestore cannot see any of that without mirroring the marketplace into
it, and a mirror that can drift is a permission bug waiting to happen.

Three more things need server logic regardless: message idempotency, length and
content limits, and attachment readiness. Plus the push outbox and rate limiting.

So the rules reduce to something small enough to be obviously right: **members
may read; nobody may write.** A rule that permits writes has to be correct about
everything above, forever, in two languages.

The cost is honest: sending pays one backend round trip. Receiving is unchanged
and still instant, because the listener is untouched.

## Firestore is the canonical message store

Postgres holds authorisation, audit metadata, attachments, counters and the
outbox - **not** a second copy of every message. Two stores that can disagree
about what somebody said is not a property worth having in a paid consultation.

## Eligibility: chat exists because an order does

A user cannot open a thread with an arbitrary expert.
`order_allows_new_conversation` requires all of:

* the order names an expert;
* `fulfillment_mode` is `expert` or `hybrid`, not an automated report;
* `delivery_type` is conversational (`chat`, `voice`, `video`) - a written report
  is delivered, not discussed;
* the catalogue's `supports_chat` is true for that `ServiceDefinition`;
* the order is in a writable state.

`POST /conversations` is idempotent: one conversation per order is a database
constraint, so a retry returns the original thread. Two concurrent requests both
insert, the constraint decides, and the loser reads the winner's row.

## Order state drives the thread

```
WRITABLE  = paid, confirmed, awaiting_expert, in_progress
READABLE  = WRITABLE + completed, cancelled, refunded
```

`pending_payment` is **not** writable. Chat before payment would be a free
consultation channel, which is not what anybody agreed to.

Read and write are separate questions on purpose. A finished consultation
somebody paid for is theirs to scroll back through; a cancelled order is not a
live chat. Collapsing the two would mean either a cancelled order stays open, or
a user loses the record of what they were told.

`GET /chat/policy` returns all of this as data, so a client can explain a closed
thread without hard-coding the reasons and the docs cannot drift from the code.

### The grace period

A completed order stays writable for `CHAT_READ_ONLY_AFTER_COMPLETION_DAYS`
(30), then becomes read-only. Somebody who has just been told something
complicated will have a follow-up question.

`conversation_status_for_order` is the single pure function that knows this.
`permission_for` derives from it rather than re-testing `order.status`, because
`completed` is never a writable order state - an earlier version checked the
order state directly and silently cancelled the whole grace period.

### Reconciliation, not a scheduler

`_reconcile` runs on every read. It is cheap and idempotent, and it means a
completed order crosses into read-only on its own with no cron job.

Two statuses outrank it:

* `suspended` - moderation outranks order state.
* `closed` **with `closed_at` set** - a thread one of the parties chose to end.
  Order state may reopen one that went read-only by itself; it must not reopen
  one somebody closed, or the next read silently undoes the close.

### A suspended expert

Loses the ability to write. The user keeps their history: it is evidence of what
they were told, and removing it would punish the wrong person.

## Membership is the account

An expert is authorised because the conversation's `expert_user_id` is them -
**not** because they hold an expert profile id. A profile id is not a credential.

Every owner-scoped path answers `404`, never `403`. A wrong guess must not
confirm that a conversation exists.

## Provisioning can fail without losing anything

Opening a conversation writes a Firestore document and an RTDB membership node.
If Firebase is unavailable, the failure is **recorded, not raised**:

```json
{"provisioning_status": "failed", "...": "..."}
```

The conversation exists. Firebase being briefly down must not roll back an order
somebody paid for. `_reconcile` retries on the next read, and
`reconcile_pending()` sweeps in bulk.

`provisioning_status` is `pending` when a member has no Firebase identity yet -
the transport identifies senders by uid, so there is nothing to project onto.

## Messages

Order of operations in `send_message`, and it matters: **authorise, validate,
check idempotency, write.** A duplicate check after the write has already sent
the message.

* `client_message_id` makes a retry return the original message.
* The same id with *different* content is `409 message_conflict`. Silently
  returning the wrong message would hide a client bug.
* Text is sanitised: control characters stripped except `\n\r\t`, trimmed, then
  length-checked. Empty after that is `422`.
* `4000` characters maximum.
* Attachments must be `ready`, belong to this conversation, belong to this
  uploader, and be unused. See [media_attachments.md](media_attachments.md).
* Deletion is soft and only the sender's own. A conversation either party can
  edit on the other's behalf is not a record of anything.

Timestamps are server-side (`firestore.SERVER_TIMESTAMP`). A client clock is
never canonical.

## Consent is untouched by any of this

**Opening a chat grants no data access.** An expert may hold a conversation and
still have no consent to the user's chart. B8's rule stands exactly as written:
a live grant on that order, or nothing. "They can see it because they are the
expert" remains forbidden.

The two are independent in both directions - granting consent does not open a
chat, and revoking it does not silence one. Both directions are tested
(`test_chat_access_does_not_grant_data_access`,
`test_consent_and_chat_are_independent`), because this is precisely the kind of
boundary that erodes by accident.

## Privacy

Message bodies are never logged. `chat_message_sent` carries the conversation
id, the message id, the sender role, the type and whether there was an
attachment - enough to debug with, nothing that reveals what was said. There is
a test that asserts it.

Push payloads carry no message content either. See
[push_notifications.md](push_notifications.md).

## Endpoints

| Method | Path |
|---|---|
| `GET` | `/api/v1/chat/policy` |
| `POST` | `/api/v1/conversations` |
| `GET` | `/api/v1/conversations` |
| `GET` | `/api/v1/conversations/{id}` |
| `POST` | `/api/v1/conversations/{id}/close` |
| `POST` | `/api/v1/conversations/{id}/messages` |
| `GET` | `/api/v1/conversations/{id}/messages` |
| `DELETE` | `/api/v1/conversations/{id}/messages/{message_id}` |
| `GET` | `/api/v1/conversations/{id}/presence` |
| `POST` | `/api/v1/conversations/{id}/attachments` |
| `GET` | `/api/v1/conversations/{id}/attachments` |
| `POST` | `/api/v1/attachments/{id}/finalize` |

## Errors

| Code | Status | Meaning |
|---|---|---|
| `chat_not_available` | 409 | the order does not entitle anybody to a thread |
| `chat_read_only` | 409 | history yes, new messages no |
| `message_conflict` | 409 | that `client_message_id` carried different content |
| `message_rejected` | 422 | empty, too long, or a bad attachment reference |
| `firebase_identity_required` | 409 | chat needs a Firebase identity |
| `firebase_not_configured` | 503 | no service account on this deployment |
