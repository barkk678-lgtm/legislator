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
    section_text: str, *, section_number: str = ""
) -> list[Reservation]:
    """כל ההסתייגויות שמצב הכמות מייצר לסעיף אחד, לפי סדר העוגנים
    בנוסח - הסדר הוא חלק מהתקינות (תקנון הכנסת: הסתייגויות מנומקות
    "לפי הסדר שבו נרשמו")."""
    out: list[Reservation] = []
    for anchor in find_anchors(section_text):
        if _blocked(anchor, section_text) or anchor.kind not in _DOMAINS:
            continue
        for value in _DOMAINS[anchor.kind](anchor.text):
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
    """שני המספרים שהממשק מציג. **מדודים, ולא מובטחים.**

    `sections` = [(מספר הסעיף, נוסח הסעיף), ...] של ההצעה כולה.

    - `total` - כמה הסתייגויות מצב הכמות מסוגל לייצר בסך הכול.
    - `distinct` - כמה **עוגנים מובחנים** יש: ערכים שונים בהצעה
      שאפשר לשנות. זהו מספר "המובחנות" שהמשתמש רואה.

    **למה עוגנים ולא נקודות עיגון בעץ** (ברק, 2026-09-18): על הסעיף
    שקיבל 484 הסתייגויות אמיתיות יש **נקודת עיגון אחת** בעץ (משפט
    אחד בלי חלוקה פנימית) אבל **ארבעה עוגנים** - תאריך, שנה, מספר
    סעיף ומספר פסקה. 484 בני אדם התייחסו לסעיף כאל ארבעה דברים.
    הגדרה שאומרת "אחד" סותרת התנהגות מתועדת, ומשתמש שרואה "דבר אחד
    להסתייג עליו" מול תאריך ושנה ומספר סעיף מפסיק לסמוך על המספרים.

    שני המספרים נשמרים ב-`per_section`, כך שהחלפה היא בחירת שדה.
    """
    from quality import anchor_points  # noqa: PLC0415

    total = 0
    distinct = 0
    per_section = []
    for number, text in sections:
        items = quantity_reservations(text, section_number=number)
        points = anchor_points(text)
        total += len(items)
        distinct += len({item.anchor for item in items})
        per_section.append({
            "section": number,
            "quantity": len(items),
            "anchors": len({item.anchor for item in items}),
            "distinct_points": len(points),
        })
    return {"total": total, "distinct": distinct, "per_section": per_section}
