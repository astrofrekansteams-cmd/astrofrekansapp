"""Fixed TR/EN content tables for the guide modules.

Keys are engine enums, so the text a user sees is always a deterministic
function of the calculated chart. AZ falls back to TR, like the app copy.
"""

from __future__ import annotations

from app.domain.enums import AspectNature, Element, MoonPhaseName, Planet, ZodiacSign

Text = tuple[str, str]  # (tr, en)


def pick(text: Text, locale: str) -> str:
    return text[1] if locale == "en" else text[0]


HOUSE_TOPICS: dict[int, Text] = {
    1: ("kendin, bedenin ve ilk izlenimin", "yourself, your body and first impressions"),
    2: ("para, kaynaklar ve öz değer", "money, resources and self-worth"),
    3: ("iletişim, yakın çevre ve kısa yollar", "communication, siblings and short trips"),
    4: ("ev, aile ve iç dünyan", "home, family and your inner world"),
    5: ("aşk, yaratıcılık ve keyif", "romance, creativity and pleasure"),
    6: ("günlük düzen, iş akışı ve sağlıklı rutinler", "daily routine, workflow and healthy habits"),
    7: ("ilişkiler, ortaklıklar ve anlaşmalar", "relationships, partnerships and agreements"),
    8: ("ortak kaynaklar, derin bağlar ve dönüşüm", "shared resources, deep bonds and transformation"),
    9: ("inançlar, öğrenme ve uzak ufuklar", "beliefs, learning and far horizons"),
    10: ("kariyer, hedefler ve görünürlük", "career, goals and public standing"),
    11: ("arkadaşlar, topluluk ve gelecek planları", "friends, community and future plans"),
    12: ("dinlenme, iç gözlem ve kapanışlar", "rest, reflection and endings"),
}

SIGN_MOODS: dict[ZodiacSign, Text] = {
    ZodiacSign.ARIES: ("hızlı, cesur ve başlatıcı", "quick, brave and initiating"),
    ZodiacSign.TAURUS: ("sakin, somut ve keyfe düşkün", "calm, tangible and pleasure-seeking"),
    ZodiacSign.GEMINI: ("meraklı, konuşkan ve hareketli", "curious, talkative and busy"),
    ZodiacSign.CANCER: ("duygusal, koruyucu ve yuvaya dönük", "emotional, protective and home-bound"),
    ZodiacSign.LEO: ("sıcak, gösterişli ve yaratıcı", "warm, expressive and creative"),
    ZodiacSign.VIRGO: ("titiz, pratik ve düzen arayan", "precise, practical and orderly"),
    ZodiacSign.LIBRA: ("uyum arayan, sosyal ve estetik", "harmony-seeking, social and aesthetic"),
    ZodiacSign.SCORPIO: ("yoğun, derin ve odaklı", "intense, deep and focused"),
    ZodiacSign.SAGITTARIUS: ("iyimser, özgür ve keşifçi", "optimistic, free and exploratory"),
    ZodiacSign.CAPRICORN: ("disiplinli, ciddi ve hedef odaklı", "disciplined, serious and goal-driven"),
    ZodiacSign.AQUARIUS: ("bağımsız, yenilikçi ve topluluk odaklı", "independent, inventive and communal"),
    ZodiacSign.PISCES: ("sezgisel, hassas ve hayalperest", "intuitive, sensitive and dreamy"),
}

SIGN_NAMES: dict[ZodiacSign, Text] = {
    ZodiacSign.ARIES: ("Koç", "Aries"),
    ZodiacSign.TAURUS: ("Boğa", "Taurus"),
    ZodiacSign.GEMINI: ("İkizler", "Gemini"),
    ZodiacSign.CANCER: ("Yengeç", "Cancer"),
    ZodiacSign.LEO: ("Aslan", "Leo"),
    ZodiacSign.VIRGO: ("Başak", "Virgo"),
    ZodiacSign.LIBRA: ("Terazi", "Libra"),
    ZodiacSign.SCORPIO: ("Akrep", "Scorpio"),
    ZodiacSign.SAGITTARIUS: ("Yay", "Sagittarius"),
    ZodiacSign.CAPRICORN: ("Oğlak", "Capricorn"),
    ZodiacSign.AQUARIUS: ("Kova", "Aquarius"),
    ZodiacSign.PISCES: ("Balık", "Pisces"),
}

PLANET_NAMES: dict[Planet, Text] = {
    Planet.SUN: ("Güneş", "Sun"),
    Planet.MOON: ("Ay", "Moon"),
    Planet.MERCURY: ("Merkür", "Mercury"),
    Planet.VENUS: ("Venüs", "Venus"),
    Planet.MARS: ("Mars", "Mars"),
    Planet.JUPITER: ("Jüpiter", "Jupiter"),
    Planet.SATURN: ("Satürn", "Saturn"),
    Planet.URANUS: ("Uranüs", "Uranus"),
    Planet.NEPTUNE: ("Neptün", "Neptune"),
    Planet.PLUTO: ("Plüton", "Pluto"),
    Planet.NORTH_NODE: ("Kuzey Ay Düğümü", "North Node"),
    Planet.SOUTH_NODE: ("Güney Ay Düğümü", "South Node"),
}

PLANET_THEMES: dict[Planet, Text] = {
    Planet.SUN: ("kimlik ve yaşam enerjisi", "identity and vitality"),
    Planet.MOON: ("duygular ve ihtiyaçlar", "emotions and needs"),
    Planet.MERCURY: ("düşünce ve iletişim", "thinking and communication"),
    Planet.VENUS: ("sevgi, değer ve keyif", "love, value and pleasure"),
    Planet.MARS: ("enerji, istek ve mücadele", "drive, desire and effort"),
    Planet.JUPITER: ("büyüme, fırsat ve anlam", "growth, opportunity and meaning"),
    Planet.SATURN: ("sorumluluk, sınır ve yapı", "responsibility, limits and structure"),
    Planet.URANUS: ("değişim ve özgürlük", "change and freedom"),
    Planet.NEPTUNE: ("sezgi, hayal ve teslimiyet", "intuition, imagination and surrender"),
    Planet.PLUTO: ("güç, derinlik ve dönüşüm", "power, depth and transformation"),
    Planet.NORTH_NODE: ("gelişim yönü", "direction of growth"),
    Planet.SOUTH_NODE: ("alışkanlıklar ve geçmiş", "habits and the past"),
}

ELEMENT_NAMES: dict[Element, Text] = {
    Element.FIRE: ("Ateş", "Fire"),
    Element.EARTH: ("Toprak", "Earth"),
    Element.AIR: ("Hava", "Air"),
    Element.WATER: ("Su", "Water"),
}

PHASE_NAMES: dict[MoonPhaseName, Text] = {
    MoonPhaseName.NEW_MOON: ("Yeni Ay", "New Moon"),
    MoonPhaseName.WAXING_CRESCENT: ("Büyüyen Hilal", "Waxing Crescent"),
    MoonPhaseName.FIRST_QUARTER: ("İlk Dördün", "First Quarter"),
    MoonPhaseName.WAXING_GIBBOUS: ("Büyüyen Ay", "Waxing Gibbous"),
    MoonPhaseName.FULL_MOON: ("Dolunay", "Full Moon"),
    MoonPhaseName.WANING_GIBBOUS: ("Küçülen Ay", "Waning Gibbous"),
    MoonPhaseName.LAST_QUARTER: ("Son Dördün", "Last Quarter"),
    MoonPhaseName.WANING_CRESCENT: ("Balzamik Hilal", "Waning Crescent"),
}

# (good for, be careful with) per phase.
PHASE_GUIDANCE: dict[MoonPhaseName, tuple[list[Text], list[Text]]] = {
    MoonPhaseName.NEW_MOON: (
        [
            ("Niyet belirlemek ve yeni bir sayfa açmak", "Setting intentions and starting fresh"),
            ("Sessizce plan yapmak", "Quiet planning"),
        ],
        [
            ("Henüz netleşmemiş konularda büyük duyurular", "Big announcements on unclear matters"),
        ],
    ),
    MoonPhaseName.WAXING_CRESCENT: (
        [
            ("İlk adımları atmak ve destek toplamak", "Taking first steps and gathering support"),
            ("Yeni alışkanlıkları başlatmak", "Starting new habits"),
        ],
        [("Sabırsızlıkla sonucu zorlamak", "Forcing results impatiently")],
    ),
    MoonPhaseName.FIRST_QUARTER: (
        [
            ("Karar vermek ve engelleri aşmak için harekete geçmek", "Deciding and acting to clear obstacles"),
        ],
        [("Gerginlik anında aceleci tepkiler", "Rash reactions under pressure")],
    ),
    MoonPhaseName.WAXING_GIBBOUS: (
        [
            ("Planı gözden geçirip ince ayar yapmak", "Reviewing and refining the plan"),
            ("Emek gerektiren işlere odaklanmak", "Focusing on effortful work"),
        ],
        [("Mükemmeliyetçilikle işi hiç bitirmemek", "Never finishing out of perfectionism")],
    ),
    MoonPhaseName.FULL_MOON: (
        [
            ("Sonuçları görmek, kutlamak ve paylaşmak", "Seeing results, celebrating and sharing"),
            ("Neyin bittiğini fark etmek", "Noticing what has run its course"),
        ],
        [
            ("Duygusal tepkileri büyütmek", "Amplifying emotional reactions"),
            ("Aşırıya kaçmak", "Overdoing things"),
        ],
    ),
    MoonPhaseName.WANING_GIBBOUS: (
        [
            ("Öğrendiklerini aktarmak ve teşekkür etmek", "Sharing what you learned and giving thanks"),
        ],
        [("Her şeyi aynı anda düzeltmeye çalışmak", "Trying to fix everything at once")],
    ),
    MoonPhaseName.LAST_QUARTER: (
        [
            ("Gereksizi bırakmak ve düzen kurmak", "Letting go of the unnecessary and tidying up"),
        ],
        [("Eski tartışmaları yeniden açmak", "Reopening old arguments")],
    ),
    MoonPhaseName.WANING_CRESCENT: (
        [
            ("Dinlenmek, iç gözlem ve kapanışlar", "Rest, reflection and closure"),
        ],
        [("Yorgunken yeni bir işe başlamak", "Starting something new while drained")],
    ),
}

ELEMENT_GUIDANCE: dict[Element, Text] = {
    Element.FIRE: (
        "Ay ateş burcunda: harekete geçmek, spor ve cesaret isteyen işler için enerji yüksek.",
        "Moon in a fire sign: energy favours action, movement and bold moves.",
    ),
    Element.EARTH: (
        "Ay toprak burcunda: pratik işler, bütçe ve somut adımlar için uygun.",
        "Moon in an earth sign: good for practical tasks, budgets and concrete steps.",
    ),
    Element.AIR: (
        "Ay hava burcunda: konuşmalar, fikir alışverişi ve sosyal bağlantılar öne çıkıyor.",
        "Moon in an air sign: conversations, ideas and social links come forward.",
    ),
    Element.WATER: (
        "Ay su burcunda: duygular derinleşir; şefkat, yakınlık ve dinlenme destekleniyor.",
        "Moon in a water sign: feelings deepen; care, closeness and rest are supported.",
    ),
}

ASPECT_NAMES: dict[str, Text] = {
    "conjunction": ("kavuşum", "conjunction"),
    "sextile": ("sekstil", "sextile"),
    "square": ("kare", "square"),
    "trine": ("üçgen", "trine"),
    "opposition": ("karşıt", "opposition"),
}


def aspect_guidance(planet: Planet, nature: AspectNature, locale: str) -> tuple[str, bool]:
    """One line for a Moon aspect to a natal planet. Returns (text, favourable)."""
    theme = pick(PLANET_THEMES[planet], locale)
    name = pick(PLANET_NAMES[planet], locale)
    if nature == AspectNature.HARMONIOUS:
        text = (
            f"Ay natal {name} ile uyumlu açıda: {theme} konularında akış kolaylaşıyor.",
            f"The Moon harmonises with your natal {name}: {theme} flows more easily.",
        )
        return pick(text, locale), True
    if nature == AspectNature.CHALLENGING:
        text = (
            f"Ay natal {name} ile gergin açıda: {theme} konularında duygusal tepkilere dikkat.",
            f"The Moon challenges your natal {name}: watch emotional reactions around {theme}.",
        )
        return pick(text, locale), False
    text = (
        f"Ay natal {name} üzerinden geçiyor: {theme} konusu bugün duygusal olarak öne çıkıyor.",
        f"The Moon meets your natal {name}: {theme} is emotionally highlighted today.",
    )
    return pick(text, locale), True
