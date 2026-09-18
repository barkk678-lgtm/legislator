"""רינדור מסמך הסתייגויות ל-Word.

**זו אינה תבנית החקיקה.** מסמך הסתייגויות הוא מסמך אחר לגמרי, עם
כותרות היררכיות ורשימה - לא טבלה בת ארבע עמודות. הפריסה משוחזרת
מהמסמך שהונח בכנסת ב-16.6.2020
(`tests/fixtures/reservations/573919.docx`):

    Heading 1       הסתייגויות ובקשות רשות דיבור
    Heading 2       הסתייגויות
    Heading 3       לסעיף <N>
    Normal          חברי הכנסת <שמות> מציעים:
    List Paragraph  <הסתייגות>
    ...
    Heading 2       בקשות רשות דיבור

**המקרה הריק** (drafting-rules.md §9.2): גם כשאין הסתייגויות,
המקטע קיים ונושא נוסח מפורש - "אין הסתייגויות". נלמד משני נוסחים
נוספים משנים 2012 ו-2014, ששניהם ריקים. רנדרר שמשמיט את המקטע
כשהרשימה ריקה מפיק מסמך שאינו תואם לפרקטיקה.

**הסדר מחייב** ואינו עניין של נוחות: תקנון הכנסת קובע שהסתייגויות
מנומקות "לגבי כל סעיף של הצעת החוק בנפרד, לפי הסדר שבו נרשמו
בנוסח שהונח על שולחן הכנסת".
"""

from __future__ import annotations

from pathlib import Path

from model import DraftedReservation, Reservation

EMPTY_NOTICE = "אין הסתייגויות"
_H1 = "הסתייגויות ובקשות רשות דיבור"
_H2_RESERVATIONS = "הסתייגויות"
_H2_SPEAKING = "בקשות רשות דיבור"


def _proposers_line(names: list[str]) -> str:
    """שורת המציעים, בדיוק בצורה שנצפתה במסמך שהונח:
    "חברי הכנסת נפתלי בנט, אילת שקד, בצלאל סמוטריץ', מתן כהנא ואופיר סופר מציעים:"

    ו' החיבור **צמודה לשם ובלי מקף** ("ואופיר"), בניגוד לכותרת
    "הוספת סעיפים 2ג ו־2ד" שבה כן מופיע מקף עברי (U+05BE). שתי
    מוסכמות שונות, שתיהן נצפו במסמכים אמיתיים - לא להאחיד ביניהן."""
    if not names:
        return "מציעים:"
    prefix = "חבר/ת הכנסת" if len(names) == 1 else "חברי הכנסת"
    joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" ו{names[-1]}"
    return f"{prefix} {joined} מציעים:"


def _bill_reference(bill_title: str) -> str:
    """"להצעת חוק X" - ולא "להצעת הצעת חוק X". שם ההצעה מגיע לפעמים
    עם התחילית "הצעת" ולפעמים בלעדיה."""
    title = bill_title.strip()
    if title.startswith("הצעת "):
        title = title[len("הצעת "):]
    return f"להצעת {title}"



def build_document(
    *,
    bill_title: str,
    reservations: list[Reservation | DraftedReservation],
    proposers: list[str],
    speaking_requests: list[str] | None = None,
    budget_flags: dict[int, str] | None = None,
):
    """בונה מסמך python-docx. הסתייגויות מקובצות לפי סעיף, **בסדר
    שבו הן התקבלו** - הפונקציה אינה ממיינת מחדש."""
    import docx  # noqa: PLC0415

    budget_flags = budget_flags or {}
    doc = docx.Document()
    doc.add_heading(_H1, level=1)
    doc.add_paragraph(_bill_reference(bill_title))
    doc.add_heading(_H2_RESERVATIONS, level=2)

    if not reservations:
        # ראו docstring: המקטע קיים גם כשהוא ריק.
        doc.add_paragraph(EMPTY_NOTICE)
    else:
        current_section = object()
        for index, item in enumerate(reservations):
            if item.section_number != current_section:
                current_section = item.section_number
                doc.add_heading(f"לסעיף {current_section}", level=3)
                doc.add_paragraph(_proposers_line(proposers))
            text = item.text
            if index in budget_flags:
                text = f"{text}  [עלות תקציבית — {budget_flags[index]}]"
            doc.add_paragraph(text, style="List Paragraph")

    doc.add_heading(_H2_SPEAKING, level=2)
    for name in speaking_requests or []:
        doc.add_paragraph(name)
    if not speaking_requests:
        doc.add_paragraph("להצעת החוק לא הוגשו בקשות רשות דיבור.")
    return doc


def write_docx(out: Path, **kwargs) -> Path:
    build_document(**kwargs).save(str(out))
    return out
