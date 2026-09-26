"""מבחן זהב: ההסתייגויות שהכלי מייצר על טבריה - בצורות של טבריה, מעוגנות בהצעה
(הסתייגויות 2, 26.9).

reference/הצעת חוק טבריה.pdf - 112 הסתייגויות אמיתיות. שלוש טענות:

1. **כל הסתייגות בצורה שמופיעה בטבריה** (packages/reservations/forms.py - הטבלה
   שם נותנת את המספרים). צורה שאינה ברשימה - כשל.
2. **כל ציטוט מההצעה נמצא בהצעה** - בסעיף, וביחידה שצוינה.
3. **הכלי משחזר הסתייגויות אמיתיות מילה במילה**: 18, 19, 20 (מחיקת פסקה),
   46 ו-50 (מחיקת "ובשינויים המחויבים"), 48/ג (מחיקת "בתוך שלושים ימים"),
   48, 65, 65/א (החלפת "שלושים ימים").

הבנק כולו ממתין לאישור של ברק, ולכן ריצה אחת עם הבנק כמות שהוא (רק שינוי ערך
ומחיקה), וריצה שנייה **כאילו כל הרשומות אושרו וסוננו** - כדי שגם הצורות של משפחות
הבנק ייבדקו היום, לפני שמישהו מאשר רשומה.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402
import families  # noqa: E402
from pdf_bill import parse_bill_pdf  # noqa: E402

PDF = ROOT / "reference" / "הצעת חוק טבריה.pdf"

_ADDR = r"(?:ברישה, |בפסקה \([^)]+\), |בסעיף קטן \([^)]+\)(?:\([^)]+\))?, |בפסקת משנה \([^)]+\), )?"
FORMS = [
    ("replace", re.compile(rf'^{_ADDR}במקום "(?P<q>[^"]+)" יבוא "[^"]+"\.$')),
    ("after", re.compile(rf'^{_ADDR}אחרי "(?P<q>[^"]+)" יבוא "[^"]+"\.$')),
    ("before", re.compile(rf'^{_ADDR}לפני "(?P<q>[^"]+)" יבוא "[^"]+"\.$')),
    ("append", re.compile(rf'^{_ADDR}בסופ[הו] יבוא "[^"]+"\.$')),
    ("delete_words", re.compile(rf'^{_ADDR}(?:המילים "(?P<q>[^"]+)" – יימחקו|המילה "(?P<q1>[^"]+)" – תימחק)\.$')),
    ("delete_unit", re.compile(r'^(?:בסעיף קטן \([^)]+\), )?(?:פסקה|סעיף קטן|פסקת משנה) \([^)]+\) – (?:תימחק|יימחק)\.$')),
    ("new_section", re.compile(r'^אחרי הסעיף יבוא:$')),
]
REAL = {
    "18/20": "פסקה (2) – תימחק.",
    "19": "פסקה (1) – תימחק.",
    "46/50": 'המילים "ובשינויים המחויבים" – יימחקו.',
    "48/ג": 'המילים "בתוך שלושים ימים" – יימחקו.',
    "48": 'במקום "שלושים ימים" יבוא "מאה ועשרים ימים".',
    "65": 'במקום "שלושים ימים" יבוא "תשעים ימים".',
    "65/א": 'במקום "שלושים ימים" יבוא "שישים ימים".',
}


def _form(line):
    for name, rx in FORMS:
        m = rx.match(line)
        if m:
            return name, (m.groupdict().get("q") or m.groupdict().get("q1"))
    return None, None


def _unit_text(bill, heading, line):
    """הטקסט שבו הציטוט חייב להימצא: הסעיף, או היחידה שבכתובת."""
    number = heading.split()[-1]
    sec = next(s for s in bill.sections if s.number == number)
    m = re.match(r"^ב(?:פסקה|סעיף קטן|פסקת משנה) ((?:\([^)]+\))+), ", line)
    if not m:
        return sec.lead.text if line.startswith("ברישה, ") else sec.text
    labels = re.findall(r"\([^)]+\)", m.group(1))
    units = sec.units
    unit = None
    for label in labels:
        unit = next((u for u in units if u.label == label), None)
        if unit is None:
            return ""
        units = unit.children
    return unit.text if unit else ""


def main():
    bill = parse_bill_pdf(PDF)
    ok = True

    def check(name, passed, detail=""):
        nonlocal ok
        ok = ok and bool(passed)
        print(("OK  " if passed else "FAIL"), name, detail if not passed else "")

    def run(label):
        produced = set()
        for level in bank.LEVELS:
            p = families.plan(bill, level, list(families.FAMILIES), 10_000)
            bad_form, ungrounded = [], []
            for it in p.items:
                form, quote = _form(it.lines[0])
                if form is None:
                    bad_form.append(it.lines[0])
                    continue
                if form == "new_section":
                    ok_quote = len(it.lines) == 2 and re.match(r'^"[^"]+ \d+[א-ת]?\. .+"$', it.lines[1])
                    if not ok_quote:
                        bad_form.append(" / ".join(it.lines))
                    continue
                if quote and quote not in _unit_text(bill, it.heading, it.lines[0]):
                    ungrounded.append(it.lines[0])
            check(f"{label}, {level}: {len(p.items)} הסתייגויות - כולן בצורות של טבריה", not bad_form, str(bad_form[:3]))
            check(f"{label}, {level}: כל ציטוט נמצא בהצעה, ביחידה שצוינה", not ungrounded, str(ungrounded[:3]))
            produced |= {it.lines[0] for it in p.items}
        return produced

    produced = run("הבנק כמות שהוא")
    for rid, text in REAL.items():
        check(f"משחזר את הסתייגות {rid} בטבריה מילה במילה: {text}", text in produced)

    # כאילו ברק אישר את כל הבנק, וכל רשומה עברה את שומר 86(ד)(2)
    original = bank.load
    bank.load = lambda level: ([r for r in bank.load_all() if r.level == level and not bank.redline_violation(r.text("ועדה"))], [])
    try:
        everything = run("כל הבנק מאושר")
        fams = {f for f in families.FAMILIES}
        got = {it.family for lv in bank.LEVELS for it in families.plan(bill, lv, list(fams), 10_000).items}
        check("כל שבע המשפחות מייצרות על טבריה", got == fams, str(sorted(fams - got)))
        print(f"     מידע: {len(everything)} הסתייגויות שונות בשלוש הרמות, כשהבנק כולו מאושר")
    finally:
        bank.load = original

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
