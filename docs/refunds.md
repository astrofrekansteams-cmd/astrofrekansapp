# Refunds

Three layers, deliberately separate:

1. **`RefundPolicy`** reads evidence and advises: `AUTO`, `MANUAL_REVIEW` or
   `NOT_ELIGIBLE`. It moves no money and invents no percentage.
2. **`RefundService`** records requests, checks amounts, and - on an
   administrator's approval - asks the provider to refund.
3. **The ledger** records what moved.

## Reasons

`user_cancellation`, `expert_cancellation`, `no_show`, `technical_failure`,
`duplicate`, `fraud`, `goodwill`, `store_reversal`.

## What the policy decides

| Situation | Decision | Basis recorded |
|---|---|---|
| order not paid | `NOT_ELIGIBLE` | `not_paid` |
| the store already refunded | `AUTO` | `store_already_refunded` |
| technical failure, B10 shows `provider_error` / `network_disconnect` | `MANUAL_REVIEW` | `technical_evidence:<reasons>` |
| no-show | `MANUAL_REVIEW` | `no_show:<who>` |
| cancellation | `MANUAL_REVIEW` | `cancelled_by:<who>` |
| anything else | `MANUAL_REVIEW` | the reason |

Nobody has decided that a technical failure is worth 100% or a no-show 0%. So
those are `MANUAL_REVIEW` with the evidence attached, not a hardcoded
percentage. B10's call end reasons are evidence, not a verdict.

## Requests

`POST /orders/{id}/refund-requests` `{reason, amount_minor?, idempotency_key}`
- the order's owner only (404 otherwise), rate-limited (`refund_request`).
Omitting `amount_minor` asks for everything refundable.

Amount safety: `0 < amount <= amount paid - refunded - pending requests`,
integers only, with the payment intent's row locked. A check constraint
(`refunded_minor <= amount_minor`) stops concurrent approvals from refunding
more than was paid. Proven on Postgres: one refund approved five times at
once → one provider refund, one reversal.

## Cancelling a paid order

The money is not forgotten. `payment_status` becomes `refund_pending` and a
refund request waits for review. It becomes `refunded` only when a provider
says the money moved.

## Approval (administrator)

`RefundService.approve(refund_id, reviewer, provider)` - no route. Calls the
provider's `refund()`; with no provider configured, that raises
`external_payment_provider_not_configured`. On success: a `refund` or
`partial_refund` transaction pointing at the charge, a proportional ledger
reversal, `payment_status` `partially_refunded` / `refunded`, and a
`refund_processed` push (generic text, no amount).

## Proportional reversal

The expert's share of a refund is computed on the running total
(`split_proportionally`), so refunding a charge in parts reverses its split
**exactly** once it is fully refunded - the parts cannot drift by a rounding
cent. Tested: 999 refunded as 333 + 666 leaves platform, expert and clearing
balances at exactly zero.

## Store refunds

Apple `REFUND` / `REVOKE` notifications and Google voided-purchase
notifications revoke the purchase and its entitlement (unused credits
revoked; used credits stay used), record a `refund` transaction, reverse the
store revenue, and push `refund_processed`. Premium access ends; the user
does not keep it indefinitely.

## Chargebacks

A provider `chargeback` event records a `chargeback` transaction and the same
proportional reversal. The expert's share comes back from wherever it sits;
`available` may go negative. No collection process exists.
