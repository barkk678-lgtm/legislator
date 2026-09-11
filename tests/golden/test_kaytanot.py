"""
מקרה זהב: שחזור הצעת חוק הקייטנות מתוך ייצוג מובנה.

המבחן: הטקסט של כל שורה בטבלה, וסגנון כל תא, זהים למקור.
זו נקודת הקבלה של משימה 5 בתוכנית העבודה.
"""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))

from render_bill import Bill, Line, write_docx  # noqa: E402

from lxml import etree  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "reference" / "golden-kaytanot.docx"
SKELETON = ROOT / "reference" / "skeleton-pshia.docx"

REFS = {
    "kaytanot": "ס\"ח התש\"ן, עמ' 155.",
    "budget": "ס\"ח התשמ\"ח, עמ' 60.",
}

BILL = Bill(
    knesset="הכנסת העשרים וחמש",
    title='הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון – הגדרת קייטנה מפוקחת), התש"ף–2023',
    initiator="יעקב אשר",
    bill_number="פ/?????????",
    submitted_date="????????????????????????",
    lines=[
        Line(
            side_heading="תיקון סעיף 1",
            text='בחוק הקייטנות (רישוי ופיקוח), התש"ן-1990',
            text_after=' (להלן \u2013 החוק העיקרי), בסעיף 1 \u2013 ',
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
            text='""מבחנים לצורך תמיכה" \u2013 מבחנים לצורך תמיכה של משרד חינוך '
                 "בפעילות ארגוני ילדים ונוער במוסדות ציבור לפי חוק יסודות "
                 'התקציב, התשמ"ה\u20131985',
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
    ],
    explanatory=[
        'מטרת חוק הקייטנות (רישוי ופיקוח), התש"ן–1990 (להלן – החוק), היא לפקח '
        "על פעילות יום יומית של נופש וחברה לקבוצת ילדים בחופשת הקיץ.",
        "הצורך בתיקון החוק בנושא זה דחוף לאור תחילתה של חופשת הקיץ.",
    ],
)


def table_shape(path: Path):
    """מחזיר לכל שורה: (רוחב, span, סגנון, טקסט) לכל תא."""
    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    tbl = root.find(f"{W}body/{W}tbl")
    rows = []
    for tr in tbl.findall(f"{W}tr"):
        cells = []
        for tc in tr.findall(f"{W}tc"):
            pr = tc.find(f"{W}tcPr")
            w = pr.find(f"{W}tcW").get(f"{W}w")
            sp = pr.find(f"{W}gridSpan")
            sp = sp.get(f"{W}val") if sp is not None else "1"
            p = tc.find(f"{W}p")
            st = p.find(f"{W}pPr/{W}pStyle")
            st = st.get(f"{W}val") if st is not None else "-"
            cells.append((w, sp, st, "".join(p.itertext())))
        rows.append(cells)
    return rows


def main():
    out = Path("/tmp/kaytanot_rebuilt.docx")
    write_docx(BILL, REFS, SKELETON, out)

    got = table_shape(out)
    want = table_shape(ORIGINAL)

    print(f"שורות: נוצרו {len(got)}, במקור {len(want)}\n")
    ok = True
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else None
        w = want[i] if i < len(want) else None
        gs = [(c[0], c[1], c[2]) for c in g] if g else None
        ws = [(c[0], c[1], c[2]) for c in w] if w else None
        shape_match = gs == ws
        text_match = (
            g and w and [c[3].strip() for c in g] == [c[3].strip() for c in w]
        )
        flag = "OK " if shape_match and text_match else "DIFF"
        if not (shape_match and text_match):
            ok = False
        print(f"{flag} r{i}  shape={'=' if shape_match else '≠'} "
              f"text={'=' if text_match else '≠'}")
        if not shape_match:
            print(f"     got : {gs}")
            print(f"     want: {ws}")
        if g and w and not text_match:
            print(f"     got : {[c[3][:45] for c in g]}")
            print(f"     want: {[c[3][:45] for c in w]}")
    print("\nתוצאה:", "עבר" if ok else "נכשל — יש פערים לסגור")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
