"""Application settings.

Everything is read from the environment (see ``.env.example``). No secret is
ever hard-coded and no secret is logged.
"""

from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


# Time a call push claim needs beyond the provider operation itself: the
# claim and record database round trips.
CALL_PUSH_LEASE_MARGIN_SECONDS = 2.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- app ----------------------------------------------------------
    app_name: str = "Astrofrekans API"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- database -----------------------------------------------------
    database_url: str = "postgresql+asyncpg://astro:astro@localhost:5432/astrofrekans"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --- redis --------------------------------------------------------
    redis_url: str | None = "redis://localhost:6379/0"

    # --- security -----------------------------------------------------
    jwt_secret: str = Field(default="dev-only-change-me", min_length=8)
    jwt_refresh_secret: str = Field(default="dev-only-change-me-too", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    password_reset_ttl_minutes: int = 30
    # Where a reset link points - the only place it is set. A hosted https
    # page that hands the token to the app (astrofrekans://app/reset-password
    # ?token=...). The token is appended as `#token=` so the web host never
    # receives it. Override per
    # environment with PASSWORD_RESET_URL_BASE; production requires https.
    password_reset_url_base: str = (
        "https://astrofrekansteams-cmd.github.io/astrofrekansapp/reset-password.html"
    )

    # --- mail -----------------------------------------------------------
    # "disabled" until a provider is chosen: password reset then says it is
    # unavailable rather than pretending to send. See services/mail/mailer.py.
    mail_provider: Literal["disabled", "smtp", "log", "memory"] = "disabled"
    mail_from: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: float = 10.0
    # Transient failures only (connection, timeout, 4xx); see mail/mailer.py.
    smtp_max_attempts: int = 3
    smtp_retry_backoff_seconds: float = 1.0

    # Comma separated list, e.g. "https://app.astrofrekans.com,https://admin..."
    cors_origins: str = ""

    # --- rate limiting ------------------------------------------------
    rate_limit_enabled: bool = True
    login_rate_limit: str = "10/minute"
    register_rate_limit: str = "5/minute"
    ai_rate_limit: str = "30/hour"

    # --- astrology ----------------------------------------------------
    ephemeris_path: Path = BACKEND_ROOT / "data" / "ephemeris" / "de421.bsp"
    default_house_system: Literal["placidus", "whole_sign", "equal", "koch"] = (
        "placidus"
    )
    natal_chart_cache_ttl_seconds: int = 60 * 60 * 24 * 30
    transit_cache_ttl_seconds: int = 60 * 30

    # --- AI (backend only; the key never reaches the client) -----------
    ai_provider: Literal["fake", "openai"] = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_base_url: str | None = None
    openai_organization: str | None = None

    # Model routing. Names are configuration, never literals in the code, so a
    # model can be swapped or rolled back without touching a service.
    ai_model_low_cost: str = "gpt-5.6-luna"
    ai_model_standard: str = "gpt-5.6-terra"
    ai_model_premium: str = "gpt-5.6-sol"

    # Optional per-use-case overrides; empty means "use the tier".
    ai_model_chat: str | None = None
    ai_model_report: str | None = None
    ai_model_summary: str | None = None

    # A tier may fall back to a cheaper model, but only loudly: the fallback
    # is recorded on the generation, never silently applied.
    #
    # The policy is per use case on purpose. A chat answer from a cheaper
    # model is still a useful answer, so falling back beats failing. A premium
    # report is something the user waited for and may have paid for; quietly
    # producing it with a weaker model and presenting it as the premium
    # reading is worse than saying the service is busy. So reports do not fall
    # back unless an operator turns it on deliberately.
    ai_allow_model_fallback: bool = True
    ai_allow_fallback_chat: bool = True
    ai_allow_fallback_summary: bool = True
    ai_allow_fallback_report: bool = False

    ai_request_timeout_seconds: float = 90.0
    ai_stream_timeout_seconds: float = 180.0
    ai_max_retries: int = 2
    ai_retry_base_delay_seconds: float = 0.5

    # Token budgets. Context is trimmed by importance before a call, never by
    # truncating the prompt blindly.
    ai_chat_context_budget: int = 6000
    ai_report_context_budget: int = 14000
    ai_summary_budget: int = 1200
    ai_max_output_tokens_chat: int = 1200
    ai_max_output_tokens_report: int = 4000
    ai_max_output_tokens_summary: int = 400

    # Conversation memory: the last N messages plus a rolling summary.
    ai_recent_message_window: int = 10
    ai_summary_trigger_messages: int = 12

    ai_chat_rate_limit: str = "40/hour"
    ai_report_rate_limit: str = "10/hour"
    ai_stream_rate_limit: str = "40/hour"

    ai_report_cache_ttl_seconds: int = 60 * 60 * 24 * 30
    ai_context_cache_ttl_seconds: int = 60 * 30
    ai_job_ttl_seconds: int = 60 * 60 * 24

    # Guards against a user firing the same expensive report twice.
    ai_generation_lock_seconds: int = 300

    # ------------------------------------------------------------ divination
    #
    # Reversal is a deck property first and a setting second: a Katina card
    # and a symmetrical rune are never reversed whatever this says.
    divination_reversal_enabled: bool = True
    divination_reversal_probability: float = 0.3
    divination_include_blank_rune: bool = False

    divination_draw_rate_limit: str = "60/hour"
    divination_interpret_rate_limit: str = "20/hour"
    compatibility_interpret_rate_limit: str = "20/hour"

    # ---------------------------------------------------- plans and coins
    daily_draws_free: int = 3
    daily_draws_premium: int = 15
    daily_draws_cosmic_plus: int = 40
    # AstroCoins granted each calendar month (UTC) while the plan is active.
    monthly_coins_premium: int = 150
    monthly_coins_cosmic_plus: int = 500
    # Rewarded ads. Without a verifier (`ad_reward_verifier`) the reward
    # endpoint is off, except the dev-only "mock" verifier outside production.
    ad_reward_coins: int = 10
    ad_rewards_per_day: int = 5
    ad_reward_verifier: str = ""
    # Kozmik+ includes the reports otherwise sold one by one.
    paid_reports_included_in_cosmic_plus: bool = True

    # A repeat of the same question on the same deck inside this window is
    # flagged in metadata. It is never blocked - people are allowed to ask
    # again - but the interpreter is told, so it does not narrate a changed
    # fate.
    divination_repeat_window_seconds: int = 60 * 60 * 6
    # A face-down user-pick session must be revealed within this time.
    divination_session_ttl_seconds: int = 15 * 60
    divination_reading_cache_ttl_seconds: int = 60 * 60 * 24 * 7

    # Report worker. The lease is how long a claim survives without being
    # renewed; it has to outlast a slow premium generation, or a healthy
    # worker's job would be stolen from under it.
    ai_job_lease_seconds: int = 600
    ai_job_max_attempts: int = 3
    ai_worker_poll_seconds: float = 2.0
    ai_worker_idle_log_seconds: float = 300.0

    # Never log raw prompts or context in a deployed environment.
    ai_log_prompts: bool = False

    # --- marketplace ---------------------------------------------------
    #
    # Commission arrives in basis points from configuration and is never a
    # literal in business logic. 10000 bp = 100%. The split is integer
    # arithmetic throughout; no percentage ever becomes a float.
    marketplace_commission_bps: int = 2000
    marketplace_default_currency: str = "TRY"

    # Slot generation. All of these are policy, not physics, so they are
    # settings rather than constants buried in the generator.
    appointment_slot_granularity_minutes: int = 15
    appointment_buffer_before_minutes: int = 5
    appointment_buffer_after_minutes: int = 5
    appointment_minimum_notice_minutes: int = 120
    appointment_max_horizon_days: int = 90
    appointment_max_slot_query_days: int = 92

    # How long a slot stays claimed while an order is being placed. Long
    # enough to finish a checkout, short enough that an abandoned form does
    # not hold a popular slot hostage.
    slot_hold_ttl_seconds: int = 600

    marketplace_search_rate_limit: str = "120/hour"
    appointment_booking_rate_limit: str = "20/hour"
    order_create_rate_limit: str = "30/hour"
    review_create_rate_limit: str = "10/hour"
    expert_mutation_rate_limit: str = "60/hour"

    marketplace_search_cache_ttl_seconds: int = 60
    expert_detail_cache_ttl_seconds: int = 120

    # --- firebase ------------------------------------------------------
    #
    # Firebase is optional infrastructure. Without credentials the app boots,
    # astrology, marketplace and AI keep working, and only the Firebase-backed
    # endpoints answer `firebase_not_configured`.
    #
    # The service-account JSON is never committed. Supply it either as a path
    # or inline (the inline form suits container secrets); both are read at
    # startup and neither is logged.
    firebase_project_id: str | None = None
    firebase_credentials_path: Path | None = None
    firebase_credentials_json: str | None = None
    firebase_storage_bucket: str | None = None
    firebase_database_url: str | None = None

    # "fake" is a test double, refused in production by assert_production_ready.
    firebase_provider: Literal["fake", "firebase"] = "firebase"

    # Emulator hosts, for local development against the Firebase Emulator
    # Suite. Empty means "talk to the real project".
    firebase_auth_emulator_host: str | None = None
    firestore_emulator_host: str | None = None
    firebase_database_emulator_host: str | None = None
    firebase_storage_emulator_host: str | None = None

    # --- authentication mode -------------------------------------------
    #
    # `hybrid` accepts both the backend's own JWTs and Firebase ID tokens, so
    # existing accounts keep working while clients migrate. Switching straight
    # to `firebase` would sign out every current user.
    auth_mode: Literal["local_jwt", "firebase", "hybrid"] = "hybrid"

    # Checking revocation costs a round trip to Firebase on every request.
    # Off by default: an ID token lives an hour, and the endpoints where an
    # hour matters can ask for the check explicitly.
    firebase_check_revoked: bool = False
    firebase_token_clock_skew_seconds: int = 5

    # Linking a Firebase identity to an existing local account is a takeover
    # risk if done on a matching email alone. Off by default; see
    # docs/firebase_auth.md.
    firebase_auto_link_verified_email: bool = False

    # --- chat ----------------------------------------------------------
    chat_message_max_length: int = 4000
    chat_history_page_size: int = 50
    chat_read_only_after_completion_days: int = 30
    chat_attachments_per_message: int = 4

    # --- attachments ---------------------------------------------------
    attachment_max_bytes: int = 8 * 1024 * 1024
    attachment_allowed_mime_types: str = "image/jpeg,image/png,image/webp"
    # A pending attachment that is never uploaded is rubbish after this.
    attachment_pending_ttl_seconds: int = 60 * 30

    # --- push ----------------------------------------------------------
    push_outbox_max_attempts: int = 5
    push_worker_poll_seconds: float = 2.0
    push_outbox_lease_seconds: int = 120
    push_worker_idle_log_seconds: float = 300.0
    # A sender does not need a notification about their own message.
    push_notify_sender_other_devices: bool = False

    # --- call push: APNs PushKit VoIP (iOS incoming calls) ---------------
    # Token-based APNs authentication (.p8 key). Nothing here is required to
    # boot: without it iOS VoIP delivery answers `apns_not_configured` and
    # everything else works. `fake` is a test double, refused in production.
    apns_provider: Literal["apns", "fake"] = "apns"
    apns_team_id: str | None = None
    apns_key_id: str | None = None
    # PEM content from a secret store, or a path to the .p8 file. Never in git.
    apns_private_key: str | None = None
    apns_private_key_path: Path | None = None
    # The app's bundle id; the VoIP topic is `<bundle id>.voip`.
    apns_bundle_id: str | None = None
    # The one APNs environment this server delivers to. A VoIP token is valid
    # in exactly one environment; tokens registered for the other are refused.
    apns_environment: Literal["production", "sandbox"] = "production"
    # `apns-expiration` for VoIP pushes, seconds from now. Apple: "0, or only a
    # few seconds", so a call is never delivered after it stopped ringing. 0
    # means APNs tries once and does not store it. Never beyond the ring.
    apns_voip_expiration_seconds: int = 0
    # httpx's per-phase timeout for APNs. The wall-clock bound on a call push
    # is CALL_PUSH_SEND_TIMEOUT_SECONDS; this must not exceed it.
    apns_timeout_seconds: float = 8.0

    # --- call push timing ------------------------------------------------
    # A call push claim's lease. Short, because a ring lasts
    # CALL_RING_TIMEOUT_SECONDS: a worker that dies after claiming must be
    # taken over while the phone could still ring - not after B9's generic
    # PUSH_OUTBOX_LEASE_SECONDS (120 s), when the call is long MISSED.
    call_push_lease_seconds: int = 15
    # Hard wall-clock bound on one call push provider operation (an APNs
    # request, an FCM batch). Enforced with a timeout around the call, so a
    # hung provider can never hold a delivery past its lease.
    call_push_send_timeout_seconds: float = 8.0

    # --- rate limits ---------------------------------------------------
    firebase_auth_bootstrap_rate_limit: str = "30/hour"
    conversation_create_rate_limit: str = "20/hour"
    message_send_rate_limit: str = "120/hour"
    attachment_create_rate_limit: str = "60/hour"
    device_register_rate_limit: str = "30/hour"

    # --- calls (LiveKit) -----------------------------------------------
    #
    # LiveKit carries the media; FastAPI decides who may join. Without
    # credentials the app boots and only the call endpoints answer
    # `call_provider_not_configured`.
    #
    # The API secret signs join tokens and verifies webhooks. It never leaves
    # the server, is never logged and is never returned by any endpoint.
    livekit_url: str | None = None
    # Where the *backend* reaches the LiveKit server API, when that differs
    # from the URL clients use (inside a compose network, say). Defaults to
    # LIVEKIT_URL; the SDK turns ws(s):// into http(s):// itself.
    livekit_api_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None

    # "fake" is a test double, refused in production by assert_production_ready.
    realtime_provider: Literal["livekit", "fake"] = "livekit"
    livekit_request_timeout_seconds: float = 5.0

    # A join token authorises *connecting*, nothing more. LiveKit checks its
    # expiry only on the initial connection and refreshes it for a connected
    # client, so this is not a limit on how long a call lasts. Short, because a
    # leaked token is a way into somebody's consultation until it expires.
    call_token_ttl_seconds: int = 600

    # The join window around an appointment: from EARLY before its start to
    # LATE after its *end*. After the end, not the start, so somebody who drops
    # at minute 30 can still get a fresh token to rejoin. The same boundary is
    # when an unfinished call is closed.
    call_join_early_seconds: int = 600
    call_join_late_seconds: int = 900

    # One party is in the room and the other has been notified. After this
    # long without them the call is MISSED.
    call_ring_timeout_seconds: int = 60

    # WebRTC drops happen. A participant absent for less than this is
    # reconnecting, not gone.
    call_reconnect_grace_seconds: int = 45

    # A hard ceiling on any call, whatever the appointment says. No room is
    # left open indefinitely.
    call_max_duration_seconds: int = 3 * 60 * 60

    # How long LiveKit keeps an empty room before closing it itself. A second
    # line of defence behind the worker, not the primary mechanism.
    call_room_empty_timeout_seconds: int = 300

    # Webhooks are not guaranteed to arrive. A live call nobody has heard about
    # for this long is re-read from the provider.
    call_reconcile_interval_seconds: int = 30

    call_worker_poll_seconds: float = 5.0
    call_worker_idle_log_seconds: float = 300.0

    call_create_rate_limit: str = "20/hour"
    call_join_token_rate_limit: str = "60/hour"
    call_end_rate_limit: str = "30/hour"
    # Webhooks are authenticated by signature; this only bounds the cost of
    # checking signatures on garbage.
    livekit_webhook_rate_limit: str = "600/minute"

    # --- payments: App Store ------------------------------------------
    #
    # Without these the backend boots and `POST /billing/apple/verify` answers
    # `store_provider_not_configured`. The private key signs App Store Server
    # API requests; it is never logged and never returned.
    apple_bundle_id: str | None = None
    # Required by Apple's library to verify production data.
    apple_app_apple_id: int | None = None
    apple_issuer_id: str | None = None
    apple_key_id: str | None = None
    apple_private_key: str | None = None
    apple_private_key_path: Path | None = None
    # "Production" or "Sandbox". Xcode and LocalTesting skip signature
    # verification inside Apple's own library, so they are refused outright.
    apple_environment: Literal["Production", "Sandbox"] = "Production"
    # Directory of Apple root certificates (.cer, DER) from
    # https://www.apple.com/certificateauthority/. Public certificates, not
    # secrets - but they are downloaded by the operator, not committed here.
    apple_root_certificates_path: Path | None = None
    # OCSP revocation checks on the signing chain. Leave on.
    apple_enable_online_checks: bool = True
    # App Review purchases in the sandbox against a production build. Off:
    # a sandbox transaction is never a production entitlement unless this is
    # deliberately enabled, and even then it is recorded as sandbox.
    apple_accept_sandbox_in_production: bool = False

    # --- payments: Google Play -----------------------------------------
    google_play_package_name: str | None = None
    google_play_service_account_json: str | None = None
    google_play_service_account_path: Path | None = None
    # Real-time developer notifications arrive as authenticated Pub/Sub push.
    # The push subscription's audience and signing service account.
    google_pubsub_push_audience: str | None = None
    google_pubsub_push_service_account: str | None = None
    # License-tester purchases in production. Off by default, and recorded as
    # sandbox when on.
    google_accept_test_purchases_in_production: bool = False
    google_play_request_timeout_seconds: float = 10.0

    # "fake" is a test double for both stores, refused in production.
    store_provider: Literal["real", "fake"] = "real"

    # Store product ids, per catalogue code, as JSON:
    #   {"premium_monthly": {"apple": "...", "google": "..."}, ...}
    # Product ids are Play Console / App Store Connect decisions, so they are
    # configuration, not code. A code with no id is not sold on that store.
    store_product_ids: str | None = None

    # --- payments: external marketplace --------------------------------
    #
    # For live 1:1 expert sessions only. No provider has been chosen, so the
    # default is "disabled" and checkout answers
    # `external_payment_provider_not_configured`. "fake" is for tests and is
    # refused in production.
    external_payment_provider: Literal["disabled", "fake"] = "disabled"
    external_payment_intent_ttl_seconds: int = 30 * 60

    # --- settlement -----------------------------------------------------
    #
    # Days after a consultation completes before the expert's share becomes
    # available. No default: this is a business decision, and until it is
    # made nothing is released automatically (an administrator can still
    # release by hand).
    expert_settlement_hold_days: int | None = None

    # --- entitlements -----------------------------------------------------
    #
    # Whether a subscription in the store's grace period keeps premium. Both
    # stores intend grace as "the user keeps access while payment is retried",
    # so the default follows them.
    premium_during_grace_period: bool = True
    # Whether an active premium subscription includes the reports that are
    # otherwise sold as credits (natal, synastry, yearly). No product decision
    # says it does, so the default fails closed: those reports need a credit.
    paid_reports_included_in_premium: bool = False
    # Server-side premium feature gating (see app/services/features.py).
    # On by default and required on in production; a local environment with
    # no store products can switch it off to exercise every screen.
    premium_gating_enabled: bool = True
    # Premium quotas. None means "same as free" - the product has not decided
    # the numbers, and the seam must not invent them.
    ai_chat_rate_limit_premium: str | None = None
    ai_report_rate_limit_premium: str | None = None

    billing_verify_rate_limit: str = "30/hour"
    billing_reconcile_rate_limit: str = "10/hour"
    external_payment_create_rate_limit: str = "10/hour"
    refund_request_rate_limit: str = "5/hour"
    store_webhook_rate_limit: str = "600/minute"

    # --- geocoding ----------------------------------------------------
    geocoding_provider: Literal["mock", "nominatim"] = "mock"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "astrofrekans-backend"

    @model_validator(mode="after")
    def _call_push_timing(self) -> "Settings":
        """provider send timeout + margin <= call push lease < ring timeout.

        Refused at startup rather than repaired: silently falling back to a
        longer lease would let a crashed worker's ring outlive the call.
        """
        margin = CALL_PUSH_LEASE_MARGIN_SECONDS
        if self.apns_timeout_seconds > self.call_push_send_timeout_seconds:
            raise ValueError(
                "APNS_TIMEOUT_SECONDS must not exceed CALL_PUSH_SEND_TIMEOUT_SECONDS"
            )
        if self.call_push_lease_seconds < self.call_push_send_timeout_seconds + margin:
            raise ValueError(
                "CALL_PUSH_LEASE_SECONDS must exceed CALL_PUSH_SEND_TIMEOUT_SECONDS "
                f"by at least {margin} s, or a worker still waiting for the provider "
                "loses its claim to another"
            )
        if self.call_push_lease_seconds >= self.call_ring_timeout_seconds:
            raise ValueError(
                "CALL_PUSH_LEASE_SECONDS must be shorter than CALL_RING_TIMEOUT_SECONDS, "
                "or a crashed worker's ring is recovered only after the call was missed"
            )
        return self

    @field_validator("jwt_secret", "jwt_refresh_secret")
    @classmethod
    def _reject_default_secrets_in_production(cls, value: str, info) -> str:
        return value

    @property
    def ai_configured(self) -> bool:
        """The AI layer is usable when a provider is actually available.

        A missing key must not crash the app: the rest of the backend keeps
        working and the AI endpoints answer ``ai_not_configured``.
        """
        if self.ai_provider == "fake":
            return True
        return bool(self.openai_api_key)

    @property
    def firebase_configured(self) -> bool:
        """Whether the Firebase-backed features can run.

        A missing service account is a degraded feature set, not a broken
        backend: everything that does not need Firebase keeps working and the
        rest answers `firebase_not_configured`.
        """
        if self.firebase_provider == "fake":
            return True
        if not self.firebase_project_id:
            return False
        return bool(self.firebase_credentials_json or self.firebase_credentials_path)

    @property
    def calls_configured(self) -> bool:
        """Whether voice and video calls can run.

        All three LiveKit values or none: a URL without a secret cannot sign a
        token, and a secret without a URL has nowhere to send the client.
        """
        if self.realtime_provider == "fake":
            return True
        return bool(
            self.livekit_url and self.livekit_api_key and self.livekit_api_secret
        )

    @field_validator(
        "apple_app_apple_id",
        "apple_private_key_path",
        "apple_root_certificates_path",
        "google_play_service_account_path",
        "expert_settlement_hold_days",
        "apns_private_key_path",
        "firebase_credentials_path",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        """`KEY=` in a .env file or compose means "not set", not "".

        Without this an empty `EXPERT_SETTLEMENT_HOLD_DAYS=` fails integer
        parsing and the API refuses to boot, and an empty path becomes
        `Path(".")`, which is truthy.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def apns_configured(self) -> bool:
        """Whether iOS VoIP call pushes can be sent."""
        if self.apns_provider == "fake":
            return True
        return bool(
            self.apns_team_id
            and self.apns_key_id
            and self.apns_bundle_id
            and (self.apns_private_key or self.apns_private_key_path)
        )

    @property
    def apple_configured(self) -> bool:
        """Verification needs the bundle id and Apple's root certificates.

        The App Store Server API (for fetching transactions) additionally needs
        the key triple; without it, client-supplied signed transactions are
        still verifiable.
        """
        if self.store_provider == "fake":
            return True
        return bool(self.apple_bundle_id and self.apple_root_certificates_path)

    @property
    def apple_api_configured(self) -> bool:
        if self.store_provider == "fake":
            return True
        return bool(
            self.apple_configured
            and self.apple_issuer_id
            and self.apple_key_id
            and (self.apple_private_key or self.apple_private_key_path)
        )

    @property
    def google_configured(self) -> bool:
        if self.store_provider == "fake":
            return True
        return bool(
            self.google_play_package_name
            and (
                self.google_play_service_account_json
                or self.google_play_service_account_path
            )
        )

    @property
    def google_rtdn_configured(self) -> bool:
        if self.store_provider == "fake":
            return True
        return bool(
            self.google_configured
            and self.google_pubsub_push_audience
            and self.google_pubsub_push_service_account
        )

    @property
    def livekit_server_url(self) -> str | None:
        return self.livekit_api_url or self.livekit_url

    @property
    def accepts_local_jwt(self) -> bool:
        return self.auth_mode in ("local_jwt", "hybrid")

    @property
    def accepts_firebase_token(self) -> bool:
        return self.auth_mode in ("firebase", "hybrid")

    @property
    def allowed_attachment_mime_types(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.attachment_allowed_mime_types.split(",")
            if item.strip()
        }

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def assert_production_ready(self) -> None:
        """Fail fast instead of booting an insecure production instance."""
        if not self.is_production:
            return
        problems: list[str] = []
        if self.jwt_secret.startswith("dev-only"):
            problems.append("JWT_SECRET is still the development default")
        if self.jwt_refresh_secret.startswith("dev-only"):
            problems.append("JWT_REFRESH_SECRET is still the development default")
        if self.debug:
            problems.append("DEBUG must be false in production")
        if not self.premium_gating_enabled:
            problems.append("PREMIUM_GATING_ENABLED must be true in production")
        if self.auth_mode != "hybrid":
            # Release decision: Firebase accounts and server (local JWT)
            # accounts both sign in.
            problems.append("AUTH_MODE must be hybrid in production")
        if self.ai_provider == "fake":
            problems.append(
                "AI_PROVIDER=fake is a test double and must never run in production"
            )
        if self.firebase_provider == "fake":
            problems.append(
                "FIREBASE_PROVIDER=fake is a test double and must never run in "
                "production"
            )
        if self.realtime_provider == "fake":
            problems.append(
                "REALTIME_PROVIDER=fake is a test double and must never run in "
                "production"
            )
        if self.store_provider == "fake":
            problems.append(
                "STORE_PROVIDER=fake is a test double and must never run in production"
            )
        if self.apns_provider == "fake":
            problems.append(
                "APNS_PROVIDER=fake is a test double and must never run in production"
            )
        if self.external_payment_provider == "fake":
            problems.append(
                "EXTERNAL_PAYMENT_PROVIDER=fake is a test double and must never run in "
                "production"
            )
        if self.mail_provider == "disabled":
            problems.append(
                "MAIL_PROVIDER=disabled prevents password reset for local accounts"
            )
        if self.mail_provider in ("log", "memory"):
            problems.append(
                f"MAIL_PROVIDER={self.mail_provider} is for development and tests "
                "and must never run in production"
            )
        if self.mail_provider == "smtp":
            # Chosen but incomplete: fail loudly now rather than answer 503
            # to every reset request later.
            from app.services.mail.mailer import smtp_config_problems

            problems.extend(smtp_config_problems())
        if not self.password_reset_url_base.startswith("https://"):
            problems.append("PASSWORD_RESET_URL_BASE must be an https URL in production")
        # Store product ids: a typo takes a product off sale, a duplicate makes
        # purchases of it unresolvable, a legacy product must not be sold, and
        # the seven products need ids on every store the server verifies.
        from app.services.payments.catalog import (
            store_catalog_problems,
            store_release_problems,
        )

        problems.extend(store_catalog_problems(self.store_product_ids))
        problems.extend(store_release_problems(self))
        if (self.ad_reward_verifier or "").strip().lower() == "mock":
            problems.append(
                "AD_REWARD_VERIFIER=mock is a test double and must never run in production"
            )
        # A development Firebase project or the emulator suite behind a
        # production API would sign people in to the wrong user base.
        if self.firebase_project_id and _looks_like_dev_project(self.firebase_project_id):
            problems.append(
                f"FIREBASE_PROJECT_ID={self.firebase_project_id} looks like a staging/dev "
                "project; production needs the production Firebase project"
            )
        for name in (
            "firebase_auth_emulator_host",
            "firestore_emulator_host",
            "firebase_database_emulator_host",
            "firebase_storage_emulator_host",
        ):
            if getattr(self, name):
                problems.append(f"{name.upper()} points at the Firebase emulator")
        # Addresses handed to phones or browsers must be public ones.
        client_facing = {
            "PASSWORD_RESET_URL_BASE": [self.password_reset_url_base],
            "LIVEKIT_URL": [self.livekit_url],
            "CORS_ORIGINS": self.cors_origin_list,
            "GOOGLE_PUBSUB_PUSH_AUDIENCE": [self.google_pubsub_push_audience],
        }
        for name, urls in client_facing.items():
            for url in urls:
                if url and _is_local_address(url):
                    problems.append(f"{name} must not point at a local address ({url})")
        if self.apple_bundle_id and self.apple_environment == "Production" and not self.apple_app_apple_id:
            problems.append("APPLE_APP_APPLE_ID is required to verify production App Store data")
        if self.livekit_url and not self.livekit_url.startswith("wss://"):
            # A plain ws:// URL in production sends the join token and the
            # media signalling in the clear.
            problems.append("LIVEKIT_URL must use wss:// in production")
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


_DEV_PROJECT = re.compile(r"(^demo-|staging|(^|[-_])(dev|test|local)([-_]|$))", re.IGNORECASE)
_LOCAL_HOST_NAMES = {"localhost", "host.docker.internal", "10.0.2.2", "10.0.3.2"}


def _looks_like_dev_project(project_id: str) -> bool:
    return bool(_DEV_PROJECT.search(project_id))


def _is_local_address(url: str) -> bool:
    """Loopback, emulator aliases (10.0.2.2), private and link-local ranges,
    and reserved local names - reachable from a developer's machine only."""
    from urllib.parse import urlsplit

    host = (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower()
    if not host:
        return False
    if host in _LOCAL_HOST_NAMES or host.endswith((".localhost", ".local", ".test", ".invalid", ".internal")):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local or address.is_unspecified


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
