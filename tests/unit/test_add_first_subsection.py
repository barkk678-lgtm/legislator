"""בודק AddFirstSubsection/_RelabelAndInsert: הוספת הסעיף הקטן הראשון
לסעיף שאין בו עדיין סעיפים קטנים - ha-hoveret-ha-sgula.pdf §7.10.6(ד),
עמ' 29-30 [PDF 58-59]:

    "(ד) בסעיף שאינו כולל סעיפים קטנים
    - בסעיף [מספר הסעיף] לחוק העיקרי, האמור בו יסומן "(א)" ואחריו יבוא:
    "(ב) [תוכן הסעיף הקטן החדש]."

    דוגמה: בחוק העונשין, התשל"ז-1977, בסעיף 6, האמור בו יסומן "(א)"
    ואחריו יבוא: "(ב) [תוכן הסעיף הקטן החדש]."."

**זהו היקף שהורחב במפורש (לא היה בתוכנית המקורית):** המשתמש אישר
תחילה להוציא את המקרה הזה מהיקף (task 10ב), ואז חזר בו - בקייטנות רק
1 מתוך 7 סעיפים כולל סעיפים קטנים בכלל, כך שזה המצב הרגיל ולא מקרה
קצה, וממשק שמושבת ברוב הסעיפים אינו שימושי.

הניסוח "בסעיף N, האמור בו יסומן (א) ואחריו יבוא:" אושר כתקני מול
המשתמש, ונמצא לו מראה מקום ישיר בחוברת (למעלה) - לא נדרש הסימון
"קביעת ברק, לא אומת" שהמשתמש הציע כחלופה למקרה שבו לא יימצא מקור.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from transform import AddFirstSubsection, apply  # noqa: E402
from engine import amend  # noqa: E402


def _law_with_section_6_no_subsections() -> LegislativeNode:
    # תואם את הדוגמה בחוברת (סעיף 6 בחוק העונשין) במספר הסעיף, לא
    # בתוכנו האמיתי (התוכן כאן מומצא לצורך הטסט בלבד).
    content = LegislativeNode(
        id="law/s6/p0", node_type="paragraph", number="", margin_title=None,
        text="הוראות סעיף זה יחולו על כל אדם.",
    )
    section6 = LegislativeNode(
        id="law/s6", node_type="section", number="6", margin_title="כותרת 6",
        text="", children=[content],
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, full_title='חוק לדוגמה, התש"ף–2020',
        children=[section6],
    )


def main():
    ok = True
    before = _law_with_section_6_no_subsections()

    after, annotations = apply(before, [
        AddFirstSubsection(
            section_number="6",
            new_child=LegislativeNode(
                id="law/s6/new", node_type="paragraph", number="",
                margin_title=None, text="תוכן הסעיף הקטן החדש.",
            ),
        ),
    ])
    lines = amend(before, after, annotations, law_footnote_key="fake")

    got_texts = [line.text for line in lines]
    # touched_count==1 - הסעיף הראשון שנוגעים בו מקבל את שם החוק המלא
    # (drafting-rules.md §7.3), בדיוק כמו בהתלכדות _Mutation.
    want_phrase = (
        'בחוק לדוגמה, התש"ף–2020 (להלן – החוק העיקרי), בסעיף 6, '
        'האמור בו יסומן "(א)" ואחריו יבוא:'
    )
    want_content = '"(ב) תוכן הסעיף הקטן החדש.".'

    passed1 = len(got_texts) == 2 and got_texts[0] == want_phrase
    ok = ok and passed1
    print(("OK  " if passed1 else "FAIL"), "שורת פתיח", "" if passed1 else f"-> {got_texts}")

    passed2 = len(got_texts) == 2 and got_texts[1] == want_content
    ok = ok and passed2
    print(("OK  " if passed2 else "FAIL"), "שורת תוכן מצוטט", "" if passed2 else f"-> {got_texts}")

    # קלט לא תקין: סעיף עם סעיף קטן קיים כבר - אמור להיכשל בקול, לא לנחש.
    before2 = _law_with_section_6_no_subsections()
    before2.children[0].children[0].number = "א"
    threw = False
    try:
        apply(before2, [
            AddFirstSubsection(
                section_number="6",
                new_child=LegislativeNode(
                    id="law/s6/new2", node_type="paragraph", number="",
                    margin_title=None, text="עוד תוכן.",
                ),
            ),
        ])
    except ValueError:
        threw = True
    ok = ok and threw
    print(("OK  " if threw else "FAIL"), "סעיף עם סעיף קטן קיים -> שגיאה, לא ניחוש")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
