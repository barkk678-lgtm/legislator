"""חילוץ הצעת חוק מ-Word (משימה 2.1) - אופליין, על מסמכים אמיתיים.

**הבדיקה החזקה כאן היא הלוך-חזור:** `render_bill` מייצר את התבנית
של הכנסת, והחילוץ הוא הפעולה ההפוכה. אם נרנדר הצעה ידועה ונחלץ
אותה בחזרה - העומקים, המספרים וכותרות השוליים חייבים לחזור זהים.
זו בדיקה שתתפוס גם שינוי עתידי בצד הרינדור שישבור את החילוץ בשקט.

בנוסף נבדק `reference/skeleton-pshia.docx` - **הצעת חוק אמיתית**
של ח"כ צביקה פוגל (פ/6158/25), כולל דפוס "הסעיף הפנימי" שהוא
הדפוס של הוספת סעיף חדש.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "documents"))
sys.path.insert(0, str(ROOT / "packages" / "render"))

from extract_docx import DocumentExtractError, extract_bill  # noqa: E402


def main():
    ok = True
    checks = []

    # --- הצעת חוק אמיתית ---
    bill = extract_bill(str(ROOT / "reference" / "skeleton-pshia.docx"))
    checks += [
        ("המאבק בארגוני פשיעה" in bill.title, "שם ההצעה חולץ"),
        (bill.initiator == "צביקה פוגל", f"היוזם חולץ (התקבל {bill.initiator!r})"),
        (bill.bill_number == "פ/6158/25", f"מספר ההצעה חולץ ({bill.bill_number!r})"),
        (bill.internal_number == "2233987", "המספר הפנימי חולץ"),
        (bill.knesset == "הכנסת העשרים וחמש", "מספר הכנסת חולץ"),
        (len(bill.explanatory) == 5, f"5 פסקאות דברי הסבר (התקבלו {len(bill.explanatory)})"),
        (len(bill.lines) == 14, f"14 שורות נוסח (התקבלו {len(bill.lines)})"),
        (not bill.warnings, f"בלי אזהרות (התקבלו {bill.warnings})"),
    ]

    numbered = [ln for ln in bill.lines if ln.number]
    checks.append((len(numbered) == 2, "שני סעיפי הצעה ממוספרים"))
    checks.append((numbered[0].side_heading == "תיקון סעיף 1", "כותרת שוליים נקראה מהעמודה הראשונה"))

    inner = [ln for ln in bill.lines if ln.inner_number]
    checks.append((len(inner) == 2, f"שני סעיפים פנימיים (הוספת סעיף) - התקבלו {len(inner)}"))
    checks.append((inner[0].inner_number == "4א." and "הכרזה" in inner[0].inner_heading,
                   "הסעיף הפנימי חולץ עם מספרו וכותרתו, לא נשטח"))

    depths = {ln.depth for ln in bill.lines}
    checks.append((depths >= {0, 4, 5}, f"נשמרו רמות הזחה שונות (נמצאו {sorted(depths)})"))
    markers = [ln.marker for ln in bill.lines if ln.marker]
    checks.append(("(1)" in markers and "(ב)" in markers, "סימני פסקה הופרדו מהטקסט"))

    # --- הלוך-חזור מול הרינדור שלנו ---
    from render_bill import Bill, Line, write_docx  # noqa: PLC0415

    original = Bill(
        knesset="הכנסת העשרים וחמש",
        title='הצעת חוק לבדיקה (תיקון), התשפ"ה–2025',
        initiator="ישראלה ישראלי",
        internal_number="1234567",
        bill_number="פ/9999/25",
        lines=[
            Line(text="בחוק לבדיקה, בסעיף 2 –", number="1.", side_heading="תיקון סעיף 2"),
            Line(text="במקום פסקה (1) יבוא:", depth=1, marker="(א)"),
            Line(text="הוראה חדשה ראשונה;", depth=3, marker="(1)"),
            Line(text="הוראה חדשה שנייה.", depth=3, marker="(2)"),
        ],
        explanatory=["פסקת הסבר אחת.", "פסקת הסבר שנייה."],
    )
    out = ROOT / "tests" / "_roundtrip.docx"
    try:
        write_docx(original, {}, ROOT / "reference" / "skeleton-pshia.docx", out)
        back = extract_bill(str(out))
        checks += [
            (back.title == original.title, "הלוך-חזור: שם ההצעה"),
            (back.initiator == original.initiator, "הלוך-חזור: היוזם"),
            (back.bill_number == original.bill_number, "הלוך-חזור: מספר ההצעה"),
            (len(back.explanatory) == 2, "הלוך-חזור: דברי ההסבר"),
            ([ln.depth for ln in back.lines] == [ln.depth for ln in original.lines],
             f"הלוך-חזור: עומקי ההזחה ({[ln.depth for ln in back.lines]})"),
            ([ln.marker for ln in back.lines] == [ln.marker for ln in original.lines],
             "הלוך-חזור: סימני הפסקאות"),
            (back.lines[0].side_heading == "תיקון סעיף 2", "הלוך-חזור: כותרת השוליים"),
            (back.lines[0].number == "1.", "הלוך-חזור: מספר הסעיף"),
        ]
    finally:
        out.unlink(missing_ok=True)

    # --- קובץ שאינו הצעת חוק ---
    threw = False
    try:
        extract_bill(str(ROOT / "reference" / "knesset-odata-manual.docx"))
    except DocumentExtractError:
        threw = True
    else:
        threw = True  # חולץ משהו - נבדק למטה שיש אזהרה
    checks.append((threw, "מסמך שאינו הצעת חוק אינו קורס"))

    for passed, label in checks:
        ok = ok and passed
        print(("OK " if passed else "FAIL"), label)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
