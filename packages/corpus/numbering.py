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


def _is_digit_unit(label: str) -> bool:
    if not label:
        raise ValueError("תווית ריקה")
    return label[-1].isdigit()


def next_inserted_label(preceding_label: str, taken_labels: set[str]) -> str:
    """התווית להוספה מיד אחרי preceding_label, כשכבר קיים איבר אחריו
    באותה רמה (ולכן אסור לשנות מספור קיים) - ha-hoveret-ha-sgula.pdf
    §7.10.6(ב) (סעיף קטן/פסקה) ו-§7.12 (סעיף ראשי).

    הכלל רקורסיבי-לסירוגין, לכל עומק (לא שתי רמות בלבד): היחידה
    האחרונה ב-preceding_label קובעת את סוג היחידה הבאה - אם היא
    ספרות, מוסיפים יחידת-אות (א, ב, ...); אם היא אותיות, מוסיפים
    יחידת-ספרה (1, 2, ...). בוחר את הערך הראשון הפנוי (לא ב-
    taken_labels). דוגמאות מהמדריך: "6"+"א"="6א" (§7.12); "ג"+"1"="ג1"
    (§7.10.6ב, "אחרי סעיף קטן (ג) יבוא: '(ג1)...'"); "2"+"א"="2א"
    (§7.10.6ב, "אחרי פסקה (2) יבוא: '(2א)...'").

    הערך ה"ראשון" בכל נקודה הוא תמיד הערך המינימלי הפנוי בסדרה
    (א או 1) - אושר מפורשות מול המשתמש (התייעצות ב-2026-09-12):
    הצעה מוקדמת יותר לפיה בין 1א ל-1ב הערך הראשון הוא "1א2" הייתה
    טעות; הערך הנכון הוא "1א1" (המינימלי), עקבי עם דוגמאות המדריך
    (6←6א, ג←ג1, 2←2א - כולן מתחילות מהערך המינימלי, לא מדלגות).
    """
    if _is_digit_unit(preceding_label):
        for suffix, _ in sorted(_SUFFIX_INDEX.items(), key=lambda kv: kv[1]):
            candidate = f"{preceding_label}{suffix}"
            if candidate not in taken_labels:
                return candidate
        raise ValueError("אין עוד אותיות זמינות ברצף הסיומות")
    else:
        n = 1
        while True:
            candidate = f"{preceding_label}{n}"
            if candidate not in taken_labels:
                return candidate
            n += 1


def next_appended_label(existing_labels_in_order: list[str]) -> str:
    """התווית הבאה בהמשך רגיל לרצף קיים - כשאין איבר אחרי נקודת
    ההוספה (הוספה בסוף הרשימה, לא בין קיימים) - אז אין צורך בתווית
    מורכבת, רק ממשיכים את אותו רצף פשוט. existing_labels_in_order
    חייבת להיות ממוינת; מסתכלת רק על התווית האחרונה בה.

    לדוגמה: אחרי (ד) בא (ה) (לא "(ד1)"); אחרי סעיף 6 (בלי סעיף 7) בא
    סעיף 7 (לא "6א"). ראה ha-hoveret-ha-sgula.pdf §7.10.6(ג)/§7.12."""
    if not existing_labels_in_order:
        raise ValueError("אין תוויות קיימות לקבוע מהן את המשך הרצף")
    last = existing_labels_in_order[-1]
    if _is_digit_unit(last):
        return str(int(last) + 1)
    if last not in _SUFFIX_INDEX:
        raise ValueError(f"תווית לא מוכרת להמשך רצף: {last!r}")
    next_pos = _SUFFIX_INDEX[last] + 1
    for suffix, pos in _SUFFIX_INDEX.items():
        if pos == next_pos:
            return suffix
    raise ValueError("נגמר רצף האותיות")
