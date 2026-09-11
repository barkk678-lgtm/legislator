"""מיון מספרי סעיפים עבריים: 3, 3א, 3ב, ..., 3י, 3יא, 34כד וכו'.

סיומת האות במספר סעיף היא סידורית (מיקום ברצף א, ב, ג...), לא ערך
גימטרי. "כד" (כ+ד) קודמת ל"לא" (ל+א) כי כ היא הסיומת הדו-אותית
ה-11 בעוד ל היא ה-12 - לא בגלל 24<31. תחלופת ט"ו/ט"ז (הימנעות
מרצף שנקרא כשם, הנהוגה בתאריכים עבריים ובמספור עמודים) אינה חלה
על מספור סעיפים.
"""

import re

_ONES = "אבגדהוזחט"  # תשע האותיות המשמשות כספרת יחידות בתוך סיומת דו-אותית
_TENS = "יכלמנסעפצ"  # תשע האותיות המשמשות כספרת עשרות בתוך סיומת דו-אותית

_NUMBER_RE = re.compile(r"^(\d+)([א-ת]*)$")


def _build_suffix_sequence(limit: int = 200) -> dict[str, int]:
    """בונה מיפוי סיומת -> מיקום סידורי (1-based): א=1, ..., ט=9, י=10,
    יא=11, ..., יט=19, כ=20, כא=21, ... הבנייה עצמה *היא* ההגדרה של
    הרצף הסידורי - אין כאן חישוב ערך, רק ספירה."""
    sequence: dict[str, int] = {}
    n = 0
    for tens_idx in range(len(_TENS) + 1):
        tens_letter = _TENS[tens_idx - 1] if tens_idx else ""
        for ones_idx in range(len(_ONES) + 1):
            if tens_idx == 0 and ones_idx == 0:
                continue
            ones_letter = _ONES[ones_idx - 1] if ones_idx else ""
            n += 1
            sequence[tens_letter + ones_letter] = n
            if n >= limit:
                return sequence
    return sequence


_SUFFIX_INDEX = _build_suffix_sequence()


def parse_section_number(number: str) -> tuple[int, int]:
    """מפרק מספר סעיף למפתח מיון (מספר_בסיס, מיקום_סיומת).

    סעיף בלי סיומת מקבל מיקום -1 כדי שיקדם לכל סעיף עם אותו מספר
    בסיס וסיומת (למשל "3" לפני "3א").
    """
    match = _NUMBER_RE.match(number.strip())
    if not match:
        raise ValueError(f"מספר סעיף לא תקין: {number!r}")
    base = int(match.group(1))
    suffix = match.group(2)
    if not suffix:
        return (base, -1)
    if suffix not in _SUFFIX_INDEX:
        raise ValueError(f"סיומת סעיף לא מוכרת: {suffix!r} (ב-{number!r})")
    return (base, _SUFFIX_INDEX[suffix])


def sort_section_numbers(numbers: list[str]) -> list[str]:
    """ממיין מספרי סעיפים לפי הסדר החוקי: 3, 3א, 3ב, ..., 3י, 3יא, 4, ..."""
    return sorted(numbers, key=parse_section_number)
