# Chat attachments

## The flow

```
1. POST /conversations/{id}/attachments   -> authorise, receive one path
2. PUT  <that path>                       -> client uploads straight to Storage
3. POST /attachments/{id}/finalize        -> backend verifies the stored object
4. POST /conversations/{id}/messages      -> send, referencing the attachment
```

The upload is direct. Proxying a phone photo through the API would double the
bytes on the wire and put a multi-megabyte upload on a request worker.

## Three decisions

### The server picks the path

```
chat/{conversationId}/{attachmentId}/original.jpg
```

Both ids were issued by the backend. The client's filename is kept as display
metadata and never touched by the path, because a client-supplied filename in a
storage path is a directory-traversal and an overwrite problem wearing a
convenience disguise. `../../etc/passwd` as `original_filename` produces exactly
the path above, and there is a test that says so.

### The claimed type is not the type

A client says `image/png`. The bucket says what was actually stored.
Finalisation compares the two and rejects a mismatch. "Trust the extension" is
how an HTML file becomes a stored XSS and an SVG becomes a script.

`NEVER_ALLOWED` is refused whatever `ATTACHMENT_ALLOWED_MIME_TYPES` says:
`image/svg+xml`, `text/html`, `application/xhtml+xml`, JavaScript, and
executables. SVG and HTML are scriptable; the rest run. A "chat image" that
executes code in the viewer's browser is not an image.

Rejection deletes the bytes. They are not wanted, so they do not stay in the
bucket.

### Pending is not a file

An attachment is an authorised *intent* until the bytes arrive. Only `ready` may
be referenced by a message - otherwise it renders as a broken image in
somebody's paid consultation. `finalize` is the only thing that sets `ready`, and
it believes the bucket rather than the client.

## Scoping

`get_own` scopes to the conversation **and** the uploader. Both, so:

* a member cannot finalise somebody else's pending upload;
* a finalised attachment cannot be replayed into a different thread.

Once sent, `message_id` is set and a second send is `attachment_already_used`.

Uploading into a read-only thread is writing to it, so the intent endpoint
requires write permission, not just read.

## Limits

| Setting | Default |
|---|---|
| `ATTACHMENT_MAX_BYTES` | 8 MiB |
| `ATTACHMENT_ALLOWED_MIME_TYPES` | `image/jpeg,image/png,image/webp` |
| `ATTACHMENT_PENDING_TTL_SECONDS` | 1800 |
| `CHAT_ATTACHMENTS_PER_MESSAGE` | 4 |
| `ATTACHMENT_CREATE_RATE_LIMIT` | 60/hour |

In-flight intents per conversation are capped, so an abandoned client loop cannot
mint authorisations indefinitely.

## Expiry

`purge_stale_intents()` retires pending rows older than the TTL. Each one is a
path somebody is still allowed to write to, so leaving them is leaving open
doors. If bytes were uploaded but never finalised they are orphans, and they go
too.

## Storage rules enforce the same things

The rules and the backend both check path shape, size, content type and
membership. Neither is trusted alone: the rules run *before* the bytes land,
which is the only thing that stops a 4 GB upload, and finalisation inspects what
actually landed, which is the only thing that catches a lying content type.

Two further rules:

* **`allow update: if false`.** An attachment that could be replaced after
  finalisation would let somebody swap the image an expert already saw.
* **`allow delete: if false`.** Deletion is the backend's job, paired with the
  metadata row.

Membership is read from the Firestore projection, which a client cannot modify.

There is no permissive default in `storage.rules`; the final match denies
everything.

## No permanent public URL

Reads go through the Firebase SDK with the caller's own credentials, evaluated
against the rules. Nothing hands out a signed URL with a long life or a token in
a query string, because a URL that works without a session is a URL that works
after the conversation ends, after consent is revoked and after it has been
pasted into a support ticket.

## Errors

| Code | Status | Meaning |
|---|---|---|
| `mime_type_forbidden` | 422 | in `NEVER_ALLOWED` |
| `mime_type_not_allowed` | 422 | not in the allow-list, or the stored object is not what was claimed |
| `attachment_too_large` | 422 | declared or actual |
| `attachment_missing` | 422 | finalise called before the upload arrived |
| `attachment_not_ready` | 422 | referenced by a message while still pending |
| `attachment_already_used` | 422 | already sent |
| `attachment_rejected` | 422 | empty, or already rejected |
| `attachment_quota_exceeded` | 429 | too many in-flight intents |
| `not_found` | 404 | not yours, or not in this conversation |
