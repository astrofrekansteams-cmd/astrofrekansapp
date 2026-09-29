"""Prompt registry.

Prompts are versioned artefacts, not strings scattered through services. Every
generation records the ``prompt_version`` it used, so changing a prompt
produces *new* output going forward and never silently rewrites a report a
user has already read.

One prompt per use case, with the output language passed as a parameter -
three translated copies of every prompt would drift apart within a month.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.ai import ContextType, Locale, ReportType, UseCase
from app.services.ai import safety


@dataclass(slots=True, frozen=True)
class Prompt:
    name: str
    version: str
    task: str

    @property
    def id(self) -> str:
        return f"{self.name}:{self.version}"

    def instructions(self, locale: Locale, *, extra: str = "") -> str:
        """Developer layer: shared rules first, then the task."""
        task_block = self.task if not extra else f"{self.task}\n\n{extra}"
        return safety.base_instructions(locale.language_name, extra=task_block)


CHAT = Prompt(
    name="astro_chat",
    version="astro_chat_v1",
    task="""\
TASK
Answer the person's question using only the astrological material in the
context. Keep it conversational: a few short paragraphs, no headings, no
bullet lists unless the person asked for a list.

Name the specific factors you are drawing on in plain language ("Saturn is
crossing your seventh house") and list the factor_id values you used in
source_factor_ids. If the context does not contain what the question needs,
say so plainly and offer what the material does cover.""",
)

NATAL_REPORT = Prompt(
    name="natal_report",
    version="natal_report_v1",
    task="""\
TASK
Write a natal chart reading from the supplied chart. Cover the person as a
whole: the Sun, Moon and Ascendant together, the dominant element and planet,
the strongest aspects, and the houses that carry the most weight.

Sections should read as a portrait, not a list of placements. Every section
cites the factors it rests on.""",
)

TRANSIT_INTERPRETATION = Prompt(
    name="transit_interpretation",
    version="transit_interpretation_v1",
    task="""\
TASK
Explain the transits in the context: what each one touches in the natal chart,
when the engine says it is exact, and how long its window runs. Use only the
dates supplied - never estimate or round a date yourself.

Where a transit perfects more than once, say so: that is one influence with
several passes, not several influences.""",
)

DAILY_INTERPRETATION = Prompt(
    name="daily_interpretation",
    version="daily_interpretation_v1",
    task="""\
TASK
Write the day's reading from the supplied scores, influences and important
hours. Lead with what actually stands out rather than walking the categories
in order. Mention an important hour only if the context supplies it, with the
reason attached.""",
)

WEEKLY_INTERPRETATION = Prompt(
    name="weekly_interpretation",
    version="weekly_interpretation_v1",
    task="""\
TASK
Write the week ahead from the supplied material: the contacts that perfect
during the week, the Moon's movement, any stations or ingresses, and the
scored themes. Give the week a shape - where the emphasis falls and when -
rather than seven daily summaries.""",
)

MONTHLY_FORECAST = Prompt(
    name="monthly_forecast",
    version="monthly_forecast_v1",
    task="""\
TASK
Write the month from the supplied themes, key periods, important dates,
retrogrades, moon events and house activations. Key periods are the backbone:
give each one its dates, its theme and what it asks for.""",
)

ANNUAL_FORECAST = Prompt(
    name="annual_forecast",
    version="annual_forecast_v1",
    task="""\
TASK
Write the year from the supplied outer-planet transits, retrograde periods,
eclipses, Jupiter and Saturn house movements, key periods and solar return
summary. A year is made of slow movements: describe arcs and chapters, not a
day-by-day account.""",
)

HORARY_INTERPRETATION = Prompt(
    name="horary_interpretation",
    version="horary_interpretation_v1",
    task="""\
TASK
Explain the horary chart in the context for someone who does not know the
technique. Identify the querent's and the quesited's significators and say
what each one is doing: its dignity, its house, its condition. Describe the
receptions, the aspects between the significators, and whether the engine
found perfection or obstruction.

Judgement, stated as it must be: describe the traditional indications as
supportive, challenging, mixed or unclear, and stop there. No verdict, no
probability, no date for an outcome.

Techniques listed under not_implemented were not examined. Do not mention them
as present or absent, and draw no conclusion from them.""",
)

SYNASTRY_REPORT = Prompt(
    name="synastry_report",
    version="synastry_report_v1",
    task="""\
TASK
Write a synastry reading from the supplied inter-aspects, house overlays and
theme scores. Keep the overlays directional: "her Venus falls in his seventh"
is a different statement from the reverse, and both are in the context.

The overall score is an astrological factor index. Explain what it measures
and never convert it into a chance, a percentage of success, or advice about
whether to stay together.""",
)

COMPOSITE_REPORT = Prompt(
    name="composite_report",
    version="composite_report_v1",
    task="""\
TASK
Write a composite chart reading. The composite is a chart of midpoints - it
describes the relationship as a third thing, not either person, and it is not
a moment that existed in the sky. Say so once, plainly.

If the context lists ambiguous midpoints, treat those points as uncertain
rather than interpreting them as settled.""",
)

DAVISON_REPORT = Prompt(
    name="davison_report",
    version="davison_report_v1",
    task="""\
TASK
Write a Davison chart reading. Unlike a composite, this is a real chart for a
real instant and place - the midpoint in time and space between the two
births. Interpret it as a chart in its own right.

Report any warning in the context, including an antipodal-birthplace warning,
rather than passing over it.""",
)

# ------------------------------------------------- compatibility readings
#
# The short readings shown right under a compatibility result. One shared
# section plan (so the app can lay the cards out), three different framings:
# synastry is two people meeting, the composite is the relationship as a
# third thing, the Davison is a real chart of a moment and place.

COMPATIBILITY_READING_RULES = """

SECTIONS
Return exactly these sections, in this order, with these keys:
  overview       - the relationship's overall dynamic, 3-5 sentences
  love           - love and attraction
  communication  - how the two communicate
  emotional      - the emotional bond
  passion        - passion and physical chemistry
  challenges     - the areas that ask for effort
  strengths      - what supports the relationship
  long_term      - the long-term dynamic, stated cautiously
  summary        - a short closing summary in plain language
Titles are short, in the output language, without emoji. Each body is 2-5
sentences of plain, warm language for someone who knows no astrology.

GROUNDING
Use only the factors in the context. Never compute or name a planet, sign,
house, aspect, degree or orb that the context does not contain. When the
context has nothing for a section, say briefly that this calculation does not
emphasise that area - do not fill it with generic astrology.
Every section except summary cites the factor_id values it rests on; a
section that genuinely has no specific factor sets general_summary to true.
Mention the key factors in plain words inside the text as well ("Merkür ile
Satürn arasındaki kare..."), using the output language's astrology names.

HOW TO SPEAK
This is reflection, not prediction. Never say the relationship will or will
not last, never give a percentage, probability or "compatibility rate", never
predict marriage, separation, children or dates, and never describe what one
person secretly thinks or intends. Prefer "may", "can", "tends to", "worth
paying attention to". If a score is in the context, it is an astrological
factor index, not a chance of success - do not restate it as one."""

SYNASTRY_READING = Prompt(
    name="synastry_reading",
    version="synastry_reading_v1",
    task="""TASK
Write a short synastry reading: how these two people affect each other. The
factors are contacts between person A's chart and person B's chart and house
overlays, which are directional - "A's Venus in B's seventh house" is a
different statement from the reverse, so keep who does what to whom.
Love and passion draw mainly on Venus, Mars, Moon and the angles
(ASC/DSC/MC/IC); communication on Mercury; the emotional bond on Moon and
Venus; challenges on hard contacts (square, opposition) and Saturn; long-term
on Saturn, the nodes and repeated patterns - whenever the context has them."""
    + COMPATIBILITY_READING_RULES,
)

COMPOSITE_READING = Prompt(
    name="composite_reading",
    version="composite_reading_v1",
    task="""TASK
Write a short composite chart reading. The composite is a chart of midpoints:
it describes the relationship itself as a third thing, not either person, and
it is not a moment that existed in the sky - say so once, plainly, in the
overview. Speak about "the relationship" and "this bond", not "you" and
"them". Read planets by sign and house and the aspects between composite
planets. If the context lists ambiguous midpoints, treat those points as
uncertain. If angles or houses are missing because a birth time is unknown,
say that those parts could not be calculated rather than guessing them."""
    + COMPATIBILITY_READING_RULES,
)

DAVISON_READING = Prompt(
    name="davison_reading",
    version="davison_reading_v1",
    task="""TASK
Write a short Davison chart reading. Unlike a composite, the Davison chart is
a real chart for a real instant and place - the midpoint in time and space
between the two births. Read it as the shared chart of the relationship's
common rhythm: its time-and-place foundation, how the bond tends to move and
mature. Say once, plainly, what a Davison chart is. Report any warning in the
context (for example an antipodal-birthplace warning) instead of passing over
it."""
    + COMPATIBILITY_READING_RULES,
)

# ---------------------------------------------------------------- divination
#
# The shared rule for all three: the draw already happened. The backend
# shuffled, dealt, decided orientation and assigned positions. The model reads
# what came out and may not change any of it.

DIVINATION_RULES = """

WHAT A DRAW IS
The cards or runes in the context have already been drawn by the application,
using a cryptographically secure random source. The draw is a completed fact.

You must not: name an item that is not in the context, change an orientation,
move an item to a different position, add a position the spread does not have,
or claim the deal could have gone differently. If the context says a card is
upright, it is upright.

The meanings supplied with each item are this deck's reference text. Use them
as the basis of your reading; do not substitute meanings from memory and do
not contradict them. Where the context marks a meaning as product-defined
rather than traditional, present it as this deck's stated meaning - never as
inherited tradition.

Read the item together with its position: a card in the "obstacle" slot says
something different from the same card in the "advice" slot. That relationship
is the reading.

HOW TO SPEAK ABOUT WHAT IT MEANS
A drawn card is a prompt for reflection, not evidence about the future. Never
say something will certainly happen, give a date for a life event, attach a
probability, or state what another person is doing, feeling or intending. Say
"this card traditionally points to...", "this combination may emphasise...",
"something worth sitting with here is...".

If the context marks the reading as a repeat of a recent question, do not
narrate it as fate having changed or as the cards correcting themselves. Say
plainly that this is a fresh draw of the same question and read it on its own
terms."""

TAROT_INTERPRETATION = Prompt(
    name="tarot_interpretation",
    version="tarot_interpretation_v1",
    task="""TASK
Interpret the tarot cards in the context, in their positions.

Give each drawn card its own passage: what the card carries, what the position
asks of it, and what the two together suggest. Then draw the spread together -
repeated suits, the balance of major and minor arcana, reversals - as one
reading rather than a list of cards.

Explain any term the first time it appears; assume the reader knows no tarot.
If a question was asked, answer it through the cards that were actually drawn,
and say so plainly when the spread does not speak to it."""
    + DIVINATION_RULES,
)

RUNE_INTERPRETATION = Prompt(
    name="rune_interpretation",
    version="rune_interpretation_v1",
    task="""TASK
Interpret the runes in the context, in their positions.

Give each rune its own passage: its name and sense, what the position asks,
and what the two together suggest. Then read the cast as a whole - which
aettir appear, whether the runes lean towards movement or holding.

Some runes cannot be reversed: their shape is symmetrical, so there is no
reversed position to read. The context marks these. Never invent a reversed
meaning for one, and never describe it as "not reversed" as though that were
a finding."""
    + DIVINATION_RULES,
)

KATINA_INTERPRETATION = Prompt(
    name="katina_interpretation",
    version="katina_interpretation_v1",
    task="""TASK
Interpret the Katina cards in the context, in their positions.

Give each card its own passage, then read the spread as a whole.

Two things to be honest about. Katina cards have no reversed tradition, so
every card here is upright; do not mention orientation as though it were a
choice. And the meanings for this deck are written by Astrofrekans rather than
inherited from a documented tradition - present them as this deck's meanings
and never as "the traditional meaning of this card", which would attribute
something we wrote to a culture."""
    + DIVINATION_RULES,
)


CONVERSATION_SUMMARY = Prompt(
    name="conversation_summary",
    version="conversation_summary_v1",
    task="""\
TASK
Summarise the conversation so far in at most 120 words, for use as memory in
later turns.

Record what the person asked about, what they said about their situation, and
the tone they prefer. Do NOT record astrological facts, placements or dates:
those always come fresh from the engine, and a remembered "my Venus is in
Aries" must never become a fact. Write plain prose, no headings.""",
)

CONVERSATION_TITLE = Prompt(
    name="conversation_title",
    version="conversation_title_v1",
    task="""\
TASK
Give the conversation a short title: at most six words, no quotation marks, no
final punctuation, in the requested language. Describe the subject, not the
answer.""",
)


REGISTRY: dict[str, Prompt] = {
    prompt.name: prompt
    for prompt in (
        SYNASTRY_READING,
        COMPOSITE_READING,
        DAVISON_READING,
        CHAT,
        NATAL_REPORT,
        TRANSIT_INTERPRETATION,
        DAILY_INTERPRETATION,
        WEEKLY_INTERPRETATION,
        MONTHLY_FORECAST,
        ANNUAL_FORECAST,
        HORARY_INTERPRETATION,
        SYNASTRY_REPORT,
        COMPOSITE_REPORT,
        DAVISON_REPORT,
        TAROT_INTERPRETATION,
        RUNE_INTERPRETATION,
        KATINA_INTERPRETATION,
        CONVERSATION_SUMMARY,
        CONVERSATION_TITLE,
    )
}

REPORT_PROMPTS: dict[ReportType, Prompt] = {
    ReportType.NATAL: NATAL_REPORT,
    ReportType.TRANSIT: TRANSIT_INTERPRETATION,
    ReportType.DAILY: DAILY_INTERPRETATION,
    ReportType.WEEKLY: WEEKLY_INTERPRETATION,
    ReportType.MONTHLY: MONTHLY_FORECAST,
    ReportType.YEARLY: ANNUAL_FORECAST,
    ReportType.HORARY: HORARY_INTERPRETATION,
    ReportType.SYNASTRY: SYNASTRY_REPORT,
    ReportType.COMPOSITE: COMPOSITE_REPORT,
    ReportType.DAVISON: DAVISON_REPORT,
    ReportType.TAROT: TAROT_INTERPRETATION,
    ReportType.RUNE: RUNE_INTERPRETATION,
    ReportType.KATINA: KATINA_INTERPRETATION,
    ReportType.SYNASTRY_READING: SYNASTRY_READING,
    ReportType.COMPOSITE_READING: COMPOSITE_READING,
    ReportType.DAVISON_READING: DAVISON_READING,
}

CONTEXT_PROMPTS: dict[ContextType, Prompt] = {
    ContextType.NATAL: NATAL_REPORT,
    ContextType.TRANSIT: TRANSIT_INTERPRETATION,
    ContextType.DAILY: DAILY_INTERPRETATION,
    ContextType.WEEKLY: WEEKLY_INTERPRETATION,
    ContextType.MONTHLY: MONTHLY_FORECAST,
    ContextType.YEARLY: ANNUAL_FORECAST,
    ContextType.HORARY: HORARY_INTERPRETATION,
    ContextType.SYNASTRY: SYNASTRY_REPORT,
    ContextType.COMPOSITE: COMPOSITE_REPORT,
    ContextType.DAVISON: DAVISON_REPORT,
    ContextType.GENERAL_ASTRO_CHAT: CHAT,
    ContextType.TAROT: TAROT_INTERPRETATION,
    ContextType.RUNE: RUNE_INTERPRETATION,
    ContextType.KATINA: KATINA_INTERPRETATION,
}


def prompt_for_report(report_type: ReportType) -> Prompt:
    return REPORT_PROMPTS[report_type]


def prompt_for_use_case(use_case: UseCase) -> Prompt:
    return {
        UseCase.CHAT: CHAT,
        UseCase.SUMMARY: CONVERSATION_SUMMARY,
        UseCase.TITLE: CONVERSATION_TITLE,
    }.get(use_case, CHAT)


def all_versions() -> dict[str, str]:
    return {prompt.name: prompt.version for prompt in REGISTRY.values()}
