# B12C backend contract issues

Backend and assets were read-only throughout B12C. No backend contract was changed.

| Severity | Contract | Flutter impact | Recommended backend-owned resolution |
| --- | --- | --- | --- |
| HIGH | `POST /ai/reports` accepts `report_type`, `source_id`, `locale`, `refresh`, `background` but no verified credit/`consumer_ref`; `POST /billing/credits/consume` is a separate call. | Flutter can require a verified credit before invoking report creation and consume with the returned report ID, but this is not an atomic payment boundary. The existing report-creation route remains callable without paying. A network failure between creation and consumption can leave a generated report uncharged. | Link report creation to a verified credit and stable consumer reference in one backend-owned idempotent transaction, or make report delivery conditional on a consumed credit. Do not rely on Flutter gating. |
| MEDIUM | `CallSummary` has `order_id` and `my_role`, but no expert display name. | History performs an extra order lookup per visible call and falls back to “Uzman” if unavailable. | Optionally include a safe display-name snapshot in the call summary, or provide a batched order-display endpoint. No Flutter/backend field mismatch; this is a payload-efficiency gap. |
| LOW | Store restoration callbacks arrive asynchronously; B11 accepts at most 20 proofs per platform in one reconcile request. | Flutter now batches over 20 proofs, but the two-second restore snapshot may still omit a late callback. Late callbacks pass through per-purchase verification. | If full restore completion must be synchronized, expose/define a provider completion signal; avoid treating a timed snapshot as exhaustive. |

`presenceVisibility/{targetUid}/{readerUid}/{conversationId}` is frozen and not changed here.
