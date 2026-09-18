"""איתור ערכים בנוסח סעיף, שעליהם מצב הכמות מייצר וריאציות.

**הקובץ הזה אינו כותב טקסט חדש, וזו כל ההגנה** (CLAUDE.md חוק ברזל
8): הוא מוצא ערכים *שכבר קיימים* בנוסח ומחזיר אותם עם המיקום שלהם.
מי שמייצר את הווריאציה (generate.py) בוחר ערך מתוך תחום מוצהר -
מספרים, שנים, מספרי סעיף - ולעולם לא מחבר מילים.

**כל regex כאן חייב טסט שלילי** על מילים עבריות רגילות, לא רק טסט
חיובי - ראו CLAUDE.md. הכלל נולד משני כשלים באותו שבוע: `[א-ת]-\\d{4}`
שתפס את `ו-2010`, ו-`ה?ת[קרש]...` שתפס את המילה "תקופה".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── ציטוט שם חוק ───────────────────────────────────────────────────
# "חוק חומרי נפץ (תיקון מס' 4 – הוראת שעה), התשע"ח–2018"
# הזיהוי מבני ולא מילולי: שם חוק/פקודה, סוגריים אופציונליים, ואז
# שנה עברית + en-dash + שנה לועזית, שהיא החותם של ציטוט שם.
_LAW_CITATION_RE = re.compile(
    r"(?:חוק|פקודת|פקודה|חוק-יסוד|תקנות|צו)"          # פותח הציטוט
    r"[^,()]{0,80}"                                    # שם החוק
    r"(?:\s*\([^)]{0,80}\))?"                          # "(תיקון מס' 4 – הוראת שעה)"
    r"\s*,?\s*"
    r"ה?ת[קרשא-ת][א-ת\"״׳']{0,4}\s*[–\-]\s*\d{4}"      # התשע"ח–2018
)

_NUMBER_RE = re.compile(r"(?<![\w֐-׿\d])(\d{1,4})(?![\w\d])")
# שנה לועזית: ארבע ספרות שמתחילות ב-18/19/20 בלבד. "2020" כן, "1954" כן, "4" לא.
_GREGORIAN_YEAR_RE = re.compile(r"(?<!\d)((?:1[89]|20)\d{2})(?!\d)")
# מספר סעיף: ספרות ואז אות/אותיות, לרבות סעיף קטן בסוגריים. "22ב", "9א1", "22(ב)".
_SECTION_REF_RE = re.compile(r"(?<![\w֐-׿])(\d{1,3}[א-ת]{1,3}\d?)(?![\w֐-׿])")
# שנה עברית: **חייבת להיות צמודה ל-en-dash ולארבע ספרות.** בלי העוגן
# הזה התבנית תופסת "תקופה", "תקנות", "תשלום" וכל מילה שמתחילה ב-ת.
_HEBREW_YEAR_RE = re.compile(r"(ה?ת[קרש][א-ת\"״׳']{0,4})(?=\s*[–\-]\s*\d{4})")


@dataclass(frozen=True)
class Anchor:
    """ערך שנמצא בנוסח, עם המיקום והסוג שלו."""

    text: str
    start: int
    end: int
    kind: str  # "number" | "gregorian_year" | "section_ref" | "hebrew_year"
    in_law_citation: bool


def law_citation_spans(text: str) -> list[tuple[int, int]]:
    """טווחי התווים של ציטוטי שמות חוקים בנוסח."""
    return [(m.start(), m.end()) for m in _LAW_CITATION_RE.finditer(text)]


def find_anchors(text: str) -> list[Anchor]:
    """כל הערכים שניתן לעגן בהם, ממוינים לפי מיקום.

    ערך שיושב בתוך ציטוט שם חוק מסומן `in_law_citation=True` -
    generate.py פוסל אותו. ראו drafting-rules.md §9.1."""
    spans = law_citation_spans(text)

    def inside(start: int, end: int) -> bool:
        return any(s <= start and end <= e for s, e in spans)

    found: dict[tuple[int, int], Anchor] = {}
    for kind, pattern in (
        ("hebrew_year", _HEBREW_YEAR_RE),
        ("section_ref", _SECTION_REF_RE),
        ("gregorian_year", _GREGORIAN_YEAR_RE),
        ("number", _NUMBER_RE),
    ):
        for m in pattern.finditer(text):
            key = (m.start(1), m.end(1))
            if key in found:
                continue  # הסוג הראשון שתפס גובר: שנה לפני מספר גנרי
            found[key] = Anchor(m.group(1), key[0], key[1], kind, inside(*key))
    return sorted(found.values(), key=lambda a: a.start)
