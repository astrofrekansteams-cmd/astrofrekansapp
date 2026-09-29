"""Personal stone guide.

A stone is chosen by an explainable score over fixed catalogue associations
(elements, planets, signs, intents). Inputs are the user's natal element
balance and placements, the chosen intent and - for "today" - the Moon and
the transits to the natal chart. Every point added carries a reason, so the
result screen can show exactly why a stone was suggested.

Associations are traditional/symbolic. Nothing here is, or may be presented
as, a health or medical claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.astrology import Chart, PlanetPosition
from app.domain.enums import AspectNature, Element, Planet, ZodiacSign
from app.services.astrology.aspects import TRANSIT_ORBS, cross_chart_aspects
from app.services.guides import content
from app.services.guides.content import Text, pick

STONES_VERSION = "stones_v1"
MAIN_BODIES = (
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
    Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO,
)


class Intent(StrEnum):
    LOVE = "love"
    MONEY = "money"
    CAREER = "career"
    CALM = "calm"
    MOTIVATION = "motivation"
    COMMUNICATION = "communication"
    PROTECTION = "protection"
    CONFIDENCE = "confidence"
    MEDITATION = "meditation"


class StoneMode(StrEnum):
    TODAY = "today"
    PERSONAL = "personal"


INTENT_NAMES: dict[Intent, Text] = {
    Intent.LOVE: ("aşk", "love"),
    Intent.MONEY: ("para", "money"),
    Intent.CAREER: ("kariyer", "career"),
    Intent.CALM: ("sakinlik", "calm"),
    Intent.MOTIVATION: ("motivasyon", "motivation"),
    Intent.COMMUNICATION: ("iletişim", "communication"),
    Intent.PROTECTION: ("korunma", "protection"),
    Intent.CONFIDENCE: ("özgüven", "confidence"),
    Intent.MEDITATION: ("meditasyon", "meditation"),
}

INTENT_PLANETS: dict[Intent, tuple[Planet, ...]] = {
    Intent.LOVE: (Planet.VENUS, Planet.MOON),
    Intent.MONEY: (Planet.VENUS, Planet.JUPITER),
    Intent.CAREER: (Planet.SATURN, Planet.SUN),
    Intent.CALM: (Planet.MOON, Planet.NEPTUNE),
    Intent.MOTIVATION: (Planet.MARS, Planet.SUN),
    Intent.COMMUNICATION: (Planet.MERCURY,),
    Intent.PROTECTION: (Planet.SATURN, Planet.PLUTO),
    Intent.CONFIDENCE: (Planet.SUN, Planet.MARS),
    Intent.MEDITATION: (Planet.NEPTUNE, Planet.MOON),
}


@dataclass(slots=True, frozen=True)
class Stone:
    key: str
    name: Text
    color: str
    elements: tuple[Element, ...]
    planets: tuple[Planet, ...]
    signs: tuple[ZodiacSign, ...]
    intents: tuple[Intent, ...]
    note: Text


E, P, S, I = Element, Planet, ZodiacSign, Intent
CATALOGUE: tuple[Stone, ...] = (
    Stone("amethyst", ("Ametist", "Amethyst"), "#9966CC", (E.WATER, E.AIR), (P.NEPTUNE, P.JUPITER),
          (S.PISCES, S.AQUARIUS, S.SAGITTARIUS), (I.CALM, I.MEDITATION, I.PROTECTION),
          ("Sakin bir odak ve iç gözlemle ilişkilendirilir.", "Associated with calm focus and reflection.")),
    Stone("rose_quartz", ("Gül Kuvars", "Rose Quartz"), "#F4C2C2", (E.WATER, E.EARTH), (P.VENUS, P.MOON),
          (S.TAURUS, S.LIBRA), (I.LOVE, I.CALM),
          ("Şefkat ve yumuşaklığın sembolü olarak bilinir.", "Known as a symbol of tenderness and care.")),
    Stone("citrine", ("Sitrin", "Citrine"), "#E4B43C", (E.FIRE,), (P.SUN, P.JUPITER),
          (S.LEO, S.SAGITTARIUS, S.GEMINI), (I.MONEY, I.MOTIVATION, I.CONFIDENCE),
          ("Güneş'in sıcaklığı ve bolluk temasıyla ilişkilendirilir.", "Linked with solar warmth and abundance.")),
    Stone("tigers_eye", ("Kaplan Gözü", "Tiger's Eye"), "#B5651D", (E.FIRE, E.EARTH), (P.SUN, P.MARS),
          (S.LEO, S.CAPRICORN), (I.CONFIDENCE, I.CAREER, I.PROTECTION),
          ("Kararlılık ve cesaret temasının taşı olarak anılır.", "Traditionally tied to resolve and courage.")),
    Stone("green_aventurine", ("Yeşil Aventurin", "Green Aventurine"), "#3E8E5B", (E.EARTH,),
          (P.VENUS, P.JUPITER), (S.TAURUS, S.VIRGO), (I.MONEY, I.LOVE, I.CAREER),
          ("Fırsat ve büyüme temalarıyla ilişkilendirilir.", "Associated with opportunity and growth.")),
    Stone("lapis_lazuli", ("Lapis Lazuli", "Lapis Lazuli"), "#26619C", (E.AIR, E.WATER),
          (P.JUPITER, P.MERCURY, P.NEPTUNE), (S.SAGITTARIUS, S.LIBRA),
          (I.COMMUNICATION, I.MEDITATION, I.CAREER),
          ("Bilgelik ve dürüst ifadeyle ilişkilendirilir.", "Linked with wisdom and honest expression.")),
    Stone("blue_lace_agate", ("Mavi Dantel Akik", "Blue Lace Agate"), "#9CC3E6", (E.AIR, E.WATER),
          (P.MERCURY, P.MOON), (S.GEMINI, S.PISCES), (I.COMMUNICATION, I.CALM),
          ("Yumuşak ve sakin iletişimin sembolü sayılır.", "Seen as a symbol of gentle, calm speech.")),
    Stone("black_tourmaline", ("Siyah Turmalin", "Black Tourmaline"), "#1C1C1C", (E.EARTH,),
          (P.SATURN, P.PLUTO), (S.CAPRICORN, S.SCORPIO), (I.PROTECTION, I.CALM),
          ("Sınır koyma ve topraklanma temasıyla bilinir.", "Known for themes of boundaries and grounding.")),
    Stone("obsidian", ("Obsidyen", "Obsidian"), "#2B2B35", (E.FIRE, E.EARTH), (P.PLUTO, P.SATURN),
          (S.SCORPIO,), (I.PROTECTION,),
          ("Derinlik ve dönüşüm temasıyla ilişkilendirilir.", "Associated with depth and transformation.")),
    Stone("carnelian", ("Karneol", "Carnelian"), "#C0392B", (E.FIRE,), (P.MARS, P.SUN),
          (S.ARIES, S.LEO, S.VIRGO), (I.MOTIVATION, I.CONFIDENCE, I.CAREER),
          ("Canlılık ve harekete geçme temasıyla anılır.", "Linked with vitality and taking action.")),
    Stone("red_jasper", ("Kırmızı Jasper", "Red Jasper"), "#9B2D20", (E.EARTH, E.FIRE), (P.MARS,),
          (S.ARIES, S.SCORPIO), (I.MOTIVATION, I.PROTECTION),
          ("İstikrarlı enerji ve dayanıklılıkla ilişkilendirilir.", "Associated with steady energy and endurance.")),
    Stone("moonstone", ("Aytaşı", "Moonstone"), "#DDE3EA", (E.WATER,), (P.MOON,), (S.CANCER,),
          (I.CALM, I.LOVE, I.MEDITATION),
          ("Ay döngüleri ve sezgiyle ilişkilendirilir.", "Associated with lunar cycles and intuition.")),
    Stone("aquamarine", ("Akuamarin", "Aquamarine"), "#7FC7C9", (E.WATER, E.AIR),
          (P.NEPTUNE, P.MOON, P.MERCURY), (S.PISCES, S.AQUARIUS), (I.COMMUNICATION, I.CALM),
          ("Akışkanlık ve açık ifadenin sembolü sayılır.", "Seen as a symbol of flow and clear expression.")),
    Stone("hematite", ("Hematit", "Hematite"), "#4A4A4A", (E.EARTH, E.FIRE), (P.MARS, P.SATURN),
          (S.ARIES, S.CAPRICORN), (I.PROTECTION, I.CONFIDENCE),
          ("Topraklanma ve odak temasıyla bilinir.", "Known for grounding and focus.")),
    Stone("pyrite", ("Pirit", "Pyrite"), "#B8A35A", (E.FIRE, E.EARTH), (P.MARS, P.SUN),
          (S.LEO, S.ARIES), (I.MONEY, I.CONFIDENCE, I.CAREER),
          ("Girişkenlik ve bolluk temasıyla ilişkilendirilir.", "Linked with initiative and abundance.")),
    Stone("selenite", ("Selenit", "Selenite"), "#F2F0E6", (E.AIR, E.WATER), (P.MOON, P.NEPTUNE),
          (S.CANCER, S.TAURUS), (I.MEDITATION, I.CALM),
          ("Berraklık ve arınma sembolü olarak anılır.", "Seen as a symbol of clarity and clearing.")),
    Stone("fluorite", ("Florit", "Fluorite"), "#7E6BB5", (E.AIR,), (P.MERCURY, P.NEPTUNE),
          (S.PISCES, S.CAPRICORN), (I.COMMUNICATION, I.MEDITATION),
          ("Zihinsel düzen ve odakla ilişkilendirilir.", "Associated with mental order and focus.")),
    Stone("garnet", ("Garnet", "Garnet"), "#7B1E2E", (E.FIRE,), (P.MARS, P.PLUTO),
          (S.ARIES, S.SCORPIO, S.CAPRICORN), (I.MOTIVATION, I.LOVE, I.CONFIDENCE),
          ("Tutku ve bağlılık temasıyla anılır.", "Linked with passion and commitment.")),
    Stone("malachite", ("Malakit", "Malachite"), "#0B8457", (E.EARTH, E.WATER), (P.VENUS, P.SATURN),
          (S.TAURUS, S.CAPRICORN, S.SCORPIO), (I.PROTECTION, I.LOVE, I.CAREER),
          ("Değişim ve korunma temasıyla ilişkilendirilir.", "Associated with change and protection.")),
    Stone("turquoise", ("Turkuaz", "Turquoise"), "#40C0B8", (E.AIR, E.WATER),
          (P.JUPITER, P.VENUS, P.MERCURY), (S.SAGITTARIUS, S.PISCES), (I.COMMUNICATION, I.PROTECTION),
          ("Yolculuk ve korunmanın geleneksel sembolüdür.", "A traditional symbol of travel and protection.")),
    Stone("clear_quartz", ("Kristal Kuvars", "Clear Quartz"), "#EEF3F7",
          (E.FIRE, E.EARTH, E.AIR, E.WATER), (P.SUN, P.MOON), tuple(ZodiacSign),
          (I.MEDITATION, I.MOTIVATION),
          ("Niyeti netleştirme temasıyla bilinir.", "Known for the theme of clarifying intent.")),
    Stone("labradorite", ("Labradorit", "Labradorite"), "#5A6E7F", (E.WATER, E.AIR),
          (P.URANUS, P.NEPTUNE, P.MOON), (S.AQUARIUS, S.SCORPIO, S.SAGITTARIUS),
          (I.MEDITATION, I.PROTECTION),
          ("Sezgi ve dönüşümle ilişkilendirilir.", "Associated with intuition and transformation.")),
    Stone("emerald", ("Zümrüt", "Emerald"), "#1F8A55", (E.EARTH,), (P.VENUS, P.MERCURY),
          (S.TAURUS, S.GEMINI), (I.LOVE, I.COMMUNICATION),
          ("Sadakat ve uyumun sembolü olarak anılır.", "Seen as a symbol of loyalty and harmony.")),
    Stone("amber", ("Kehribar", "Amber"), "#F5A623", (E.FIRE,), (P.SUN,), (S.LEO,),
          (I.CONFIDENCE, I.MOTIVATION),
          ("Güneş'in sıcaklığı ve neşesiyle ilişkilendirilir.", "Linked with solar warmth and cheer.")),
    Stone("sodalite", ("Sodalit", "Sodalite"), "#2C4F9E", (E.AIR, E.WATER), (P.MERCURY, P.JUPITER),
          (S.SAGITTARIUS, S.VIRGO), (I.COMMUNICATION, I.CALM),
          ("Mantık ve sezginin dengesiyle ilişkilendirilir.", "Associated with balancing logic and intuition.")),
    Stone("smoky_quartz", ("Dumanlı Kuvars", "Smoky Quartz"), "#6E5A4B", (E.EARTH,), (P.SATURN, P.PLUTO),
          (S.CAPRICORN, S.SAGITTARIUS), (I.PROTECTION, I.CALM),
          ("Bırakma ve topraklanma temasıyla bilinir.", "Known for letting go and grounding.")),
)
STONES_BY_KEY = {stone.key: stone for stone in CATALOGUE}

DISCLAIMER: Text = (
    "Taş önerileri geleneksel ve sembolik ilişkilendirmelere dayanır; tıbbi, psikolojik veya finansal "
    "tavsiye değildir ve hiçbir tedavinin yerine geçmez.",
    "Stone suggestions rest on traditional, symbolic associations; they are not medical, psychological "
    "or financial advice and replace no treatment.",
)


@dataclass(slots=True)
class Reason:
    kind: str  # intent | element | placement | planet | moon | transit
    weight: int
    text: str


@dataclass(slots=True)
class StoneSuggestion:
    stone: Stone
    score: int
    reasons: list[Reason] = field(default_factory=list)


@dataclass(slots=True)
class StoneRecommendation:
    mode: StoneMode
    intent: Intent | None
    moment: datetime
    element_balance: dict[Element, int]
    weakest_elements: list[Element]
    suggestions: list[StoneSuggestion]
    disclaimer: str
    version: str = STONES_VERSION


def element_balance(chart: Chart) -> dict[Element, int]:
    counts = {element: 0 for element in Element}
    for position in chart.positions:
        if position.planet in MAIN_BODIES:
            counts[position.sign.element] += 1
    return counts


class StoneGuide:
    def recommend(
        self,
        natal: Chart,
        *,
        mode: StoneMode,
        intent: Intent | None,
        moment: datetime,
        sky: list[PlanetPosition] | None = None,
        locale: str = "tr",
        limit: int = 3,
    ) -> StoneRecommendation:
        balance = element_balance(natal)
        lowest = min(balance.values())
        weakest = [element for element, count in balance.items() if count == lowest]

        suggestions = [
            self._score(stone, natal, balance, weakest, intent, mode, sky, locale)
            for stone in CATALOGUE
        ]
        if intent is not None:
            suggestions = [s for s in suggestions if intent in s.stone.intents]
        suggestions.sort(key=lambda s: (-s.score, s.stone.key))
        return StoneRecommendation(
            mode=mode,
            intent=intent,
            moment=moment,
            element_balance=balance,
            weakest_elements=weakest,
            suggestions=suggestions[:limit],
            disclaimer=pick(DISCLAIMER, locale),
        )

    def _score(
        self,
        stone: Stone,
        natal: Chart,
        balance: dict[Element, int],
        weakest: list[Element],
        intent: Intent | None,
        mode: StoneMode,
        sky: list[PlanetPosition] | None,
        locale: str,
    ) -> StoneSuggestion:
        reasons: list[Reason] = []
        name = pick(stone.name, locale)

        def add(kind: str, weight: int, text: Text) -> None:
            reasons.append(Reason(kind=kind, weight=weight, text=pick(text, locale)))

        if intent is not None and intent in stone.intents:
            label = pick(INTENT_NAMES[intent], locale)
            add("intent", 40, (f"{label.capitalize()} niyetinle geleneksel olarak ilişkilendirilir.",
                               f"Traditionally associated with your {label} intent."))
            for planet in INTENT_PLANETS[intent]:
                if planet in stone.planets:
                    position = natal.position(planet)
                    if position is None:
                        continue
                    planet_name = pick(content.PLANET_NAMES[planet], locale)
                    sign_name = pick(content.SIGN_NAMES[position.sign], locale)
                    add("planet", 12, (
                        f"{label.capitalize()} niyeti {planet_name} ile ilişkili; natal {planet_name} {sign_name} burcunda "
                        f"ve {name} {planet_name} ile ilişkilendirilen bir taş.",
                        f"The {label} intent is ruled by {planet_name}; your natal {planet_name} is in {sign_name} "
                        f"and {name} is associated with {planet_name}.",
                    ))
                    break

        # A stone tied to every element says nothing about balance.
        universal = len(stone.elements) == len(Element)
        for element in weakest:
            if element in stone.elements and not universal:
                element_name = pick(content.ELEMENT_NAMES[element], locale)
                add("element", 15, (
                    f"Haritanda {element_name} elementi en zayıf ({balance[element]}/10); "
                    f"{name} bu elementle ilişkilendirilir ve dengeyi temsil eder.",
                    f"{element_name} is your weakest element ({balance[element]}/10); "
                    f"{name} is associated with it and stands for balance.",
                ))
                break

        placements = (
            (natal.sun, ("Güneş", "Sun")),
            (natal.moon, ("Ay", "Moon")),
        )
        for position, label in placements:
            if position is not None and position.sign in stone.signs and len(stone.signs) < 12:
                sign_name = pick(content.SIGN_NAMES[position.sign], locale)
                add("placement", 6, (
                    f"Natal {label[0]} {sign_name} burcunda; {name} {sign_name} ile ilişkilendirilir.",
                    f"Natal {label[1]} in {sign_name}; {name} is associated with {sign_name}.",
                ))
        ascendant = natal.ascendant_sign
        if ascendant is not None and ascendant in stone.signs and len(stone.signs) < 12:
            sign_name = pick(content.SIGN_NAMES[ascendant], locale)
            add("placement", 6, (f"Yükselenin {sign_name}; {name} bu burçla ilişkilendirilir.",
                                 f"Your Ascendant is {sign_name}; {name} is associated with it."))

        if mode == StoneMode.TODAY and sky is not None:
            self._today(stone, natal, sky, name, add, locale)

        return StoneSuggestion(stone=stone, score=sum(r.weight for r in reasons), reasons=reasons)

    def _today(self, stone, natal, sky, name, add, locale) -> None:  # noqa: ANN001
        moon = next((p for p in sky if p.planet == Planet.MOON), None)
        if moon is not None:
            sign_name = pick(content.SIGN_NAMES[moon.sign], locale)
            if moon.sign.element in stone.elements and len(stone.elements) < len(Element):
                element_name = pick(content.ELEMENT_NAMES[moon.sign.element], locale)
                add("moon", 8, (f"Ay bugün {sign_name} burcunda ({element_name}); {name} bu elementle uyumlu.",
                                f"The Moon is in {sign_name} ({element_name}) today; {name} matches that element."))
            if moon.sign in stone.signs and len(stone.signs) < 12:
                add("moon", 5, (f"Ay bugün {name} ile ilişkilendirilen {sign_name} burcunda.",
                                f"The Moon is in {sign_name}, a sign associated with {name}."))

        transiting = [p for p in sky if p.planet in MAIN_BODIES and p.planet != Planet.MOON]
        natal_bodies = [p for p in natal.positions if p.planet in MAIN_BODIES]
        hits = cross_chart_aspects(transiting, natal_bodies, policy=TRANSIT_ORBS)
        for hit in hits:
            if hit.second not in stone.planets:
                continue
            transit_name = pick(content.PLANET_NAMES[hit.first], locale)
            natal_name = pick(content.PLANET_NAMES[hit.second], locale)
            aspect = pick(content.ASPECT_NAMES[hit.aspect.value], locale)
            if hit.aspect.nature == AspectNature.CHALLENGING:
                add("transit", 10, (
                    f"Bugün transit {transit_name} natal {natal_name} ile {aspect} açısı yapıyor (orb {hit.orb:.1f}°); "
                    f"{name} {natal_name} ile ilişkilendirilir ve dengeleyici bir odak olarak seçildi.",
                    f"Transit {transit_name} {aspect} natal {natal_name} today (orb {hit.orb:.1f}°); "
                    f"{name} is associated with {natal_name} and chosen as a balancing focus.",
                ))
            else:
                add("transit", 5, (
                    f"Bugün transit {transit_name} natal {natal_name} ile {aspect} açısı yapıyor (orb {hit.orb:.1f}°); "
                    f"{name} bu desteği simgeler.",
                    f"Transit {transit_name} {aspect} natal {natal_name} today (orb {hit.orb:.1f}°); "
                    f"{name} symbolises that support.",
                ))
            break
