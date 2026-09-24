"""בדיקות ל-packages/corpus/chunking.py (משימה א, 2026-09-16) - בלי
רשת/embeddings בכלל (טהור, ראו דוקסטרינג המודול). חלק על fixture
אמיתי (hesderim-1991, מקונן תחת פרקים - אותו fixture ממשימה 7/
test_amend_hesderim.py) + עצים סינתטיים קטנים לבדיקת גבולות הפיצול
(2,000 תווים, אטומיות raw_block) שלא קיימים בפועל בשני ה-fixtures
הקטנים הקיימים.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from chunking import chunk_law, chunk_section  # noqa: E402
from node import LegislativeNode  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "wikitext"


def _section(number, children=None, text="", margin_title=None, node_id=None):
    return LegislativeNode(
        id=node_id or f"law-x/s{number}",
        node_type="section",
        number=number,
        margin_title=margin_title,
        text=text,
        children=children or [],
    )


def _child(node_type, node_id, text):
    return LegislativeNode(id=node_id, node_type=node_type, number="", margin_title=None, text=text)


def main():
    ok = True

    # --- fixture אמיתי (hesderim-1991, מקונן תחת פרקים - node.find_sections
    #     רקורסיבי כבר נבדק על החוק הזה ב-test_amend_hesderim.py) ---
    meta = json.loads((FIXTURES / "hesderim-1991.meta.json").read_text(encoding="utf-8"))
    text = (FIXTURES / "hesderim-1991.wikitext").read_text(encoding="utf-8")
    root = parse_wikitext(text, law_id="hesderim-1991", as_of=meta["revision_timestamp"])
    chunks = chunk_law(root)
    passed = len(chunks) == 4 and {c.section_number for c in chunks} == {"1", "2", "3", "4"}
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "fixture אמיתי (hesderim-1991): 4 סעיפים -> 4 chunks ->",
          [c.section_number for c in chunks] if not passed else "")

    c3 = next(c for c in chunks if c.section_number == "3")
    passed = c3.context_prefix.startswith(root.full_title) and "סעיף 3" in c3.context_prefix and c3.chunk_index == 0
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "context_prefix מכיל שם חוק + מספר סעיף ->", c3.context_prefix if not passed else "")

    # --- סעיף קצר בלי ילדים ארוכים מדי -> chunk יחיד, לא מפוצל ---
    short_section = _section("1", children=[_child("paragraph", "law-x/s1/p0", "טקסט קצר.")])
    chunks = chunk_section("law-x", "חוק לדוגמה", short_section)
    passed = len(chunks) == 1 and chunks[0].chunk_index == 0
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "סעיף קצר -> chunk יחיד, לא מפוצל")

    # --- סעיף ארוך (>2000 תווים) עם כמה ילדים -> מפוצל, chunk אחד לכל ילד ---
    long_children = [_child("paragraph", f"law-x/s2/p{i}", "מילה " * 100) for i in range(5)]  # ~600 תווים כל אחד, 5*600>2000
    long_section = _section("2", children=long_children)
    chunks = chunk_section("law-x", "חוק לדוגמה", long_section)
    passed = len(chunks) == 5 and all(c.section_number == "2" for c in chunks) and [c.chunk_index for c in chunks] == [0, 1, 2, 3, 4]
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "סעיף ארוך -> מפוצל לפי ילדים, chunk_index רציף ->",
          [c.chunk_index for c in chunks] if not passed else "")
    passed = all(c.context_prefix == chunks[0].context_prefix for c in chunks)
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "כל ה-chunks המפוצלים חולקים את אותו context_prefix")

    # --- raw_block בתוך סעיף ארוך שמתפצל -> נשאר שלם בתוך chunk אחד, לא נחתך ---
    raw_text = "<table>" + ("<tr><td>נתון</td></tr>" * 50) + "</table>"  # ארוך, לא קשור לגודל שאר הילדים
    mixed_children = [
        _child("paragraph", "law-x/s3/p0", "פסקה רגילה ראשונה " * 30),
        _child("raw_block", "law-x/s3/table0", raw_text),
        _child("paragraph", "law-x/s3/p1", "פסקה רגילה שניה " * 30),
    ]
    mixed_section = _section("3", children=mixed_children)
    chunks = chunk_section("law-x", "חוק לדוגמה", mixed_section)
    raw_chunks = [c for c in chunks if c.contains_raw_block]
    passed = (
        len(chunks) == 3
        and len(raw_chunks) == 1
        and raw_text in raw_chunks[0].body
        and raw_chunks[0].node_ids == ["law-x/s3/table0"]
        and not any(raw_text in c.body for c in chunks if c is not raw_chunks[0])
    )
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "raw_block לא נחתך - נשאר שלם בתוך chunk אחד משלו")

    # --- סעיף עלה (בלי ילדים בכלל) וארוך -> chunk יחיד למרות האורך (אין יחידה עדינה יותר לפצל לפיה) ---
    leaf_section = _section("4", children=[], text="מילה " * 1000)  # ~5000 תווים, בלי ילדים
    chunks = chunk_section("law-x", "חוק לדוגמה", leaf_section)
    passed = len(chunks) == 1 and len(chunks[0].body) > 2000
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "סעיף-עלה ארוך בלי ילדים -> נשאר chunk יחיד (אין לאן לפצל)")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
