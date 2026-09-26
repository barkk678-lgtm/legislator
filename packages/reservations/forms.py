"""צורות ההסתייגות - נגזרו מ-112 ההסתייגויות בטבריה (הסתייגויות 2, 26.9).

**לא מומצאות.** כל צורה כאן מופיעה בהצעת חוק הרשויות המקומיות (בחירות)
(תיקון מס' 53), פ/3343/25 (reference/הצעת חוק טבריה.pdf), והמספרים בכל
פונקציה הם ההסתייגויות שממנה נגזרה. מה שבטבריה ואינו כאן - ולכן לא מיוצר:
"לפני הסעיף יבוא" (1-3, מטרה - טקסט חופשי), "אחרי פסקה (1) יבוא:" (21-31,
38 - נוסח משפטי חדש), "האמור בו ... יסומן כפסקה (1)" (42), ותיקון סעיפים
בחוק העיקרי מתוך סעיף חדש (89-112 - נוגע בחוק העיקרי, ברק: לא).

**הכתובת** ("ברישה, ", "בפסקה (2), ") - לפני הפעולה, כמו בטבריה. בסעיף שאין
בו יחידות - בלי כתובת (טבריה, סעיף 3: `במקום "שר הפנים" יבוא ...`).

| צורה | בטבריה |
|---|---|
| `{כתובת}במקום "X" יבוא "Y".` | 9, 12, 13, 15, 17, 32, 33, 43, 48, 49, 56, 65, 67 |
| `{כתובת}אחרי "X" יבוא "Y".` | 4-6, 34, 36/א, 44, 53-55, 59, 60 |
| `{כתובת}לפני "X" יבוא "Y".` | 7, 14, 40, 45 |
| `{כתובת}בסופה/בסופו יבוא "Y".` | 8, 10, 11, 16 (+68 חלופות), 37, 51 |
| `{כתובת}המילים "X" – יימחקו.` | 39, 46, 48/ג, 50, 64, 70 |
| `פסקה (n) – תימחק.` | 18, 19, 20 |
| `אחרי הסעיף יבוא:` + `"כותרת N. נוסח"` | 41, 74-88 |
"""

from __future__ import annotations

_UNIT_WORD = {"paragraph": "פסקה", "subsection": "סעיף קטן", "subparagraph": "פסקת משנה"}
# "בסופה" לנקבה (פסקה, רישה), "בסופו" לזכר (סעיף, סעיף קטן) - טבריה 16 מול 51.
_FEMININE = {"paragraph", "subparagraph", "lead"}


def address(kind: str, labels: list[str], *, section_has_units: bool) -> str:
    """"ברישה, " / "בפסקה (2), " / "בסעיף קטן (א)(2), " / "" (סעיף בלי יחידות)."""
    if kind == "lead":
        return "ברישה, " if section_has_units else ""
    if not labels:
        return ""
    return f"ב{_UNIT_WORD[kind]} {''.join(labels)}, "


def replace(addr: str, old: str, new: str) -> str:
    return f'{addr}במקום "{old}" יבוא "{new}".'


def after(addr: str, anchor: str, new: str) -> str:
    return f'{addr}אחרי "{anchor}" יבוא "{new}".'


def before(addr: str, anchor: str, new: str) -> str:
    return f'{addr}לפני "{anchor}" יבוא "{new}".'


def append(addr: str, kind: str, new: str) -> str:
    end = "בסופה" if (kind in _FEMININE and addr) else "בסופו"
    return f'{addr}{end} יבוא "{new}".'


def delete_words(addr: str, phrase: str) -> str:
    # מילה אחת - "המילה ... – תימחק" (התאמת מין ומספר, כמו engine._render_word_operation).
    if len(phrase.split()) == 1:
        return f'{addr}המילה "{phrase}" – תימחק.'
    return f'{addr}המילים "{phrase}" – יימחקו.'


def delete_unit(kind: str, labels: list[str]) -> str:
    """"פסקה (2) – תימחק." (טבריה 18-20); סעיף קטן - "יימחק" (זכר)."""
    *outer, last = labels
    verb = "יימחק" if kind == "subsection" else "תימחק"
    prefix = f"בסעיף קטן {''.join(outer)}, " if outer else ""
    return f"{prefix}{_UNIT_WORD[kind]} {last} – {verb}."


def new_section_after(margin_title: str, number: str, text: str) -> list[str]:
    """טבריה 74: `אחרי הסעיף יבוא:` / `"תחילה 4. תחילתו של חוק זה ..."`."""
    return ["אחרי הסעיף יבוא:", f'"{margin_title} {number}. {text}"']


__all__ = ["address", "after", "append", "before", "delete_unit", "delete_words",
           "new_section_after", "replace"]
