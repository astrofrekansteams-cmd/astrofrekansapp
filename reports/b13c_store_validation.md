# B13C store validation — 2026-09-25

**Store recommendation: NOT READY FOR SUBMISSION.** No App Store Connect, Play Console, sandbox/test-track, signing or physical-device access was available in this session. Nothing was uploaded, purchased, restored, refunded or submitted. Store account existence outside this workspace remains **unverified**, not presumed absent.

## Apple StoreKit / App Store

| Test | Status | Evidence / closing prerequisite |
| --- | --- | --- |
| App record, matching bundle ID, sandbox tester | BLOCKED | Source bundle ID `com.astrofrekans.astrofrekans`; account record/tester not accessible |
| Signed IPA, Push capability/profile | BLOCKED | No Codemagic/macOS run, certificate/profile or IPA |
| Product discovery: Premium monthly/yearly and report credit | BLOCKED | No App Store Connect product configuration or signed app |
| Sandbox purchase and Apple server verification | BLOCKED | No signed build, sandbox tester or backend Store API credentials |
| Store callback alone remains locked; verified entitlement unlocks | PASS host / BLOCKED sandbox | Existing Flutter fake regression passed in 141-test suite; no real StoreKit/Apple-server run |
| Restore on reinstall/second session | BLOCKED | No sandbox purchase or signed iPhone build |
| Refund/revoke removes entitlement | BLOCKED | No Apple server notifications/sandbox transaction |

## Google Play Billing / Play Console

| Test | Status | Evidence / closing prerequisite |
| --- | --- | --- |
| App record, package ID, license tester, internal/test track | BLOCKED | Source application ID `com.astrofrekans.astrofrekans`; account/tester/track not accessible |
| Signed AAB and catalog product discovery | BLOCKED | Android SDK, upload keystore, Firebase config and AAB absent |
| Purchase, pending state, backend Developer API verification | BLOCKED | No Play test-track build/tester/service account |
| Pending or callback alone locked; verified entitlement unlocks | PASS host / BLOCKED Play | Existing fake callback/pending regression passed; no real Play purchase |
| Restore on reinstall/second device | BLOCKED | No test-track purchase/device |
| Refund/revoke removes entitlement | BLOCKED | No Play RTDN/PubSub or live transaction |

## Paid report and expert-payment rails

| Test | Status | Evidence / closing prerequisite |
| --- | --- | --- |
| Real verified credit purchase → `POST /ai/reports` | BLOCKED | Apple/Google store and OpenAI provider not configured |
| Same `consumer_ref` request/network retry → one logical report/credit | PASS host / BLOCKED real | B13B Flutter contract tests passed; real backend/store/OpenAI transaction not executed |
| 202 job polling and report delivery | PASS host contract / BLOCKED real | Fake 202 routing/contract proof only |
| External expert PSP | BLOCKED by product decision | B13A provider remains `disabled`; no false paid order claimed |
| `REVIEW_REQUIRED` bypass | NOT RUN live | No real store/order flow; B13B backend/Flutter policy remains source-level only |

## Listing and policy evidence still needed

| Item | Status | Owner/evidence needed |
| --- | --- | --- |
| App Store and Play screenshots | MISSING | Product/mobile QA: real signed-build screenshots for target devices/languages |
| Privacy policy and support URLs | MISSING/UNVERIFIED | Product/legal: published URLs, ownership and contact channel |
| Age rating, review notes, test account | MISSING/UNVERIFIED | Product/store operator: truthful questionnaire and reviewer access |
| Subscription metadata, pricing, terms, product IDs | MISSING/UNVERIFIED | Store operator: finalized monthly/yearly and credit SKUs, territories, prices, renewal/restore terms; compare backend catalog |
| App Store Privacy / Play Data Safety answers | BLOCKED | Product/legal: confirm real processors, purposes, retention, deletion/export, sharing and regions before filing |

## Data-flow inventory for privacy questionnaires

This is a **source/contract inventory**, not a claim that any external provider is live or a final legal disclosure. B13B's `b13b_flutter_release_validation.md` contains the earlier inventory. Each row needs product/legal and actual-service confirmation before the App Store Privacy or Play Data Safety form can be finalized.

| Data | Intended destination from code/contracts | B13C live confirmation | Open disclosure decision |
| --- | --- | --- | --- |
| Account/email and birth date/time/place/coordinates | FastAPI/PostgreSQL; secure local profile cache; astrology calculations | Local backend health only, no real Firebase/device flow | Retention, deletion/export, chart sharing, location precision |
| Horary questions and AI prompts/reports | FastAPI; OpenAI provider when configured | OpenAI absent | Sensitive free text, processor/region, model retention and user notice |
| Expert chat text/conversation IDs | Backend message POST → Firestore projection/listener | Firebase absent | Participant visibility, moderation, retention and deletion |
| Chat images | Backend upload intent/finalize → Firebase Storage | Firebase absent | MIME/size, region, expiry/deletion and public access policy |
| Call metadata and media | FastAPI lifecycle → LiveKit/TURN when configured | LiveKit absent | Media provider/region, recording policy, logs and retention |
| FCM/VoIP tokens | Device SDK → backend registration → FCM/APNs | Firebase/APNs absent | Push consent, token rotation and deletion |
| Purchase tokens/Apple JWS, product and account mapping | StoreKit/Play → FastAPI → Apple/Google verification | Both stores absent | Payment processor data, refunds and account linkage |
| Paid-report `consumer_ref` | Secure local store → FastAPI report idempotency | Host test only | Attempt retention/cleanup |

Release artifacts: **AAB none, IPA none**. Artifact path, size, build number and signing status: **N/A**. No store listing was submitted.
