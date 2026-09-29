"""Pythagorean numerology.

Pure arithmetic on the name and birth date. Turkish and Azerbaijani letters
are folded to their Latin base (Ç→C, Ğ→G, İ/I/ı→I, Ö→O, Ş→S, Ü→U, Ə→E)
before lookup. Master numbers 11, 22 and 33 are kept wherever the method
calls for it. Y is treated as a consonant.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date

NUMEROLOGY_VERSION = "numerology_pythagorean_v1"
MASTER_NUMBERS = (11, 22, 33)
VOWELS = frozenset("AEIOU")
_FOLD = str.maketrans(
    {
        "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
        "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
        "ə": "e", "Ə": "E",
    }
)


def letter_value(letter: str) -> int:
    """A=1 ... I=9, J=1 ... R=9, S=1 ... Z=8."""
    return (ord(letter) - ord("A")) % 9 + 1


def normalize_name(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name.translate(_FOLD))
    return "".join(ch for ch in folded.upper() if "A" <= ch <= "Z")


def reduce_number(value: int, *, keep_master: bool = True) -> int:
    while value > 9 and not (keep_master and value in MASTER_NUMBERS):
        value = sum(int(digit) for digit in str(value))
    return value


def life_path(birth: date) -> int:
    """Month, day and year are reduced separately, then summed and reduced."""
    parts = (
        reduce_number(birth.month),
        reduce_number(birth.day),
        reduce_number(sum(int(d) for d in str(birth.year))),
    )
    return reduce_number(sum(parts))


def _sum_letters(name: str, *, want_vowels: bool | None) -> int:
    letters = normalize_name(name)
    total = 0
    for letter in letters:
        is_vowel = letter in VOWELS
        if want_vowels is None or want_vowels == is_vowel:
            total += letter_value(letter)
    return total


def destiny(name: str) -> int:
    """Expression / destiny: every letter of the full birth name."""
    return reduce_number(_sum_letters(name, want_vowels=None))


def soul_urge(name: str) -> int:
    return reduce_number(_sum_letters(name, want_vowels=True))


def personality(name: str) -> int:
    return reduce_number(_sum_letters(name, want_vowels=False))


def birthday_number(birth: date) -> int:
    return reduce_number(birth.day)


def personal_year(birth: date, year: int) -> int:
    return reduce_number(
        reduce_number(birth.month, keep_master=False)
        + reduce_number(birth.day, keep_master=False)
        + reduce_number(year, keep_master=False),
        keep_master=False,
    )


def personal_month(birth: date, year: int, month: int) -> int:
    return reduce_number(personal_year(birth, year) + month, keep_master=False)


@dataclass(slots=True, frozen=True)
class NumerologyProfile:
    name_used: str
    birth_date: date
    reference: date
    life_path: int
    destiny: int
    soul_urge: int
    personality: int
    birthday: int
    personal_year: int
    personal_month: int
    version: str = NUMEROLOGY_VERSION


def profile(name: str, birth: date, reference: date) -> NumerologyProfile:
    if not normalize_name(name):
        raise ValueError("name has no letters")
    return NumerologyProfile(
        name_used=name.strip(),
        birth_date=birth,
        reference=reference,
        life_path=life_path(birth),
        destiny=destiny(name),
        soul_urge=soul_urge(name),
        personality=personality(name),
        birthday=birthday_number(birth),
        personal_year=personal_year(birth, reference.year),
        personal_month=personal_month(birth, reference.year, reference.month),
    )


# (title, keywords, meaning) per number, TR then EN.
MEANINGS: dict[int, tuple[tuple[str, str], tuple[str, str], tuple[str, str]]] = {
    1: (("Öncü", "The Pioneer"), ("bağımsızlık, cesaret, başlangıç", "independence, courage, beginnings"),
        ("Kendi yolunu çizme, liderlik ve ilk adımı atma enerjisi.",
         "The energy of forging your own path, leading and taking the first step.")),
    2: (("Uzlaştırıcı", "The Mediator"), ("iş birliği, diplomasi, hassasiyet", "cooperation, diplomacy, sensitivity"),
        ("İlişkiler, denge ve birlikte üretme yeteneği ön planda.",
         "Relationships, balance and the gift of building together come first.")),
    3: (("İfade Eden", "The Communicator"), ("yaratıcılık, neşe, ifade", "creativity, joy, expression"),
        ("Kendini söz, sanat ve sosyallik yoluyla ifade etme gücü.",
         "The power to express yourself through words, art and company.")),
    4: (("İnşa Eden", "The Builder"), ("düzen, emek, güvenilirlik", "order, effort, reliability"),
        ("Sağlam temeller, sabır ve sistem kurma yeteneği.",
         "Solid foundations, patience and a talent for systems.")),
    5: (("Özgür Ruh", "The Free Spirit"), ("değişim, macera, esneklik", "change, adventure, flexibility"),
        ("Deneyim, hareket ve yenilik arayan uyarlanabilir bir enerji.",
         "An adaptable energy that seeks experience, movement and novelty.")),
    6: (("Koruyan", "The Nurturer"), ("sorumluluk, sevgi, aile", "responsibility, love, family"),
        ("Şefkat, hizmet ve çevresine güzellik katma isteği.",
         "Care, service and the wish to bring beauty to those around you.")),
    7: (("Arayan", "The Seeker"), ("iç görü, analiz, maneviyat", "insight, analysis, spirituality"),
        ("Derin düşünce, sorgulama ve anlam arayışı.",
         "Deep thought, questioning and the search for meaning.")),
    8: (("Yönetici", "The Achiever"), ("güç, başarı, maddi dünya", "power, success, the material world"),
        ("Hedef, otorite ve kaynakları yönetme kapasitesi.",
         "Ambition, authority and the capacity to manage resources.")),
    9: (("Hümanist", "The Humanitarian"), ("merhamet, tamamlama, bilgelik", "compassion, completion, wisdom"),
        ("Geniş bir vizyon, cömertlik ve döngüleri kapatma yeteneği.",
         "A wide vision, generosity and the ability to close cycles.")),
    11: (("Işık Taşıyıcı", "The Illuminator"), ("sezgi, ilham, idealizm", "intuition, inspiration, idealism"),
         ("Usta sayı: güçlü sezgi ve başkalarına ilham verme potansiyeli.",
          "Master number: strong intuition and the potential to inspire others.")),
    22: (("Usta İnşacı", "The Master Builder"), ("vizyon, uygulama, büyük projeler", "vision, execution, large projects"),
         ("Usta sayı: büyük hayalleri somut yapılara dönüştürme potansiyeli.",
          "Master number: the potential to turn big visions into lasting structures.")),
    33: (("Usta Öğretmen", "The Master Teacher"), ("şefkat, rehberlik, hizmet", "compassion, guidance, service"),
         ("Usta sayı: sevgi ve rehberlik yoluyla dönüştürme potansiyeli.",
          "Master number: the potential to transform through love and guidance.")),
}

CYCLE_MEANINGS: dict[int, tuple[str, str]] = {
    1: ("Yeni başlangıçlar ve tohum ekme dönemi.", "A period of new beginnings and planting seeds."),
    2: ("Sabır, iş birliği ve ilişkilerin güçlendiği dönem.", "Patience, cooperation and strengthening bonds."),
    3: ("Yaratıcılık, sosyallik ve ifade dönemi.", "Creativity, socialising and self-expression."),
    4: ("Çalışma, düzen ve temel atma dönemi.", "Work, order and laying foundations."),
    5: ("Değişim, hareket ve yeni deneyimler dönemi.", "Change, movement and new experiences."),
    6: ("Aile, sorumluluk ve ilişkilere odaklanma dönemi.", "Family, responsibility and relationships."),
    7: ("İç gözlem, öğrenme ve dinlenme dönemi.", "Reflection, study and rest."),
    8: ("Kariyer, para ve somut sonuçlar dönemi.", "Career, money and tangible results."),
    9: ("Tamamlama, bırakma ve döngü kapanışı dönemi.", "Completion, release and closing a cycle."),
}
