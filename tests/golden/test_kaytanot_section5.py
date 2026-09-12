"""
מקרה זהב: תיקון סעיף 5 בחוק הקייטנות - דפוס "החלפת מילים" (משימה 4א).

"לפני" נטען מ-fixture אמיתי (task 3), "אחרי" נבנה כטרנספורמציה מפורשת
(ReplaceWords) עליו - לא כתוב ביד, כדי לא לפתוח מחדש את בעיית
המעגליות (ראו test_kaytanot.py למשימה 4). זהו מקרה שלא היה נתמך לפני
משימה 4א: _diff_text (הכנסה) הייתה מזהה אותו בשקט ובאופן שגוי כהכנסה
טהורה ("...מאסר ש" + "נה"), בגלל חפיפת תו מקרית - זה מה שהוביל להוספת
_diff_replace ול-ReplaceWords.

הפלט הצפוי כאן נקבע במפורש על ידי המשתמש (לא נגזר משום דיף):
'בסעיף 5 לחוק העיקרי, במקום "מאסר ששה חדשים" יבוא "מאסר שנה".'
עם side_heading="תיקון סעיף 5".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from render_bill import Line  # noqa: E402
from node import LegislativeNode  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402
from transform import ReplaceWords, apply  # noqa: E402
from engine import amend  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WIKITEXT_FIXTURE = ROOT / "tests" / "fixtures" / "wikitext" / "kaytanot.wikitext"

EXPECTED_LINES = [
    Line(
        side_heading="תיקון סעיף 5",
        text='בסעיף 5 לחוק העיקרי, במקום "מאסר ששה חדשים" יבוא "מאסר שנה".',
        depth=0,
    ),
]


def load_before() -> LegislativeNode:
    text = WIKITEXT_FIXTURE.read_text(encoding="utf-8")
    return parse_wikitext(text, law_id="kaytanot-1990")


def build_after(before: LegislativeNode) -> tuple[LegislativeNode, list]:
    """מוצא את הצומת היחיד תחת סעיף 5 (הפסקה היחידה בו) ובונה 'אחרי'
    כטרנספורמציית ReplaceWords מפורשת עליו - לא ביד."""
    section5 = next(c for c in before.children if c.node_type == "section" and c.number == "5")
    target = section5.children[0]
    return apply(
        before,
        [ReplaceWords(target_id=target.id, old_phrase="מאסר ששה חדשים", new_phrase="מאסר שנה")],
    )


def main():
    before = load_before()
    after, annotations = build_after(before)
    got = amend(before, after, annotations, law_footnote_key="kaytanot")
    want = EXPECTED_LINES

    ok = True
    print(f"שורות: נוצרו {len(got)}, במקור {len(want)}\n")
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else None
        w = want[i] if i < len(want) else None
        passed = g == w
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), f"line {i}")
        if not passed:
            print(f"     got : {g}")
            print(f"     want: {w}")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
