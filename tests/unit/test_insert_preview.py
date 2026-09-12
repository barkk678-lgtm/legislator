"""בודק insert_preview.preview_insertion_label - תצוגה מקדימה של תווית
הוספה, בלי לבצע את ההוספה. ראו TASKS.md משימה 10ב.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from node import LegislativeNode  # noqa: E402
from insert_preview import preview_insertion_label  # noqa: E402


def _tree() -> LegislativeNode:
    # סעיף 5: יש סעיפים קטנים (א),(ב).
    section5 = LegislativeNode(
        id="law/s5", node_type="section", number="5", margin_title="כותרת 5", text="",
        children=[
            LegislativeNode(id="law/s5/a", node_type="subsection", number="א",
                             margin_title=None, text="תוכן א."),
            LegislativeNode(id="law/s5/b", node_type="subsection", number="ב",
                             margin_title=None, text="תוכן ב."),
        ],
    )
    # סעיף 6: אין עדיין סעיפים קטנים - ילד יחיד בלי תווית.
    section6 = LegislativeNode(
        id="law/s6", node_type="section", number="6", margin_title="כותרת 6", text="",
        children=[
            LegislativeNode(id="law/s6/p0", node_type="paragraph", number="",
                             margin_title=None, text="תוכן 6."),
        ],
    )
    # סעיף 1: פסקאות ממוספרות ישירות (כמו קייטנות סעיף 1).
    section1 = LegislativeNode(
        id="law/s1", node_type="section", number="1", margin_title="הגדרות", text="",
        children=[
            LegislativeNode(id="law/s1/p1", node_type="paragraph", number="1",
                             margin_title=None, text="פרט 1."),
            LegislativeNode(id="law/s1/p2", node_type="paragraph", number="2",
                             margin_title=None, text="פרט 2."),
        ],
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, children=[section1, section5, section6],
    )


def main():
    ok = True

    def check(name, node_id, level, expect_supported, expect_label=None):
        nonlocal ok
        result = preview_insertion_label(_tree(), node_id, level)
        passed = result.supported == expect_supported and (
            not expect_supported or result.label == expect_label
        )
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name, "" if passed else f"-> {result!r}")

    # סעיף ראשי - הוספה אחרי סעיף 5 (יש סעיף 6 אחריו) -> "5א".
    check("סעיף ראשי, בין 5 ל-6", "law/s5", "section", True, "5א")
    # סעיף ראשי - הוספה אחרי הסעיף האחרון (6) -> "7".
    check("סעיף ראשי, בסוף (אחרי 6)", "law/s6", "section", True, "7")

    # סעיף קטן - יש כבר (א),(ב); על הסעיף עצמו -> מוסיף בסוף -> "ג".
    check("סעיף קטן, על הסעיף עצמו (יש כבר קטנים)", "law/s5", "subsection", True, "ג")
    # על סעיף קטן (א) עצמו -> בין א ל-ב -> "א1".
    check("סעיף קטן, על (א) - בין א ל-ב", "law/s5/a", "subsection", True, "א1")
    # על סעיף קטן (ב) (האחרון) -> בסוף -> "ג".
    check("סעיף קטן, על (ב) - בסוף", "law/s5/b", "subsection", True, "ג")
    # סעיף 6 - אין עדיין סעיפים קטנים -> "ב" (AddFirstSubsection).
    check("סעיף קטן, סעיף בלי קטנים בכלל", "law/s6", "subsection", True, "ב")

    # פסקה - ילד ישיר של סעיף (לא של סעיף קטן) - נתמך.
    check("פסקה, ילד ישיר של סעיף - בין 1 ל-2", "law/s1/p1", "paragraph", True, "1א")
    check("פסקה, ילד ישיר של סעיף - בסוף", "law/s1/p2", "paragraph", True, "3")

    # פסקה בתוך סעיף קטן - לא נתמך (אין ילד כזה בעץ הזה, אבל בודקים גם
    # ניסיון להוסיף פסקה "על" סעיף קטן עצמו, כשאין פסקאות בו).
    check("פסקה, על סעיף קטן (א) עצמו - לא נתמך", "law/s5/a", "paragraph", False)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
