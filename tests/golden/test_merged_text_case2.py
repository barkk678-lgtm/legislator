"""מקרה הזהב השני של הנוסח המשולב - משימה 63.

**מה המשתמש רואה:** הוא מעלה את הצעה 13948380 ("דמי מחלה
(היעדרות בשל מחלת בן זוג) - זקיפת חלקי ימים והרחבת הזכאות",
הכנסת ה-25), ומקבל את נוסח החוק אחרי שההצעה התקבלה.

**למה דווקא ההצעה הזו:** היא מכילה בשתי הוראות את **שלושת
הדפוסים** שלא נתמכו אחרי מקרה 1, ובהם הדפוס הנפוץ ביותר בהצעות
אמיתיות - החלפת מילים. בלעדיו רוב ההצעות היו נדחות:

1. **מספור מחדש** - `בסעיף 1, האמור בו יסומן "(א)" ואחריו יבוא:`
   התוכן הקיים של הסעיף מקבל תווית (א), ואחריו נוסף (ב) חדש
   (ha-hoveret-ha-sgula.pdf §7.10.6(ד)).
2. **החלפת מילים** - `במקום "לחלוטין" יבוא "במידה רבה"`.
3. **הוספה בסוף** - `ובסופו יבוא "או שזקוק להשגחה מתמדת..."`.

**שתיים ושלוש יושבות באותה שורה**, ומוחלות כשתי פעולות נפרדות.
זה מה שמונע "פעולה מורכבת" שאיש לא הגדיר.

**סימן הפיסוק הסוגר בהוספה בסוף** - הבדיקה נועלת אותו במפורש:
הטקסט הקיים מסתיים ב-";", והתוספת נכנסת **לפניו**. הוספה אחרי
הנקודה-פסיק הייתה מייצרת פסקה שמסתיימת בלי סימן פיסוק.

נתונים אמיתיים בלבד: `13948380.docx` מה-OData, ו-
`dmei-machala.wikitext` (גרסה 970170) מ-he.wikisource.org.
רץ אופליין.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in ("packages/corpus", "packages/render", "packages/amend", "packages/documents"):
    sys.path.insert(0, str(ROOT / _p))

from wikitext_parser import parse_wikitext  # noqa: E402
from extract_docx import extract_bill  # noqa: E402
from node import LegislativeNode  # noqa: E402
from parse_instructions import (  # noqa: E402
    AppendAtEnd, RelabelAndInsert, ReplaceWords, parse_instructions,
)
from merge import build_merged_text  # noqa: E402

BILL = ROOT / "tests/fixtures/real-bills/13948380.docx"
LAW = ROOT / "tests/fixtures/wikitext/dmei-machala.wikitext"

WANT_S3_1 = (
    "יראו כחולה – בן זוג שחלה והפך להיות תלוי במידה רבה בעזרת הזולת "
    "בביצוע פעולות יום-יום או שזקוק להשגחה מתמדת מפאת מצבו הרפואי;"
)


def _law() -> LegislativeNode:
    return parse_wikitext(LAW.read_text(encoding="utf-8"), law_id="law-2000160",
                          as_of="2020-07-22T22:01:18Z")


def _find(node, node_id):
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find(child, node_id)
        if found is not None:
            return found
    return None


def main() -> int:
    checks = []

    def check(name, passed, got=""):
        checks.append((name, bool(passed), str(got)))

    bill = extract_bill(str(BILL))
    plan = parse_instructions([(line.number, line.text) for line in bill.lines])

    check("התוכנית שלמה - אין הוראה שלא פורשה", plan.ok, plan.blocking_reason)
    kinds = [type(op).__name__ for op in plan.operations]
    check("שלוש פעולות: מספור מחדש, החלפה, הוספה בסוף",
          kinds == ["RelabelAndInsert", "ReplaceWords", "AppendAtEnd"], str(kinds))
    check("שתי הפעולות שבשורה אחת נרשמו בנפרד",
          len([o for o in plan.operations if o.source_line == plan.operations[-1].source_line]) == 2,
          str([o.source_line for o in plan.operations]))

    before = _law()
    before_s1 = _find(before, "law-2000160/s1")
    check("לפני: סעיף 1 בלי סעיפים קטנים",
          [c.number for c in before_s1.children if c.is_normative] == [""],
          str([c.number for c in before_s1.children if c.is_normative]))

    result = build_merged_text(before, plan)
    check("המיזוג הצליח", result.ok, result.error)
    if not result.ok:
        for name, passed, got in checks:
            print(("OK   " if passed else "FAIL "), name)
            if not passed:
                print(f"        got: {got}")
        print("\nתוצאה: נכשל")
        return 1

    # ── מספור מחדש ──
    after_s1 = _find(result.tree, "law-2000160/s1")
    labels = [c.number for c in after_s1.children if c.is_normative]
    check('אחרי: סעיף 1 מסומן (א),(ב)', labels == ["(א)", "(ב)"], str(labels))
    check("תוכן (א) הוא הנוסח הקיים, בלי שינוי",
          after_s1.children[0].text == before_s1.children[0].text,
          after_s1.children[0].text[:70])
    check("(ב) הוא הנוסח שההצעה מוסיפה",
          after_s1.children[1].text.startswith("בזקיפת ימי היעדרות כאמור בסעיף קטן (א)"),
          after_s1.children[1].text[:70])

    # ── החלפת מילים + הוספה בסוף, על אותה פסקה ──
    after_31 = _find(result.tree, "law-2000160/s3/p0/1")
    check("פסקה 3(1) אותרה למרות שהיא מתחת לצומת בלי תווית",
          after_31 is not None)
    check("החלפה והוספה-בסוף יחד: הנוסח המלא",
          after_31 is not None and after_31.text == WANT_S3_1,
          after_31.text if after_31 else "")
    check('סימן הפיסוק הסוגר (";") נשאר בסוף',
          after_31 is not None and after_31.text.endswith(";"),
          after_31.text[-40:] if after_31 else "")
    check('"לחלוטין" הוסר', after_31 is not None and "לחלוטין" not in after_31.text)

    after_32 = _find(result.tree, "law-2000160/s3/p0/2")
    check("פסקה (2) לא נגעו בה",
          after_32.text == _find(before, "law-2000160/s3/p0/2").text)
    check("עץ המקור לא השתנה",
          [c.number for c in _find(before, "law-2000160/s1").children if c.is_normative] == [""])
    check("דווחו שלושה שינויים", len(result.applied) == 3, str(len(result.applied)))
    check("סוגי השינויים שדווחו",
          [c.kind for c in result.applied] == ["relabel", "replace", "append"],
          str([c.kind for c in result.applied]))

    # ── דחיות: אין מיזוג חלקי ──
    law_head = 'בחוק דמי מחלה (היעדרות בשל מחלת בן זוג), התשנ"ח–1988, '

    missing = parse_instructions([("1.", law_head + 'בסעיף 3(1), במקום "אין-כזה" יבוא "חדש".')])
    r1 = build_merged_text(_law(), missing)
    check("ביטוי שאינו בנוסח - נדחה", not r1.ok and r1.tree is None, r1.error)
    check("הסיבה מצטטת את הביטוי", "אין-כזה" in r1.error, r1.error)

    # "יום" מופיע פעמיים בפסקה 3(1) ("פעולות יום-יום") - דו-משמעות
    # אמיתית בנתונים, לא מומצאת. הניסיון הראשון כאן השתמש בביטוי
    # שמופיע פעם אחת בלבד, והבדיקה "עברה" בלי להפעיל את המחסום.
    ambiguous = parse_instructions([("1.", law_head + 'בסעיף 3(1), במקום "יום" יבוא "שבוע".')])
    r2 = build_merged_text(_law(), ambiguous)
    check("ביטוי שמופיע יותר מפעם אחת - נדחה", not r2.ok and r2.tree is None, r2.error)
    check("הסיבה אומרת שזה דו-משמעי", "דו-משמעי" in r2.error, r2.error)

    bad_relabel = parse_instructions([
        ("1.", law_head + 'בסעיף 1, האמור בו יסומן "(ג)" ואחריו יבוא:'),
        ("", '"(ד)\tנוסח כלשהו."'),
    ])
    r3 = build_merged_text(_law(), bad_relabel)
    check("מספור מחדש בתוויות שאינן (א)/(ב) - נדחה",
          not r3.ok and r3.tree is None, r3.error)

    ok = all(passed for _, passed, _ in checks)
    for name, passed, got in checks:
        print(("OK   " if passed else "FAIL "), name)
        if not passed:
            print(f"        got: {got}")
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
