"""מקרה זהב: הוספת פסקה **בתוך הגדרה** - משימה 62.

**מה המשתמש רואה:** עומד על פסקה (1) שבתוך ההגדרה "ארגון פשיעה"
בסעיף 1, לוחץ "הוסף פסקה", ומקבל הוראת תיקון תקנית:
`בסעיף 1, בהגדרה "ארגון פשיעה", אחרי פסקה (1) יבוא:`.

עד משימה 62 הכפתור היה חסום, **ומטעם נכון**: `_container_suffix`
בונה את המכולה מהמספרים בלבד, ולהגדרה אין מספר - ההוראה שהייתה
יוצאת, `בסעיף 1, אחרי פסקה (1) יבוא:`, מצביעה על מקום אחר בחוק.
הפתרון אינו לבטל את החסימה אלא לנסח את ההגדרה **במילים**.

**מקור הניסוח - ומה בו הרכבה ומה ציטוט** (ראו drafting-rules.md
§8.7.3):

- פסוקית ההגדרה `בסעיף N לחוק העיקרי, בהגדרה "X", <פעולה>` -
  **מצוטטת** ממדריך משפטים §7.9.1, עמ' 26 [PDF 55].
- עיגון היחידה לפי תווית (`אחרי פסקה (1) יבוא:`) - **מצוטט**
  מ-ha-hoveret-ha-sgula.pdf §7.10.6(ב), עמ' 29.
- **הצירוף של שניהם בשורה אחת הוא הרכבה**, ואינו מופיע ככתובת
  שלמה לא במדריך ולא ב-40 ההצעות האמיתיות. מוצהר ולא מוסתר.

**שני עומקים בכוונה:** מאבק בארגוני פשיעה (הגדרה ישירות בסעיף)
וחוק העונשין (הגדרה בתוך סעיף קטן ממוספר), שבו הכתובת מרכיבה גם
מכולה בסוגריים וגם פסוקית במילים: `בסעיף 295(ב1), בהגדרה "..."`.
בלי המקרה השני, הרכבה שגויה של שני החלקים הייתה עוברת בשקט.

נתונים אמיתיים בלבד, רץ אופליין.
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

CASES = [
    # (פיקסצ'ר, law_id, מזהה העוגן, תווית צפויה, סוף הכתובת הצפוי)
    ("maavak-birgunei-plisha", "maavak-2003", "maavak-2003/פרק א/s1/p1/1", "(1א)",
     'בסעיף 1, בהגדרה "ארגון פשיעה", אחרי פסקה (1) יבוא:'),
    ("penal", "penal", "penal/חלק ב/פרק ט/פרק ט סימן ה/s295/ב1/p2/1", "(1א)",
     'בסעיף 295(ב1), בהגדרה "בעל השפעה ניכרת", אחרי פסקה (1) יבוא:'),
]


def _law(slug, law_id):
    return parse_wikitext((ROOT / f"tests/fixtures/wikitext/{slug}.wikitext").read_text(
        encoding="utf-8"), law_id=law_id, as_of="2024-01-01T00:00:00Z")


def _find(node, node_id):
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find(child, node_id)
        if found is not None:
            return found
    return None


def _section_of(root, node_id):
    cur = find_parent(root, node_id)
    while cur is not None and cur.node_type != "section":
        cur = find_parent(root, cur.id)
    return cur


def main() -> int:
    checks = []

    def check(name, passed, got=""):
        checks.append((name, bool(passed), str(got)))

    for slug, law_id, node_id, want_label, want_address in CASES:
        root = _law(slug, law_id)
        anchor = _find(root, node_id)
        check(f"{law_id}: העוגן קיים בעץ", anchor is not None, node_id)
        if anchor is None:
            continue
        parent = find_parent(root, node_id)
        check(f"{law_id}: ההורה הוא הגדרה", parent.node_type == "definition",
              parent.node_type)

        preview = preview_insertion_label(root, node_id, "paragraph")
        check(f"{law_id}: נתמך (לא חסום)", preview.supported, str(preview.reason))
        check(f"{law_id}: התווית {want_label}", preview.label == want_label,
              str(preview.label))
        if not preview.supported:
            continue

        section = _section_of(root, node_id)
        new = LegislativeNode(id=node_id + "/NEW", node_type="paragraph",
                              number=want_label, margin_title=None,
                              text="תוכן חדש לבדיקה.")
        after, annotations = apply(root, [InsertAfter(
            section_number=section.number, anchor_id=node_id, new_child=new)])

        merged_parent = _find(after, parent.id)
        labels = [c.number for c in merged_parent.children if c.is_normative and c.number]
        check(f"{law_id}: הפסקה נכנסה לתוך ההגדרה, אחרי (1)",
              labels[:2] == ["(1)", want_label], str(labels[:3]))

        lines = amend(root, after, annotations, law_footnote_key="k")
        check(f"{law_id}: הופקה הוראה", bool(lines), str(len(lines)))
        if not lines:
            continue
        full = (lines[0].text or "") + (lines[0].text_after or "")
        check(f"{law_id}: הכתובת המלאה", full.endswith(want_address), full[-90:])
        # ההוכחה הישירה שההגדרה לא נשמטה - הניסוח השגוי שהיה יוצא
        # לפני התיקון, כשורה מפורשת שאסור לה לחזור.
        check(f"{law_id}: ההגדרה אינה נשמטת מהכתובת",
              'בהגדרה "' in full, full[-90:])
        check(f"{law_id}: כותרת השוליים בלי ההגדרה",
              lines[0].side_heading == f"תיקון סעיף {section.number}",
              str(lines[0].side_heading))

    ok = all(passed for _, passed, _ in checks)
    for name, passed, got in checks:
        print(("OK   " if passed else "FAIL "), name)
        if not passed:
            print(f"        got: {got}")
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
