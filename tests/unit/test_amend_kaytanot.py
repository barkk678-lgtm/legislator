"""משווה amend() מול רשימת Line קבועה ובלתי-תלויה, שאומתה בעבר ידנית
מול reference/golden-kaytanot.docx (ראו tests/golden/test_kaytanot.py -
זה בדיוק מה שהיה שם לפני שהוחלף בקריאה למנוע). ראו TASKS.md משימה 4.

**חשוב:** ה-EXPECTED_LINES כאן היא עותק קבוע, לא ייבוא מ-BILL.lines
ב-test_kaytanot.py - מאז שהוחלף שם הרשימה המקודדת בקריאה ל-amend(),
BILL.lines *הוא* הפלט של amend(), והשוואה מולו הייתה טאוטולוגית
(אמנד מול עצמו, תמיד יעבור). הטסט הזה נשאר בדיקת רגרסיה עצמאית
אמיתית: אם engine.py ישתנה בעתיד וישבור את הניסוח המדויק, הטסט הזה
יתפוס את זה גם אם אף אחד לא ישווה שוב ידנית מול ה-docx האמיתי.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "golden"))

from render_bill import Line  # noqa: E402
from engine import amend  # noqa: E402
from test_kaytanot import load_before, build_after  # noqa: E402

EXPECTED_LINES = [
    Line(
        side_heading="תיקון סעיף 1",
        text='בחוק הקייטנות (רישוי ופיקוח), התש"ן-1990',
        text_after=' (להלן – החוק העיקרי), בסעיף 1 – ',
        footnotes=["kaytanot"],
        depth=0,
    ),
    Line(text='אחרי "בחוק זה" יבוא:', depth=0),
    Line(
        text='""ארגון נוער או תנועת נוער" – ארגון או תנועה או חוגי סיור '
        "הנתמכים על ידי משרד החינוך לפי מבחנים לצורך תמיכה;\";",
        style="TableBlockOutdent",
        depth=0,
    ),
    Line(text='אחרי ההגדרה "ילד" יבוא:', depth=0),
    Line(
        text='""מבחנים לצורך תמיכה" – מבחנים לצורך תמיכה של משרד חינוך '
        "בפעילות ארגוני ילדים ונוער במוסדות ציבור לפי חוק יסודות "
        'התקציב, התשמ"ה–1985',
        text_after='; מבחנים לצורך תמיכה של משרד החינוך בתנועות נוער לפי חוק '
        'יסודות התקציב, התשמ"ה-1985; מבחנים נוספים לחלוקת כספים '
        'לצורך תמיכה של משרד החינוך, התרבות והספורט במוסדות ציבור '
        'לפי חוק יסודות התקציב, התשמ"ה-1985";',
        footnotes=["budget"],
        style="TableBlockOutdent",
        depth=0,
    ),
    Line(marker="(3)", text="בסופו יבוא:", depth=0),
    Line(
        text='""קייטנה מפוקחת" – פעילות קיץ שמנהל ארגון נוער או תנועת נוער.".',
        style="TableBlockOutdent",
        depth=0,
    ),
    Line(
        side_heading="תיקון סעיף 2",
        number="2.",
        text='בסעיף 2 לחוק העיקרי, אחרי המילים "לא ינהל אדם קייטנה" יבוא '
        '"שאינה קייטנה מפוקחת".',
        depth=0,
    ),
]


def main():
    before = load_before()
    after, annotations = build_after(before)
    got = amend(before, after, annotations, law_footnote_key="kaytanot")
    want = EXPECTED_LINES

    ok = True
    print(f"שורות: נוצרו {len(got)}, במקור {len(want)}\n")
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else None
        w = want[i] if i < len(want) else None
        passed = g == w
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), f"line {i}")
        if not passed:
            print(f"     got : {g}")
            print(f"     want: {w}")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
