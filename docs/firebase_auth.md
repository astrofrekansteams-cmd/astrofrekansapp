# Firebase authentication

## Hybrid, so nobody is signed out

`AUTH_MODE=hybrid` is the default. `get_current_user` tries the backend's own
JWT first, because verifying one is free and local, and falls back to verifying
the bearer token as a Firebase ID token. Existing accounts keep working with no
client change; new clients can send a Firebase token and never see a backend
JWT.

The other modes exist for the ends of the migration: `local_jwt` refuses
Firebase tokens, `firebase` refuses local ones. Switching straight to `firebase`
signs out every current user, which is why it is not the default.

## No token is wrapped in another token

`POST /auth/firebase/session` resolves an ID token to a local account and says
whether that created one. It does **not** mint a backend JWT.

Wrapping a Firebase token in one of ours would mean two session lifetimes to
keep in step, two revocation stories, and a refresh token whose expiry nobody is
watching. The Firebase SDK already refreshes its own token on the client, so the
client sends that and the backend verifies it. The endpoint is optional: the same
mapping happens implicitly on any authenticated request.

## The token payload is a claim, not a record

`verify_id_token` establishes the signature, the issuer, the audience and the
expiry. It establishes nothing about the person. So:

* **`uid` is the only thing trusted.** It identifies the credential.
* **`email` is not an identity.** Several providers do not verify it. See
  linking, below.
* **`name` and `picture` seed a new profile once, as a convenience**, and then
  belong to the user. A display name changed in Google does not overwrite what
  somebody typed into Astrofrekans.
* **Custom claims carry no business permission.** Tier, subscription, expert
  status and consent all live in Postgres. A claim is a cached copy an attacker
  would love to be authoritative, and it goes stale between token refreshes even
  when nobody is attacking.

`FIREBASE_CHECK_REVOKED` is off by default: the check costs a round trip to
Firebase on every request, and an ID token lives an hour. Endpoints where an hour
matters ask for it explicitly.

## Account linking is the dangerous part

The tempting shortcut: a token arrives carrying `alice@example.com`, an account
with that address exists, so sign them in. **That is an account-takeover
primitive.** Anyone who can obtain a token for an address - from a provider that
does not verify email, or one configured badly - takes the Astrofrekans account
behind it.

Three paths, and only the first two are on by default.

| Path | When | Default |
|---|---|---|
| `new_account` | uid unknown, email matches nothing | on |
| `existing_session` | the caller is already signed in and links deliberately | on |
| `automatic_verified_email` | uid unknown, email matches an account | **off** |

The third needs `FIREBASE_AUTO_LINK_VERIFIED_EMAIL=true` **and** a
provider-verified address. Without both, the response is `409`:

```json
{
  "error": {
    "code": "account_link_required",
    "message": "An account already exists with this email address. Sign in with your existing password and link this sign-in method from your account settings."
  }
}
```

That is not an error a client can work around, and deliberately so. The remedy
is `POST /auth/firebase/link` from inside a session, where being signed in is
the proof of ownership that a matching address is not.

A refusal is logged with the uid, the provider and the reason. The address is
not logged.

## Unlinking

`DELETE /auth/firebase/link` detaches the identity and keeps the account. Refused
with `last_sign_in_method` when the account has no password, because the
alternative is locking somebody out of their own data to honour a request they
did not understand.

## Deletion

`detach_for_deletion` revokes refresh tokens and deletes the Firebase user, and
reports each step separately:

```python
{"firebase_identity": True, "tokens_revoked": False}
```

Deliberately not one irreversible call. Each step fails independently, and a
caller that believes everything was removed when it was not is worse than one
that knows what is left.

## Concurrency

Two simultaneous first sign-ins for the same identity both try to insert. The
unique constraint on `users.firebase_uid` decides; the loser reads the row the
winner wrote. The application-level "look first" is for the ordinary case, not
the guarantee.

## Schema

`users.firebase_uid` - nullable, unique, indexed. Nullable because most accounts
are password accounts and always will be; unique because a credential belongs to
one account.

`firebase_identities` records the provider, the address as presented, whether it
was verified, which of the three link methods was used, and when the identity
last signed in. It is an audit trail: "how did this account come to be reachable
by this credential" is a question worth being able to answer.

## Endpoints

| Method | Path | Auth |
|---|---|---|
| `GET` | `/api/v1/auth/capabilities` | none |
| `POST` | `/api/v1/auth/firebase/session` | a Firebase ID token in the body |
| `POST` | `/api/v1/auth/firebase/link` | an existing session |
| `DELETE` | `/api/v1/auth/firebase/link` | an existing session |

## Errors

| Code | Status | Meaning |
|---|---|---|
| `firebase_not_configured` | 503 | no service account on this deployment |
| `firebase_auth_disabled` | 503 | `AUTH_MODE=local_jwt` |
| `invalid_firebase_token` | 401 | signature, audience or issuer |
| `firebase_token_expired` | 401 | refresh and retry |
| `firebase_token_revoked` | 401 | signed out elsewhere |
| `firebase_account_disabled` | 401 | disabled in the Firebase console |
| `account_link_required` | 409 | see linking |
| `identity_already_linked` | 409 | that credential belongs to another account |
| `last_sign_in_method` | 409 | set a password before unlinking |

## Account centre (Phase 2)

* `GET /auth/sessions` lists email-and-password sign-ins per device session
  (user agent, shortened IP `85.105.x.x`, last use); `current` marks the
  caller (access tokens now carry the session id `sid`).
  `DELETE /auth/sessions/{id}` revokes one session's refresh token; an access
  token already issued stays valid until it expires (minutes). Firebase
  sign-ins are managed by Firebase and are not listed.
* `POST /auth/change-password` is rate-limited per account (10/hour) and still
  revokes every session; the app signs straight back in with the new password.
  A Firebase account changes its password in Firebase after re-authenticating.
* `GET /users/me/deletion-check` / `POST /users/me/delete` (and `DELETE
  /users/me`, same rules): the password is required (the email address for an
  account without a local password), and deletion is refused with `409
  account_has_active_services` while an appointment is live, an order is
  unfinished, a refund is under review, or - for an expert - an order placed
  with them is open. Soft delete: sessions revoked, push devices disabled, an
  expert profile set `inactive`; orders, payments and the ledger are kept.
