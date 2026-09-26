"""השומרים של §86 ו-§3ג (הסתייגויות, בנייה מחדש 26.9). **כל שומר - עם מקרה חסום.**

- 86(ד)(2) - screen_text, על רשומות הבנק (המודל לא כותב אף מילה בפלט): fail-closed
  בכל מסלול - רשימה חסומה, קריסה, תשובה ריקה/עמומה, "כן", ו"לאחר..." (תחילית "לא").
- 86(ד)(1) - screen_negates_bill, ובמבנה המשפחות: מחיקת יחידה רק כשיש לפחות שתיים,
  ואף פעם לא מחיקת סעיף שלם.
- 86(ד)(3) - screen_bill_name, ובמשפחות: אף עוגן בתוך ציטוט שם חוק.
- §3ג - screen_budgetary מסמן (לא חוסם), ורק בהקשר כספי.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import families  # noqa: E402
import guards  # noqa: E402
from anchors import find_anchors  # noqa: E402
from pdf_bill import BillSection, BillUnit, ParsedBill, parse_bill_pdf  # noqa: E402

ITEM = "באישור ועדת הפנים והגנת הסביבה של הכנסת"


def test_86d2_fail_closed():
    no = lambda **kw: "לא"   # noqa: E731
    assert not guards.screen_text("ההצעה תחול במדינת כל אזרחיה", draft_fn=no).allowed, "רשימה חסומה"

    def boom(**kw):
        raise RuntimeError("השירות נפל")

    assert not guards.screen_text(ITEM, draft_fn=boom).allowed, "קריסה"
    for answer in ("", "אולי", "כן", "לאחר בדיקה - תקין", "לא בטוח"):
        v = guards.screen_text(ITEM, draft_fn=lambda answer=answer, **kw: answer)
        assert not v.allowed and v.rule == "86(ד)(2)", answer
    for answer in ("לא", "לא.", " לא "):
        assert guards.screen_text(ITEM, draft_fn=lambda answer=answer, **kw: answer).allowed, answer


def test_86d1_negates_bill():
    assert not guards.screen_negates_bill("ההצעה כולה – תימחק.").allowed
    assert not guards.screen_negates_bill("סעיף 1 – תימחק.", section_heading="מטרה").allowed
    assert not guards.screen_negates_bill("x", deleted_sections=3, total_sections=3).allowed
    assert guards.screen_negates_bill("פסקה (2) – תימחק.", deleted_sections=0, total_sections=3).allowed


def test_86d3_bill_name():
    section = 'בחוק הרשויות המקומיות (בחירות), התשכ"ה–1965 (להלן – החוק העיקרי), בסעיף 7 –'
    assert not guards.screen_bill_name("במקום שם החוק יבוא").allowed
    v = guards.screen_bill_name('במקום "1965" יבוא "1966".', anchor="1965", section_text=section)
    assert not v.allowed and v.rule == "86(ד)(3)", v
    assert guards.screen_bill_name('במקום "7" יבוא "8".', anchor="7", section_text=section).allowed


def test_3c_budget_flag_only_in_money_context():
    flag = guards.screen_budgetary("1,000", "2,000", section_text="קנס בסך 1,000 שקלים חדשים")
    assert flag.budgetary and flag.lenient_direction == "increase"
    assert guards.screen_budgetary("1,000", "500", section_text="קנס בסך 1,000 שקלים").lenient_direction == "decrease"
    assert not guards.screen_budgetary("1,000", "2,000", section_text="בתוך 1,000 ימים").budgetary


SOLE = ParsedBill(title="חוק הבדיקה", committee="ועדת הכלכלה", sections=[
    BillSection("1", "מטרה", BillUnit("lead", "", "מטרתו של חוק זה לקדם את הבדיקה בתוך שלושים ימים."), []),
    BillSection("2", "תיקון", BillUnit("lead", "", "בחוק הבדיקה, בסעיף 3 –"), [
        BillUnit("paragraph", "(1)", "השר יקבע כללים בתוך שלושים ימים."),
    ]),
], warnings=[])


def test_families_never_delete_a_sole_unit_or_a_section():
    for level in ("serious", "clever", "absurd"):
        items = families.plan(SOLE, level, list(families.FAMILIES), 1000).items
        units = [it.text for it in items if it.text.startswith(("פסקה", "סעיף קטן", "סעיף "))]
        assert not units, (level, units)
        assert not any(it.text.endswith("– בטל.") for it in items), level


def test_families_never_anchor_in_a_law_citation():
    bill = parse_bill_pdf(ROOT / "reference" / "הצעת חוק טבריה.pdf")
    for section in bill.sections:
        cited = {a.text for a in find_anchors(section.text) if a.in_law_citation}
        for level in ("serious", "clever", "absurd"):
            for it in families.plan(bill, level, list(families.FAMILIES), 1000).items:
                if it.heading != f"לסעיף {section.number}":
                    continue
                quoted = it.lines[0].split('"')[1::2][:1]
                assert not (set(quoted) & cited), (level, it.text, cited)


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservation_guards: כל הבדיקות עברו")
