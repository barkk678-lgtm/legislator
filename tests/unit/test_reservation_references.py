"""הכרעה א (ברק, 26.9.2026): **שינוי ערך לא נוגע אף פעם במספר שהוא הפניה** -
לסעיף, לסעיף קטן, לפסקה, לתקנה, לפרט או לתוספת, בחוק העיקרי או בכל חוק אחר, בכל
הרמות. "במקום "7" יבוא "8"" על "בסעיף 7" מפנה לסעיף אחר - נוסח לא קוהרנטי שייפסל.

ההגדרה מבנית (anchors.reference_spans): שם עצם של הפניה ואחריו תווית או רשימת
תוויות. לא רשימת מספרים. בדיקות חיוביות **ושליליות** (CLAUDE.md: כל regex - גם
טסט שלילי על ערכים רגילים).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import anchors  # noqa: E402
import bank  # noqa: E402
import families  # noqa: E402
from pdf_bill import parse_bill_pdf  # noqa: E402


def _covered(text):
    spans = anchors.reference_spans(text)
    return [a.text for a in anchors.find_anchors(text) if any(s <= a.start and a.end <= e for s, e in spans)]


def test_references_are_found():
    cases = {
        "לפי סעיף 143, 143א או 206 לפקודת העיריות": ["143", "143א", "206"],
        "או לפי סעיף 38 או 38א לפקודת המועצות המקומיות": ["38", "38א"],
        "(להלן – החוק העיקרי), בסעיף 7 –": ["7"],
        "בהתאם לסעיף 7 לחוק העיקרי": ["7"],
        "יקראו את סעיף 22(ב) לחוק": ["22"],
        'כך שהאמור בו יסומן כפסקה "(1)" ואחריה': ["1"],
        "כאמור בפרט 5 לתוספת השנייה": ["5"],
        "לפי תקנה 3(א)": ["3"],
        "סעיפים 3 עד 5 יחולו": ["3", "5"],
        "בסעיפים קטנים (א) ו-(ב)": [],
        "האמור בפרק 4": ["4"],
        "ובסעיף 12ב1": ["12ב1"],
    }
    for text, want in cases.items():
        got = _covered(text)
        assert got == want, (text, got)


def test_values_are_not_references():
    for text in ("בתוך 30 ימים מיום התחילה", "עד יום 31 בדצמבר 2020", "קנס של 1,000 שקלים חדשים",
                 "שיעור של 5% לפחות", "לעניין סעיף זה, 30 ימים לאחר ההודעה",
                 "לפי סעיף 5, 30 ימים לאחר ההודעה", "שבעה חברים, מהם 3 נציגי ציבור"):
        spans = anchors.reference_spans(text)
        nums = [a.text for a in anchors.find_anchors(text) if any(s <= a.start and a.end <= e for s, e in spans)]
        assert nums in ([], ["5"]), (text, nums)   # רק "5" של "סעיף 5" - לא ה-30
    assert _covered("לפי סעיף 5, 30 ימים לאחר ההודעה") == ["5"]


BILL = parse_bill_pdf(ROOT / "reference" / "הצעת חוק טבריה.pdf")
REFS = {"7", "2", "143", "143א", "206", "38", "38א"}


def _anchors_used(items):
    out = set()
    for it in items:
        line = it.lines[0]
        if "במקום" in line:
            out.add(line.split('"')[1])
    return out


def _all_levels(approve_bank=False):
    original = bank.load
    if approve_bank:
        bank.load = lambda level: ([r for r in bank.load_all() if r.level == level
                                    and not bank.redline_violation(r.text("ועדה"))], [])
    try:
        return {lv: families.plan(BILL, lv, list(families.FAMILIES), 10_000).items for lv in bank.LEVELS}
    finally:
        bank.load = original


def test_tiberias_no_reference_is_changed():
    for approve in (False, True):
        for level, items in _all_levels(approve).items():
            used = _anchors_used(items) & REFS
            assert not used, (level, approve, sorted(used))


def test_tiberias_quantities_still_vary():
    for level, items in _all_levels().items():
        texts = [it.text for it in items]
        assert any('במקום "שלושים ימים" יבוא' in t for t in texts), (level, texts[:5])


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservation_references: כל הבדיקות עברו")
