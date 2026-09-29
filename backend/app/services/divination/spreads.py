"""The spread registry.

Every spread is defined once, here, with a version. Nothing elsewhere in the
codebase may hardcode "the third card means the future" - that knowledge lives
in `interpretation_role`, travels into the AI context, and is what turns "the
third card is Death" into "what you are moving towards is Death".

**Origin is recorded honestly.** `TRADITIONAL` means the layout is documented
and widely used - the Celtic Cross, a past/present/future line. Everything we
designed ourselves says `PRODUCT_DEFINED`. Labelling an Astrofrekans layout as
traditional Katina methodology would be inventing a tradition, and the Katina
spreads in particular are ours: no single documented Katina method could be
verified, so none of them claims to be one.

Versioning works like the prompt registry: a stored reading keeps its
`spread_version`, so redesigning `tarot_celtic_cross_v1` into `_v2` leaves
existing readings describing the layout they were actually dealt in.
"""

from __future__ import annotations

from app.domain.divination import (
    DeckType,
    DivinationSpread,
    SpreadOrigin,
    SpreadPosition,
)


def position(
    index: int,
    key: str,
    tr: str,
    en: str,
    role: str,
    *,
    tr_description: str = "",
    en_description: str = "",
) -> SpreadPosition:
    default_tr, default_en = DEFAULT_DESCRIPTIONS.get(key, ("", ""))
    return SpreadPosition(
        index=index,
        key=key,
        titles={"tr": tr, "en": en},
        interpretation_role=role,
        descriptions={
            "tr": tr_description or default_tr,
            "en": en_description or default_en,
        },
    )


# Reader-facing position meanings for the original spreads, whose positions
# were defined with an AI role only. Display text; the draw ignores it.
DEFAULT_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "focus": ("Sorunun bütününe verilen tek yanıt.", "The single answer to the question as a whole."),
    "first": ("Konunun ilk katmanı.", "The first layer of the matter."),
    "second": ("Konunun ikinci katmanı.", "The second layer of the matter."),
    "third": ("Konunun üçüncü katmanı.", "The third layer of the matter."),
    "past": ("Bugünü şekillendiren geçmiş.", "The past that shaped today."),
    "present": ("Konunun şu anki hali.", "Where the matter stands now."),
    "future": ("Gidişat; kesin bir sonuç değil, eğilim.", "The direction; a tendency, not a fixed outcome."),
    "situation": ("Konunun gerçek durumu.", "What is actually going on."),
    "action": ("Atabileceğin adım.", "The step you can take."),
    "outcome": ("O adımın eğilimi; kehanet değildir.", "Where that step tends; not a prediction."),
    "challenge": ("Konuyu zorlaştıran etken.", "What makes this difficult."),
    "advice": ("Önerilen yaklaşım.", "The suggested approach."),
    "you": ("İlişkiye getirdiğin enerji.", "The energy you bring."),
    "them": ("Karşı tarafın kattığı dinamik; ne hissettiğini söylemez.",
             "The dynamic the other side brings; it does not say what they feel."),
    "between": ("Aranızdaki bağ.", "The bond between you."),
    "position": ("İş hayatındaki yerin.", "Where you stand at work."),
    "obstacle": ("Önündeki engel.", "What is in the way."),
    "path": ("Önerilen yol.", "The suggested path."),
    "significator": ("Konunun kalbi.", "The heart of the matter."),
    "crossing": ("Konuyu kesen ya da karmaşıklaştıran etki.", "What crosses or complicates the matter."),
    "foundation": ("Durumun kökü.", "The root of the situation."),
    "recent_past": ("Geride kalmakta olan.", "What is passing away."),
    "conscious": ("Bilinçli olarak istediğin ya da hedeflediğin.", "What you consciously want or aim for."),
    "near_future": ("Yaklaşan etki; kesin bir olay değil.", "What is approaching; not a fixed event."),
    "self": ("Bu konuda kendi duruşun.", "Your own stance in this matter."),
    "environment": ("Çevren: insanlar ve koşullar.", "Your surroundings: people and circumstances."),
    "hopes_fears": ("Umutların ve korkuların; çoğu zaman aynı şey.", "Your hopes and fears, often the same thing."),
    "overview": ("Genel tablo.", "The overall picture."),
    "past_influence": ("Etkisi süren geçmiş.", "The past that still shapes it."),
    "direction": ("Gidişat; kesin sonuç değil, eğilim.", "The direction; a tendency, not a fixed outcome."),
    "bond": ("Aranızdaki bağın doğası.", "The nature of the bond."),
    "hidden": ("Henüz görünmeyen ya da söylenmeyen.", "What is not yet seen or said."),
    "support": ("Sana destek olan.", "What supports you."),
    "home": ("Ev ve yakın çevre.", "Home and close circle."),
    "feeling": ("Durumun duygusal havası.", "The emotional weather of the situation."),
}


# ------------------------------------------------------------ shared shapes


def _single(deck: DeckType, code: str, tr_name: str, en_name: str, noun: str):
    return DivinationSpread(
        deck_type=deck,
        spread_code=code,
        spread_version=f"{deck.value}_{code}_v1",
        origin=SpreadOrigin.TRADITIONAL,
        names={"tr": tr_name, "en": en_name},
        positions=(
            position(
                1,
                "focus",
                "Odak",
                "Focus",
                f"The single {noun} that answers the question as a whole.",
                tr_description="Sorunun bütününe verilen tek yanıt.",
            ),
        ),
    )


def _three(
    deck: DeckType,
    code: str,
    tr_name: str,
    en_name: str,
    slots: tuple[tuple[str, str, str, str], ...],
    origin: SpreadOrigin = SpreadOrigin.TRADITIONAL,
    theme: str = "general",
):
    return DivinationSpread(
        deck_type=deck,
        spread_code=code,
        spread_version=f"{deck.value}_{code}_v1",
        origin=origin,
        theme=theme,
        names={"tr": tr_name, "en": en_name},
        positions=tuple(
            position(index, key, tr, en, role)
            for index, (key, tr, en, role) in enumerate(slots, start=1)
        ),
    )


def _spread(
    deck: DeckType,
    code: str,
    tr_name: str,
    en_name: str,
    slots: tuple[tuple[str, str, str, str, str, str], ...],
    *,
    theme: str = "general",
    origin: SpreadOrigin = SpreadOrigin.PRODUCT_DEFINED,
    allow_reversed: bool = True,
):
    """A spread whose every position carries a reader-facing description.

    Slot: (key, tr title, en title, AI role, tr description, en description).
    """
    return DivinationSpread(
        deck_type=deck,
        spread_code=code,
        spread_version=f"{deck.value}_{code}_v1",
        origin=origin,
        names={"tr": tr_name, "en": en_name},
        allow_reversed=allow_reversed,
        theme=theme,
        positions=tuple(
            position(
                index, key, tr, en, role,
                tr_description=tr_description,
                en_description=en_description,
            )
            for index, (key, tr, en, role, tr_description, en_description)
            in enumerate(slots, start=1)
        ),
    )


PAST_PRESENT_FUTURE = (
    ("past", "Geçmiş", "Past", "What has already shaped the situation."),
    ("present", "Şimdi", "Present", "Where the situation stands now."),
    (
        "future",
        "Gidişat",
        "Where this is heading",
        "The direction the situation is currently tending in - a tendency, "
        "not a fixed outcome.",
    ),
)

SITUATION_ACTION_OUTCOME = (
    ("situation", "Durum", "Situation", "What is actually going on."),
    ("action", "Eylem", "Action", "What the person can do about it."),
    (
        "outcome",
        "Olası Sonuç",
        "Likely direction",
        "Where that action tends to lead - a tendency, never a prediction.",
    ),
)

SITUATION_CHALLENGE_ADVICE = (
    ("situation", "Durum", "Situation", "What is actually going on."),
    ("challenge", "Zorluk", "Challenge", "What makes this difficult."),
    ("advice", "Öneri", "Advice", "What this reading suggests considering."),
)


# ------------------------------------------------------------------- tarot

TAROT_SPREADS = [
    _single(DeckType.TAROT, "single_card", "Tek Kart", "Single Card", "card"),
    _three(
        DeckType.TAROT,
        "three_card",
        "Üç Kart",
        "Three Card",
        (
            ("first", "Birinci", "First", "The first thread of the situation."),
            ("second", "İkinci", "Second", "The second thread."),
            ("third", "Üçüncü", "Third", "The third thread."),
        ),
    ),
    _three(
        DeckType.TAROT,
        "past_present_future",
        "Geçmiş - Şimdi - Gidişat",
        "Past - Present - Direction",
        PAST_PRESENT_FUTURE,
    ),
    _three(
        DeckType.TAROT,
        "situation_action_outcome",
        "Durum - Eylem - Sonuç",
        "Situation - Action - Outcome",
        SITUATION_ACTION_OUTCOME,
    ),
    _three(
        DeckType.TAROT,
        "love_three_card",
        "Aşk Üçlemesi",
        "Love Three Card",
        (
            ("you", "Sen", "You", "What the querent brings to the connection."),
            (
                "them",
                "Diğer Kişi",
                "The other person",
                "The dynamic the other person brings, read symbolically. This "
                "position never states what that person is doing or feeling.",
            ),
            (
                "between",
                "Aranızdaki",
                "Between you",
                "The dynamic between them, rather than either individual.",
            ),
        ),
        origin=SpreadOrigin.PRODUCT_DEFINED,
        theme="love",
    ),
    _three(
        DeckType.TAROT,
        "career_three_card",
        "Kariyer Üçlemesi",
        "Career Three Card",
        (
            ("position", "Mevcut Durum", "Current position", "Where work stands."),
            ("obstacle", "Engel", "Obstacle", "What is in the way."),
            ("path", "Yol", "Path", "What this reading suggests considering."),
        ),
        origin=SpreadOrigin.PRODUCT_DEFINED,
        theme="career",
    ),
    _spread(
        DeckType.TAROT, "situation_obstacle_advice", "Durum - Engel - Tavsiye",
        "Situation - Obstacle - Advice",
        (
            ("situation", "Durum", "Situation", "What is actually going on.",
             "Konunun şu anki gerçek hali.", "Where the matter truly stands."),
            ("obstacle", "Engel", "Obstacle", "What stands in the way.",
             "İlerlemeyi zorlaştıran etken.", "What makes progress harder."),
            ("advice", "Tavsiye", "Advice", "What this reading suggests considering.",
             "Kartların önerdiği yaklaşım.", "The approach the cards suggest."),
        ),
    ),
    _spread(
        DeckType.TAROT, "mind_body_spirit", "Zihin - Beden - Ruh", "Mind - Body - Spirit",
        (
            ("mind", "Zihin", "Mind", "The state of the querent's thoughts.",
             "Düşüncelerinin ve zihinsel yükünün durumu.", "The state of your thoughts."),
            ("body", "Beden", "Body", "Energy, rest and the physical rhythm - never a health claim.",
             "Enerjin, dinlenme ve günlük ritmin (sağlık yorumu değildir).",
             "Your energy, rest and daily rhythm (not a health reading)."),
            ("spirit", "Ruh", "Spirit", "Inner meaning, faith and what nourishes the querent.",
             "Seni içten besleyen anlam ve inanç.", "The meaning and faith that nourish you."),
        ),
        theme="spiritual",
    ),
    _spread(
        DeckType.TAROT, "five_card", "Beş Kart", "Five Card",
        (
            ("current_situation", "Mevcut Durum", "Current situation", "The heart of the matter now.",
             "Konunun bugünkü özü.", "The heart of the matter today."),
            ("past_influence", "Geçmişin Etkisi", "Past influence", "What from the past still shapes it.",
             "Hâlâ etkisini sürdüren geçmiş.", "What from the past still shapes it."),
            ("hidden_influence", "Görünmeyen Etki", "Hidden influence", "What has not been noticed or said.",
             "Fark edilmeyen ya da konuşulmayan etken.", "What has gone unnoticed or unsaid."),
            ("advice", "Tavsiye", "Advice", "What this reading suggests considering.",
             "Kartların önerdiği tutum.", "The attitude the cards suggest."),
            ("possible_outcome", "Olası Sonuç", "Possible outcome",
             "Where things tend if nothing changes - a tendency, never a fixed outcome.",
             "Hiçbir şey değişmezse gidişat; kesin bir sonuç değildir.",
             "Where things tend if nothing changes; not a fixed outcome."),
        ),
    ),
    _spread(
        DeckType.TAROT, "love_spread", "Aşk Açılımı", "Love Spread",
        (
            ("you", "Sen", "You", "What the querent brings to love now.",
             "Aşka şu an getirdiğin enerji.", "The energy you bring to love now."),
            ("other", "Karşı Taraf", "The other side",
             "The dynamic the other person brings, read symbolically. Never states what they feel or do.",
             "Karşı tarafın ilişkiye kattığı dinamik; onun ne hissettiğini söylemez.",
             "The dynamic the other side brings; it does not say what they feel."),
            ("bond", "Bağ", "The bond", "What lives between them.",
             "Aranızdaki bağın doğası.", "The nature of the bond between you."),
            ("strength", "Güçlü Yan", "Strength", "What supports the connection.",
             "İlişkiyi taşıyan güç.", "What carries the connection."),
            ("challenge", "Zorluk", "Challenge", "What strains it.",
             "İlişkiyi zorlayan konu.", "What strains the connection."),
            ("advice", "Tavsiye", "Advice", "What this reading suggests considering.",
             "Aşk için önerilen yaklaşım.", "The suggested approach in love."),
            ("direction", "Gidişat", "Direction", "Where the connection tends; not a prediction.",
             "Bağın eğilimi; kehanet değildir.", "Where the bond tends; not a prediction."),
        ),
        theme="love",
    ),
    _spread(
        DeckType.TAROT, "career_spread", "Kariyer Açılımı", "Career Spread",
        (
            ("current_role", "Mevcut Konum", "Current role", "Where work stands.",
             "İş hayatında bulunduğun yer.", "Where you stand at work."),
            ("strengths", "Güçlü Yönler", "Strengths", "What the querent can rely on.",
             "Güvenebileceğin yeteneklerin.", "The abilities you can rely on."),
            ("obstacle", "Engel", "Obstacle", "What is in the way.",
             "Önündeki engel.", "What is in the way."),
            ("hidden_factor", "Görünmeyen Etken", "Hidden factor", "What is not yet visible at work.",
             "İş ortamında henüz görünmeyen etken.", "What is not yet visible at work."),
            ("advice", "Tavsiye", "Advice", "What this reading suggests considering.",
             "Kariyer için önerilen adım.", "The suggested career step."),
            ("direction", "Gidişat", "Direction", "Where work tends; not a prediction.",
             "İşin eğilimi; kesin sonuç değildir.", "Where work tends; not a fixed outcome."),
        ),
        theme="career",
    ),
    _spread(
        DeckType.TAROT, "money_spread", "Para Açılımı", "Money Spread",
        (
            ("current_flow", "Mevcut Akış", "Current flow", "How resources move now.",
             "Kaynaklarının bugünkü akışı.", "How your resources move today."),
            ("drain", "Kaçak", "What drains", "What uses up resources.",
             "Kaynaklarını tüketen alışkanlık ya da durum.", "The habit or situation that drains resources."),
            ("support", "Destek", "What supports", "What strengthens the position.",
             "Maddi durumunu güçlendiren etken.", "What strengthens your position."),
            ("advice", "Tavsiye", "Advice", "What this reading suggests considering - never financial advice.",
             "Kartların önerdiği tutum (finansal tavsiye değildir).",
             "The attitude the cards suggest (not financial advice)."),
            ("direction", "Gidişat", "Direction", "Where things tend; not a prediction.",
             "Maddi eğilim; kesin sonuç değildir.", "The material tendency; not a fixed outcome."),
        ),
        theme="money",
    ),
    _spread(
        DeckType.TAROT, "spiritual_guide", "Ruhsal Rehber", "Spiritual Guide",
        (
            ("where_you_are", "Bulunduğun Yer", "Where you are", "The querent's inner state now.",
             "İç yolculuğunda şu an bulunduğun nokta.", "Where you are on your inner path."),
            ("lesson", "Ders", "Lesson", "What this period is teaching.",
             "Bu dönemin sana öğrettiği.", "What this period teaches you."),
            ("release", "Bırak", "Release", "What is ready to be let go.",
             "Bırakmaya hazır olduğun şey.", "What you are ready to let go."),
            ("nurture", "Besle", "Nurture", "What is worth nurturing.",
             "Büyütmeye değer olan.", "What is worth nurturing."),
            ("guidance", "Rehberlik", "Guidance", "The reading's overall counsel.",
             "Açılımın genel rehberliği.", "The overall guidance of the reading."),
        ),
        theme="spiritual",
    ),
    _spread(
        DeckType.TAROT, "question_insight", "Soruya Özel", "Question Insight",
        (
            ("core", "Sorunun Özü", "Core of the question", "What the question is really about.",
             "Sorunun gerçekte neyle ilgili olduğu.", "What the question is really about."),
            ("helps", "Yardım Eden", "What helps", "What works in the querent's favour.",
             "Lehine çalışan etken.", "What works in your favour."),
            ("consider", "Dikkat Edilecek", "What to consider", "What deserves attention before acting.",
             "Harekete geçmeden önce dikkat edilecek nokta.", "What deserves attention before acting."),
        ),
    ),
    DivinationSpread(
        deck_type=DeckType.TAROT,
        spread_code="celtic_cross",
        spread_version="tarot_celtic_cross_v1",
        origin=SpreadOrigin.TRADITIONAL,
        names={"tr": "Kelt Haçı", "en": "Celtic Cross"},
        positions=(
            position(1, "significator", "Mevcut Durum", "The present",
                     "The heart of the matter as it stands."),
            position(2, "crossing", "Engel", "The crossing",
                     "What crosses or complicates the matter, for better or "
                     "worse."),
            position(3, "foundation", "Temel", "The foundation",
                     "The root of the situation; what underlies it."),
            position(4, "recent_past", "Yakın Geçmiş", "Recent past",
                     "What is passing out of the situation."),
            position(5, "conscious", "Bilinçli Hedef", "Conscious aim",
                     "What the querent is aware of wanting or aiming at."),
            position(6, "near_future", "Yakın Gelecek", "Near future",
                     "What is coming into the situation - a tendency, not a "
                     "fixed event."),
            position(7, "self", "Kendisi", "The querent",
                     "How the querent is positioned in this matter."),
            position(8, "environment", "Çevre", "Environment",
                     "The setting: people and circumstances around it."),
            position(9, "hopes_fears", "Umutlar ve Korkular", "Hopes and fears",
                     "What the querent hopes for and fears, often the same "
                     "thing."),
            position(10, "outcome", "Gidişat", "Direction",
                     "Where the whole reading tends. A direction to reflect "
                     "on, never a settled outcome."),
        ),
    ),
]


# -------------------------------------------------------------------- rune

RUNE_SPREADS = [
    _single(DeckType.RUNE, "single_rune", "Tek Rün", "Single Rune", "rune"),
    _three(
        DeckType.RUNE,
        "three_rune",
        "Üç Rün",
        "Three Rune",
        (
            ("first", "Birinci", "First", "The first thread of the situation."),
            ("second", "İkinci", "Second", "The second thread."),
            ("third", "Üçüncü", "Third", "The third thread."),
        ),
    ),
    _three(
        DeckType.RUNE,
        "past_present_future",
        "Geçmiş - Şimdi - Gidişat",
        "Past - Present - Direction",
        PAST_PRESENT_FUTURE,
    ),
    _three(
        DeckType.RUNE,
        "situation_challenge_advice",
        "Durum - Zorluk - Öneri",
        "Situation - Challenge - Advice",
        SITUATION_CHALLENGE_ADVICE,
    ),
    DivinationSpread(
        deck_type=DeckType.RUNE,
        spread_code="five_rune_cross",
        spread_version="rune_five_rune_cross_v1",
        origin=SpreadOrigin.TRADITIONAL,
        names={"tr": "Beş Rün Haçı", "en": "Five Rune Cross"},
        positions=(
            position(1, "overview", "Genel Durum", "Overview",
                     "The situation as a whole."),
            position(2, "challenge", "Zorluk", "Challenge",
                     "What resists or complicates it."),
            position(3, "past_influence", "Geçmiş Etki", "Past influence",
                     "What has been shaping it."),
            position(4, "advice", "Öneri", "Advice",
                     "What this reading suggests considering."),
            position(5, "direction", "Gidişat", "Direction",
                     "Where it tends. A tendency, not a fixed outcome."),
        ),
    ),
    _spread(
        DeckType.RUNE, "problem_hidden_solution", "Sorun - Görünmeyen Etki - Çözüm",
        "Problem - Hidden Influence - Solution",
        (
            ("problem", "Sorun", "Problem", "The difficulty as it presents itself.",
             "Karşına çıkan sorun.", "The difficulty in front of you."),
            ("hidden", "Görünmeyen Etki", "Hidden influence", "What works beneath the surface.",
             "Yüzeyin altında çalışan etki.", "What works beneath the surface."),
            ("solution", "Çözüm", "Solution", "The approach this reading suggests.",
             "Rünlerin önerdiği yaklaşım.", "The approach the runes suggest."),
        ),
    ),
    _spread(
        DeckType.RUNE, "love_rune", "Aşk Rün Açılımı", "Love Runes",
        (
            ("you", "Sen", "You", "What the querent brings to love.",
             "Aşka getirdiğin enerji.", "The energy you bring to love."),
            ("bond", "Bağ", "The bond", "What lives between the two, read symbolically.",
             "Aranızdaki bağın doğası; karşı tarafın duygularını söylemez.",
             "The nature of the bond; it does not state the other's feelings."),
            ("counsel", "Öğüt", "Counsel", "What this reading suggests considering.",
             "Aşk için rünlerin öğüdü.", "The runes' counsel for love."),
        ),
        theme="love",
    ),
    _spread(
        DeckType.RUNE, "career_rune", "Kariyer Rün Açılımı", "Career Runes",
        (
            ("position", "Mevcut Konum", "Current position", "Where work stands.",
             "İş hayatındaki yerin.", "Where you stand at work."),
            ("obstacle", "Engel", "Obstacle", "What is in the way.",
             "Önündeki engel.", "What is in the way."),
            ("counsel", "Öğüt", "Counsel", "What this reading suggests considering.",
             "Kariyer için rünlerin öğüdü.", "The runes' counsel for work."),
        ),
        theme="career",
    ),
    _spread(
        DeckType.RUNE, "question_rune", "Soruya Özel Rün", "Question Runes",
        (
            ("core", "Sorunun Özü", "Core of the question", "What the question is really about.",
             "Sorunun gerçekte neyle ilgili olduğu.", "What the question is really about."),
            ("helps", "Yardım Eden", "What helps", "What works in the querent's favour.",
             "Lehine çalışan etken.", "What works in your favour."),
            ("consider", "Dikkat Edilecek", "What to consider", "What deserves attention.",
             "Dikkat etmen gereken nokta.", "What deserves your attention."),
        ),
    ),
]


# ------------------------------------------------------------------ katina
#
# Every Katina spread is PRODUCT_DEFINED. No documented Katina layout could be
# verified, so none of these claims to be traditional - saying otherwise would
# be inventing a methodology and attributing it to a culture.

KATINA_SPREADS = [
    DivinationSpread(
        deck_type=DeckType.KATINA,
        spread_code="single_card",
        spread_version="katina_single_card_v1",
        origin=SpreadOrigin.PRODUCT_DEFINED,
        names={"tr": "Tek Kart", "en": "Single Card"},
        allow_reversed=False,
        positions=(
            position(1, "focus", "Odak", "Focus",
                     "The single card that answers the question as a whole."),
        ),
    ),
    DivinationSpread(
        deck_type=DeckType.KATINA,
        spread_code="three_card",
        spread_version="katina_three_card_v1",
        origin=SpreadOrigin.PRODUCT_DEFINED,
        names={"tr": "Üç Kart", "en": "Three Card"},
        allow_reversed=False,
        positions=tuple(
            position(index, key, tr, en, role)
            for index, (key, tr, en, role) in enumerate(
                PAST_PRESENT_FUTURE, start=1
            )
        ),
    ),
    DivinationSpread(
        deck_type=DeckType.KATINA,
        spread_code="relationship",
        spread_version="katina_relationship_v1",
        origin=SpreadOrigin.PRODUCT_DEFINED,
        names={"tr": "İlişki Açılımı", "en": "Relationship"},
        allow_reversed=False,
        theme="relationship",
        positions=(
            position(1, "you", "Sen", "You",
                     "What the querent brings to the connection."),
            position(2, "them", "Diğer Kişi", "The other person",
                     "The dynamic the other person brings, read symbolically. "
                     "This position never states what that person is doing or "
                     "feeling."),
            position(3, "bond", "Bağ", "The bond",
                     "What is between them, rather than either individual."),
            position(4, "obstacle", "Engel", "Obstacle",
                     "What makes this harder."),
            position(5, "direction", "Gidişat", "Direction",
                     "Where the connection tends. A tendency, not a "
                     "prediction."),
        ),
    ),
    DivinationSpread(
        deck_type=DeckType.KATINA,
        spread_code="seven_card",
        spread_version="katina_seven_card_v1",
        origin=SpreadOrigin.PRODUCT_DEFINED,
        names={"tr": "Yedi Kart", "en": "Seven Card"},
        allow_reversed=False,
        positions=(
            position(1, "situation", "Durum", "Situation",
                     "What is actually going on."),
            position(2, "past", "Geçmiş", "Past",
                     "What has shaped it."),
            position(3, "present", "Şimdi", "Present",
                     "Where it stands now."),
            position(4, "hidden", "Görünmeyen", "What is not visible",
                     "What has not been said or noticed yet."),
            position(5, "support", "Destek", "Support",
                     "What helps here."),
            position(6, "obstacle", "Engel", "Obstacle",
                     "What is in the way."),
            position(7, "direction", "Gidişat", "Direction",
                     "Where it tends. A tendency, not a settled outcome."),
        ),
    ),
    DivinationSpread(
        deck_type=DeckType.KATINA,
        spread_code="nine_card",
        spread_version="katina_nine_card_v1",
        origin=SpreadOrigin.PRODUCT_DEFINED,
        names={"tr": "Dokuz Kart", "en": "Nine Card"},
        allow_reversed=False,
        positions=(
            position(1, "self", "Kendisi", "The querent",
                     "How the querent stands in this matter."),
            position(2, "home", "Ev ve Yakın Çevre", "Home and close circle",
                     "The immediate surroundings."),
            position(3, "feeling", "Duygu", "Feeling",
                     "The emotional weather of the situation."),
            position(4, "past", "Geçmiş", "Past", "What has shaped it."),
            position(5, "present", "Şimdi", "Present", "Where it stands."),
            position(6, "hidden", "Görünmeyen", "What is not visible",
                     "What has not been said or noticed yet."),
            position(7, "obstacle", "Engel", "Obstacle", "What resists."),
            position(8, "support", "Destek", "Support", "What helps."),
            position(9, "direction", "Gidişat", "Direction",
                     "Where it tends. A tendency, never a settled outcome."),
        ),
    ),
    _spread(
        DeckType.KATINA, "relationship_three", "3 Kart İlişki Açılımı", "Three Card Relationship",
        (
            ("you", "Sen", "You", "What the querent brings to the connection.",
             "İlişkiye getirdiğin enerji.", "The energy you bring."),
            ("other", "Karşı Taraf", "The other side",
             "The dynamic the other person brings, read symbolically. Never states what they feel or do.",
             "Karşı tarafın ilişkiye kattığı dinamik; ne hissettiğini söylemez.",
             "The dynamic the other side brings; it does not say what they feel."),
            ("bond", "Bağ", "The bond", "What is between them.",
             "Aranızdaki bağ.", "The bond between you."),
        ),
        theme="relationship", allow_reversed=False,
    ),
    _spread(
        DeckType.KATINA, "love_future", "Aşk Geleceği", "Love Ahead",
        (
            ("now", "Şimdiki Duygu", "Current feeling", "The querent's emotional state in love now.",
             "Aşkta şu anki duygusal hâlin.", "Your emotional state in love now."),
            ("growing", "Büyüyen", "What grows", "What is developing.",
             "Gelişmekte olan duygu ya da fırsat.", "The feeling or chance that is growing."),
            ("test", "Sınav", "What tests it", "What will ask for patience.",
             "Sabır isteyecek konu.", "What will ask for patience."),
            ("advice", "Tavsiye", "Advice", "What this reading suggests considering.",
             "Önerilen tutum.", "The suggested attitude."),
            ("direction", "Gidişat", "Direction", "Where love tends; not a prediction.",
             "Aşkın eğilimi; kehanet değildir.", "Where love tends; not a prediction."),
        ),
        theme="love", allow_reversed=False,
    ),
    _spread(
        DeckType.KATINA, "partner_feelings", "Partnerin Duyguları", "Partner's Feelings",
        (
            ("climate", "Duygusal İklim", "Emotional climate",
             "The emotional climate around the connection, read symbolically. It never claims to know what the other person actually feels.",
             "İlişkinin etrafındaki duygusal iklim. Kartlar karşı tarafın gerçekte ne hissettiğini bilemez; sembolik bir yansımadır.",
             "The emotional climate around the connection. The cards cannot know what the other person actually feels."),
            ("shown", "Görünen", "What shows", "What is visible in how the connection is lived.",
             "İlişkide dışa yansıyan taraf.", "What shows in how the connection is lived."),
            ("unspoken", "Söylenmeyen", "What is unspoken", "Themes that have not been voiced.",
             "Henüz dile gelmemiş temalar.", "Themes not yet voiced."),
        ),
        theme="relationship", allow_reversed=False,
    ),
    _spread(
        DeckType.KATINA, "relationship_future", "İlişkinin Geleceği", "The Relationship Ahead",
        (
            ("now", "Şimdi", "Now", "Where the relationship stands.",
             "İlişkinin bugünkü hâli.", "Where the relationship stands."),
            ("strength", "Güç", "Strength", "What holds it together.",
             "İlişkiyi bir arada tutan.", "What holds it together."),
            ("challenge", "Zorluk", "Challenge", "What strains it.",
             "İlişkiyi zorlayan.", "What strains it."),
            ("turning_point", "Dönüm Noktası", "Turning point", "A theme likely to become decisive.",
             "Belirleyici olabilecek tema.", "A theme likely to become decisive."),
            ("direction", "Gidişat", "Direction", "Where it tends; not a prediction.",
             "İlişkinin eğilimi; kesin sonuç değildir.", "Where it tends; not a fixed outcome."),
        ),
        theme="relationship", allow_reversed=False,
    ),
    _spread(
        DeckType.KATINA, "ex_partner", "Eski Sevgili Açılımı", "Former Partner",
        (
            ("remains", "Kalan", "What remains", "What still lingers from the past relationship.",
             "Geçmiş ilişkiden hâlâ süren duygu.", "What still lingers from that relationship."),
            ("lesson", "Ders", "Lesson", "What it taught.",
             "O ilişkinin sana öğrettiği.", "What it taught you."),
            ("release", "Bırakılacak", "To release", "What is ready to be let go.",
             "Bırakmaya hazır olduğun.", "What you are ready to let go."),
            ("contact_theme", "Temas Teması", "Contact theme",
             "The symbolic theme of any renewed contact - never a prediction of reunion.",
             "Yeniden temasın sembolik teması; barışma kehaneti değildir.",
             "The symbolic theme of renewed contact; not a prediction of reunion."),
            ("direction", "Gidişat", "Direction", "Where the querent's path tends.",
             "Senin yolunun eğilimi.", "Where your own path tends."),
        ),
        theme="relationship", allow_reversed=False,
    ),
    _spread(
        DeckType.KATINA, "new_love", "Yeni Aşk Açılımı", "New Love",
        (
            ("readiness", "Hazırlık", "Readiness", "How ready the querent is for someone new.",
             "Yeni birine ne kadar hazır olduğun.", "How ready you are for someone new."),
            ("attracts", "Çeken", "What attracts", "What draws connection in.",
             "Yakınlık çeken yönün.", "What draws connection to you."),
            ("where", "Nerede", "Where", "The kind of setting that favours meeting - a theme, not a place.",
             "Tanışmayı destekleyen ortamın teması; kesin bir yer değildir.",
             "The kind of setting that favours meeting; not a specific place."),
            ("watch", "Dikkat", "Watch for", "What to be mindful of.",
             "Dikkat etmen gereken.", "What to be mindful of."),
            ("direction", "Gidişat", "Direction", "Where it tends; not a prediction.",
             "Eğilim; kehanet değildir.", "The tendency; not a prediction."),
        ),
        theme="love", allow_reversed=False,
    ),
    _spread(
        DeckType.KATINA, "question_katina", "Soruya Özel Katina", "Question Katina",
        (
            ("core", "Sorunun Özü", "Core of the question", "What the question is really about.",
             "Sorunun gerçekte neyle ilgili olduğu.", "What the question is really about."),
            ("helps", "Yardım Eden", "What helps", "What works in the querent's favour.",
             "Lehine çalışan etken.", "What works in your favour."),
            ("consider", "Dikkat Edilecek", "What to consider", "What deserves attention.",
             "Dikkat etmen gereken nokta.", "What deserves your attention."),
        ),
        allow_reversed=False,
    ),
]


REGISTRY: dict[DeckType, dict[str, DivinationSpread]] = {
    DeckType.TAROT: {spread.spread_code: spread for spread in TAROT_SPREADS},
    DeckType.RUNE: {spread.spread_code: spread for spread in RUNE_SPREADS},
    DeckType.KATINA: {spread.spread_code: spread for spread in KATINA_SPREADS},
}


class UnknownSpread(KeyError):
    """A spread code that this deck does not have."""


def get_spread(deck_type: DeckType, spread_code: str) -> DivinationSpread:
    """Look up a spread, refusing a deck/spread mismatch.

    A tarot spread requested for the rune deck is not "close enough" - the
    positions mean different things and the counts differ - so it is an error
    rather than a silent substitution.
    """
    try:
        return REGISTRY[deck_type][spread_code]
    except KeyError as exc:
        raise UnknownSpread(
            f"{deck_type.value} has no spread '{spread_code}'"
        ) from exc


def spreads_for(deck_type: DeckType) -> list[DivinationSpread]:
    return list(REGISTRY[deck_type].values())


def all_spread_versions() -> dict[str, str]:
    return {
        f"{deck.value}:{code}": spread.spread_version
        for deck, spreads in REGISTRY.items()
        for code, spread in spreads.items()
    }
