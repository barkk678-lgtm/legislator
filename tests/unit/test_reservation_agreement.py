"""הכרעה ג (ברק, 26.9.2026): החלפת גורם - **מחליפים את הגורם ומתאימים את הפועל או
התואר שאחריו למין של הגורם החדש**: "הממשלה תתקן", לא "הממשלה יתקן".

- דטרמיניסטי בלבד: טבלה סגורה (agreement.py) של מין הגורם ושל צמדי צורות.
- ההתאמה רק כשהמילה שאחרי הגורם בטבלה - המיקום הוודאי הוא המילה הצמודה.
- אחרת - רק גורם מאותו מין. המודל לא כותב כלום.
נכשל על הקוד הקודם (`במקום "שר הפנים" יבוא "הממשלה".`).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import agreement  # noqa: E402
import bank  # noqa: E402
import families  # noqa: E402
from pdf_bill import BillSection, BillUnit, ParsedBill, parse_bill_pdf  # noqa: E402

TIBERIAS = parse_bill_pdf(ROOT / "reference" / "הצעת חוק טבריה.pdf")


def _with_records(values, fn):
    records = [bank.Record(id=f"t-{i}", level="serious", family="actor_swap", template="{value}",
                           value=v, status="approved") for i, v in enumerate(values)]
    verdicts = {r.id: {"key": r.screen_key, "allowed": True} for r in records}
    orig_all, orig_v = bank.load_all, bank._screen_verdicts
    bank.load_all, bank._screen_verdicts = (lambda: records), (lambda: verdicts)
    try:
        return fn()
    finally:
        bank.load_all, bank._screen_verdicts = orig_all, orig_v


def _swaps(bill, values):
    items = _with_records(values, lambda: families.candidates(bill, "serious", ["actor_swap"])[0])
    return [it.text for it in items]


def test_tables():
    assert agreement.gender("שר הפנים") == "m" and agreement.gender("הממשלה") == "f"
    assert agreement.gender("ועדה ציבורית שימנה השר") == "f" and agreement.gender("מבקר המדינה") == "m"
    assert agreement.gender("משהו שאינו בטבלה") is None
    assert agreement.inflect("יתקן", "f") == "תתקן" and agreement.inflect("תתקן", "m") == "יתקן"
    assert agreement.inflect("רשאי", "f") == "רשאית" and agreement.inflect("יקבע", "f") == "תקבע"
    assert agreement.inflect("ימציא", "f") is None      # לא בטבלה - אין התאמה


def test_tiberias_feminine_actor_agrees():
    got = _swaps(TIBERIAS, ["הממשלה"])
    assert got == ['במקום "שר הפנים יתקן" יבוא "הממשלה תתקן".'], got


def test_tiberias_masculine_actor_unchanged():
    got = _swaps(TIBERIAS, ["שר האוצר"])
    assert got == ['במקום "שר הפנים" יבוא "שר האוצר".'], got


def test_no_table_word_means_same_gender_only():
    bill = ParsedBill(title="חוק הבדיקה", committee="ועדת הכלכלה", sections=[
        BillSection("1", "תיקון", BillUnit("lead", "", "שר האוצר ימציא לוועדה דוח שנתי על ביצוע החוק."), [])],
        warnings=[])
    got = _swaps(bill, ["הממשלה", "שר המשפטים", "מבקר המדינה"])
    assert got == ['במקום "שר האוצר" יבוא "שר המשפטים".', 'במקום "שר האוצר" יבוא "מבקר המדינה".'], got


def test_unknown_gender_record_is_skipped():
    got = _swaps(TIBERIAS, ["גורם שאין לו מין בטבלה"])
    assert got == [], got


def test_same_point_for_estimate():
    items = _with_records(["הממשלה", "שר האוצר"],
                          lambda: families.candidates(TIBERIAS, "serious", ["actor_swap"])[0])
    assert len({it.group for it in items}) == 1, [it.group for it in items]


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservation_agreement: כל הבדיקות עברו")
