"""הכרעה ד (ברק, 26.9.2026): בתבניות הבנק שכתוב בהן "השר" ("ובלבד שהשר ידווח...")
כותבים את השר המפורש **מתוך ההצעה עצמה**:
1. שר בשמו בסעיף - הוא; 2. אחרת, שר אחד בלבד בהצעה כולה - הוא;
3. אחרת, ההצעה משתמשת ב"השר" - נשאר "השר"; 4. אחרת - התבנית לא מופעלת.
המודל לא בוחר שר. הרשומות עצמן (ופסק הסינון שלהן) לא משתנות - ההחלפה בזמן הרינדור.
נכשל על הקוד הקודם (בטבריה יצא "ובלבד שהשר ידווח...").
"""

import dataclasses
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402
import families  # noqa: E402
from pdf_bill import BillSection, BillUnit, ParsedBill, parse_bill_pdf  # noqa: E402

TIBERIAS = parse_bill_pdf(ROOT / "reference" / "הצעת חוק טבריה.pdf")
# הרשומות של ד (conditions-001/002, actor_swap-007/009) נמחקו באישורי הבנק (26.9) והוחלפו:
# תנאי "{השר}" - בתבניות לאחרי הסעיף האחרון ובתנאים מתחכמים; "סגן השר" - "סגן {שר}".
# הכלל של ד לא השתנה, ולכן הבדיקה עליו - על רשומות בזיכרון בלבד. **השר בבנק נכתב
# כמציין {השר}**, ורק הוא מוחלף (סבב התיקונים, 26.9 - "השר ל..." מרשימת השרים לא נוגעים בו).
def _rec(rid, family, level, template, value):
    return bank.Record(id=rid, level=level, family=family, template=template, value=value, status="approved")


RECORDS = [
    _rec("t-c1", "conditions", "serious", "ובלבד ש{value}", "{השר} ידווח ל{committee} של הכנסת בתוך שישה חודשים"),
    _rec("t-c2", "conditions", "serious", "ובלבד ש{value}", "{השר} יפרסם את החלטתו ברשומות"),
    _rec("t-a1", "actor_swap", "clever", "{value}", "סגן {שר}"),
    bank.Record(id="t-a2", level="clever", family="actor_swap", template="{value}",
                value="ועדה ציבורית שימנה {שר}", status="approved", gender="f"),
]


def _run(bill, level, fams):
    verdicts = {r.id: {"key": r.screen_key, "allowed": True} for r in RECORDS}
    orig_all, orig_v = bank.load_all, bank._screen_verdicts
    bank.load_all, bank._screen_verdicts = (lambda: RECORDS), (lambda: verdicts)
    try:
        return [it.text for it in families.candidates(bill, level, fams)[0]]
    finally:
        bank.load_all, bank._screen_verdicts = orig_all, orig_v


def _bill(*texts):
    return ParsedBill(title="חוק הבדיקה", committee="ועדת הכלכלה", warnings=[], sections=[
        BillSection(str(i + 1), "תיקון", BillUnit("lead", "", t), []) for i, t in enumerate(texts)])


def test_bank_uses_the_minister_placeholder():
    """הרשומות החדשות כותבות {השר} (אישורי הבנק) - ומגיעות לפלט עם השר מההצעה."""
    texts = [r.template + r.value for r in bank.load_all()]
    assert any("{השר} ידווח ל{הוועדה} של הכנסת על יישום חוק זה אחת לשנה." in t for t in texts)
    assert not any(" השר " in f" {t} " and "{השר}" not in t for t in texts if "השר ל" not in t)


def test_tiberias_conditions_name_the_minister():
    got = _run(TIBERIAS, "serious", ["conditions"])
    assert got, got
    assert not any("שהשר" in t or " השר " in t for t in got), got
    assert any("ובלבד ששר הפנים ידווח לוועדת הפנים והגנת הסביבה של הכנסת" in t for t in got), got
    assert any("ובלבד ששר הפנים יפרסם את החלטתו ברשומות" in t for t in got), got


def test_tiberias_actor_swap_names_the_minister():
    got = _run(TIBERIAS, "clever", ["actor_swap"])
    assert 'במקום "שר הפנים" יבוא "סגן שר הפנים".' in got, got
    assert 'במקום "שר הפנים יתקן" יבוא "ועדה ציבורית שימנה שר הפנים תתקן".' in got, got


def test_section_minister_wins():
    bill = _bill("שר האוצר יקבע תקנות לעניין זה.", "שר הבריאות רשאי להורות על כך.")
    got = _run(bill, "serious", ["conditions"])
    assert any("ובלבד ששר האוצר ידווח" in t for t in got) and any("ובלבד ששר הבריאות ידווח" in t for t in got), got
    assert not any("השר" in t.replace("ששר", "") for t in got), got


def test_single_bill_minister_for_other_sections():
    bill = _bill("שר המשפטים יקבע תקנות לעניין זה.", "תחילתו של חוק זה ביום פרסומו.")
    got = _run(bill, "serious", ["conditions"])
    assert got and all("ששר המשפטים" in t for t in got), got


def test_hasar_kept_when_bill_uses_it():
    bill = _bill("בחוק זה, \"השר\" - השר שהממשלה הסמיכה.", "השר יקבע תקנות לעניין זה.")
    got = _run(bill, "serious", ["conditions"])
    assert got and all("ובלבד שהשר" in t for t in got), got


def test_two_ministers_in_section_not_guessed():
    bill = _bill("שר האוצר ושר הבריאות יקבעו תקנות.")
    assert _run(bill, "serious", ["conditions"]) == []


def test_no_minister_template_not_applied():
    bill = _bill("המועצה תקבע כללים לעניין זה.")
    assert _run(bill, "serious", ["conditions"]) == []


def test_minister_names_regex():
    assert families._named_ministers("ושר העבודה והרווחה יקבע, ולשר הפנים") == ["שר העבודה והרווחה", "שר הפנים"]
    assert families._named_ministers("שר הפנים והשר לביטחון") == ["שר הפנים"]
    assert families._named_ministers("משרד הפנים ומשרד האוצר") == []


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservation_minister: כל הבדיקות עברו")
