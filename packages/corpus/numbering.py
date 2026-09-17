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

_SEGMENT_RE = re.compile(r"\d+|[א-ת]+")
_LAST_SEGMENT_RE = re.compile(r"(\d+|[א-ת]+)$")


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


def parse_section_number(number: str) -> tuple[int, ...]:
    """מפרק מספר סעיף למפתח מיון: tuple באורך משתנה, מקטע אחר מקטע.

    מספר סעיף הוא רצף מקטעים מתחלפים - ספרות, אותיות, ספרות, ... -
    שמתחיל תמיד בספרות: "4" -> (4,), "4א" -> (4, 1), "4א1" -> (4, 1, 1),
    "51ח1" -> (51, 8, 1). התחלופה אינה הנחה אלא תוצאה של הפירוק עצמו
    (רצף ספרות או אותיות נבלע כולו למקטע אחד), ולכן זוגיות המיקום
    ברשימה מספיקה כדי לדעת מה סוג המקטע - אין צורך לשמור אותו.

    התבנית ספרה-אות-ספרה נוצרת מהכנסה חוזרת: סעיף שהוכנס אחרי סעיף
    שהוכנס (ראו next_inserted_label, שכבר מייצרת אותה רקורסיבית).
    988 סעיפים אמיתיים ב-135 חוקים בקורפוס נושאים מספר כזה, ועד
    לתיקון הזה דולגו בשקט. ראו
    docs/strategy/section-numbering-fix-plan-2026-09-16.md.

    מיון: Python משווה tuples לקסיקוגרפית, וה-tuple הקצר קטן מזה
    שהוא קידומת שלו - ולכן (4,) < (4, 1) < (4, 1, 1) < (4, 2) < (5,).
    זו בדיוק ההתנהגות שהערך המלאכותי -1 לסיומת ריקה דימה קודם לרמה
    אחת, מוכללת לכל עומק בלי קוד נוסף.
    """
    text = number.strip()
    segments = _SEGMENT_RE.findall(text)
    if not segments or "".join(segments) != text:
        raise ValueError(f"מספר סעיף לא תקין: {number!r}")
    if not segments[0].isdigit():
        raise ValueError(f"מספר סעיף חייב להתחיל בספרות: {number!r}")
    key: list[int] = []
    for position, segment in enumerate(segments):
        if position % 2 == 0:
            key.append(int(segment))
        else:
            if segment not in _SUFFIX_INDEX:
                raise ValueError(f"סיומת סעיף לא מוכרת: {segment!r} (ב-{number!r})")
            key.append(_SUFFIX_INDEX[segment])
    return tuple(key)


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
    סעיף 7 (לא "6א"). ראה ha-hoveret-ha-sgula.pdf §7.10.6(ג)/§7.12.

    **פועלת על המקטע האחרון בלבד, לא על המחרוזת השלמה.** עד לתיקון
    2026-09-17 הקוד הניח ש-last הוא מקטע יחיד (ספרות טהורות או אותיות
    טהורות) - הנחה שהייתה נכונה רק כל עוד parse_section_number לא
    הכירה במספרים מורכבים. משהכירה, תווית כמו "4א1" יכולה להיות
    האחרונה ברשימה, ואז int("4א1") היה זורק ValueError ו-
    _SUFFIX_INDEX["4א"] היה זורק KeyError - קריסה ממשית בהוספת סעיף
    בסוף חוק שסעיפו האחרון ממוספר מורכב. הפתרון: לקלף את המקטע
    האחרון, לקדם אותו, ולהדביק בחזרה לקידומת ("4א1" -> "4א2").

    **הכרעה פתוחה (רשומה ב-docs/night-report.md):** כשהתווית האחרונה
    היא "4א" (בלי סעיף 5 אחריה), הכלל כאן מחזיר "4ב" - המשך המקטע
    האחרון - ולא "5" (המשך הבסיס). שתי הקריאות נתמכות בטקסט של §7.12,
    והכלל המקומי נבחר כי הוא עקבי עם רצף האותיות של §7.10.6(ג); דורש
    אישור לפני שמסתמכים עליו בהוראת תיקון אמיתית.
    """
    if not existing_labels_in_order:
        raise ValueError("אין תוויות קיימות לקבוע מהן את המשך הרצף")
    last = existing_labels_in_order[-1]
    match = _LAST_SEGMENT_RE.search(last)
    if not match:
        raise ValueError(f"תווית לא מוכרת להמשך רצף: {last!r}")
    prefix, segment = last[: match.start()], match.group(1)
    if segment.isdigit():
        return f"{prefix}{int(segment) + 1}"
    if segment not in _SUFFIX_INDEX:
        raise ValueError(f"תווית לא מוכרת להמשך רצף: {last!r}")
    next_pos = _SUFFIX_INDEX[segment] + 1
    for suffix, pos in _SUFFIX_INDEX.items():
        if pos == next_pos:
            return f"{prefix}{suffix}"
    raise ValueError("נגמר רצף האותיות")
