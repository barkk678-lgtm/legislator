"""בודק InsertSectionAfter/_render_new_section: הוספת סעיף ראשי חדש
(לא סעיף קטן/פסקה בתוך סעיף קיים) - ha-hoveret-ha-sgula.pdf §7.12,
עמ' 31 [PDF 60]:

    "בחוק [שם החוק], אחרי סעיף [מספר הסעיף] לחוק העיקרי יבוא:
    'כותרת שוליים [מספר הסעיף החדש] [תוכן הסעיף].'"

**הפער שהורחב כאן (drafting-rules.md §8.5):** amend() עבר עד כה רק על
before_sections.keys() - סעיף ראשי חדש לגמרי (שלא קיים ב"לפני" בכלל)
היה בלתי-נראה למנוע, מפיק אפס פלט בשקט. תוקן: הלולאה עוברת עכשיו על
איחוד המספרים משני העצים.

**מרכאות (השאלה הפתוחה שהוכרעה 2026-09-12, לא ניחוש):** אומת מול
reference/skeleton-pshia.docx - הצעה פרטית טרומית אמיתית (פ/6158/25,
ח"כ צביקה פוגל, הכנסת 25; BillID 2233987 אומת מול ה-OData של הכנסת -
SubTypeDesc="פרטית"). ב-XML הגולמי של הקובץ: המרכאה הפותחת יושבת כתו
הראשון של כותרת השוליים של הסעיף/הפרק החדש (תא TableHead/
TableInnerSideHeading), והסוגרת כתו האחרון של תוכן הסעיף האחרון (תא
TableBlock) - בלי מרכאות נפרדות בכל תא באמצע. ראו docs/drafting-rules.md
§8.5 לפירוט המלא.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from transform import InsertSectionAfter, apply  # noqa: E402
from engine import amend  # noqa: E402


def _law_with_sections_8_and_9() -> LegislativeNode:
    section8 = LegislativeNode(
        id="law/s8", node_type="section", number="8", margin_title="כותרת 8",
        text="תוכן סעיף 8.",
    )
    section9 = LegislativeNode(
        id="law/s9", node_type="section", number="9", margin_title="כותרת 9",
        text="תוכן סעיף 9.",
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, full_title='חוק לדוגמה, התש"ף–2020',
        children=[section8, section9],
    )


def main():
    ok = True
    before = _law_with_sections_8_and_9()

    # מקרה 1: הוספה בין 8 ל-9 קיימים - מקבלת תווית מורכבת ("8א"), לא
    # "9" (שכבר תפוס) - §8.1.
    after, annotations = apply(before, [
        InsertSectionAfter(
            after_section_number="8",
            new_section=LegislativeNode(
                id="law/s8a", node_type="section", number="",
                margin_title="כותרת הסעיף החדש", text="תוכן הסעיף החדש.",
            ),
        ),
    ])
    inserted_number = after.children[1].number
    passed_label = inserted_number == "8א"
    ok = ok and passed_label
    print(("OK  " if passed_label else "FAIL"), "מספור אוטומטי -> 8א",
          "" if passed_label else f"-> {inserted_number!r}")

    lines = amend(before, after, annotations, law_footnote_key="fake")
    # מראה המקום מפוצל ל-text/text_after (יושב מיד אחרי השנה, לפני
    # "(להלן..." - ראו engine._render_new_section) - משווים את הצירוף.
    got_texts = [line.text + line.text_after for line in lines]

    want_phrase = (
        'בחוק לדוגמה, התש"ף–2020, אחרי סעיף 8 '
        "לחוק העיקרי יבוא:"
    )
    passed_phrase = len(got_texts) == 2 and got_texts[0] == want_phrase
    ok = ok and passed_phrase
    print(("OK  " if passed_phrase else "FAIL"), "שורת פתיח (אחרי סעיף 8)",
          "" if passed_phrase else f"-> {got_texts}")

    want_content = 'תוכן הסעיף החדש."'
    passed_content = len(got_texts) == 2 and got_texts[1] == want_content
    ok = ok and passed_content
    print(("OK  " if passed_content else "FAIL"), "תא התוכן - בלי מרכאה פותחת",
          "" if passed_content else f"-> {got_texts}")

    passed_side_heading = len(lines) == 2 and lines[0].side_heading == "הוספת סעיף 8א"
    ok = ok and passed_side_heading
    print(("OK  " if passed_side_heading else "FAIL"), "כותרת שוליים - הוספת סעיף 8א",
          "" if passed_side_heading else f"-> {lines[0].side_heading!r}")

    passed_inner = (
        len(lines) == 2
        and lines[1].inner_heading == '"כותרת הסעיף החדש'
        and lines[1].inner_number == "8א."
        and lines[1].style == "TableBlock"
    )
    ok = ok and passed_inner
    print(("OK  " if passed_inner else "FAIL"),
          "מרכאה פותחת על inner_heading + inner_number + style=TableBlock",
          "" if passed_inner else f"-> {lines[1].inner_heading!r} {lines[1].inner_number!r} {lines[1].style!r}")

    # מקרה 2: הוספה בסוף (אחרי הילד האחרון, אין שכן אחריו) -> תווית
    # פשוטה שממשיכה את הרצף ("10"), לא תווית מורכבת - §8.1.
    after2, _annotations2 = apply(before, [
        InsertSectionAfter(
            after_section_number="9",
            new_section=LegislativeNode(
                id="law/s10", node_type="section", number="",
                margin_title="כותרת 10", text="תוכן 10.",
            ),
        ),
    ])
    inserted_number2 = after2.children[2].number
    passed_label2 = inserted_number2 == "10"
    ok = ok and passed_label2
    print(("OK  " if passed_label2 else "FAIL"), "מספור אוטומטי בסוף -> 10",
          "" if passed_label2 else f"-> {inserted_number2!r}")

    # מקרה שבור: number נקבע מראש -> שגיאה, לא ניחוש/דריסה שקטה.
    threw = False
    try:
        apply(before, [
            InsertSectionAfter(
                after_section_number="8",
                new_section=LegislativeNode(
                    id="law/sbad", node_type="section", number="8א",
                    margin_title="לא אמור", text="לא אמור.",
                ),
            ),
        ])
    except ValueError:
        threw = True
    ok = ok and threw
    print(("OK  " if threw else "FAIL"), "number נקבע מראש -> שגיאה, לא ניחוש")

    # עודכן במכוון ב-2026-09-17 (היה NotImplementedError): הוספה רצופה
    # של שני סעיפים חדשים היא הפער הנפוץ ביותר שנמצא בביקורת מול 40
    # הצעות אמיתיות - הצעה שהונחה בכנסת מוסיפה 2ג ו-2ד בהוראה אחת עם
    # כותרת "הוספת סעיפים 2ג ו־2ד" (tests/fixtures/real-bills/
    # 13948392.docx). §8.5 סימנה את זה כ"היקף שלא נכלל", וזה מומש -
    # תיקון, לא רגרסיה. נבנה ידנית (בלי transform.apply()) כדי לבודד
    # את התנהגות amend() מלוגיקת המספור.
    after3 = _law_with_sections_8_and_9()
    after3.children.insert(1, LegislativeNode(
        id="law/s8a-2", node_type="section", number="8א",
        margin_title="כותרת 8א", text="תוכן 8א.",
    ))
    after3.children.insert(2, LegislativeNode(
        id="law/s8b-2", node_type="section", number="8ב",
        margin_title="כותרת 8ב", text="תוכן 8ב.",
    ))
    lines3 = amend(before, after3, [], law_footnote_key="fake")
    headings3 = [ln.side_heading for ln in lines3 if ln.side_heading]
    ok = ok and headings3 == ["הוספת סעיפים 8א ו\u05be8ב"]
    print(("OK  " if headings3 == ["הוספת סעיפים 8א ו\u05be8ב"] else "FAIL"),
          "שני סעיפים רצופים -> הוראה אחת, כותרת אחת ->", headings3)

    numbers3 = [ln.number for ln in lines3 if ln.number]
    ok = ok and numbers3 == ["1."]
    print(("OK  " if numbers3 == ["1."] else "FAIL"),
          "שני סעיפים רצופים -> הוראת תיקון אחת בלבד ->", numbers3)

    inner3 = [(ln.inner_heading, ln.inner_number) for ln in lines3 if ln.inner_number]
    expected3 = [('"כותרת 8א', "8א."), ("כותרת 8ב", "8ב.")]
    ok = ok and inner3 == expected3
    print(("OK  " if inner3 == expected3 else "FAIL"),
          "מרכאה פותחת רק בסעיף הראשון ->", inner3)

    closing3 = [ln.text for ln in lines3 if ln.inner_number]
    closes_once = closing3 == ["תוכן 8א.", 'תוכן 8ב."']
    ok = ok and closes_once
    print(("OK  " if closes_once else "FAIL"),
          "מרכאה סוגרת רק בסעיף האחרון ->", closing3)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
