"""טיפוסי ההסתייגות. **ההפרדה כאן היא ההגנה, לא התיעוד.**

שני טיפוסים ולא אחד, כי שני מצבי הכלי נבדלים בדבר אחד מהותי:

- `Reservation` (מצב כמות) נבנית מעוגן שקיים בנוסח ומערך מתוך תחום
  מוצהר. **אין בה שדה טקסט חופשי.** לא ניתן לבטא בה תוכן פוגעני,
  ולכן שומר 86(ד)(2) אינו חל עליה - לא כהחלטה אלא כעובדה על הטיפוס.
- `DraftedReservation` (מצב איכות) מכילה טקסט שמודל ניסח. **היא
  הטיפוס היחיד שעובר את שומר 86(ד)(2)**, וזה נאכף בחתימה של
  `guards.screen_content` שמקבלת אותה בלבד.

מי שיוסיף בעתיד שדה טקסט חופשי ל-`Reservation` שובר את חוק ברזל 8
ואת ההגנה על חוק ברזל 7 - ולכן `__post_init__` מוודא במפורש שהטקסט
נגזר מהעוגן ומהערך ואינו מחרוזת שרירותית.
"""

from __future__ import annotations

from dataclasses import dataclass

_AXIS_TEMPLATES = {
    "replace": 'במקום "{anchor}" יבוא "{value}".',
    "after": 'אחרי "{anchor}" יבוא "{value}".',
}


@dataclass(frozen=True)
class Reservation:
    """הסתייגות ממצב הכמות. הטקסט **נגזר** ואינו נתון."""

    anchor: str
    value: str
    axis: str
    section_number: str = ""

    def __post_init__(self) -> None:
        if self.axis not in _AXIS_TEMPLATES:
            raise ValueError(f"ציר לא מוכר: {self.axis!r}")

    @property
    def text(self) -> str:
        return _AXIS_TEMPLATES[self.axis].format(anchor=self.anchor, value=self.value)


@dataclass(frozen=True)
class DraftedReservation:
    """הסתייגות ממצב האיכות. מכילה טקסט שמודל ניסח, ולכן **חייבת**
    לעבור את `guards.screen_content` לפני שהיא מוצגת."""

    text: str
    section_number: str = ""
    rationale: str = ""
