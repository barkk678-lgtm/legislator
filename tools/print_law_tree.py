#!/usr/bin/env python3
"""מדפיס עץ LegislativeNode כתרשים מוזח בעברית, לבדיקה מול דף הוויקיטקסט.

שימוש:
    python3 tools/print_law_tree.py <slug> [law_id]

<slug> הוא שם ה-fixture תחת tests/fixtures/wikitext/ (בלי סיומת),
למשל kaytanot או maavak-birgunei-plisha. law_id, אם לא ניתן, נגזר
מ-slug.

מסמן במפורש:
- is_normative=False: [metadata] בשורש (מטא-דאטה של החוק, לא נוסח),
  [editor_note] בכל מקום אחר (הערת עורך שמקורה ב-{{ח:הערה}}) - שני
  מקרים שונים לגמרי מאחורי אותו שדה, ולכן שתי תוויות נפרדות.
- status שאינו active (repealed/merged).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))

from wikitext_parser import parse_wikitext  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "wikitext"

TYPE_HE = {
    "law": "חוק",
    "part": "חלק",
    "chapter": "פרק",
    "siman": "סימן",
    "section": "סעיף",
    "subsection": "סעיף קטן",
    "paragraph": "פסקה",
    "subparagraph": "פסקת משנה",
    "definition": "הגדרה",
}


def line_for(node) -> str:
    label = TYPE_HE.get(node.node_type, node.node_type)
    parts = [label]
    if node.number:
        parts.append(node.number)
    if node.margin_title:
        parts.append(f"— {node.margin_title}")
    flags = []
    if not node.is_normative:
        if node.node_type == "law":
            flags.append("⚠ is_normative=False [metadata] — שורש החוק, לא הערת עורך")
        else:
            flags.append("⚠ is_normative=False [editor_note] — הערת עורך, לא נוסח")
    if node.status != "active":
        flags.append(f"⚠ status={node.status}")
    header = " ".join(parts)
    if flags:
        header += "   " + " | ".join(flags)
    return header


def dump(node, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"{prefix}{line_for(node)}")
    if node.text:
        snippet = node.text if len(node.text) <= 90 else node.text[:87] + "..."
        print(f'{prefix}    "{snippet}"')
    for child in node.children:
        dump(child, indent + 1)


def main() -> int:
    if len(sys.argv) < 2:
        print(f"שימוש: {sys.argv[0]} <slug> [law_id]", file=sys.stderr)
        return 1
    slug = sys.argv[1]
    law_id = sys.argv[2] if len(sys.argv) > 2 else slug

    fixture = FIXTURES / f"{slug}.wikitext"
    if not fixture.exists():
        print(f"לא נמצא fixture: {fixture}", file=sys.stderr)
        return 1

    text = fixture.read_text(encoding="utf-8")
    root = parse_wikitext(text, law_id=law_id)

    print("=" * 70)
    print(f"עץ LegislativeNode — {root.full_title or slug}")
    if root.source_ref:
        print(f"source_ref (בשורש בלבד): {root.source_ref}")
    print("=" * 70)
    dump(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
