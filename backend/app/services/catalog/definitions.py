"""The service catalogue, as data.

Every row says what the service is, who can deliver it (automated engine,
a real astrologer, or both in a hybrid consultation) and what input it needs
before an order can be created. Seeding is idempotent, so this file is the
source of truth and ``scripts/seed_services.py`` can be re-run after every
deploy.

Prices are deliberately absent: automated services are gated by subscription
tier, and expert prices belong to each expert (phase B8).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.marketplace import FulfillmentMode, ServiceCategory, ServiceCode

AUTOMATED = FulfillmentMode.AUTOMATED
EXPERT = FulfillmentMode.EXPERT
HYBRID = FulfillmentMode.HYBRID


@dataclass(slots=True, frozen=True)
class ServiceSpec:
    code: ServiceCode
    name: str
    name_tr: str
    category: ServiceCategory
    fulfillment_modes: tuple[FulfillmentMode, ...]
    description: str = ""
    estimated_duration_minutes: int | None = None
    requires_birth_data: bool = True
    requires_partner_data: bool = False
    requires_question: bool = False
    supports_chat: bool = False
    supports_voice: bool = False
    supports_video: bool = False
    supports_appointment: bool = False
    supports_automated_report: bool = False
    requires_premium: bool = False
    active: bool = True
    sort_order: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)


def _consultation(**overrides) -> dict:
    """Defaults for anything an expert can deliver live."""
    base = {
        "supports_chat": True,
        "supports_voice": True,
        "supports_video": True,
        "supports_appointment": True,
    }
    base.update(overrides)
    return base


CATALOG: tuple[ServiceSpec, ...] = (
    # ------------------------------------------------------------- natal
    ServiceSpec(
        code=ServiceCode.NATAL_CHART_ANALYSIS,
        name="Natal Chart Analysis",
        name_tr="Doğum Haritası Analizi",
        category=ServiceCategory.NATAL,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        description=(
            "Full natal chart: planets, houses, angles, aspects and the "
            "interpretation built on them."
        ),
        estimated_duration_minutes=45,
        supports_automated_report=True,
        sort_order=10,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.KARMIC_ANALYSIS,
        name="Karmic Analysis",
        name_tr="Karmik Analiz",
        category=ServiceCategory.NATAL,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=45,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=20,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.LUNAR_NODES_ANALYSIS,
        name="Lunar Nodes Analysis",
        name_tr="Ay Düğümleri Analizi",
        category=ServiceCategory.NATAL,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=30,
        supports_automated_report=True,
        sort_order=30,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.CAREER_ANALYSIS,
        name="Career Analysis",
        name_tr="Kariyer Analizi",
        category=ServiceCategory.NATAL,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=45,
        supports_automated_report=True,
        sort_order=40,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.LOVE_ANALYSIS,
        name="Love and Relationship Analysis",
        name_tr="Aşk ve İlişki Analizi",
        category=ServiceCategory.NATAL,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=45,
        supports_automated_report=True,
        sort_order=50,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.FINANCIAL_ANALYSIS,
        name="Financial Astrology Reading",
        name_tr="Finansal Astroloji Yorumu",
        category=ServiceCategory.NATAL,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        description=(
            "Astrological commentary on the money houses. Guidance for "
            "reflection, never investment advice."
        ),
        estimated_duration_minutes=45,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=60,
        **_consultation(),
    ),
    # ---------------------------------------------------------- forecast
    ServiceSpec(
        code=ServiceCode.DAILY_HOROSCOPE,
        name="Personalised Daily Horoscope",
        name_tr="Günlük Kişisel Horoskop",
        category=ServiceCategory.FORECAST,
        fulfillment_modes=(AUTOMATED,),
        description=(
            "Built from the user's own natal chart and today's transits, not "
            "from a sun-sign template."
        ),
        supports_automated_report=True,
        sort_order=100,
    ),
    ServiceSpec(
        code=ServiceCode.WEEKLY_HOROSCOPE,
        name="Personalised Weekly Horoscope",
        name_tr="Haftalık Kişisel Horoskop",
        category=ServiceCategory.FORECAST,
        fulfillment_modes=(AUTOMATED,),
        supports_automated_report=True,
        sort_order=110,
    ),
    ServiceSpec(
        code=ServiceCode.MONTHLY_FORECAST,
        name="Monthly Forecast",
        name_tr="Aylık Öngörü",
        category=ServiceCategory.FORECAST,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=45,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=120,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.ANNUAL_FORECAST,
        name="Annual Forecast",
        name_tr="Yıllık Öngörü",
        category=ServiceCategory.FORECAST,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        description=(
            "Year ahead from solar return, outer-planet transits, eclipses and "
            "house activations."
        ),
        estimated_duration_minutes=60,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=130,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.TRANSIT_ANALYSIS,
        name="Transit Analysis",
        name_tr="Transit Analizi",
        category=ServiceCategory.FORECAST,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=30,
        supports_automated_report=True,
        sort_order=140,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.SOLAR_RETURN,
        name="Solar Return Chart",
        name_tr="Solar Return Haritası",
        category=ServiceCategory.FORECAST,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=45,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=150,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.LUNAR_RETURN,
        name="Lunar Return Chart",
        name_tr="Lunar Return Haritası",
        category=ServiceCategory.FORECAST,
        fulfillment_modes=(AUTOMATED, EXPERT),
        estimated_duration_minutes=30,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=160,
        **_consultation(),
    ),
    # ------------------------------------------------------ relationship
    ServiceSpec(
        code=ServiceCode.SYNASTRY,
        name="Synastry",
        name_tr="Sinastri",
        category=ServiceCategory.RELATIONSHIP,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        description=(
            "Chart-to-chart comparison: inter-aspects, house overlays and "
            "category scores."
        ),
        estimated_duration_minutes=45,
        requires_partner_data=True,
        supports_automated_report=True,
        sort_order=200,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.RELATIONSHIP_ANALYSIS,
        name="Relationship Analysis",
        name_tr="İlişki Analizi",
        category=ServiceCategory.RELATIONSHIP,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=60,
        requires_partner_data=True,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=210,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.COMPOSITE_CHART,
        name="Composite Chart",
        name_tr="Composite Harita",
        category=ServiceCategory.RELATIONSHIP,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=45,
        requires_partner_data=True,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=220,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.DAVISON_CHART,
        name="Davison Chart",
        name_tr="Davison Haritası",
        category=ServiceCategory.RELATIONSHIP,
        fulfillment_modes=(AUTOMATED, EXPERT, HYBRID),
        estimated_duration_minutes=45,
        requires_partner_data=True,
        supports_automated_report=True,
        requires_premium=True,
        sort_order=230,
        **_consultation(),
    ),
    # ----------------------------------------------------------- horary
    ServiceSpec(
        code=ServiceCode.HORARY_QUESTION,
        name="Horary Question",
        name_tr="Horary Sorusu",
        category=ServiceCategory.HORARY,
        fulfillment_modes=(AUTOMATED, EXPERT),
        description=(
            "A chart cast for the moment and place the question was asked. "
            "Birth data is not used."
        ),
        estimated_duration_minutes=30,
        requires_birth_data=False,
        requires_question=True,
        supports_automated_report=True,
        sort_order=300,
        **_consultation(),
    ),
    # ------------------------------------------------------- divination
    ServiceSpec(
        code=ServiceCode.TAROT_READING,
        name="Tarot Reading",
        name_tr="Tarot Açılımı",
        category=ServiceCategory.DIVINATION,
        fulfillment_modes=(AUTOMATED, EXPERT),
        estimated_duration_minutes=30,
        requires_birth_data=False,
        supports_automated_report=True,
        sort_order=400,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.RUNE_READING,
        name="Rune Reading",
        name_tr="Rün Açılımı",
        category=ServiceCategory.DIVINATION,
        fulfillment_modes=(AUTOMATED, EXPERT),
        estimated_duration_minutes=30,
        requires_birth_data=False,
        supports_automated_report=True,
        sort_order=410,
        **_consultation(),
    ),
    ServiceSpec(
        code=ServiceCode.KATINA_READING,
        name="Katina Reading",
        name_tr="Katina Açılımı",
        category=ServiceCategory.DIVINATION,
        fulfillment_modes=(AUTOMATED, EXPERT),
        estimated_duration_minutes=30,
        requires_birth_data=False,
        supports_automated_report=True,
        sort_order=420,
        **_consultation(),
    ),
    # --------------------------------------------------------------- ai
    ServiceSpec(
        code=ServiceCode.ASTRO_AI_CONSULTATION,
        name="Astro AI Consultation",
        name_tr="Astro AI Danışmanlığı",
        category=ServiceCategory.AI,
        fulfillment_modes=(AUTOMATED,),
        description=(
            "Chat grounded in the user's own chart and current transits, with "
            "the calculations done by the engine."
        ),
        supports_chat=True,
        supports_automated_report=False,
        sort_order=500,
    ),
    # --------------------------------- planned, inactive until implemented
    ServiceSpec(
        code=ServiceCode.SECONDARY_PROGRESSIONS,
        name="Secondary Progressions",
        name_tr="Sekonder Progresyonlar",
        category=ServiceCategory.SPECIAL,
        fulfillment_modes=(AUTOMATED, EXPERT),
        active=False,
        sort_order=600,
    ),
    ServiceSpec(
        code=ServiceCode.SOLAR_ARC,
        name="Solar Arc Directions",
        name_tr="Solar Arc Yönelimleri",
        category=ServiceCategory.SPECIAL,
        fulfillment_modes=(AUTOMATED, EXPERT),
        active=False,
        sort_order=610,
    ),
    ServiceSpec(
        code=ServiceCode.ANNUAL_PROFECTIONS,
        name="Annual Profections",
        name_tr="Yıllık Profeksiyonlar",
        category=ServiceCategory.SPECIAL,
        fulfillment_modes=(AUTOMATED, EXPERT),
        active=False,
        sort_order=620,
    ),
    ServiceSpec(
        code=ServiceCode.ASTROCARTOGRAPHY,
        name="Astrocartography",
        name_tr="Astrokartografi",
        category=ServiceCategory.SPECIAL,
        fulfillment_modes=(AUTOMATED, EXPERT),
        active=False,
        sort_order=630,
    ),
    ServiceSpec(
        code=ServiceCode.RELOCATION_CHART,
        name="Relocation Chart",
        name_tr="Relokasyon Haritası",
        category=ServiceCategory.SPECIAL,
        fulfillment_modes=(AUTOMATED, EXPERT),
        active=False,
        sort_order=640,
    ),
    ServiceSpec(
        code=ServiceCode.ELECTIONAL_ASTROLOGY,
        name="Electional Astrology",
        name_tr="Elektif Astroloji",
        category=ServiceCategory.SPECIAL,
        fulfillment_modes=(EXPERT, HYBRID),
        requires_question=True,
        active=False,
        sort_order=650,
        **_consultation(),
    ),
)

CATALOG_BY_CODE: dict[ServiceCode, ServiceSpec] = {
    spec.code: spec for spec in CATALOG
}
