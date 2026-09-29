# Marketplace settlement: commission, ledger, payouts

## Commission

The B8 order snapshot is reused unchanged: `commission_basis_points`,
`platform_fee_minor`, `expert_net_minor`, computed at order time with
rounding that favours the expert (`999` minor at `2000` bp → platform `199`,
expert `800`). It is attributed to the live session line item only.

Store fees are **not** platform commission. Apple's and Google's cut is not
posted: it is not known per transaction and is not guessed from a published
rate. A provider fee is recorded (`provider_fee_minor`) only if the provider
reports it.

Digital store revenue is the platform's. A StoreKit or Play purchase never
credits an expert.

## Ledger

Double-entry, per currency, immutable.

| Account | Kind | Meaning |
|---|---|---|
| `store_clearing` | asset | owed to us by a store |
| `external_provider_clearing` | asset | held for us by the external provider |
| `platform_receivable` | asset | owed to us, not collected |
| `platform_revenue` | revenue | commission, digital sales |
| `expert_payable_pending` | liability | an expert's share, on hold |
| `expert_payable_available` | liability | an expert's share, releasable |
| `refund_liability` | liability | refunds approved, not yet paid out |

Journals:

| Journal | Lines |
|---|---|
| `store_charge:<txn>` | Dr store_clearing / Cr platform_revenue |
| `charge:<txn>` (live 1:1) | Dr external_provider_clearing gross / Cr platform_revenue fee / Cr expert_payable_pending net |
| `release:<order>:<ccy>` | Dr expert_payable_pending / Cr expert_payable_available |
| `payout:<id>` | Dr expert_payable_available / Cr external_provider_clearing |
| `refund:<id>`, `chargeback:<evt>` | reverse of the charge, proportional |
| `store_refund:<txn>` | Dr platform_revenue / Cr store_clearing |

Guarantees:

* **Balanced:** the service refuses an unbalanced journal; on Postgres a
  `DEFERRABLE INITIALLY DEFERRED` constraint trigger refuses to commit one.
* **Immutable:** a Postgres trigger refuses any UPDATE of a money column and
  any DELETE on `ledger_entries` and `payment_transactions`. A refund is a new
  row. (Foreign keys may still be nulled, so deleting a user is not blocked.)
* **Idempotent:** `journal_key` + `line_no` is unique; a replayed event posts
  nothing.
* **No floats, no cross-currency netting.**

All three database guarantees were exercised against Postgres.

## Settlement

A verified live-session payment credits `expert_payable_pending`. It moves to
`expert_payable_available` when the order is **COMPLETED** and
`EXPERT_SETTLEMENT_HOLD_DAYS` have passed.

**The hold has no default.** It is a business decision (refund and chargeback
windows, provider rules). Until it is set, nothing is released automatically;
an administrator can release by hand (`SettlementService.release_order(force=True)`).

Release runs when an order completes and whenever an expert reads
`GET /expert/earnings`; it is idempotent per `(order, currency)`.

## Balances

`GET /expert/earnings` → per currency: `pending`, `available`, `paid`, derived
from the ledger - never stored.

**`available` may be negative.** A refund or chargeback after release takes
the expert's share back from `available`; if it was already paid out, the
balance goes below zero and the expert's future earnings net it off. No debt
collection exists and none is attempted.

## Payouts

`expert_payouts`: `pending → approved → processing → paid | failed`, or
`cancelled`. Transitions are a table (`PAYOUT_TRANSITIONS`).

* An expert can **see** their payouts (`GET /expert/payouts`). They cannot
  create, approve or mark one paid - there is no route that does.
* An administrator (service methods only; there is no admin surface yet)
  creates a payout up to the available balance (serialised per expert),
  approves it, and marks it paid or failed once a provider or bank confirms.
* Only `paid` posts to the ledger.
* **No payout provider exists. No money is sent automatically.**

## Refunds

See [refunds.md](refunds.md).
