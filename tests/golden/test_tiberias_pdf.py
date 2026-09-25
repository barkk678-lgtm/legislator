"""מקרה זהב של כלי ההסתייגויות: קריאת reference/הצעת חוק טבריה.pdf (הסתייגויות 1, 26.9).

הצעת חוק הרשויות המקומיות (בחירות) (תיקון מס' 53), פ/3343/25, נוסח לקריאה
שנייה ושלישית עם 112 הסתייגויות אמיתיות.

**שתי שכבות:**
1. **הקריאה, מילה במילה** - הנוסח הצפוי הוקלד מהעמוד עצמו (עמ' 1 של ההצעה),
   לא הועתק מהפלט. כל אחד מארבעת הכשלים של חילוץ טקסט רגיל נבדק כאן:
   `)1(`, `התשכ"ה–11965`, כותרת שוליים בתוך הגוף, `סעיף ,143`.
2. **הציטוטים** - כל ביטוי שהסתייגות אמיתית מצטטת מההצעה נמצא בחילוץ
   (tools/reservations_quote_check.py). 116 מתוך 124. **שמונה החסרים הם
   ציטוטים לא מדויקים בהסתייגויות עצמן**, ונבדקו מול העמוד:
   - 17: `במקום "(א1), (2)"` - בהצעה `"(א1), (א2)"` (נבדק בתמונת העמוד);
   - 47/ג-ז: `"בהתאם לסעיף 7 לחוק העיקרי, כנוסחו בסעיף 1 לחוק זה, ..."` - בהצעה
     `"בהתאם לסעיף 7 לחוק העיקרי כנוסחו בחוק זה, ..."`;
   - 48/ז-ח: `"בתוך 30 ימים"` - בהצעה `"בתוך שלושים ימים"`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))
sys.path.insert(0, str(ROOT / "tools"))

from pdf_bill import _logical, parse_bill_pdf  # noqa: E402
import reservations_quote_check as quote_check  # noqa: E402

PDF = ROOT / "reference" / "הצעת חוק טבריה.pdf"

WANT_SECTIONS = [
    ("1", "תיקון סעיף 7",
     'בחוק הרשויות המקומיות (בחירות), התשכ"ה–1965 (להלן – החוק העיקרי), בסעיף 7 –',
     [("(1)", 'בסעיף קטן (א), במקום "(א1), (א2)" יבוא "(א2)";'),
      ("(2)", "סעיף קטן (א1) – בטל.")]),
    ("2", "תיקון חוק הרשויות המקומיות (הגבלת הזכות להיבחר)",
     'בחוק הרשויות המקומיות (הגבלת הזכות להיבחר), התשכ"ד–1964, בסעיף 2, אחרי סעיף קטן (ב) יבוא: '
     '"(ג) לעניין סעיף זה, יראו את מי שכיהן כיושב ראש ועדה או כחבר ועדה למילוי תפקידי ראש רשות '
     'מקומית ומועצת הרשות או למילוי תפקידי המועצה, בהתאם להוראות לפי סעיף 143, 143א או 206 '
     'לפקודת העיריות, או לפי סעיף 38 או 38א לפקודת המועצות המקומיות, כעובד הרשות המקומית המנוי '
     'בתוספת."',
     []),
    ("3", "תיקון צו כינון",
     'שר הפנים יתקן את צו המועצות המקומיות (מועצות אזוריות), התשי"ח–1958, בהתאם לסעיף 7 לחוק '
     'העיקרי כנוסחו בחוק זה, ובשינויים המחויבים, בתוך שלושים ימים מיום תחילתו של חוק זה.',
     []),
]

# ציטוטים שההסתייגויות עצמן מצטטות לא במדויק (ראו למעלה) - לא כשל קריאה.
KNOWN_MISQUOTES = {"17", "47/ג", "47/ד", "47/ה", "47/ו", "47/ז", "48/ז", "48/ח"}


def main() -> int:
    checks = []

    # ── הכיוון: שורה חזותית -> לוגית ─────────────────────────────────────
    # "(1)" נשמר ב-PDF בסדר חזותי ")", "1", "(" (התו הימני הוא "(" הלוגי).
    checks.append(("כיוון: סוגריים סביב ספרה", _logical(list(")1(")) == "(1)", _logical(list(")1("))))
    checks.append(("כיוון: מספר עם מפריד", _logical(list("3343/25")) == "3343/25", _logical(list("3343/25"))))
    checks.append(("כיוון: עברית ומספר", _logical(list("143 ףיעס")) == "סעיף 143", _logical(list("143 ףיעס"))))

    bill = parse_bill_pdf(PDF)
    checks.append(("שם החוק", bill.title == 'חוק הרשויות המקומיות (בחירות) (תיקון מס\' 53) התשפ"ג–2023', bill.title))
    checks.append(("הוועדה מעמוד השער", bill.committee == "ועדת הפנים והגנת הסביבה", bill.committee))
    checks.append(("שלושה סעיפים, ולא יותר (ההסתייגויות אינן חלק מההצעה)",
                   [s.number for s in bill.sections] == ["1", "2", "3"], str([s.number for s in bill.sections])))
    for (number, margin, lead, units), got in zip(WANT_SECTIONS, bill.sections):
        checks.append((f"סעיף {number}: כותרת השוליים", got.margin_title == margin, got.margin_title))
        checks.append((f"סעיף {number}: הרישה, מילה במילה", got.lead.text == lead, got.lead.text))
        got_units = [(u.label, u.text) for u in got.units]
        checks.append((f"סעיף {number}: היחידות", got_units == units, str(got_units)))
        checks.append((f"סעיף {number}: קריאה ודאית", got.certain, ""))
    all_text = " ".join(s.text for s in bill.sections)
    checks.append(("בלי מספר הערת שוליים שנדבק לשנה", "11965" not in all_text and "21964" not in all_text, ""))
    checks.append(("בלי סוגריים הפוכים", ")1(" not in all_text and ")א(" not in all_text, ""))
    checks.append(("בלי פסיק לפני מספר", "סעיף ,143" not in all_text, ""))
    checks.append(("כותרת השוליים לא בתוך הגוף", "המקומיות (הגבלת הזכות" not in bill.sections[1].lead.text.split("בסעיף 2")[1], ""))

    # ── הציטוטים ─────────────────────────────────────────────────────────
    quotes, summary = quote_check.check(PDF)
    checks.append(("124 ציטוטים מההצעה ב-112 ההסתייגויות", len(quotes) == 124, str(len(quotes))))
    found = [q for q in quotes if q.result in ("exact", "typography", "inner_quotes")]
    checks.append(("116 נמצאו", len(found) == 116, str(summary["counts"])))
    missing = {q.reservation for q in quotes if q.result not in ("exact", "typography", "inner_quotes")}
    checks.append(("כל החסרים - ציטוטים לא מדויקים בהסתייגויות עצמן", missing == KNOWN_MISQUOTES, str(sorted(missing))))
    checks.append(("אף ציטוט לא נמצא רק בסעיף ולא ביחידה שצוינה",
                   not any(q.result == "section_only" for q in quotes), ""))

    bad = [c for c in checks if not c[1]]
    for name, ok, info in checks:
        print(("OK   " if ok else "FAIL "), name, "" if ok else f"\n      {info}")
    print("\nתוצאה:", "עבר" if not bad else f"נכשל ({len(bad)})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
