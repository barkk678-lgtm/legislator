"""validate(bill, before, refs) -> list[Finding]. 15 הבדיקות מ-
docs/validator-checklist.md. ראו TASKS.md משימה 6.

טהור: בלי רשת, בלי LLM (אותו עיקרון כמו amend/render). קלט זהה נותן
פלט זהה תמיד. כל בדיקה מוחזרת גם אם עברה - "15 מתוך 15 עברו" הוא מידע
בפני עצמו, לא רק כשלים. כשל אף פעם לא שקט: או "עבר"/"נכשל"/"אזהרה"
(רכה) עם הודעה, או "לא נבדק" עם הסבר למה - לעולם לא נעלם מהרשימה.

היקף מכוון, לא בדיקת-כל: כמה בדיקות (2, 11) בודקות רק את מה שניתן
לגזור באופן מובנה מ-Bill.lines/before/refs, לא ניתוח שפה טבעי חופשי -
מסומן בקוד היכן הבדיקה חלקית. בדיקות 10/13 תלויות ביכולות שעדיין לא
קיימות (הצעת חוק מרובת-חוקים; חיפוש OData ממשימה 8) ומוחזרות כ"לא
נבדק" עם הסבר, לא מדולגות בשקט ולא מוצגות כ"עבר".
"""

import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "render"))
from node import LegislativeNode  # noqa: E402
from numbering import sort_section_numbers  # noqa: E402
from render_bill import Bill  # noqa: E402

CHECKS = {
    1: ("מספרי הסעיפים בהוראות התיקון קיימים בפועל בחוק המתוקן", "רגילה"),
    2: ("כל אזכור חוק חיצוני מלווה בהערת שוליים עם מראה מקום ברשומות", "רכה"),
    3: ("הסעיף הראשון מגדיר (להלן – החוק העיקרי) והשאר משתמשים בו", "רגילה"),
    4: ("לכל סעיף יש כותרת שוליים בפורמט '{סוג פעולה} סעיף {N}'", "רגילה"),
    5: ('מרכאות: שימוש עקבי ב-" (U+0022), לא ב-״ (U+05F4)', "רגילה"),
    6: ("מקף בשנה עברית הוא en-dash (U+2013)", "רגילה"),
    7: ("שם ההצעה בפורמט 'חוק X (תיקון – {תיאור}), התש{ע}–{ל}'", "רגילה"),
    8: ("השנה בשם ההצעה היא שנת ההצעה, לא שנת החוק המקורי", "רגילה"),
    9: ("סעיפים מסודרים כרונולוגית לפי סדרם בחוק המתוקן", "רגילה"),
    10: ("תיקונים עקיפים באים אחרי התיקונים לחוק העיקרי", "רגילה"),
    11: ("הגדרות בסדר אלפביתי, ללא הוראות אופרטיביות", "רכה"),
    12: ("סעיפי תחילה / תחולה / הוראת מעבר בסוף", "רגילה"),
    13: ("נבדקו הצעות זהות או דומות, ונוספה השורה הנדרשת בדברי ההסבר", "רגילה"),
    14: ("הסגנונות בקובץ ה-docx תואמים לתבנית", "רגילה"),
    15: ("אין בפלט טקסט חוק שאין לו provenance", "רגילה"),
}


@dataclass
class Finding:
    check_number: int
    description: str
    severity: str  # "רגילה" | "רכה"
    status: str  # "עבר" | "נכשל" | "אזהרה" | "לא נבדק"
    message: str


def _finding(number: int, status: str, message: str) -> Finding:
    description, severity = CHECKS[number]
    return Finding(number, description, severity, status, message)


def _all_node_ids(root: LegislativeNode) -> set[str]:
    ids = {root.id}
    for child in root.children:
        ids |= _all_node_ids(child)
    return ids


def _check_1(bill: Bill, before: LegislativeNode) -> Finding:
    valid_ids = _all_node_ids(before)
    bad = [
        (i, ln.source_node_id)
        for i, ln in enumerate(bill.lines)
        if ln.source_node_id is not None and ln.source_node_id not in valid_ids
    ]
    if bad:
        return _finding(1, "נכשל", f"שורות עם source_node_id שאינו צומת קיים ב'לפני': {bad}")
    return _finding(1, "עבר", "כל source_node_id בשורות הפלט מפנה לצומת שקיים בפועל ב'לפני'")


def _check_2(bill: Bill, refs: dict[str, str]) -> Finding:
    """בודקת רק שלכל מפתח הערת שוליים שבפועל נעשה בו שימוש ב-Line.footnotes
    יש מראה מקום ב-refs. **לא** מזהה אזכור חוק חיצוני שנעדר ממנו הערת
    שוליים לגמרי (זה ניתוח שפה טבעי חופשי, לא נבדק כאן).

    **דרגה "רכה" (2026-09-17):** ביקורת מול 40 הצעות חוק אמיתיות
    שהונחו בכנסת ה-25 מצאה שרק **3 מתוכן** מזכירות מראה מקום ("ס\"ח")
    בגוף הנוסח. סביר שהערות השוליים נוספות בשלב ההכנה בלשכה המשפטית
    ולא בהנחה הטרומית. הכלל נשאר - הוא נכון לנוסח מוגמר - אבל הוא
    אינו תנאי לתקינות הצעה בהנחה, ולכן אזהרה ולא כישלון."""
    used_keys = sorted({key for ln in bill.lines for key in ln.footnotes})
    missing = [key for key in used_keys if key not in refs]
    if missing:
        return _finding(2, "נכשל", f"מפתחות הערת שוליים בשימוש בלי מראה מקום ב-refs: {missing}")
    return _finding(
        2,
        "עבר",
        f"לכל {len(used_keys)} מפתחות הערת השוליים בשימוש יש מראה מקום ב-refs "
        "(לא נבדק: אזכור חוק חיצוני שלא צוין לו מפתח הערת שוליים כלל)",
    )


_PRINCIPAL_LAW_DEFINE_RE = re.compile(r"להלן\s*–\s*החוק העיקרי")
_PRINCIPAL_LAW_MENTION_RE = re.compile(r"החוק העיקרי")
# ניסוח "כמעט נכון" - מקף רגיל במקום en-dash, רווח חסר, או ה' ידיעה
# חסרה ("להלן– החוק עיקרי", שנמצא בפועל בהצעה אמיתית). משמש רק כדי
# להבחין בין "אין כינוי" לבין "יש כינוי בניסוח לא תקני" - שני ממצאים
# שונים לגמרי למי שקורא את הדוח.
_PRINCIPAL_LAW_LOOSE_RE = re.compile(r"להלן\s*[–\-]?\s*ה?חוק\s+ה?עיקרי")


_ACTION = r"(?:תיקון|החלפת|ביטול|הוספת)"
# כותרת שוליים שמצביעה על יחידה *בתוך* החוק העיקרי ("תיקון סעיף 24")
_PRINCIPAL_HEADING_RE = re.compile(rf"^{_ACTION}\s+(?:סעיפים|סעיף|פרק|סימן|התוספת|תוספת)\b")
# כותרת שוליים שנוקבת בשם חוק אחר ("תיקון חוק כביש אגרה") - הצעה
# מתקנת-חקיקה שנוגעת בכמה חוקים שונים, שבה אין "חוק עיקרי" יחיד
_OTHER_LAW_HEADING_RE = re.compile(rf"^{_ACTION}\s+(?:חוק|פקודת|פקודה|תקנות|צו)\b")


def _instruction_counts(bill: Bill) -> tuple[int, int]:
    """(הוראות לחוק העיקרי, הוראות לחוקים נקובים אחרים).

    כותרת שוליים מופיעה בדיוק פעם אחת לכל הוראה (בשורה הראשונה שלה),
    ולכן ספירת הכותרות היא ספירת ההוראות - נגזר מהפלט ולא מהמנוע, כדי
    שהבדיקה תעבוד גם על הצעה שהגיעה מחילוץ docx.

    ההבחנה בין שני הסוגים אינה קוסמטית: הכלל ב-§5.8 מדבר על יותר
    מהוראת תיקון אחת **לאותו חוק**. בהצעה מסוג "תיקוני חקיקה" שכל
    הוראה בה נוגעת בחוק אחר, כל חוק נקוב בשמו המלא פעם אחת ואין חוק
    עיקרי לכנות - נמצא בפועל ב-4 מתוך 40 ההצעות האמיתיות."""
    principal = other = 0
    for ln in bill.lines:
        heading = ln.side_heading or ""
        if _PRINCIPAL_HEADING_RE.match(heading):
            principal += 1
        elif _OTHER_LAW_HEADING_RE.match(heading):
            other += 1
    return principal, other


def _check_3(bill: Bill) -> Finding:
    """הכינוי "(להלן – החוק העיקרי)" נדרש **רק כשיש יותר מהוראת תיקון
    אחת לאותו חוק** - אחרת שם החוק המלא מופיע פעם אחת ואין למה לקצר.

    תוקן 2026-09-17 אחרי ביקורת מול 40 הצעות חוק אמיתיות שהונחו בכנסת
    (tests/fixtures/real-bills): הבדיקה דרשה את הכינוי ללא תנאי ונכשלה
    על 30 מתוך 40 - כלומר היא סתרה את הפרקטיקה בפועל, וגם את התיקון
    שנעשה ב-engine._drop_principal_law_alias_if_single באותו יום. ראו
    docs/drafting-rules.md §5.8."""
    combined = [ln.text + ln.text_after for ln in bill.lines]
    defining_idxs = [i for i, t in enumerate(combined) if _PRINCIPAL_LAW_DEFINE_RE.search(t)]
    loose_idxs = [i for i, t in enumerate(combined) if _PRINCIPAL_LAW_LOOSE_RE.search(t)]
    principal, other = _instruction_counts(bill)

    if principal == 0:
        if other:
            return _finding(
                3,
                "לא נבדק",
                f"כל {other} הוראות התיקון בהצעה נוקבות בשם חוק אחר (הצעת "
                "\"תיקוני חקיקה\") - אין בה חוק עיקרי יחיד, והכלל על "
                "'(להלן – החוק העיקרי)' אינו חל",
            )
        return _finding(
            3,
            "לא נבדק",
            "לא זוהתה אף הוראת תיקון בהצעה (כנראה הצעת חוק חדש ולא הצעה "
            "מתקנת) - הכלל על '(להלן – החוק העיקרי)' אינו חל",
        )

    if loose_idxs and not defining_idxs:
        return _finding(
            3,
            "נכשל",
            f"הכינוי מופיע בשורה {loose_idxs[0]} אך לא בניסוח התקני "
            "'(להלן – החוק העיקרי)' - בדקו רווחים, en-dash (–) וה' הידיעה: "
            f"{combined[loose_idxs[0]][:90]!r}",
        )

    if principal == 1:
        if defining_idxs:
            return _finding(
                3,
                "נכשל",
                "יש הוראת תיקון אחת בלבד לחוק העיקרי, ולכן הכינוי "
                f"'(להלן – החוק העיקרי)' מיותר - הוא מופיע בשורה {defining_idxs[0]}. "
                "שם החוק המלא מופיע פעם אחת, אין למה לקצר (drafting-rules.md §5.8)",
            )
        return _finding(
            3,
            "עבר",
            "הוראת תיקון אחת בלבד, ואין כינוי '(להלן – החוק העיקרי)' - נכון "
            "לפי §5.8 (הכינוי נדרש רק מהוראה שנייה ואילך)",
        )

    if not defining_idxs:
        return _finding(
            3,
            "נכשל",
            f"יש {principal} הוראות תיקון לחוק העיקרי אבל אין שורה שמגדירה "
            "'(להלן – החוק העיקרי)' - מההוראה השנייה ואילך צריך כינוי",
        )
    if len(defining_idxs) > 1:
        return _finding(3, "נכשל", f"ההגדרה מופיעה {len(defining_idxs)} פעמים, צריך פעם אחת בדיוק")
    define_at = defining_idxs[0]
    used_before = [
        i for i, t in enumerate(combined) if i < define_at and _PRINCIPAL_LAW_MENTION_RE.search(t)
    ]
    if used_before:
        return _finding(3, "נכשל", f"'החוק העיקרי' מוזכר בשורה {used_before[0]}, לפני שהוגדר בשורה {define_at}")
    return _finding(
        3,
        "עבר",
        f"{principal} הוראות תיקון לחוק העיקרי; ההגדרה מופיעה פעם אחת "
        f"(שורה {define_at}), וכל שימוש בא אחריה",
    )


_SIDE_HEADING_RE = re.compile(r"^(תיקון|החלפת|ביטול|הוספת) סעיף [^()]+$")


def _check_4(bill: Bill) -> Finding:
    bad = [ln.side_heading for ln in bill.lines if ln.side_heading and not _SIDE_HEADING_RE.match(ln.side_heading)]
    if bad:
        return _finding(4, "נכשל", f"כותרות שוליים שאינן בפורמט '{{סוג פעולה}} סעיף {{N}}': {bad}")
    return _finding(4, "עבר", "כל כותרות השוליים בפורמט התקני (§5.4), בלי אזכור סעיף קטן/פסקה")


def _check_5(bill: Bill) -> Finding:
    bad_idxs = [
        i for i, ln in enumerate(bill.lines) if "״" in (ln.text + ln.text_after + ln.side_heading)
    ]
    if bad_idxs:
        return _finding(5, "נכשל", f"נמצא ״ (U+05F4) בשורות: {bad_idxs} - יש להשתמש ב-\" (U+0022)")
    return _finding(5, "עבר", 'אין שימוש ב-״ (U+05F4) בשום שורה - כל הגרשיים הם " (U+0022)')


_HYPHEN_YEAR_RE = re.compile(r"[א-ת]-\d{4}")


def _check_6(bill: Bill) -> Finding:
    """בודקת רק טקסט שהמנוע עצמו מנסח (כותרות, side_heading, שורות
    ניסוח מנהלתיות) - לא תוכן מצוטט חדש (style="TableBlockOutdent",
    ראו template-spec.md: "הסגנון לכל שורה שמתחילה במרכאות ומצטטת
    נוסח חדש"). תוקן במשימה 6א אחרי שהתגלה מקרה אמיתי: הגדרה חדשה
    שהוכנסה (InsertAfter.new_child, נוסח מצוטט מקורי) הזכירה אותה
    שנה עברית שלוש פעמים באותו משפט עם en-dash פעם אחת ומקף רגיל
    פעמיים - חוסר עקביות אמיתי בטקסט המקור (Special:Export, לא משהו
    שהמנוע בנה), לא תקלה. חוק ברזל 1 אוסר על המנוע "לתקן" נוסח מצוטט
    כזה - השוואת דייקנות בטקסט המנוע בלבד היא הבדיקה הנכונה.

    **מגבלת היקף ידועה:** שורות מוטציה (_render_mutation) משלבות ניסוח
    מנהלתי וציטוט בתוך אותה שורה, באותו style="TableBlock" - הבדיקה
    לא מבחינה ביניהם בתוך שורה כזו. לא רלוונטי לשני מקרי הזהב הנוכחיים
    (אין שנה עברית בתוך הציטוט של שורת מוטציה), אבל עלול להצריך הכללה
    כשיגיע מקרה זהב עם שנה עברית בתוך ביטוי מוחלף/מוכנס."""
    bad_idxs = [
        i
        for i, ln in enumerate(bill.lines)
        if ln.style != "TableBlockOutdent"
        and (
            _HYPHEN_YEAR_RE.search(ln.text)
            or _HYPHEN_YEAR_RE.search(ln.text_after)
            or _HYPHEN_YEAR_RE.search(ln.side_heading)
        )
    ]
    if bad_idxs:
        return _finding(
            6,
            "נכשל",
            f"נמצא מקף רגיל (-) בשנה עברית בניסוח שהמנוע עצמו בנה, בשורות: "
            f"{bad_idxs} - צריך en-dash (–, U+2013)",
        )
    return _finding(
        6,
        "עבר",
        "כל שנה עברית בטקסט שהמנוע בנה משתמשת ב-en-dash (–) - לא נבדק תוכן "
        "מצוטט חדש (TableBlockOutdent), שחייב להישאר בדיוק כפי שסופק",
    )


_BILL_TITLE_RE = re.compile(r"^הצעת חוק .+ \(תיקון – .+\), התש[^–]+–\d{4}$")


def _check_7(bill: Bill) -> Finding:
    if not _BILL_TITLE_RE.match(bill.title):
        return _finding(
            7,
            "נכשל",
            f"שם ההצעה לא תואם לפורמט 'הצעת חוק X (תיקון – תיאור), התשע–שנה': {bill.title!r}",
        )
    return _finding(7, "עבר", "שם ההצעה תואם לפורמט §5.6 (פורמט קובץ הזהב, הצעה פרטית טרומית)")


_TITLE_YEAR_RE = re.compile(r"–(\d{4})$")
_SUBMITTED_YEAR_RE = re.compile(r"(\d{4})")


def _check_8(bill: Bill) -> Finding:
    """משווה את שנת ההצעה בשם ההצעה לשנת ההגשה בפועל - **רק כאשר תאריך
    ההגשה ידוע**.

    תוקן 2026-09-17: הבדיקה דרשה submitted_date כקלט חובה ונכשלה על
    40 מתוך 40 ההצעות האמיתיות שנבדקו. זו הייתה סתירה לתיעוד שלנו
    עצמנו - render_bill.Bill קובע במפורש ש-submitted_date "לא מודפס
    בכלל ב-docx... מזכירות הכנסת היא שכותבת את פסקת ההגשה, ורק אחרי
    שההצעה אושרה והונחה בפועל", כלומר זה לא שדה שהמנסח ממלא. כשהשדה
    ריק/placeholder הבדיקה מדווחת "לא נבדק" עם הסבר, לא "נכשל" -
    כשל שקוף על מידע שלא אמור להיות קיים אינו ממצא."""
    if not bill.submitted_date or not _SUBMITTED_YEAR_RE.search(bill.submitted_date):
        return _finding(
            8,
            "לא נבדק",
            "תאריך ההגשה בפועל לא ידוע (submitted_date ריק או placeholder) - "
            "פסקת ההגשה נכתבת על ידי מזכירות הכנסת אחרי ההנחה, לא על ידי "
            "המנסח. אין מול מה להשוות את שנת ההצעה בשם.",
        )
    title_match = _TITLE_YEAR_RE.search(bill.title)
    if not title_match:
        return _finding(8, "נכשל", f"לא נמצאה שנה בסוף שם ההצעה: {bill.title!r}")
    submitted_year = _SUBMITTED_YEAR_RE.search(bill.submitted_date).group(1)
    title_year = title_match.group(1)
    if submitted_year != title_year:
        return _finding(
            8,
            "נכשל",
            f"שנת ההצעה בשם ({title_year}) לא תואמת את שנת ההגשה בפועל ({submitted_year})",
        )
    return _finding(8, "עבר", f"שנת ההצעה בשם ({title_year}) תואמת את תאריך ההגשה בפועל")


_HEADING_SECTION_RE = re.compile(r"סעיף (\S+)$")


def _check_9(bill: Bill) -> Finding:
    seen_order: list[str] = []
    for ln in bill.lines:
        if not ln.side_heading:
            continue
        match = _HEADING_SECTION_RE.search(ln.side_heading)
        if match and match.group(1) not in seen_order:
            seen_order.append(match.group(1))
    if not seen_order:
        return _finding(9, "עבר", "אין כותרות סעיף בהצעה הזו - אין מה לבדוק")
    expected = sort_section_numbers(seen_order)
    if seen_order != expected:
        return _finding(9, "נכשל", f"סדר הסעיפים בפועל {seen_order} שונה מהסדר הכרונולוגי {expected}")
    return _finding(9, "עבר", f"סדר הסעיפים ({seen_order}) תואם את הסדר הכרונולוגי בחוק המתוקן")


def _check_10() -> Finding:
    return _finding(
        10,
        "לא נבדק",
        "דורש הצעת חוק שמתקנת יותר מחוק אחד (תיקונים עקיפים) - אין עדיין מקרה "
        "כזה במערכת. ממתין למקרה זהב עתידי עם יותר מחוק אחד.",
    )


_DEFINE_ANCHOR_RE = re.compile(r'^אחרי ההגדרה "([^"]+)" יבוא:$')
_DEFINE_TERM_RE = re.compile(r'^"([^"]+)"')


def _hebrew_sort_key(term: str) -> str:
    """מסיר ה' הידיעה בתחילת המונח לצורך מיון, לפי §3.6."""
    return term[1:] if term.startswith("ה") and len(term) > 1 else term


def _check_11(bill: Bill) -> Finding:
    """בודקת רק את המקרה הצר: הגדרה חדשה שהוכנסה אחרי הגדרה קיימת קונקרטית
    (דפוס 'אחרי ההגדרה X יבוא'), ומזהה חשד אם המונח החדש קטן א"ב-ית מהעוגן.
    **לא** בודקת סדר של רשימת ההגדרות המלאה, ולא בודקת הוספה בסוף רשימה
    לא-ממוינת (המדריך מתיר זאת במפורש - §2, כלל תיקון הגדרות)."""
    suspects = []
    for i, ln in enumerate(bill.lines):
        anchor_match = _DEFINE_ANCHOR_RE.match(ln.text)
        if not anchor_match or i + 1 >= len(bill.lines):
            continue
        anchor_term = anchor_match.group(1)
        term_match = _DEFINE_TERM_RE.match(bill.lines[i + 1].text)
        if not term_match:
            continue
        new_term = term_match.group(1)
        if _hebrew_sort_key(new_term) < _hebrew_sort_key(anchor_term):
            suspects.append((anchor_term, new_term))
    if suspects:
        return _finding(
            11,
            "אזהרה",
            f"הגדרות חדשות שהמונח שלהן קטן א\"ב-ית מהעוגן שאחריו הוכנסו (חשד לסדר "
            f"לא-אלפביתי, לא פסילה): {suspects}",
        )
    return _finding(11, "עבר", "לא נמצא חשד לסדר לא-אלפביתי בהגדרות שהוכנסו אחרי הגדרה קיימת")


_TRANSITION_WORDS = ("תחילה", "תחולה", "הוראת מעבר")


def _check_12(bill: Bill) -> Finding:
    headers = [ln.side_heading for ln in bill.lines if ln.side_heading]
    transition_headers = [h for h in headers if any(w in h for w in _TRANSITION_WORDS)]
    if not transition_headers:
        return _finding(12, "עבר", "אין סעיפי תחילה/תחולה/הוראת מעבר בהצעה הזו - אין מה לבדוק")
    if headers[-1] not in transition_headers:
        return _finding(
            12,
            "נכשל",
            f"יש כותרת תחילה/תחולה/הוראת מעבר ({transition_headers}) שאינה הכותרת "
            f"האחרונה בהצעה (האחרונה בפועל: {headers[-1]!r})",
        )
    return _finding(12, "עבר", "סעיפי תחילה/תחולה/הוראת מעבר ממוקמים בסוף ההצעה")


def _check_13() -> Finding:
    return _finding(
        13,
        "לא נבדק",
        "דורש חיפוש הצעות זהות/דומות ב-OData של הכנסת (משימה 8) - טרם מומש. "
        "ממתין למשימה 8.",
    )


_VALID_STYLES = {
    "TableBlock",
    "TableBlockOutdent",
    "TableHead",
    "TableSideHeading",
    "TableText",
    "TableText2",
    "TableHead2",
    "TableSideHeading2",
}  # ראו docs/template-spec.md - הרשימה המלאה של סגנונות הפסקה התקניים בטבלה
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _check_14(docx_path: Path | None) -> Finding:
    """בודקת רק שכל סגנון פסקה בטבלה הוא אחד מהסגנונות התקניים, וכל שורה
    בטבלה נותנת אותו רוחב כולל (gridSpan*width) - מגלה קריסה גסה של
    התבנית. **לא** משווה מול template-spec.md שדה-בשדה (זה בדיוק מה
    שמבחני הזהב עושים כבר, מול docx מקור אמיתי - ראו tests/golden/)."""
    if docx_path is None:
        return _finding(14, "לא נבדק", "לא סופק נתיב ל-docx שהופק - הבדיקה דורשת קובץ בפועל")
    from lxml import etree

    with zipfile.ZipFile(docx_path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    tbl = root.find(f"{_W_NS}body/{_W_NS}tbl")
    if tbl is None:
        return _finding(14, "נכשל", "לא נמצאה טבלה במסמך")
    bad_styles = []
    for tr in tbl.findall(f"{_W_NS}tr"):
        for tc in tr.findall(f"{_W_NS}tc"):
            style_el = tc.find(f"{_W_NS}p/{_W_NS}pPr/{_W_NS}pStyle")
            style = style_el.get(f"{_W_NS}val") if style_el is not None else None
            if style is not None and style not in _VALID_STYLES:
                bad_styles.append(style)
    if bad_styles:
        return _finding(14, "נכשל", f"נמצאו סגנונות פסקה שאינם תקניים: {sorted(set(bad_styles))}")
    return _finding(14, "עבר", "כל סגנונות הפסקה בטבלה הם מהרשימה התקנית (לא הושוו שדה-מול-שדה מול התבנית)")


def _check_15(bill: Bill) -> Finding:
    no_source = [i for i, ln in enumerate(bill.lines) if ln.source_node_id is None]
    if no_source:
        return _finding(15, "נכשל", f"שורות בלי source_node_id בכלל (אין מקור לצומת): {no_source}")
    no_date = [i for i, ln in enumerate(bill.lines) if ln.as_of is None]
    if no_date:
        return _finding(
            15,
            "נכשל",
            f"שורות עם source_node_id אבל בלי as_of (תאריך הנוסח לא ידוע): {no_date}",
        )
    return _finding(15, "עבר", "לכל שורה יש source_node_id ו-as_of")


def validate(
    bill: Bill,
    before: LegislativeNode,
    refs: dict[str, str],
    *,
    docx_path: Path | None = None,
) -> list[Finding]:
    """מריצה את כל 15 הבדיקות (docs/validator-checklist.md) ומחזירה
    Finding לכל אחת, לפי סדר. אף בדיקה לא נעלמת - "לא נבדק" גלוי כמו
    "נכשל" וכמו "עבר"."""
    return [
        _check_1(bill, before),
        _check_2(bill, refs),
        _check_3(bill),
        _check_4(bill),
        _check_5(bill),
        _check_6(bill),
        _check_7(bill),
        _check_8(bill),
        _check_9(bill),
        _check_10(),
        _check_11(bill),
        _check_12(bill),
        _check_13(),
        _check_14(docx_path),
        _check_15(bill),
    ]
