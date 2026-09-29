"""What kind of thing is being sold, in store-policy terms - and who may collect it.

Both rules below were read from the stores' own current documents on
**2026-09-24** (`POLICY_LAST_VERIFIED`), not recalled:

* **Apple, App Review Guideline 3.1.1** - unlocking features, content or
  subscriptions in the app must use in-app purchase.
* **Apple, 3.1.3(d) Person-to-Person Services** - "real-time person-to-person
  services between two individuals" may use other purchase methods;
  one-to-few and one-to-many must use in-app purchase.
* **Google Play Payments policy** - digital items, subscriptions and app
  functionality must use Play billing. A "1:1 online paid service" is exempt
  if it is between two individuals **and not available for replay afterwards
  (not recorded)**.

So a live voice or video consultation with an astrologer - two people, real
time, never recorded (B10 holds recording off with a database constraint) - is
person-to-person on both stores. Everything automated is digital. Text chat and
written expert reports are neither clearly: chat is asynchronous and its
history is kept, and a written report is a delivered artefact. They fail
closed: REVIEW_REQUIRED, and no rail collects money for them until somebody
with the authority to read the policy decides.

Policies change. This module is data plus a few rules, so a change is an edit
here and a new `POLICY_LAST_VERIFIED`, not a hunt through checkout code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.marketplace import DeliveryType
from app.domain.payments import ClientPlatform, PaymentClassification, PaymentRail

POLICY_LAST_VERIFIED = "2026-09-24"

POLICY_SOURCES = (
    "Apple App Review Guidelines 3.1.1, 3.1.3(d) - "
    "https://developer.apple.com/app-store/review/guidelines/",
    "Google Play Payments policy - "
    "https://support.google.com/googleplay/android-developer/answer/9858738",
    "Understanding Google Play's Payments policy (1:1 online paid services) - "
    "https://support.google.com/googleplay/android-developer/answer/10281818",
)

LIVE_CHANNELS = frozenset({DeliveryType.VOICE.value, DeliveryType.VIDEO.value})


def live_sessions_replayable() -> bool:
    """Whether a live expert session could be replayed afterwards.

    Read from the schema, not from a flag: B10 holds
    `call_sessions.recording_enabled` at false with a check constraint. If that
    constraint is ever removed to allow recording, this returns True and every
    live session becomes REVIEW_REQUIRED - Google's exemption depends on
    "not available for replay", and it must not survive recording by accident.
    """
    from app.db.models.calls import CallSession

    names = {
        constraint.name for constraint in CallSession.__table__.constraints
    }
    return "ck_call_sessions_no_recording" not in names


@dataclass(slots=True, frozen=True)
class Classification:
    value: PaymentClassification
    basis: str  # machine-readable reason, for docs, audit and support


class PaymentClassificationService:
    """The one place that decides a line item's classification."""

    def classify_expert_session(
        self,
        delivery_type: str | None,
        *,
        amount_minor: int,
        participants: int = 2,
        replayable: bool | None = None,
    ) -> Classification:
        if amount_minor == 0:
            return Classification(PaymentClassification.FREE, "free")
        if participants != 2:
            # One-to-few and one-to-many are in-app purchase on Apple, and
            # outside Google's 1:1 exemption.
            return Classification(PaymentClassification.REVIEW_REQUIRED, "not_one_to_one")
        if replayable if replayable is not None else live_sessions_replayable():
            return Classification(PaymentClassification.REVIEW_REQUIRED, "replayable")
        if delivery_type in LIVE_CHANNELS:
            return Classification(
                PaymentClassification.LIVE_PERSON_TO_PERSON, f"live_{delivery_type}_1to1"
            )
        if delivery_type == DeliveryType.CHAT.value:
            return Classification(
                PaymentClassification.REVIEW_REQUIRED, "chat_is_async_and_persistent"
            )
        if delivery_type == DeliveryType.WRITTEN_REPORT.value:
            return Classification(
                PaymentClassification.REVIEW_REQUIRED, "written_report_is_delivered_content"
            )
        return Classification(PaymentClassification.REVIEW_REQUIRED, "unknown_channel")

    def classify_digital(self, *, amount_minor: int | None = None) -> Classification:
        """Automated reports, AI interpretations, readings, subscriptions."""
        if amount_minor == 0:
            return Classification(PaymentClassification.FREE, "free")
        return Classification(PaymentClassification.DIGITAL_STORE, "digital_in_app")


class PaymentRouter:
    """Classification + platform (+ storefront) -> the rail that may collect.

    Region-specific alternative-billing programmes (store-approved external
    payment for digital goods in some countries) are **not** assumed. They are
    opt-in programmes with their own terms; supporting one is a new entry in
    `ALTERNATIVE_PROGRAMMES`, keyed by store and storefront, after the terms
    have been accepted - never a general permission.
    """

    ALTERNATIVE_PROGRAMMES: dict[tuple[PaymentRail, str], PaymentRail] = {}

    def route(
        self,
        classification: PaymentClassification,
        platform: ClientPlatform | None,
        *,
        storefront: str | None = None,
    ) -> PaymentRail:
        if classification is PaymentClassification.LIVE_PERSON_TO_PERSON:
            return PaymentRail.EXTERNAL_MARKETPLACE
        if classification is PaymentClassification.DIGITAL_STORE:
            if platform is ClientPlatform.IOS:
                rail = PaymentRail.APPLE_STORE
            elif platform is ClientPlatform.ANDROID:
                rail = PaymentRail.GOOGLE_PLAY
            else:
                # There is no web store. Digital goods on the web would need a
                # decision of their own.
                return PaymentRail.NONE
            if storefront:
                return self.ALTERNATIVE_PROGRAMMES.get((rail, storefront.upper()), rail)
            return rail
        # REVIEW_REQUIRED and FREE: nobody collects.
        return PaymentRail.NONE


@dataclass(slots=True, frozen=True)
class PolicyRow:
    service: str
    classification: str
    ios_rail: str
    android_rail: str
    reason: str
    review_required: bool


POLICY_MATRIX: tuple[PolicyRow, ...] = (
    PolicyRow("Premium subscription", "digital_store", "StoreKit", "Play Billing",
              "subscription unlocking app functionality (Apple 3.1.1, Google: subscriptions)", False),
    PolicyRow("Automated natal / transit / forecast report", "digital_store", "StoreKit", "Play Billing",
              "digital content generated and consumed in the app", False),
    PolicyRow("AI synastry / horary / tarot / rune / katina interpretation", "digital_store",
              "StoreKit", "Play Billing", "digital content generated and consumed in the app", False),
    PolicyRow("Live 1:1 voice consultation (not recorded)", "live_person_to_person",
              "external eligible", "external eligible",
              "real-time, two individuals, no replay (Apple 3.1.3(d); Google 1:1 exemption)", False),
    PolicyRow("Live 1:1 video consultation (not recorded)", "live_person_to_person",
              "external eligible", "external eligible",
              "real-time, two individuals, no replay (Apple 3.1.3(d); Google 1:1 exemption)", False),
    PolicyRow("Expert text chat", "review_required", "TBD", "TBD",
              "asynchronous and its history persists: not clearly real-time or non-replayable", True),
    PolicyRow("Written expert report", "review_required", "TBD", "TBD",
              "a delivered artefact, re-readable: not a real-time service", True),
    PolicyRow("Hybrid: AI pre-analysis + live video", "split", "StoreKit + external",
              "Play Billing + external",
              "two line items, two classifications; the digital part is never paid externally", True),
    PolicyRow("Any live session if recording is enabled", "review_required", "TBD", "TBD",
              "replay breaks Google's 1:1 exemption; classification flips automatically", True),
)
