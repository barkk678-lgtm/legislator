"""טסטים ל-packages/documents/extract_doc.py, על קובץ `.doc` אמיתי.

**הטסט המרכזי כאן הוא טסט מפריך.** בדקתי אם אפשר לשחזר מ-`.doc` את
מבנה שמונה העמודות של תבנית הכנסת - כלומר את עומק ההזחה - על ידי
חלוקת רצף התאים לקבוצות של שמונה. ההנחה נפלה על שני הקבצים
האמיתיים שיש: שארית שאינה מתחלקת, ועשרות תאים שנוחתים בעמודה
הלא-נכונה. הטסט נועל את ההפרכה כדי שלא ינסו שוב ויאמינו.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "documents"))

from extract_doc import DocBinaryError, extract_rows, extract_text, plain_text  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "doc" / "302894.doc"
_NUMBER_RE = re.compile(r"^\d+[א-ת]*\.$")


def main() -> int:
    checks: list[tuple[str, bool]] = []
    data = FIXTURE.read_bytes()

    text = extract_text(data)
    checks.append(("טקסט חולץ בכלל", len(text) > 1000))
    checks.append(("עברית נקייה, לא ג'יבריש מ-cp1252",
                   "הצעת חוק ההגבלים העסקיים" in text))
    checks.append(("שם ההצעה המלא, כולל גרש ומקף עברי",
                   'הצעת חוק ההגבלים העסקיים (תיקון מס\' 16), התשע"ה–2014' in text))
    checks.append(("נוסח מגוף ההצעה, לא רק העמוד הראשון",
                   "אחרי סעיף 30 לחוק העיקרי יבוא" in text))
    checks.append(("סימני תא נשמרים ב-extract_text", "\x07" in text))

    plain = plain_text(data)
    checks.append(("plain_text בלי סימני תא", "\x07" not in plain))
    checks.append(("plain_text בלי תווי בקרה של שדות",
                   not any(chr(c) in plain for c in (0x01, 0x02, 0x13, 0x14, 0x15))))
    checks.append(("plain_text בלי שורות ריקות", "\n\n" not in plain))
    checks.append(("plain_text שומר את הנוסח", "תחילתו של סעיף 1 לחוק זה" in plain))

    rows = extract_rows(data)
    table_rows = [r for r in rows if len(r) > 1]
    checks.append(("זוהו שורות טבלה", len(table_rows) >= 1))
    checks.append(("כותרת שוליים אמיתית בתא הראשון", table_rows[0][0] == "תיקון סעיף 3"))
    checks.append(("מספר סעיף אמיתי בתא השני", table_rows[0][1] == "1."))

    # **ההפרכה.** אם מבנה שמונה העמודות היה משתחזר מרצף התאים, כל
    # התאים היו מתחלקים ב-8 וכל תא שני בכל קבוצה היה מספר סעיף.
    cells = [c for r in table_rows for c in r]
    remainder = len(cells) % 8
    misplaced = sum(
        1 for i in range(0, len(cells) - 7, 8)
        if cells[i + 1] and not _NUMBER_RE.match(cells[i + 1])
    )
    checks.append(("שמונה עמודות: השארית אינה אפס (ההנחה נופלת)", remainder != 0))
    checks.append(("שמונה עמודות: יש תאים בעמודה הלא-נכונה", misplaced > 0))
    # ולכן: אין depth, ולכן extract_doc אינו מחובר לנתיב שדורש עומק.
    checks.append(("extract_doc אינו מייצא ExtractedBill",
                   not any(n.startswith("extract_bill") for n in dir(sys.modules["extract_doc"]))))

    raised = False
    try:
        extract_text(b"not an ole file at all")
    except DocBinaryError:
        raised = True
    checks.append(("קובץ שאינו OLE -> DocBinaryError, לא קריסה", raised))

    raised = False
    try:
        extract_text((Path(__file__).resolve().parents[1] / "fixtures" / "reservations"
                      / "387338.docx").read_bytes())
    except DocBinaryError:
        raised = True
    checks.append((".docx מוגש כ-.doc -> DocBinaryError מפורש", raised))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
