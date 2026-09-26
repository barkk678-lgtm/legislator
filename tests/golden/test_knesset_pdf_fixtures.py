"""הכרעה ז (ברק, 26.9.2026): נוסחים ציבוריים מהכנסת כ-fixtures (עד 20), ובדיקת
זהב שנכשלת לפני כל תיקון. הקבצים: tests/fixtures/reservations/pdf (README שם).

מה נמצא בכל אחד, ומה תוקן:
- **491290** - כותרות "לסעיף 2(1)", "לסעיף 15(2) עד (12)" לא זוהו בכלי המדידה, וכל
  ההסתייגויות אחרי "לסעיף 1" נספרו תחתיו (31/81). **לא תוכן עניינים** - האבחון
  בלילה היה שגוי; הקריאה של ההצעה הייתה נכונה.
- **175006** - הזנב של "* הערה: ... לסעיף 10" נשבר לשורה משלו ונקרא ככותרת: ההסתייגות
  לסעיף 11 נספרה תחת 10. **לא הזחה במספור** - גם כאן כלי המדידה.
- **4715569** - מספור של נוסח מצוטט ("1-4", "1-7" אחרי סעיף 38) נקרא כסעיפים חדשים
  ודרס את סעיפים 2 ו-4. **תוקן בקורא:** מספר שאינו עולה אינו סעיף חדש, והסעיף - לא ודאי.
- **263401** - הספרות בשכבת הטקסט של הקובץ עצמו משובשות (1 ו-0 -> "4", 3 ו-4 -> "0",
  2 ו-5 -> "9"; pdftotext קורא בדיוק כך) - **הכשל במקור, לא אצלנו**. גם "ש-04%" בא
  משם. מה שתוקן: הקובץ מזוהה, כל ההצעה לא ודאית, ואין עוגנים - לא מנחשים.
- **5121778** - "לסעיף 6" כשבהצעה חמישה סעיפים בלבד (אחרי 5 - הכוכביות): ההסתייגות
  מפנה לסעיף שאינו קיים בנוסח הזה. הכשל במקור; נשאר חסר.
- **4690270** - "בתוספת הראשונה, בפרטים 1 ו־2" תחת "לסעיף 2": התוספת יושבת בסוף ההצעה.
- **10842601, 7184628** - ביקורת נקייה (11/11, 49/49) - לא נשברת.
- **628446** - חיובי שגוי של "ספרות לא קריאות" שנמצא בריצת המדגם: "1" בלי נקודה. תוקן.
- **240417** - ספרות מוזזות במקור (אחד משבעה נוספים במדגם); מסומן כלא ודאי - נכון.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))
sys.path.insert(0, str(ROOT / "tools"))

import families  # noqa: E402
import reservations_quote_check as qc  # noqa: E402
from pdf_bill import parse_bill_pdf  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "reservations" / "pdf"
FOUND = ("exact", "typography", "inner_quotes")
_cache: dict = {}


def _check(doc):
    if doc not in _cache:
        _cache[doc] = qc.check(FIX / f"{doc}.pdf")
    return _cache[doc]


def _found(doc):
    quotes, _ = _check(doc)
    return sum(q.result in FOUND for q in quotes), len(quotes)


def _numbers(doc):
    return _check(doc)[1]["section_numbers"]


def test_491290_heading_with_unit():
    quotes, _ = _check("491290")
    q13 = [q for q in quotes if q.reservation == "13"]
    assert q13 and all(q.section == "2" and q.unit == "(2)" for q in q13), [(q.heading, q.unit) for q in q13]
    assert {q.heading for q in quotes} >= {"לסעיף 2(2)", "לסעיף 24(2)"}, sorted({q.heading for q in quotes})
    found, total = _found("491290")
    assert found >= 77, (found, total)          # היה 31


def test_175006_note_tail_is_not_a_heading():
    quotes, _ = _check("175006")
    alt = [q for q in quotes if q.phrase in ("ולטיפול השוטף בו", "לפי חוק זה;") and q.reservation == "2/חלופה"]
    assert len(alt) == 2 and all(q.section == "11" for q in alt), [(q.heading, q.phrase) for q in alt]
    assert _found("175006") == (25, 25)


def test_4715569_quoted_numbering_is_not_sections():
    nums = _numbers("4715569")
    assert len(nums) == len(set(nums)) == 77, nums          # היו 88, עם 1-7 פעמיים
    keys = [(int(n.rstrip("אבגדהוזחטיכלמנסעפצקרשת")), n) for n in nums]
    assert keys == sorted(keys), nums
    bill = parse_bill_pdf(FIX / "4715569.pdf")
    s38 = next(s for s in bill.sections if s.number == "38")
    assert not s38.certain                                   # המצוטט נכנס אליו - לא ודאי
    found, total = _found("4715569")
    assert found >= 9, (found, total)                        # היה 2


def test_263401_unreadable_digits_no_anchors():
    bill = parse_bill_pdf(FIX / "263401.pdf")
    assert any("מספרי הסעיפים בקובץ אינם קריאים" in w for w in bill.warnings), bill.warnings
    assert bill.sections and not any(s.certain for s in bill.sections)
    for level in ("serious", "clever", "absurd"):
        items = families.plan(bill, level, list(families.FAMILIES), 1000).items
        assert items == [], (level, [it.text for it in items][:3])


def test_5121778_reservation_to_missing_section_stays_missing():
    assert _numbers("5121778") == ["1", "2", "3", "4", "5"]
    quotes, _ = _check("5121778")
    q6 = [q for q in quotes if q.section == "6"]
    assert q6 and all(q.result == "missing" for q in q6)     # כשל המקור - לא ממציאים סעיף 6


def test_4690270_schedule_quote():
    assert _found("4690270") == (1, 1)


def test_clean_controls():
    assert _found("10842601") == (11, 11)
    assert _found("7184628") == (49, 49)
    for doc in ("10842601", "7184628", "175006"):
        bill = parse_bill_pdf(FIX / f"{doc}.pdf")
        assert all(s.certain for s in bill.sections) or doc == "7184628", doc
        assert not any("אינם קריאים" in w for w in bill.warnings), (doc, bill.warnings)


def test_628446_number_without_period_is_a_section():
    """המספר של סעיף 1 נקרא "1" בלי נקודה (הנקודה נפלה מהעמודה). בלי זה סעיף 1 לא זוהה,
    הרצף התחיל ב-2, וכל ההצעה סומנה "ספרות לא קריאות" - חיובי שגוי (ריצת המדגם, 26.9)."""
    bill = parse_bill_pdf(FIX / "628446.pdf")
    assert [s.number for s in bill.sections][:3] == ["1", "2", "3"], [s.number for s in bill.sections]
    assert bill.sections[0].margin_title == "תיקון סעיף 3" and "להטלה" in bill.sections[0].text
    assert not any("אינם קריאים" in w for w in bill.warnings), bill.warnings
    assert all(s.certain for s in bill.sections)


def test_240417_shifted_digits_flagged():
    """הספרות בשכבת הטקסט מוזזות ("התש"ע–3121" במקום 2010, סעיפים 2..9, 21..27) - במקור."""
    bill = parse_bill_pdf(FIX / "240417.pdf")
    assert any("אינם קריאים" in w for w in bill.warnings), bill.warnings
    assert not any(s.certain for s in bill.sections)


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_knesset_pdf_fixtures: כל הבדיקות עברו")
