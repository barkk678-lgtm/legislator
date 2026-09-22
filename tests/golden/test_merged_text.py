"""מקרה הזהב הראשון של הנוסח המשולב - משימה 55.

**מה המשתמש רואה:** הוא מעלה את קובץ ה-Word של הצעת חוק
13948412 ("שוויון ההזדמנויות בעבודה - זכויות הוריות במקרה של
מחלת בן זוג", פ/6803/25, הכנסת ה-25), ומקבל את נוסח סעיף 4
לחוק **אחרי** שההצעה התקבלה: פסקה (3) חדשה בתוך סעיף קטן (א),
אחרי פסקה (2), והשאר ללא שינוי.

**מקצה לקצה, על נתונים אמיתיים בלבד:**

- ההצעה: `tests/fixtures/real-bills/13948412.docx` - קובץ Word
  אמיתי שנמשך מה-OData של הכנסת.
- החוק: `tests/fixtures/wikitext/shivyon-hizdamnuyot.wikitext` -
  ה-wikitext האמיתי מ-he.wikisource.org (גרסה 3023936). נבדק
  שהעץ שנבנה ממנו זהה למה שהפרודקשן מגישה, כולל המזהים.

רץ אופליין, בלי רשת ובלי DB.

**מה שהטסט שומר עליו יותר מכול: אין מיזוג חלקי.** נוסח משולב
שחלק מההוראות לא הוחלו בו הוא נוסח חוק שגוי שנראה אמין. לכן
נבדקות גם שלוש דחיות: סעיף שאינו קיים, עוגן שאינו קיים, ותווית
חדשה שכבר תפוסה - בכל אחת מהן `tree` חייב להישאר None.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in ("packages/corpus", "packages/render", "packages/amend", "packages/documents"):
    sys.path.insert(0, str(ROOT / _p))

from wikitext_parser import parse_wikitext  # noqa: E402
from extract_docx import extract_bill  # noqa: E402
from node import LegislativeNode  # noqa: E402
from parse_instructions import parse_instructions  # noqa: E402
from merge import build_merged_text  # noqa: E402

BILL = ROOT / "tests/fixtures/real-bills/13948412.docx"
LAW = ROOT / "tests/fixtures/wikitext/shivyon-hizdamnuyot.wikitext"

WANT_NEW_TEXT = (
    "הילד נמצא בטיפולו הבלעדי של העובד מחמת נכות או מחלה של בת הזוג "
    "ורופא אישר בכתב כי בשל הנכות או המחלה כאמור בת הזוג אינה מסוגלת "
    "לטפל בילד."
)


def _bill_lines() -> list[tuple[str, str]]:
    """שורות ההוראות של ההצעה, דרך המחלץ האמיתי.

    **לא קריאה ישירה של פסקאות ה-XML** - זו הייתה הגרסה הראשונה
    של הטסט, והיא הזינה לפרסר גם את עמוד השער, את דברי ההסבר ואת
    פסקת ההגשה: 16 שורות "לא זוהו" והמיזוג נדחה. `extract_bill`
    הוא שיודע להפריד את גוף ההוראות משאר המסמך, והוא החוליה
    הראשונה בצנרת האמיתית - לכן הטסט עובר דרכו."""
    bill = extract_bill(str(BILL))
    return [(line.number, line.text) for line in bill.lines]


def _law_tree() -> LegislativeNode:
    return parse_wikitext(
        LAW.read_text(encoding="utf-8"), law_id="law-2001217",
        as_of="2026-07-12T14:30:14Z",
    )


def _find(node: LegislativeNode, node_id: str) -> LegislativeNode | None:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find(child, node_id)
        if found is not None:
            return found
    return None


def _subsection_a(tree: LegislativeNode) -> LegislativeNode | None:
    return _find(tree, "law-2001217/s4/א")


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name, passed, got=""):
        checks.append((name, bool(passed), str(got)))

    lines = _bill_lines()
    plan = parse_instructions(lines)

    check("ההצעה נקראה מהקובץ", bool(lines), f"{len(lines)} שורות")
    check("זוהה החוק המתוקן",
          plan.law is not None and plan.law.name == "שוויון ההזדמנויות בעבודה",
          plan.law.full if plan.law else "")
    check("זוהתה הוראה אחת", len(plan.operations) == 1, str(len(plan.operations)))
    check("התוכנית שלמה - אין הוראה שלא פורשה", plan.ok, plan.blocking_reason)

    before = _law_tree()
    before_labels = [c.number for c in _subsection_a(before).children]
    check('לפני המיזוג: סעיף קטן (א) מכיל (1),(2)',
          before_labels == ["(1)", "(2)"], str(before_labels))

    result = build_merged_text(before, plan)
    check("המיזוג הצליח", result.ok, result.error)
    if not result.ok:
        for name, passed, got in checks:
            print(("OK   " if passed else "FAIL "), name)
            if not passed:
                print(f"        got: {got}")
        print("\nתוצאה: נכשל")
        return 1

    merged_a = _subsection_a(result.tree)
    labels = [c.number for c in merged_a.children]
    check('אחרי המיזוג: (1),(2),(3) - הפסקה החדשה במקום הנכון',
          labels == ["(1)", "(2)", "(3)"], str(labels))
    check("נוסח הפסקה החדשה הוא מה שההצעה כותבת",
          merged_a.children[2].text == WANT_NEW_TEXT, merged_a.children[2].text[:80])
    check("הפסקאות הקיימות לא השתנו",
          merged_a.children[0].text == _subsection_a(before).children[0].text
          and merged_a.children[1].text == "הילד נמצא בהחזקתו הבלעדית.",
          merged_a.children[1].text)

    # סעיף קטן (ב) לא נגעו בו - ההוראה מדברת רק על (א).
    before_b = [c.text for c in _find(before, "law-2001217/s4/ב").children]
    merged_b = [c.text for c in _find(result.tree, "law-2001217/s4/ב").children]
    check("סעיף קטן (ב) לא נגעו בו", before_b == merged_b, f"{len(merged_b)} פסקאות")

    # עץ המוצא לא שונה במקום (apply עובדת על עותק).
    check("עץ המקור לא השתנה",
          [c.number for c in _subsection_a(before).children] == ["(1)", "(2)"],
          str([c.number for c in _subsection_a(before).children]))

    check("דווח שינוי אחד שהוחל", len(result.applied) == 1, str(len(result.applied)))
    if result.applied:
        change = result.applied[0]
        check("השינוי מקושר לעוגן הנכון (פסקה (2))",
              change.anchor_id == "law-2001217/s4/א/2", change.anchor_id)
        check("התווית שדווחה היא (3)", change.label == "(3)", change.label)

    # ── אין מיזוג חלקי: שלוש דחיות ────────────────────────────
    def plan_with(text: str):
        return parse_instructions([
            ("1.", text),
            ("", '"(9)\tנוסח כלשהו לבדיקה."'),
        ])

    missing_section = plan_with(
        'בחוק שוויון ההזדמנויות בעבודה, התשמ"ח–1988, בסעיף 999(א), אחרי פסקה (2) יבוא:'
    )
    r1 = build_merged_text(_law_tree(), missing_section)
    check("סעיף שאינו קיים - נדחה", not r1.ok and r1.tree is None, r1.error)
    check("הסיבה מזכירה את מספר הסעיף", "999" in r1.error, r1.error)

    missing_anchor = plan_with(
        'בחוק שוויון ההזדמנויות בעבודה, התשמ"ח–1988, בסעיף 4(א), אחרי פסקה (7) יבוא:'
    )
    r2 = build_merged_text(_law_tree(), missing_anchor)
    check("עוגן שאינו קיים - נדחה", not r2.ok and r2.tree is None, r2.error)

    taken_label = parse_instructions([
        ("1.", 'בחוק שוויון ההזדמנויות בעבודה, התשמ"ח–1988, בסעיף 4(ב), אחרי פסקה (1) יבוא:'),
        ("", '"(3)\tנוסח כלשהו לבדיקה."'),
    ])
    r3 = build_merged_text(_law_tree(), taken_label)
    check("תווית חדשה שכבר תפוסה - נדחה", not r3.ok and r3.tree is None, r3.error)
    check("הסיבה מסבירה שהתווית תפוסה", "תפוסה" in r3.error, r3.error)

    ok = all(passed for _, passed, _ in checks)
    for name, passed, got in checks:
        print(("OK   " if passed else "FAIL "), name)
        if not passed:
            print(f"        got: {got}")
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
