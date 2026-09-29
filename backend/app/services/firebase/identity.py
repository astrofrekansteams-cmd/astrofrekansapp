"""Mapping a verified Firebase identity to a local account.

The rule: **Postgres owns the account, Firebase owns the credential.**

A Firebase uid is proof of who signed in. It is not an account, it is not a
foreign key, and it is not a source of profile data. Every business table still
references the local user id, so a rotated or lost Firebase project orphans
nothing and a display name changed in Google does not overwrite what the user
typed into Astrofrekans.

## Account linking is the dangerous part

The tempting shortcut is: a Firebase token arrives carrying
`alice@example.com`, an account with that email already exists, so log them in.
That is an account takeover primitive. Several identity providers do not verify
email at all, and a provider that does can still be configured badly - so a
match on email is a claim, not proof.

Three linking paths, and only the first two are on by default:

1. **Known uid** - a `firebase_identities` row exists. Sign in.
2. **New account** - no uid, no matching email. Create an account owned by this
   identity from the start.
3. **Matching email** - an account exists with that address. Refused unless
   `FIREBASE_AUTO_LINK_VERIFIED_EMAIL` is deliberately enabled *and* the
   provider verified the address. Otherwise the caller is told to sign in with
   their existing credentials and link from inside the session, where they have
   already proved they own the account.

See `docs/firebase_auth.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.models.chat import FirebaseIdentityRecord
from app.db.models.user import User, UserProfile
from app.domain.chat import FirebaseIdentity
from app.services.firebase.provider import FirebaseIdentityProvider

logger = get_logger(__name__)

LINK_NEW_ACCOUNT = "new_account"
LINK_EXISTING_SESSION = "existing_session"
LINK_AUTOMATIC_VERIFIED_EMAIL = "automatic_verified_email"


class AccountLinkRequired(AppError):
    """An account with this email exists, and this identity is not it.

    Deliberately not an error the client can bypass: the remedy is to sign in
    with the existing credentials and link from inside that session.
    """

    status_code = 409
    code = "account_link_required"
    message = (
        "An account already exists with this email address. Sign in with your "
        "existing password and link this sign-in method from your account "
        "settings."
    )


class IdentityAlreadyLinked(AppError):
    status_code = 409
    code = "identity_already_linked"
    message = "That sign-in method is already linked to another account."


class FirebaseIdentityService:
    def __init__(
        self, session: AsyncSession, provider: FirebaseIdentityProvider
    ) -> None:
        self.session = session
        self.provider = provider

    # ------------------------------------------------------------ lookup

    async def find_user_by_uid(self, firebase_uid: str) -> User | None:
        """The fast path: the column on `users` carries the index."""
        return await self.session.scalar(
            select(User).where(
                User.firebase_uid == firebase_uid,
                User.deleted_at.is_(None),
            )
        )

    async def find_record(self, firebase_uid: str) -> FirebaseIdentityRecord | None:
        return await self.session.scalar(
            select(FirebaseIdentityRecord).where(
                FirebaseIdentityRecord.firebase_uid == firebase_uid
            )
        )

    # ------------------------------------------------------- resolution

    async def resolve(self, identity: FirebaseIdentity) -> User:
        """Turn a verified identity into a local account.

        Never creates an account for an identity whose email collides with an
        existing one unless that is explicitly permitted.
        """
        user, _ = await self.resolve_detailed(identity)
        return user

    async def resolve_detailed(
        self, identity: FirebaseIdentity
    ) -> tuple[User, bool]:
        """As `resolve`, and say whether the account was **created**.

        Linking an identity to an account that already existed is not the same
        event as signing up, and a client showing an onboarding flow needs to
        tell them apart.
        """
        existing = await self.find_user_by_uid(identity.uid)
        if existing is not None:
            await self._touch(existing, identity)
            return existing, False

        if identity.email:
            clash = await self.session.scalar(
                select(User).where(
                    User.email == identity.email.lower(),
                    User.deleted_at.is_(None),
                )
            )
            if clash is not None:
                return await self._link_to_existing(clash, identity), False

        return await self._create_account(identity), True

    async def _link_to_existing(
        self, user: User, identity: FirebaseIdentity
    ) -> User:
        """An account with this email exists. Proceed only if allowed.

        A matching email is a claim about identity, not proof of it. Silently
        adopting the account here would let anyone who can obtain a token for
        an address take over the Astrofrekans account behind it.
        """
        permitted = (
            settings.firebase_auto_link_verified_email
            and identity.is_email_trustworthy
        )
        if not permitted:
            logger.warning(
                "firebase_link_refused",
                firebase_uid=identity.uid,
                reason=(
                    "email_not_verified"
                    if not identity.email_verified
                    else "auto_link_disabled"
                ),
                # The address itself is not logged.
                provider=identity.provider_id,
            )
            raise AccountLinkRequired()

        return await self.link(
            user, identity, method=LINK_AUTOMATIC_VERIFIED_EMAIL
        )

    async def _create_account(self, identity: FirebaseIdentity) -> User:
        """A new account, owned by this identity from the start.

        The display name is seeded from the provider once, as a convenience,
        and then belongs to the user: Firebase is not the source of truth for
        an Astrofrekans profile.
        """
        user = User(
            email=(identity.email or f"{identity.uid}@firebase.local").lower(),
            password_hash=None,
            is_active=True,
            is_email_verified=identity.email_verified,
            firebase_uid=identity.uid,
        )
        self.session.add(user)

        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            # Two concurrent first sign-ins for the same identity. Whoever lost
            # simply reads the row the winner wrote.
            existing = await self.find_user_by_uid(identity.uid)
            if existing is not None:
                return existing
            raise IdentityAlreadyLinked() from exc

        # `name` is required on the profile. Seeded from the provider once as a
        # convenience, then it belongs to the user - Firebase is not the source
        # of truth for an Astrofrekans profile.
        user.profile = UserProfile(
            user_id=user.id,
            name=(identity.name or "").strip()[:120] or "Astrofrekans",
        )
        self.session.add(
            FirebaseIdentityRecord(
                user_id=user.id,
                firebase_uid=identity.uid,
                provider_id=identity.provider_id,
                email=identity.email,
                email_verified=identity.email_verified,
                link_method=LINK_NEW_ACCOUNT,
                last_firebase_login_at=datetime.now(UTC),
            )
        )
        await self.session.flush()

        logger.info(
            "firebase_account_created",
            user_id=str(user.id),
            firebase_uid=identity.uid,
            provider=identity.provider_id,
        )
        return user

    async def link(
        self,
        user: User,
        identity: FirebaseIdentity,
        *,
        method: str = LINK_EXISTING_SESSION,
    ) -> User:
        """Attach a Firebase identity to an account.

        `method=existing_session` is the safe path: the caller already proved
        they own the account by being signed in to it.
        """
        clash = await self.find_record(identity.uid)
        if clash is not None and clash.user_id != user.id:
            raise IdentityAlreadyLinked()

        if user.firebase_uid and user.firebase_uid != identity.uid:
            raise IdentityAlreadyLinked(
                "This account is already linked to a different sign-in "
                "method."
            )

        user.firebase_uid = identity.uid
        if identity.email_verified and identity.email:
            user.is_email_verified = True

        if clash is None:
            self.session.add(
                FirebaseIdentityRecord(
                    user_id=user.id,
                    firebase_uid=identity.uid,
                    provider_id=identity.provider_id,
                    email=identity.email,
                    email_verified=identity.email_verified,
                    link_method=method,
                    last_firebase_login_at=datetime.now(UTC),
                )
            )
        else:
            clash.last_firebase_login_at = datetime.now(UTC)
            clash.email_verified = identity.email_verified

        await self.session.flush()
        logger.info(
            "firebase_identity_linked",
            user_id=str(user.id),
            firebase_uid=identity.uid,
            method=method,
            provider=identity.provider_id,
        )
        return user

    async def unlink(self, user: User) -> None:
        """Detach the Firebase identity, keeping the account.

        Refused when it would leave the account with no way to sign in.
        """
        if user.password_hash is None:
            raise AppError(
                "Set a password before removing your only sign-in method.",
                code="last_sign_in_method",
                status_code=409,
            )

        record = await self.find_record(user.firebase_uid or "")
        if record is not None:
            await self.session.delete(record)
        user.firebase_uid = None
        await self.session.flush()
        logger.info("firebase_identity_unlinked", user_id=str(user.id))

    async def _touch(self, user: User, identity: FirebaseIdentity) -> None:
        record = await self.find_record(identity.uid)
        if record is not None:
            record.last_firebase_login_at = datetime.now(UTC)
            record.email_verified = identity.email_verified
            if identity.provider_id:
                record.provider_id = identity.provider_id
            await self.session.flush()

    # ------------------------------------------------------------ deletion

    async def detach_for_deletion(self, user: User) -> dict[str, bool]:
        """Best-effort teardown of a user's Firebase footprint.

        Deliberately **not** an irreversible one-shot delete. Each step can
        fail independently, and a partial result is reported rather than
        hidden - a caller that believes everything was removed when it was not
        is worse than one that knows what is left.
        """
        outcome = {"firebase_identity": False, "tokens_revoked": False}
        if not user.firebase_uid:
            return outcome

        try:
            await self.provider.revoke_refresh_tokens(user.firebase_uid)
            outcome["tokens_revoked"] = True
        except Exception:  # noqa: BLE001 - reported, never fatal
            logger.warning("firebase_revoke_failed", user_id=str(user.id))

        try:
            await self.provider.delete_user(user.firebase_uid)
            outcome["firebase_identity"] = True
        except Exception:  # noqa: BLE001
            logger.warning("firebase_delete_failed", user_id=str(user.id))

        return outcome
