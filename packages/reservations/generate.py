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

_MAX_VALUES_PER_ANCHOR = 50

# תחומי ערך מוצהרים. **סגורים בכוונה** - הרחבה היא החלטה, לא תוצאה
# של קלט. hebrew_year אינו כאן: הוא משמש כעוגן ל"אחרי" בלבד, ואינו
# מוחלף, כי ייצור שנה עברית חדשה הוא חיבור מחרוזת ולא בחירה מתוך
# תחום (וגם לא נצפה בפועל).
_LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"


def _number_values(current: str) -> list[str]:
    n = int(current)
    return [str(v) for v in range(1, _MAX_VALUES_PER_ANCHOR + 2) if v != n][:_MAX_VALUES_PER_ANCHOR]


def _year_values(current: str) -> list[str]:
    n = int(current)
    return [str(y) for y in range(1948, 1948 + _MAX_VALUES_PER_ANCHOR) if y != n]


def _section_values(current: str) -> list[str]:
    base = re.match(r"(\d+)", current).group(1)
    return [f"{base}{letter}" for letter in _LETTERS if f"{base}{letter}" != current][
        :_MAX_VALUES_PER_ANCHOR
    ]


_DOMAINS = {
    "number": _number_values,
    "gregorian_year": _year_values,
    "section_ref": _section_values,
}


@dataclass(frozen=True)
class Reservation:
    text: str
    anchor: str
    value: str
    axis: str  # "replace" | "after"


def _blocked(anchor: Anchor) -> str | None:
    """שומר מבני. מחזיר סיבה אם אסור לעגן בערך הזה, אחרת None."""
    if anchor.in_law_citation:
        # ראו drafting-rules.md §9.1: 5 ערכים בתוך ציטוטי שם, אפס
        # עיגונים אנושיים מתוך 484. להסתייג ממספר התיקון או משנת
        # החוק המתוקן הוא להסתייג משם החוק - 86(ד)(3).
        return "יושב בתוך ציטוט של שם חוק"
    return None


def quantity_reservations(section_text: str) -> list[Reservation]:
    """כל ההסתייגויות שמצב הכמות מייצר לסעיף אחד, לפי סדר העוגנים
    בנוסח - הסדר הוא חלק מהתקינות (תקנון הכנסת: הסתייגויות מנומקות
    "לפי הסדר שבו נרשמו")."""
    out: list[Reservation] = []
    for anchor in find_anchors(section_text):
        if _blocked(anchor) or anchor.kind not in _DOMAINS:
            continue
        for value in _DOMAINS[anchor.kind](anchor.text):
            out.append(Reservation(f'במקום "{anchor.text}" יבוא "{value}".',
                                   anchor.text, value, "replace"))
            out.append(Reservation(f'אחרי "{anchor.text}" יבוא "{value}".',
                                   anchor.text, value, "after"))
    return out


def measure(section_texts: list[str]) -> dict:
    """שני המספרים שהממשק מציג, **מדודים ולא מובטחים**: כמה אפשר
    לייצר בסך הכול, וכמה נקודות עיגון מובחנות יש."""
    total = 0
    anchors: set[str] = set()
    for text in section_texts:
        items = quantity_reservations(text)
        total += len(items)
        anchors |= {item.anchor for item in items}
    return {"total": total, "distinct_anchors": len(anchors)}
