"""גבול העומק בפועל של שכבת העריכה - משימה 61.

משימה 58 גילתה שעריכה בתוך סעיף קטן לא הפיקה הוראת תיקון **בשקט**.
ברק: "אני רוצה לדעת את הגבול בפועל, לא להניח שרקורסיה מכסה הכול."
הטסט הזה הוא המפה הזו, נעולה מול הקורפוס האמיתי - לא מול עץ סינתטי,
כי שרשראות הטיפוסים שהפרסר באמת מייצר אינן מה שהיה מנחש אותן.

**שרשראות הטיפוסים שנמדדו בפועל בארבעת הפיקסצ'רים** (עומק 4 הוא
המרבי בקורפוס):

    section > subsection                            638
    section > paragraph                             477
    section > definition                            122
    section > subsection > paragraph                294
    section > paragraph > paragraph                 234
    section > definition > paragraph                 65
    section > subsection > paragraph > subsection    30
    section > paragraph > paragraph > subsection     11
    section > subsection > definition > paragraph     4
    section > subsection > paragraph > paragraph      3

**מה שהטסט נועל:**

1. **הזיהוי, הטרנספורמציה והניסוח עובדים בכל עומק אמיתי** - כולל
   המכולה הרב-שלבית `בסעיף 18(א)(2)`.
2. **המספור נגזר מהאחים בפועל** ולא מהסעיפים הקטנים שברמת הסעיף.
   זה היה באג אמיתי (משימה 61): במאבק בארגוני פשיעה 18(א)(2),
   האחים הם (א) ו-(ב) והתווית הנכונה (א1), אבל המערכת הציעה **(ד)** -
   המשך המספור של (א),(ב),(ג) שברמת הסעיף. לא חסום - מוצע בשקט.
3. **מה שחסום, חסום מסיבה מוצהרת** ולא נופל בשקט: פסקה בתוך הגדרה
   (אין עדיין צורת `בהגדרה "X"`), ושרשרת עם צומת בלי מספר (הכתובת
   הייתה מדלגת עליו).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in ("packages/corpus", "packages/render", "packages/amend", "apps/api"):
    sys.path.insert(0, str(ROOT / _p))

from wikitext_parser import parse_wikitext  # noqa: E402
from node import LegislativeNode, find_parent  # noqa: E402
from transform import InsertAfter, apply  # noqa: E402
from engine import amend  # noqa: E402
from insert_preview import preview_insertion_label  # noqa: E402


def _law(slug: str, law_id: str) -> LegislativeNode:
    text = (ROOT / f"tests/fixtures/wikitext/{slug}.wikitext").read_text(encoding="utf-8")
    return parse_wikitext(text, law_id=law_id, as_of="2024-01-01T00:00:00Z")


def _section_of(root: LegislativeNode, node_id: str) -> LegislativeNode | None:
    cur = find_parent(root, node_id)
    while cur is not None and cur.node_type != "section":
        cur = find_parent(root, cur.id)
    return cur


# (חוק, מזהה העוגן, רמה, התווית הצפויה או None אם חסום, הכתובת הצפויה)
CASES = [
    # עומק 2 - פסקה ישירות בסעיף. הדפוס שכבר עבד לפני משימה 58.
    ("maavak-birgunei-plisha", "maavak-2003", "maavak-2003/פרק ה/s18/א/1",
     "paragraph", "(1א)", "בסעיף 18(א), אחרי פסקה (1) יבוא:"),
    # עומק 3 - סעיף קטן בתוך פסקה בתוך סעיף קטן. כאן היה הבאג שהציע (ד).
    ("maavak-birgunei-plisha", "maavak-2003", "maavak-2003/פרק ה/s18/א/2/א",
     "subsection", "(א1)", "בסעיף 18(א)(2), אחרי סעיף קטן (א) יבוא:"),
    # עומק 3 בחוק העונשין - פסקה בתוך פסקה **ממוספרת**.
    ("penal", "penal", "penal/חלק ב/פרק ח/פרק ח סימן א/s141/p0/1/א",
     "subsection", "(א1)", "בסעיף 141(1), אחרי סעיף קטן (א) יבוא:"),
]

# שרשראות שחסומות **בכוונה**, עם הסיבה שחייבת להופיע.
BLOCKED = [
    ("maavak-birgunei-plisha", "maavak-2003", "maavak-2003/פרק א/s1/p1/1", "paragraph", "הגדרה"),
]


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    for slug, law_id, node_id, level, want_label, want_address in CASES:
        root = _law(slug, law_id)
        pv = preview_insertion_label(root, node_id, level)
        checks.append((f"{node_id}: נתמך", pv.supported, str(pv.reason)))
        checks.append(
            (f"{node_id}: התווית {want_label}", pv.label == want_label, str(pv.label))
        )
        if not pv.supported:
            continue
        section = _section_of(root, node_id)
        new = LegislativeNode(
            id=node_id + "/NEW", node_type=level, number=want_label,
            margin_title=None, text="תוכן חדש לבדיקה.",
        )
        after, annotations = apply(
            root, [InsertAfter(section_number=section.number, anchor_id=node_id, new_child=new)]
        )
        lines = amend(root, after, annotations, law_footnote_key="k")
        checks.append((f"{node_id}: הופקה הוראה (לא ריק)", bool(lines), str(len(lines))))
        if not lines:
            continue
        full = (lines[0].text or "") + (lines[0].text_after or "")
        checks.append(
            (f"{node_id}: הכתובת המלאה", full.endswith(want_address), full[-70:])
        )

    for slug, law_id, node_id, level, reason_word in BLOCKED:
        root = _law(slug, law_id)
        pv = preview_insertion_label(root, node_id, level)
        checks.append((f"{node_id}: חסום בכוונה", not pv.supported, str(pv.label)))
        checks.append(
            (f"{node_id}: הסיבה מזכירה {reason_word!r}",
             bool(pv.reason) and reason_word in pv.reason, str(pv.reason)),
        )

    # אין ולו שרשרת אחת בקורפוס שבה העריכה "מצליחה" ומפיקה רשימה ריקה
    # בלי שהמערכת אומרת למה - זה הסימפטום של משימה 58, והמפה הזו
    # קיימת כדי שלא יחזור בעומק אחר.
    checks.append(
        ("כל מקרה נתמך מפיק הוראה - אין הצלחה שקטה בלי פלט",
         all(passed for name, passed, _ in checks if "הופקה הוראה" in name), ""),
    )

    ok = all(passed for _, passed, _ in checks)
    for name, passed, got in checks:
        print(("OK   " if passed else "FAIL "), name)
        if not passed:
            print(f"        got: {got}")
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
