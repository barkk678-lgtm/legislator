"""בדיקות ל-provenance (source_node_id/as_of על Line, ראו TASKS.md
משימה 5א - חוק ברזל 3). מקרי הזהב (test_amend_kaytanot.py,
test_kaytanot_section5.py) כבר בודקים את זה במפורש כחלק מהשוואת
Line מלאה; הטסט הזה מבודד את ההתנהגות עצמה, כולל המקרה השבור
המרכזי: כשאין as_of בעץ המקור, אסור להמציא אחד - צריך לזרום None
עד שהוולידטור (משימה 6) יתריע.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from transform import InsertAfter, apply  # noqa: E402
from engine import amend  # noqa: E402


def _tree(as_of: str | None) -> LegislativeNode:
    p0 = LegislativeNode(
        id="law/s1/p0", node_type="paragraph", number="", margin_title=None, text="בחוק זה –"
    )
    section = LegislativeNode(
        id="law/s1", node_type="section", number="1", margin_title="הגדרות", text="",
        children=[p0],
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        children=[section], is_normative=False, as_of=as_of,
    )


def main():
    checks = []

    # מקרה תקין: as_of ידוע בשורש - כל שורה שהמנוע מפיק חייבת לשאת אותו.
    before = _tree(as_of="2024-01-01T00:00:00Z")
    new_def = LegislativeNode(
        id="law/s1/new", node_type="definition", number="", margin_title=None,
        text='"הגדרה חדשה" – תוכן.',
    )
    after, annotations = apply(
        before, [InsertAfter(section_number="1", anchor_id="law/s1/p0", new_child=new_def)]
    )
    lines = amend(before, after, annotations, law_footnote_key="x")

    # header (סעיף ראשון שנוגעים בו) + phrase_line + content_line
    checks.append(("יש 3 שורות: כותרת + phrase + content", len(lines) == 3))
    checks.append(
        ("לכל שורה יש source_node_id", all(line.source_node_id is not None for line in lines))
    )
    checks.append(
        (
            "as_of על כל שורה תואם את as_of השורש",
            all(line.as_of == "2024-01-01T00:00:00Z" for line in lines),
        )
    )
    checks.append(("כותרת הסעיף: source_node_id הוא שורש החוק", lines[0].source_node_id == "law"))
    checks.append(
        (
            "phrase_line ו-content_line: source_node_id מצביע על העוגן p0 (לא על הצומת החדש)",
            lines[1].source_node_id == "law/s1/p0" and lines[2].source_node_id == "law/s1/p0",
        )
    )

    # המקרה השבור המרכזי: אין as_of בשורש בכלל (למשל law שנבנה בלי
    # מטא-דאטה של ingest). אסור להמציא תאריך - as_of על השורה חייב
    # לזרום None, לא ערך שרירותי (חוק ברזל 3: "אם המערכת לא יודעת עד
    # מתי הנוסח מעודכן - היא אומרת זאת למשתמש, לא מנחשת").
    before_no_date = _tree(as_of=None)
    after_no_date, annotations_no_date = apply(
        before_no_date, [InsertAfter(section_number="1", anchor_id="law/s1/p0", new_child=new_def)]
    )
    lines_no_date = amend(before_no_date, after_no_date, annotations_no_date, law_footnote_key="x")
    checks.append(
        (
            "בלי as_of במקור: זורם None ולא ערך מומצא",
            all(line.as_of is None for line in lines_no_date),
        )
    )
    checks.append(
        (
            "source_node_id עדיין קיים גם כש-as_of חסר (שני שדות עצמאיים)",
            all(line.source_node_id is not None for line in lines_no_date),
        )
    )

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
