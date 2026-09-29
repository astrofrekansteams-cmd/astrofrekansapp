"""The digital product catalogue.

Codes and what they unlock are code; store product ids are configuration
(`STORE_PRODUCT_IDS`), because they are App Store Connect / Play Console
decisions. Prices are neither: the stores own them.

Entitlement codes are few and plain. Credits are one unit per purchase of a
consumable, used once. AstroCoin packs are consumables too, but what they
grant is a balance in the coin ledger (`app/services/coins`), written once per
verified purchase - never by the client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.payments import StoreProduct
from app.domain.payments import ClientPlatform, StoreProductType

logger = get_logger(__name__)

PREMIUM = "premium"
COSMIC_PLUS = "cosmic_plus"
COINS = "astro_coins"

# Subscription entitlement codes, lowest plan first.
PLAN_ENTITLEMENTS: tuple[str, ...] = (PREMIUM, COSMIC_PLUS)


@dataclass(slots=True, frozen=True)
class ProductDefinition:
    code: str
    product_type: StoreProductType
    entitlement_code: str
    service_code: str | None = None
    units_per_purchase: int = 1
    # AstroCoins credited per purchase (coin packs only).
    coins: int = 0
    # Sold in the App Store / Google Play. Legacy one-off reports are not:
    # they are reached through AstroCoin and the plans. Their definitions stay
    # so past records still resolve, but they never get a store id.
    sellable: bool = True


CATALOG: tuple[ProductDefinition, ...] = (
    ProductDefinition("premium_monthly", StoreProductType.SUBSCRIPTION, PREMIUM),
    ProductDefinition("premium_yearly", StoreProductType.SUBSCRIPTION, PREMIUM),
    ProductDefinition("cosmic_plus_monthly", StoreProductType.SUBSCRIPTION, COSMIC_PLUS),
    ProductDefinition("cosmic_plus_yearly", StoreProductType.SUBSCRIPTION, COSMIC_PLUS),
    # AstroCoin packs. Prices are the stores'; the amounts are ours.
    ProductDefinition("coins_120", StoreProductType.CONSUMABLE, COINS, coins=120),
    ProductDefinition("coins_350", StoreProductType.CONSUMABLE, COINS, coins=350),
    ProductDefinition("coins_800", StoreProductType.CONSUMABLE, COINS, coins=800),
    # Legacy - not sold in the stores (see `sellable`).
    ProductDefinition(
        "natal_report", StoreProductType.CONSUMABLE, "natal_report_credit",
        service_code="natal_chart_analysis", sellable=False,
    ),
    ProductDefinition(
        "synastry_report", StoreProductType.CONSUMABLE, "synastry_report_credit",
        service_code="synastry", sellable=False,
    ),
    ProductDefinition(
        "annual_forecast_report", StoreProductType.CONSUMABLE, "annual_forecast_credit",
        service_code="annual_forecast", sellable=False,
    ),
    # The digital half of a hybrid consultation. Not sold in the stores, so a
    # hybrid order simply does not include it.
    ProductDefinition(
        "ai_pre_analysis", StoreProductType.CONSUMABLE, "pre_analysis_credit",
        sellable=False,
    ),
)

# What the stores sell: four subscriptions and three AstroCoin packs.
SELLABLE_CODES: tuple[str, ...] = tuple(d.code for d in CATALOG if d.sellable)
LEGACY_CODES: tuple[str, ...] = tuple(d.code for d in CATALOG if not d.sellable)


def configured_ids() -> dict[str, dict[str, str]]:
    if not settings.store_product_ids:
        return {}
    try:
        data = json.loads(settings.store_product_ids)
    except json.JSONDecodeError:
        logger.warning("store_product_ids_invalid")
        return {}
    if not isinstance(data, dict):
        logger.warning("store_product_ids_invalid")
        return {}
    return {str(code): dict(ids) for code, ids in data.items() if isinstance(ids, dict)}


def store_catalog_problems(raw: str | None = None) -> list[str]:
    """What is wrong with `STORE_PRODUCT_IDS`, in words. Empty: fine.

    Checked at production start. A typo in a code silently takes a product
    off sale; one store id under two codes makes that store's purchases of it
    unresolvable (which code was bought?). Google subscriptions are matched by
    product id alone, so each code needs its own Play subscription product.
    """
    raw = settings.store_product_ids if raw is None else raw
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ["STORE_PRODUCT_IDS is not valid JSON"]
    if not isinstance(data, dict):
        return ["STORE_PRODUCT_IDS must be a JSON object of code -> {apple, google}"]
    known = {d.code for d in CATALOG}
    problems: list[str] = []
    seen: dict[tuple[str, str], str] = {}
    for code, ids in data.items():
        if code not in known:
            problems.append(f"STORE_PRODUCT_IDS: unknown product code {code!r}")
            continue
        if not isinstance(ids, dict):
            problems.append(f"STORE_PRODUCT_IDS: {code} must map to {{apple, google}}")
            continue
        if code in LEGACY_CODES and any(
            isinstance(v, str) and v.strip() for v in ids.values()
        ):
            problems.append(
                f"STORE_PRODUCT_IDS: {code} is a legacy product and is not sold in "
                "the stores; remove its id"
            )
            continue
        for store, product_id in ids.items():
            if store not in ("apple", "google"):
                problems.append(f"STORE_PRODUCT_IDS: {code} has unknown store {store!r}")
                continue
            if not isinstance(product_id, str) or not product_id.strip():
                continue
            other = seen.setdefault((store, product_id), code)
            if other != code:
                problems.append(
                    f"STORE_PRODUCT_IDS: {store} id {product_id!r} is used by both {other} and {code}"
                )
    return problems


def store_release_problems(config=None) -> list[str]:  # noqa: ANN001 - Settings
    """Production only: can the stores actually sell the seven products?

    Empty ids mean nothing can be bought; ids for a store whose purchases the
    server cannot verify mean every purchase would fail after payment; a store
    that is configured but lacks an id for one of the seven sells an
    incomplete catalogue.
    """
    config = config or settings
    ids = _parse_ids(config.store_product_ids)
    if not ids:
        return [
            "STORE_PRODUCT_IDS is empty: no subscription or AstroCoin pack can be sold. "
            "Map " + ", ".join(SELLABLE_CODES) + " to their App Store / Google Play ids"
        ]
    problems: list[str] = []
    for store, configured, name in (
        ("google", config.google_configured, "Google Play (GOOGLE_PLAY_PACKAGE_NAME + service account)"),
        ("apple", config.apple_configured, "App Store (APPLE_BUNDLE_ID + root certificates)"),
    ):
        mapped = [c for c in SELLABLE_CODES if (ids.get(c) or {}).get(store)]
        if mapped and not configured:
            problems.append(
                f"STORE_PRODUCT_IDS has {store} ids but {name} verification is not configured"
            )
        if configured:
            missing = [c for c in SELLABLE_CODES if not (ids.get(c) or {}).get(store)]
            if missing:
                problems.append(f"STORE_PRODUCT_IDS: no {store} id for " + ", ".join(missing))
    return problems


def _parse_ids(raw: str | None) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
    return {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


class StoreCatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._synced = False

    async def sync(self) -> None:
        """Make the table match the definitions and configured ids. Idempotent.

        In a savepoint: two first requests racing to insert the same code is
        harmless - the loser finds the rows the winner wrote. Once per service
        instance (so once per request): configuration does not change mid-way.
        """
        if self._synced:
            return
        self._synced = True
        try:
            async with self.session.begin_nested():
                await self._sync()
        except IntegrityError:
            logger.info("store_catalog_sync_raced")

    async def _sync(self) -> None:
        ids = configured_ids()
        existing = {
            row.code: row for row in await self.session.scalars(select(StoreProduct))
        }
        for definition in CATALOG:
            mapped = ids.get(definition.code, {})
            row = existing.get(definition.code)
            if row is None:
                row = StoreProduct(code=definition.code)
                self.session.add(row)
            row.product_type = definition.product_type.value
            row.entitlement_code = definition.entitlement_code
            row.service_code = definition.service_code
            row.units_per_purchase = definition.units_per_purchase
            if definition.sellable:
                row.apple_product_id = mapped.get("apple") or None
                row.google_product_id = mapped.get("google") or None
                row.active = True
            else:
                # Never offered, whatever the configuration says (production
                # refuses such a configuration at start).
                if mapped:
                    logger.warning("store_product_id_ignored_for_legacy", code=definition.code)
                row.apple_product_id = None
                row.google_product_id = None
                row.active = False
        # A code removed from the catalogue is no longer sold. Its row stays
        # (past purchases point at it) but it is not offered any more.
        defined = {d.code for d in CATALOG}
        for code, row in existing.items():
            if code not in defined:
                row.active = False
        await self.session.flush()

    @staticmethod
    def definition(code: str) -> ProductDefinition | None:
        return next((d for d in CATALOG if d.code == code), None)

    async def for_platform(self, platform: ClientPlatform) -> list[StoreProduct]:
        """Active products that have an id on this platform's store."""
        await self.sync()
        column = (
            StoreProduct.apple_product_id
            if platform is ClientPlatform.IOS
            else StoreProduct.google_product_id
        )
        return list(
            await self.session.scalars(
                select(StoreProduct)
                .where(StoreProduct.active.is_(True), column.is_not(None))
                .order_by(StoreProduct.code)
            )
        )

    async def by_code(self, code: str) -> StoreProduct | None:
        await self.sync()
        return await self.session.scalar(
            select(StoreProduct).where(StoreProduct.code == code, StoreProduct.active.is_(True))
        )

    async def by_store_ref(self, provider: str, product_ref: str) -> StoreProduct | None:
        await self.sync()
        column = (
            StoreProduct.apple_product_id if provider == "apple" else StoreProduct.google_product_id
        )
        return await self.session.scalar(select(StoreProduct).where(column == product_ref))
