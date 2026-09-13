"""כותרת ברירת מחדל להצעת חוק, כשהמשתמש לא הזין שם משלו.

טהור ודטרמיניסטי (חוק ברזל: אין LLM, אין ניחוש) - נבנה רק מה שידוע
בוודאות: שם החוק המתוקן (מ-full_title, ללא הקידומת "חוק " וללא סיומת
השנה שלו) והתאריך הנוכחי (עברי ולועזי, מחושב - לא מוזן). תיאור התיקון
עצמו ("תיקון – ...") אינו ידוע מראש ואינו ניתן לגזירה אמינה מרשימת
השינויים - במקום זאת מסומן PLACEHOLDER, שרנדרר ה-docx (render_bill.
run_with_placeholder_highlight) מדגיש ברקע צהוב כדי שהמשתמש ישים לב
שיש להשלים אותו ידנית לפני הגשה.
"""

from __future__ import annotations

import re

from pyluach import dates

PLACEHOLDER = "יש להשלים"

_LAW_NAME_YEAR_RE = re.compile(r"^חוק (.+), התש[^–]*–\d{4}$")


def strip_law_own_year(full_title: str) -> str:
    """שולף את שם החוק בלי קידומת 'חוק ' ובלי סיומת השנה שלו:
    'חוק הקייטנות (רישוי ופיקוח), התש"ן–1990' -> 'הקייטנות (רישוי
    ופיקוח)'. אם הפורמט לא מוכר (למשל בלי שנה בכותרת) מחזירה את
    המקור כמו שהוא - לא מנחשת חיתוך שרירותי."""
    match = _LAW_NAME_YEAR_RE.match(full_title)
    return match.group(1) if match else full_title


_HUNDREDS = [(400, "ת"), (300, "ש"), (200, "ר"), (100, "ק")]
_TENS = [
    (90, "צ"), (80, "פ"), (70, "ע"), (60, "ס"), (50, "נ"),
    (40, "מ"), (30, "ל"), (20, "כ"), (10, "י"),
]
_UNITS = {1: "א", 2: "ב", 3: "ג", 4: "ד", 5: "ה", 6: "ו", 7: "ז", 8: "ח", 9: "ט"}


def _hebrew_numeral(n: int) -> str:
    """ממירה 1..999 לגימטריה עברית, עם גרשיים (") לפני האות האחרונה
    (גרש בודד לאות יחידה) - כולל חריגי ט"ו/ט"ז (15/16) כדי לא לאיית
    את שם ה'. n הוא תמיד שארית שנה עברית מודרנית (5000+), לא קלט
    משתמש חופשי - טווח 1..999 מספיק."""
    if not 1 <= n <= 999:
        raise ValueError(f"gematria תומכת רק ב-1..999, קיבל {n}")
    letters: list[str] = []
    remaining = n
    for value, letter in _HUNDREDS:
        while remaining >= value:
            letters.append(letter)
            remaining -= value
    if remaining == 15:
        letters += ["ט", "ו"]
        remaining = 0
    elif remaining == 16:
        letters += ["ט", "ז"]
        remaining = 0
    else:
        for value, letter in _TENS:
            if remaining >= value:
                letters.append(letter)
                remaining -= value
                break
        if remaining:
            letters.append(_UNITS[remaining])
    if len(letters) == 1:
        return letters[0] + "'"
    return "".join(letters[:-1]) + '"' + letters[-1]


def current_hebrew_year_label() -> str:
    """שנה עברית נוכחית, בפורמט 'התשפ"ז' (קידומת ה', בלי ספרת האלפים -
    המוסכמה בכל שאר הפרויקט). מחושבת מהתאריך הנוכחי בפועל."""
    today_heb = dates.GregorianDate.today().to_heb()
    return "ה" + _hebrew_numeral(today_heb.year % 1000)


def default_bill_title(law_full_title: str) -> str:
    """כותרת ברירת מחדל: 'הצעת חוק {שם} (תיקון – {PLACEHOLDER}),
    {שנה עברית}–{שנה לועזית}'. תיאור התיקון מסומן PLACEHOLDER, לא
    מנוחש - ראו מודול-דוק למעלה."""
    base_name = strip_law_own_year(law_full_title)
    gregorian_year = dates.GregorianDate.today().year
    return (
        f"הצעת חוק {base_name} (תיקון – {PLACEHOLDER}), "
        f"{current_hebrew_year_label()}–{gregorian_year}"
    )
