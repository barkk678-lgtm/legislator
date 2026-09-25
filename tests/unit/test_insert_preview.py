"""בודק insert_preview.preview_insertion_label - תצוגה מקדימה של תווית
הוספה, בלי לבצע את ההוספה. ראו TASKS.md משימה 10ב.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from insert_preview import build_insertion_transform, preview_insertion_label  # noqa: E402
from transform import apply  # noqa: E402


def _tree() -> LegislativeNode:
    # סעיף 5: יש סעיפים קטנים (א),(ב) - עם סוגריים, בדיוק כפי שהם
    # מגיעים בפועל מ-wikitext_parser (הארגומנט הגולמי בתבנית כבר כולל
    # את הסוגריים - ראו _SUBSECTION_LABEL/_PARAGRAPH_LABEL). גרסה
    # קודמת של הפיקסצ'ר השתמשה בתוויות בלי סוגריים ("א"/"1") - זה
    # החביא באג אמיתי (סוגריים כפולים) שנתפס רק מול חוק אמיתי.
    section5 = LegislativeNode(
        id="law/s5", node_type="section", number="5", margin_title="כותרת 5", text="",
        children=[
            LegislativeNode(id="law/s5/a", node_type="subsection", number="(א)",
                             margin_title=None, text="תוכן א."),
            LegislativeNode(id="law/s5/b", node_type="subsection", number="(ב)",
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
            LegislativeNode(id="law/s1/p1", node_type="paragraph", number="(1)",
                             margin_title=None, text="פרט 1."),
            LegislativeNode(id="law/s1/p2", node_type="paragraph", number="(2)",
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

    # סעיף קטן - יש כבר (א),(ב); על הסעיף עצמו -> מוסיף בסוף -> "(ג)".
    check("סעיף קטן, על הסעיף עצמו (יש כבר קטנים)", "law/s5", "subsection", True, "(ג)")
    # על סעיף קטן (א) עצמו -> בין א ל-ב -> "(א1)".
    check("סעיף קטן, על (א) - בין א ל-ב", "law/s5/a", "subsection", True, "(א1)")
    # על סעיף קטן (ב) (האחרון) -> בסוף -> "(ג)".
    check("סעיף קטן, על (ב) - בסוף", "law/s5/b", "subsection", True, "(ג)")
    # סעיף 6 - אין עדיין סעיפים קטנים -> "(ב)" (AddFirstSubsection).
    check("סעיף קטן, סעיף בלי קטנים בכלל", "law/s6", "subsection", True, "(ב)")

    # פסקה - ילד ישיר של סעיף (לא של סעיף קטן) - נתמך.
    check("פסקה, ילד ישיר של סעיף - בין 1 ל-2", "law/s1/p1", "paragraph", True, "(1א)")
    check("פסקה, ילד ישיר של סעיף - בסוף", "law/s1/p2", "paragraph", True, "(3)")

    # פסקה "על" סעיף קטן עצמו, כשאין פסקאות בו - עד 26.9 לא נתמך. ח11-ב
    # (ברק): "(א) הופך ל-(א)(1)" - הנוסח הקיים הופך לפסקה (1), החדש (2).
    check("פסקה, על סעיף קטן (א) בלי פסקאות - (א) הופך ל-(א)(1)", "law/s5/a", "paragraph", True, "(2)")

    # אינטגרציה: build_insertion_transform + apply() בפועל, לכל שלושת
    # ה-kind-ים - סוגר את הלולאה בין מה שמוצג מראש למה שקורה בפועל.
    t, err = build_insertion_transform(
        _tree(), "law/s5", "section", text="תוכן חדש.", margin_title="כותרת חדשה"
    )
    ok = ok and err is None
    after, _ = apply(_tree(), [t])
    new_numbers = [c.number for c in after.children if c.node_type == "section"]
    passed_section = "5א" in new_numbers
    ok = ok and passed_section
    print(("OK  " if passed_section else "FAIL"), "אינטגרציה: InsertSectionAfter -> 5א בעץ")

    t2, err2 = build_insertion_transform(_tree(), "law/s6", "subsection", text="תוכן ב.")
    ok = ok and err2 is None
    after2, _ = apply(_tree(), [t2])
    section6_after = next(c for c in after2.children if c.number == "6")
    labels2 = [c.number for c in section6_after.children if c.is_normative]
    passed_subsection = labels2 == ["(א)", "(ב)"]
    ok = ok and passed_subsection
    print(("OK  " if passed_subsection else "FAIL"), "אינטגרציה: AddFirstSubsection -> (א),(ב)",
          "" if passed_subsection else f"-> {labels2}")

    t3, err3 = build_insertion_transform(_tree(), "law/s5/a", "subsection", text="תוכן חדש.")
    ok = ok and err3 is None
    after3, _ = apply(_tree(), [t3])
    section5_after = next(c for c in after3.children if c.number == "5")
    labels3 = [c.number for c in section5_after.children if c.is_normative]
    passed_insert_after = labels3 == ["(א)", "(א1)", "(ב)"]
    ok = ok and passed_insert_after
    print(("OK  " if passed_insert_after else "FAIL"), "אינטגרציה: InsertAfter (סעיף קטן) -> (א),(א1),(ב)",
          "" if passed_insert_after else f"-> {labels3}")

    # שגוי: הוספת סעיף ראשי בלי כותרת שוליים -> None + סיבה, לא ניחוש.
    t_bad, err_bad = build_insertion_transform(_tree(), "law/s5", "section", text="תוכן.")
    passed_bad = t_bad is None and err_bad is not None
    ok = ok and passed_bad
    print(("OK  " if passed_bad else "FAIL"), "בלי כותרת שוליים -> None + סיבה")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
