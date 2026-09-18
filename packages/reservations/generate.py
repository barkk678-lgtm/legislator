"""מצב הכמות: וריאציות דטרמיניסטיות על ערכים שקיימים בנוסח.

**המנוע אינו כותב טקסט חדש בשום דפוס** (CLAUDE.md חוק ברזל 8). כל
הסתייגות היא צירוף של עוגן שנמצא בנוסח מילה במילה ושל ערך מתוך תחום
מוצהר וסגור. הדפוס `בסופו יבוא "<טקסט חופשי>"`, שהוא 13% מההסתייגויות
שנצפו בפועל, **הוצא מכאן במכוון** - הוא היחיד שדורש חיבור מילים,
והוא זה שמאיים על חוק ברזל 7.

שני צירים, שניהם נצפו בהצעה אמיתית (`tests/fixtures/reservations/`):
`במקום "X" יבוא "Y"` ו-`אחרי "X" יבוא "Y"`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from anchors import Anchor, find_anchors
from guards import screen_bill_name, screen_budgetary
from model import Reservation

# **אין תקרה** (ברק, 2026-09-18). תקרה שאנחנו קובעים הופכת כל "מספר
# ההסתייגויות האפשריות" לתוצר של החלטה שלנו ולא למדידה של ההצעה -
# ומספר שאפשר לשנות בשורת קוד לא מוצג כעובדה. המשתמש מבקש כמות,
# והמנוע מייצר עד שנגמרים הערכים. `_DOMAIN_SPAN` הוא רק גודל הצעד
# שבו כל תחום מתרחב, לא גבול.
_DOMAIN_SPAN = 50

# תחומי ערך מוצהרים. **סגורים בכוונה** - הרחבה היא החלטה, לא תוצאה
# של קלט. hebrew_year אינו כאן: הוא משמש כעוגן ל"אחרי" בלבד, ואינו
# מוחלף, כי ייצור שנה עברית חדשה הוא חיבור מחרוזת ולא בחירה מתוך
# תחום (וגם לא נצפה בפועל).
_LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"


def _number_values(current: str, span: int) -> list[str]:
    n = int(current)
    return [str(v) for v in range(1, span + 2) if v != n][:span]


def _year_values(current: str, span: int) -> list[str]:
    n = int(current)
    return [str(y) for y in range(1948, 1948 + span + 1) if y != n][:span]


def _section_values(current: str, span: int) -> list[str]:
    """אותיות בודדות, ואז דו-אותיות - כך שהתחום גדל בלי גבול עליון
    מלאכותי כשמבקשים כמות גדולה."""
    base = re.match(r"(\d+)", current).group(1)
    out = [f"{base}{letter}" for letter in _LETTERS if f"{base}{letter}" != current]
    for tens in "יכלמנסעפצ":
        for ones in "אבגדהוזחט":
            if len(out) >= span:
                return out[:span]
            candidate = f"{base}{tens}{ones}"
            if candidate != current:
                out.append(candidate)
    return out[:span]


_DOMAINS = {
    "number": _number_values,
    "gregorian_year": _year_values,
    "section_ref": _section_values,
}


def _blocked(anchor: Anchor, section_text: str) -> str | None:
    """שומר מבני על העוגן. מחזיר סיבה אם אסור לעגן בו, אחרת None.

    השומר על שם ההצעה (86(ד)(3)) נאכף כאן ולא אחרי הייצור: אין טעם
    לייצר 50 הסתייגויות ואז לפסול את כולן - העוגן נפסל פעם אחת."""
    verdict = screen_bill_name(
        "", anchor=anchor.text, section_text=section_text, amends_existing_law=True
    )
    if not verdict.allowed:
        return verdict.reason
    return None


def quantity_reservations(
    section_text: str, *, section_number: str = "", span: int = _DOMAIN_SPAN
) -> list[Reservation]:
    """כל ההסתייגויות שמצב הכמות מייצר לסעיף אחד, לפי סדר העוגנים
    בנוסח - הסדר הוא חלק מהתקינות (תקנון הכנסת: הסתייגויות מנומקות
    "לפי הסדר שבו נרשמו")."""
    out: list[Reservation] = []
    for anchor in find_anchors(section_text):
        if _blocked(anchor, section_text) or anchor.kind not in _DOMAINS:
            continue
        for value in _DOMAINS[anchor.kind](anchor.text, span):
            for axis in ("replace", "after"):
                out.append(
                    Reservation(
                        anchor=anchor.text, value=value, axis=axis,
                        section_number=section_number,
                    )
                )
    return out


def budgetary_flags(
    reservations: list[Reservation], *, section_text: str
) -> dict[int, str]:
    """סימון הסתייגויות תקציביות (§3ג). מפתח = אינדקס ברשימה."""
    flags = {}
    for i, item in enumerate(reservations):
        flag = screen_budgetary(item, section_text=section_text)
        if flag.budgetary:
            flags[i] = flag.reason
    return flags


def measure(sections: list[tuple[str, str]]) -> dict:
    """**המספר היחיד שמוצג: עוגנים מובחנים.**

    `sections` = [(מספר הסעיף, נוסח הסעיף), ...] של ההצעה כולה.

    **למה אין כאן "כמה הסתייגויות אפשר לייצר"** (ברק, 2026-09-18):
    המספר הזה אינו מדידה של ההצעה אלא תוצר של תקרה שאנחנו קובעים,
    ובלי תקרה הוא בלתי מוגבל. מספר שאפשר לשנות בשורת קוד לא מוצג
    כעובדה. `distinct` לעומת זאת נמדד מההצעה עצמה ואינו תלוי בשום
    החלטה שלנו - זה מספר הערכים השונים שקיימים בה וניתנים לשינוי.

    המודל בממשק הפוך: המשתמש מקליד כמה הוא רוצה, והמנוע מייצר.
    """
    total_anchors = 0
    per_section = []
    for number, text in sections:
        items = quantity_reservations(text, section_number=number, span=1)
        anchors = {item.anchor for item in items}
        total_anchors += len(anchors)
        per_section.append({"section": number, "anchors": len(anchors),
                            "anchor_values": sorted(anchors)})
    return {"distinct": total_anchors, "per_section": per_section}


def generate_upto(
    sections: list[tuple[str, str]], requested: int
) -> tuple[list[Reservation], int]:
    """מייצר עד `requested` הסתייגויות, ומחזיר (הרשימה, כמה התבקשו).

    **מרחיב את התחומים עד שמגיעים לכמות או עד שנגמרים הערכים.**
    אם נגמרו - מחזיר פחות, והקורא מדווח "ייצרתי N, זה המקסימום
    בהצעה הזו". לא משלים באוויר ולא נכשל בשקט."""
    span = 50
    best: list[Reservation] = []
    while True:
        produced: list[Reservation] = []
        for number, text in sections:
            produced.extend(quantity_reservations(text, section_number=number, span=span))
        if len(produced) >= requested:
            return produced[:requested], requested
        if len(produced) <= len(best):
            return best, requested  # התחום מוצה - אין עוד ערכים
        best = produced
        span *= 4
