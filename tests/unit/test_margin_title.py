"""בודק ReplaceMarginTitleWords/_MarginTitleMutation - עריכת כותרת
שוליים של סעיף - ha-hoveret-ha-sgula.pdf §7.8, עמ' 26 [PDF 55]:
"בסעיף מס' הסעיף לחוק העיקרי, בכותרת השוליים, במקום 'טקסט קיים' יבוא
'טקסט חדש'". ראו TASKS.md משימה 10ב.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from transform import ReplaceMarginTitleWords, apply  # noqa: E402
from engine import amend  # noqa: E402


def _law_with_section_5() -> LegislativeNode:
    section5 = LegislativeNode(
        id="law/s5", node_type="section", number="5", margin_title="עונשין", text="",
        children=[
            LegislativeNode(id="law/s5/p0", node_type="paragraph", number="",
                             margin_title=None, text="תוכן הסעיף."),
        ],
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, full_title='חוק לדוגמה, התש"ף–2020',
        children=[section5],
    )


def main():
    ok = True
    before = _law_with_section_5()

    after, annotations = apply(before, [
        ReplaceMarginTitleWords(section_number="5", old_phrase="עונשין", new_phrase="עונשין וקנסות"),
    ])
    passed_title = after.children[0].margin_title == "עונשין וקנסות"
    ok = ok and passed_title
    print(("OK  " if passed_title else "FAIL"), "כותרת השוליים משתנה בעץ ה'אחרי'",
          "" if passed_title else f"-> {after.children[0].margin_title!r}")

    lines = amend(before, after, annotations, law_footnote_key="fake")
    want = (
        'בחוק לדוגמה, התש"ף–2020 (להלן – החוק העיקרי), בסעיף 5, '
        'בכותרת השוליים, במקום "עונשין" יבוא "עונשין וקנסות".'
    )
    passed_line = len(lines) == 1 and lines[0].text == want
    ok = ok and passed_line
    print(("OK  " if passed_line else "FAIL"), "מתלכד לשורה בודדת בניסוח §7.8",
          "" if passed_line else f"-> {[l.text for l in lines]!r}")

    passed_heading = len(lines) == 1 and lines[0].side_heading == "תיקון סעיף 5"
    ok = ok and passed_heading
    print(("OK  " if passed_heading else "FAIL"), "כותרת שוליים בטבלה: תיקון סעיף 5")

    # קלט לא תקין: ביטוי לא ייחודי/לא קיים - כושל בקול, לא ניחוש.
    threw = False
    try:
        apply(before, [
            ReplaceMarginTitleWords(section_number="5", old_phrase="לא קיים", new_phrase="x"),
        ])
    except ValueError:
        threw = True
    ok = ok and threw
    print(("OK  " if threw else "FAIL"), "ביטוי לא קיים בכותרת -> שגיאה, לא ניחוש")

    # שילוב: גם כותרת שוליים וגם גוף הטקסט משתנים באותו סעיף - שתי
    # שורות (כותרת קודם, אז גוף), לא התלכדות.
    from transform import ReplaceWords

    after2, annotations2 = apply(before, [
        ReplaceMarginTitleWords(section_number="5", old_phrase="עונשין", new_phrase="עונשין חמורים"),
        ReplaceWords(target_id="law/s5/p0", old_phrase="תוכן הסעיף", new_phrase="תוכן חדש"),
    ])
    lines2 = amend(before, after2, annotations2, law_footnote_key="fake")
    # שני מכשירים בסעיף אחד -> לא מתלכד: כותרת (header נפרד, בדיוק כמו
    # שכל סעיף עם כמה הוראות מקבל) + שורת כותרת שוליים + שורת גוף.
    passed_combo = (
        len(lines2) == 3
        and lines2[0].side_heading == "תיקון סעיף 5"
        and "בכותרת השוליים" in lines2[1].text
        and "תוכן חדש" in lines2[2].text
    )
    ok = ok and passed_combo
    print(("OK  " if passed_combo else "FAIL"), "שילוב כותרת+גוף באותו סעיף -> כותרת+2 שורות",
          "" if passed_combo else f"-> {[l.text for l in lines2]!r}")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
