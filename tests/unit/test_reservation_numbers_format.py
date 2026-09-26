"""הכרעה ב (ברק, 26.9.2026): "שנה 3000" ו-"10,000 ימים" בהזוי - מאושר; **מספר
מ-1,000 ומעלה נכתב עם מפריד אלפים** ("10,000", לא "10000"). שנה - בלי מפריד.
נכשל על הקוד הקודם (573919 בהזוי יצר "1000" ו-"10000").
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import families  # noqa: E402
from bill_input import read_bill  # noqa: E402
from pdf_bill import BillSection, BillUnit, ParsedBill  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "reservations" / "573919.docx"


def _new_values(items):
    return [m.group(1) for it in items for m in [re.search(r'יבוא "([^"]+)"', it.text)] if m]


def test_no_bare_thousands():
    bills = [read_bill("573919.docx", FIX.read_bytes()),
             ParsedBill(title="חוק הבדיקה", committee="ועדת הכלכלה", sections=[
                 BillSection("1", "תיקון", BillUnit("lead", "", "השר יודיע על כך בתוך 30 ימים ממועד ההחלטה."), [])],
                 warnings=[])]
    for bill in bills:
        for level in ("serious", "clever", "absurd"):
            values = _new_values(families.plan(bill, level, list(families.FAMILIES), 1000).items)
            bad = [v for v in values if re.search(r"(?<![\d,])\d{4,}(?![\d,])", v) and not re.fullmatch(r"(?:1[89]|2\d)\d{2}|3000", v)]
            assert not bad, (level, bad)


def test_absurd_years_on_573919():
    bill = read_bill("573919.docx", FIX.read_bytes())
    values = _new_values(families.plan(bill, "absurd", list(families.FAMILIES), 1000).items)
    assert "3000" in values and "2100" in values, values          # שנה - בלי מפריד


def test_absurd_bare_number():
    bill = ParsedBill(title="חוק הבדיקה", committee="ועדת הכלכלה", sections=[
        BillSection("1", "תיקון", BillUnit("lead", "", "הוועדה תמנה לפחות 7 חברים מקרב הציבור."), [])],
        warnings=[])
    values = _new_values(families.plan(bill, "absurd", list(families.FAMILIES), 1000).items)
    assert "10,000" in values and "1,000" in values, values        # מספר - עם מפריד
    assert "10000" not in values and "1000" not in values, values


def test_digit_quantity_gets_separator():
    bill = ParsedBill(title="חוק הבדיקה", committee="ועדת הכלכלה", sections=[
        BillSection("1", "תיקון", BillUnit("lead", "", "השר יודיע על כך בתוך 30 ימים ממועד ההחלטה."), [])],
        warnings=[])
    values = _new_values(families.plan(bill, "absurd", list(families.FAMILIES), 1000).items)
    assert "3,000 ימים" in values and "30,000 ימים" in values, values


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservation_numbers_format: כל הבדיקות עברו")
