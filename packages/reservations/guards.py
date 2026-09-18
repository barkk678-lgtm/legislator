"""ארבעת השומרים של תקנון הכנסת §86. **כולם חוסמים, אף אחד אינו
אזהרה** (CLAUDE.md חוק ברזל 7).

הנוסחים כאן נשלפו מהקורפוס ולא ממסמך ביניים (חוק ברזל 9).

**חלוקת התפקידים בין השומרים לשני מצבי הכלי:**

| שומר | כמות | איכות |
|---|---|---|
| 86(ד)(2) תוכן פוגעני | **לא חל - מבנית** | חל, חוסם |
| 86(ד)(1) שלילת ההצעה | חל | חל |
| 86(ד)(3) שם ההצעה | חל | חל |
| §3ג עלות תקציבית | חל (סימון + כיוון מקל) | חל (סימון) |

"לא חל - מבנית" אינו ויתור: `model.Reservation` אינה מחזיקה טקסט
חופשי כלל, ו-`screen_content` מקבלת `DraftedReservation` בלבד.
הטיפוס הוא האכיפה.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from anchors import find_anchors
from model import DraftedReservation, Reservation

# ── §86(ד)(2), נוסח מלא מהקורפוס (law-tkanon-haknesset) ─────────────
RULE_86_D_2 = (
    "הסתייגות לא תשלול את קיומה של מדינת ישראל כמדינתו של העם היהודי, "
    "לא תהיה גזענית במהותה והיא לא תכיל כינוי או ביטוי פוגע או גזעני, "
    "או פגיעה בכבוד הכנסת; התעורר ספק, תכריע בעניין נשיאות הכנסת."
)


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    rule: str = ""
    reason: str = ""


ALLOWED = Verdict(True)


# ── שומר 1: 86(ד)(2) - מצב האיכות בלבד ─────────────────────────────
# שכבה א': ביטויים שנחסמים בלי שיקול דעת. רשימה מכוונת-חסר: היא לא
# מתיימרת לכסות, היא תופסת את המובהק בלי קריאת רשת.
_HARD_BLOCK = (
    "מדינת כל אזרחיה", "ביטול חוק השבות", "לבטל את חוק השבות",
    "אינה מדינת העם היהודי", "אינה מדינה יהודית",
)

# שכבה ב': המודל, ו**רק כדי לחסום**. הוא אינו רשאי לאשר: ברירת
# המחדל בכל מסלול כישלון היא חסימה (fail-closed). זו אינה סתירה
# ל"מודל אינו קובע עובדות" - כאן הוא לא קובע שמשהו תקין, הוא רק
# מוסיף חסימות מעבר לרשימה.
_CLASSIFIER_INSTRUCTIONS = f"""אתה בודק אם נוסח הסתייגות מפר את סעיף 86(ד)(2) לתקנון הכנסת:

"{RULE_86_D_2}"

ענה במילה אחת בלבד:
חסום - אם יש בנוסח ולו צל של ספק לגבי גזענות, שלילת קיום מדינת ישראל
כמדינת העם היהודי, כינוי או ביטוי פוגע, או פגיעה בכבוד הכנסת.
שים לב ש"כינוי" כולל שם של אדם בהקשר מבזה.
תקין - רק אם אין שום ספק.

בספק - חסום. אין ניסוח שלישי."""


def screen_content(
    reservation: DraftedReservation, *, draft_fn=None
) -> Verdict:
    """שומר 86(ד)(2). **מקבל `DraftedReservation` בלבד** - הסתייגות
    ממצב הכמות אינה יכולה להגיע לכאן, כי היא אינה מחזיקה טקסט חופשי.

    כל מסלול שאינו "תקין" מפורש מחזיר חסימה: רשימה, תשובת מודל
    שאינה חד-משמעית, חריגה, או היעדר שירות. **ברירת המחדל היא
    חסימה** - פסילה בטעות עולה אחת מתוך אלפיים, פלט פוגעני עולה
    את החברה."""
    if not isinstance(reservation, DraftedReservation):
        raise TypeError(
            "screen_content מקבלת DraftedReservation בלבד. הסתייגות ממצב "
            "הכמות מוגנת מבנית ואינה עוברת כאן - ראו model.py."
        )
    text = reservation.text
    for phrase in _HARD_BLOCK:
        if phrase in text:
            return Verdict(False, "86(ד)(2)", f"ביטוי חסום: {phrase!r}")

    if draft_fn is None:
        import sys  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "llm"))
        try:
            from service import draft as draft_fn  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return Verdict(False, "86(ד)(2)", f"שכבת הסינון אינה זמינה: {exc}")

    try:
        answer = draft_fn(
            instructions=_CLASSIFIER_INSTRUCTIONS, content=text, max_tokens=8
        ).strip()
    except Exception as exc:  # noqa: BLE001
        return Verdict(False, "86(ד)(2)", f"הסינון נכשל: {type(exc).__name__}")

    if answer.startswith("תקין"):
        return ALLOWED
    return Verdict(False, "86(ד)(2)", f"הסינון החזיר {answer[:40]!r}")


# ── שומר 2: 86(ד)(1) - אין לשלול את עצם ההצעה ──────────────────────
_NEGATES_RE = re.compile(
    r"(?:כל\s+סעיפי\s+ה?הצעה|ההצעה\s+כולה|החוק\s+כולו)\s*[–\-]?\s*(?:תימחק|יימחק|יבוטל)"
    r"|תימחק\s+ההצעה|ההצעה\s*[–\-]\s*תימחק"
)
_PURPOSE_HEADINGS = ("מטרה", "מטרות", "מטרת החוק")


def screen_negates_bill(
    text: str, *, section_heading: str = "", deleted_sections: int = 0,
    total_sections: int = 0
) -> Verdict:
    """שומר 86(ד)(1). שלושה מסלולים: ניסוח מפורש שמבטל את ההצעה,
    מחיקת סעיף המטרה, ומחיקת כל הסעיפים."""
    if _NEGATES_RE.search(text):
        return Verdict(False, "86(ד)(1)", "ההסתייגות שוללת את עצם ההצעה")
    if section_heading.strip() in _PURPOSE_HEADINGS and "תימחק" in text:
        return Verdict(False, "86(ד)(1)",
                       f"מחיקת סעיף המטרה ({section_heading}) שוללת את ההצעה")
    if total_sections and deleted_sections >= total_sections:
        return Verdict(False, "86(ד)(1)",
                       f"מחיקת כל {total_sections} הסעיפים שוללת את ההצעה")
    return ALLOWED


# ── שומר 3: 86(ד)(3) - אין הסתייגות לשם ההצעה ──────────────────────
_BILL_NAME_RE = re.compile(r"שם\s+(?:ה?הצעה|ה?חוק)")


def screen_bill_name(text: str, *, anchor: str = "", section_text: str = "",
                     amends_existing_law: bool = True) -> Verdict:
    """שומר 3. שתי דרכים לפגוע בשם ההצעה: לנסח הסתייגות עליו
    במפורש, או לעגן בערך שיושב **בתוך ציטוט שם חוק** - מספר תיקון,
    שנה עברית או לועזית. השני נלמד מהנתונים: 5 ערכים בציטוט, אפס
    עיגונים אנושיים מתוך 484. ראו drafting-rules.md §9.1."""
    if not amends_existing_law:
        return ALLOWED
    if _BILL_NAME_RE.search(text):
        return Verdict(False, "86(ד)(3)", "הסתייגות לשינוי שם ההצעה")
    if anchor and section_text:
        cited = {a.text for a in find_anchors(section_text) if a.in_law_citation}
        if anchor in cited:
            return Verdict(False, "86(ד)(3)",
                           f"העוגן {anchor!r} יושב בתוך ציטוט שם חוק")
    return ALLOWED


# ── שומר 4: §3ג לחוק-יסוד: משק המדינה - עלות תקציבית ───────────────
# הסף אינו "רוב מיוחד" אלא מספר: **50 חברי כנסת**, ואם התקבלה
# הסתייגות תקציבית גם החוק עצמו דורש 50 בקריאה השלישית.
BUDGETARY_MAJORITY = 50

_SUM_RE = re.compile(r"(?<![\d])(\d{1,3}(?:,\d{3})+|\d{4,})(?![\d])")
_MONEY_CONTEXT_RE = re.compile(r"שקל|ש\"ח|₪|אגור|תקציב|קנס|עיצום|אגרה|גמלה|קצבה")


@dataclass(frozen=True)
class BudgetFlag:
    budgetary: bool
    reason: str = ""
    lenient_direction: str = ""  # "decrease" = מקל


def screen_budgetary(reservation: Reservation, *, section_text: str) -> BudgetFlag:
    """שומר 4. **אינו חוסם** - הוא מסמן, ומטה לכיוון מקל.

    הסתייגות תקציבית אינה אסורה; היא דורשת 50 ח"כים. לכן הפעולה
    הנכונה היא סימון גלוי (כדי שהמסתייג ידע מה הוא מגיש) והעדפת
    כיוון שמקטין עלות."""
    if not _MONEY_CONTEXT_RE.search(section_text):
        return BudgetFlag(False)
    if not _SUM_RE.match(reservation.value) and not _SUM_RE.search(reservation.anchor):
        return BudgetFlag(False)
    try:
        increases = int(reservation.value.replace(",", "")) > int(
            reservation.anchor.replace(",", "")
        )
    except ValueError:
        return BudgetFlag(True, "שינוי סכום בהקשר כספי - כיוון לא ידוע")
    return BudgetFlag(
        True,
        f"שינוי סכום בהקשר כספי (דורש {BUDGETARY_MAJORITY} ח\"כ לפי §3ג)",
        "increase" if increases else "decrease",
    )
