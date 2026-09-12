"""בדיקות לולידטור (packages/validate/validator.py). ראו TASKS.md משימה 6.

לכל אחת מ-15 הבדיקות: מקרה שבור אחד לפחות, בנוי ידנית (לא ממתין
למקרה זהב) ומוכיח שהבדיקה תופסת אותו. ראו tests/golden/test_kaytanot.py
ו-tests/golden/test_kaytanot_section5.py לריצה על מקרים אמיתיים.
"""

import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "validate"))

from node import LegislativeNode  # noqa: E402
from render_bill import Bill, Line  # noqa: E402
from validator import validate  # noqa: E402

_GOOD_TITLE = 'הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון – הגדרת קייטנה מפוקחת), התש"ף–2023'


def _tree() -> LegislativeNode:
    """עץ קטן, שקיים בו s1/p0 ו-s2/p0 - מספיק לרוב הבדיקות."""
    s1p0 = LegislativeNode(id="law/s1/p0", node_type="paragraph", number="", margin_title=None, text="בחוק זה –")
    s1 = LegislativeNode(
        id="law/s1", node_type="section", number="1", margin_title="הגדרות", text="", children=[s1p0]
    )
    s2p0 = LegislativeNode(id="law/s2/p0", node_type="paragraph", number="", margin_title=None, text="טקסט 2")
    s2 = LegislativeNode(
        id="law/s2", node_type="section", number="2", margin_title="", text="", children=[s2p0]
    )
    s5p0 = LegislativeNode(id="law/s5/p0", node_type="paragraph", number="", margin_title=None, text="טקסט 5")
    s5 = LegislativeNode(
        id="law/s5", node_type="section", number="5", margin_title="", text="", children=[s5p0]
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        children=[s1, s2, s5], is_normative=False, as_of="2024-01-01T00:00:00Z",
    )


def _good_line(**overrides) -> Line:
    """שורה תקינה בסיסית (הפניית סעיף 1 שמגדירה 'להלן'), לשימוש כרקע
    ניטרלי כשבודקים שדה ספציפי אחד."""
    defaults = dict(
        side_heading="תיקון סעיף 1",
        text="בחוק כלשהו",
        text_after=" (להלן – החוק העיקרי), בסעיף 1 – ",
        source_node_id="law",
        as_of="2024-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return Line(**defaults)


def _bill(lines, **overrides) -> Bill:
    defaults = dict(
        knesset="הכנסת העשרים וחמש",
        title=_GOOD_TITLE,
        initiator="פלוני",
        submitted_date="15.11.2023",
        lines=lines,
    )
    defaults.update(overrides)
    return Bill(**defaults)


def _status(findings, number: int) -> str:
    return next(f.status for f in findings if f.check_number == number)


def main():
    checks = []
    before = _tree()
    refs = {"k": "מראה מקום"}

    # --- מקרה תקין בסיסי: 15 ממצאים, לפי סדר 1..15 ---
    baseline = validate(_bill([_good_line()]), before, refs)
    checks.append(("15 ממצאים בדיוק", len(baseline) == 15))
    checks.append(("הממצאים ממוספרים 1..15 לפי סדר", [f.check_number for f in baseline] == list(range(1, 16))))

    # 1: source_node_id שמצביע לצומת שלא קיים
    broken1 = validate(_bill([_good_line(source_node_id="law/s99/p0")]), before, refs)
    checks.append(("1: צומת לא קיים -> נכשל", _status(broken1, 1) == "נכשל"))

    # 2: מפתח הערת שוליים בשימוש בלי מראה מקום ב-refs
    broken2 = validate(_bill([_good_line(footnotes=["missing"])]), before, refs)
    checks.append(("2: מפתח הערת שוליים בלי refs -> נכשל", _status(broken2, 2) == "נכשל"))

    # 3: "החוק העיקרי" (בה' הידיעה, לא "לחוק העיקרי") מוזכר לפני שהוגדר
    broken3 = validate(
        _bill(
            [
                Line(text="לפי החוק העיקרי, נדרש רישיון.", source_node_id="law", as_of="2024-01-01T00:00:00Z"),
                _good_line(),
            ]
        ),
        before,
        refs,
    )
    checks.append(('3: "החוק העיקרי" לפני שהוגדר -> נכשל', _status(broken3, 3) == "נכשל"))

    # 4: כותרת שוליים שמתארת מהות, לא {פעולה} סעיף {N}
    broken4 = validate(_bill([_good_line(side_heading="עדכון תנאי הרישוי")]), before, refs)
    checks.append(("4: כותרת שוליים שגויה -> נכשל", _status(broken4, 4) == "נכשל"))

    # 5: גרש עברי ״ (U+05F4) במקום "
    broken5 = validate(_bill([_good_line(text='ה״חוק')]), before, refs)
    checks.append(("5: גרש עברי ״ -> נכשל", _status(broken5, 5) == "נכשל"))

    # 6: מקף רגיל בשנה עברית במקום en-dash
    broken6 = validate(_bill([_good_line(text='התש"ן-1990')]), before, refs)
    checks.append(("6: מקף רגיל בשנה עברית -> נכשל", _status(broken6, 6) == "נכשל"))

    # 7: שם הצעה לא בפורמט התקני
    broken7 = validate(_bill([_good_line()], title="חוק סתם"), before, refs)
    checks.append(("7: שם הצעה שגוי -> נכשל", _status(broken7, 7) == "נכשל"))

    # 8: submitted_date חסר, ו-submitted_date עם שנה לא תואמת
    broken8a = validate(_bill([_good_line()], submitted_date=""), before, refs)
    checks.append(("8: submitted_date ריק -> נכשל", _status(broken8a, 8) == "נכשל"))
    broken8b = validate(_bill([_good_line()], submitted_date="15.11.1999"), before, refs)
    checks.append(("8: שנת ההגשה לא תואמת את שם ההצעה -> נכשל", _status(broken8b, 8) == "נכשל"))

    # 9: סדר סעיפים לא כרונולוגי (סעיף 5 לפני סעיף 2)
    broken9 = validate(
        _bill(
            [
                _good_line(side_heading="תיקון סעיף 5", source_node_id="law/s5/p0"),
                _good_line(side_heading="תיקון סעיף 2", source_node_id="law/s2/p0"),
            ]
        ),
        before,
        refs,
    )
    checks.append(("9: סעיפים לא כרונולוגיים -> נכשל", _status(broken9, 9) == "נכשל"))

    # 10: תמיד "לא נבדק"
    checks.append(('10: תמיד "לא נבדק"', _status(baseline, 10) == "לא נבדק"))

    # 11: הגדרה חדשה לפני הגדרה קיימת א"ב-ית (חשד, לא פסילה)
    broken11 = validate(
        _bill(
            [
                _good_line(),
                Line(text='אחרי ההגדרה "תנועת נוער" יבוא:', source_node_id="law", as_of="2024-01-01T00:00:00Z"),
                Line(text='"ארגון" – ארגון כלשהו.', source_node_id="law", as_of="2024-01-01T00:00:00Z"),
            ]
        ),
        before,
        refs,
    )
    checks.append(("11: הגדרה חדשה לפני העוגן א\"ב-ית -> אזהרה", _status(broken11, 11) == "אזהרה"))

    # 12: כותרת "תחילה" שאינה הכותרת האחרונה
    broken12 = validate(
        _bill(
            [
                _good_line(side_heading="תחילה", source_node_id="law/s2/p0"),
                _good_line(side_heading="תיקון סעיף 5", source_node_id="law/s5/p0"),
            ]
        ),
        before,
        refs,
    )
    checks.append(('12: "תחילה" לא אחרונה -> נכשל', _status(broken12, 12) == "נכשל"))

    # 13: תמיד "לא נבדק"
    checks.append(('13: תמיד "לא נבדק"', _status(baseline, 13) == "לא נבדק"))

    # 14: docx עם סגנון פסקה לא תקני
    with tempfile.TemporaryDirectory() as tmp:
        bad_docx = Path(tmp) / "bad.docx"
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        xml = (
            f'<w:document xmlns:w="{w}"><w:body><w:tbl><w:tr><w:tc>'
            f'<w:p><w:pPr><w:pStyle w:val="BadStyle"/></w:pPr></w:p>'
            f"</w:tc></w:tr></w:tbl></w:body></w:document>"
        )
        with zipfile.ZipFile(bad_docx, "w") as z:
            z.writestr("word/document.xml", xml)
        broken14 = validate(_bill([_good_line()]), before, refs, docx_path=bad_docx)
        checks.append(("14: סגנון פסקה לא תקני בדocx -> נכשל", _status(broken14, 14) == "נכשל"))
    checks.append(('14: בלי docx_path -> "לא נבדק"', _status(baseline, 14) == "לא נבדק"))

    # 15: as_of חסר על שורה עם source_node_id
    broken15 = validate(_bill([_good_line(as_of=None)]), before, refs)
    checks.append(("15: as_of חסר -> נכשל", _status(broken15, 15) == "נכשל"))
    broken15b = validate(_bill([_good_line(source_node_id=None)]), before, refs)
    checks.append(("15: source_node_id חסר -> נכשל", _status(broken15b, 15) == "נכשל"))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
