"""
מקרה זהב: שחזור הצעת חוק הקייטנות מתוך ייצוג מובנה.

המבחן: הטקסט של כל שורה בטבלה, וסגנון כל תא, זהים למקור.
זו נקודת הקבלה של משימה 5 בתוכנית העבודה.

lines= נבנה כאן על ידי מנוע ה-amend (משימה 4), לא כרשימה מקודדת ביד:
טעון "לפני" אמיתי מ-ingest (משימה 3), בונה "אחרי" כטרנספורמציה מפורשת
עליו (packages/amend/transform.apply), ומריץ diff (packages/amend/engine.amend).
tests/unit/test_amend_kaytanot.py משווה את פלט amend() ישירות מול
BILL.lines - זו הבדיקה שסוגרת את הלולאה, לפני שהרנדור בכלל נכנס לתמונה.
"""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from render_bill import Bill, Line, write_docx  # noqa: E402
from node import LegislativeNode  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402
from transform import InsertAfter, InsertWordsAfter, apply  # noqa: E402
from engine import amend  # noqa: E402

from lxml import etree  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "reference" / "golden-kaytanot.docx"
SKELETON = ROOT / "reference" / "skeleton-pshia.docx"
WIKITEXT_FIXTURE = ROOT / "tests" / "fixtures" / "wikitext" / "kaytanot.wikitext"

REFS = {
    "kaytanot": "ס\"ח התש\"ן, עמ' 155.",
    "budget": "ס\"ח התשמ\"ח, עמ' 60.",
}


def load_before() -> LegislativeNode:
    """טוען את עץ 'לפני' האמיתי מ-fixture ויקיטקסט (task 3, ingest) -
    לא בנוי ביד, לא מהקובץ הזהב עצמו."""
    text = WIKITEXT_FIXTURE.read_text(encoding="utf-8")
    return parse_wikitext(text, law_id="kaytanot-1990")


def build_after(before: LegislativeNode) -> LegislativeNode:
    """בונה את עץ 'אחרי' כטרנספורמציה מפורשת ומתועדת על ה'לפני' האמיתי
    (ולא ככתיבה עצמאית של עץ שלם - זה היה מחזיר את בעיית המעגליות).
    שלושה שינויים: שתי הגדרות חדשות בסעיף 1 (בשתי נקודות שונות ברשימה),
    ותוספת מילים בתוך הפסקה הקיימת של סעיף 2. ⟦footnote:budget⟧ מסמן
    איפה הערת השוליים החיצונית נכנסת בתוך ההגדרה החדשה השנייה."""
    transformations = [
        InsertAfter(
            section_number="1",
            anchor_id="kaytanot-1990/s1/p0",  # "בחוק זה –"
            new_child=LegislativeNode(
                id="kaytanot-1990/s1/new-organization",
                node_type="definition",
                number="",
                margin_title=None,
                text=(
                    '"ארגון נוער או תנועת נוער" – ארגון או תנועה או חוגי סיור '
                    "הנתמכים על ידי משרד החינוך לפי מבחנים לצורך תמיכה;"
                ),
            ),
        ),
        InsertAfter(
            section_number="1",
            anchor_id="kaytanot-1990/s1/p2",  # ההגדרה "ילד"
            new_child=LegislativeNode(
                id="kaytanot-1990/s1/new-standards",
                node_type="definition",
                number="",
                margin_title=None,
                text=(
                    '"מבחנים לצורך תמיכה" – מבחנים לצורך תמיכה של משרד חינוך '
                    "בפעילות ארגוני ילדים ונוער במוסדות ציבור לפי חוק יסודות "
                    'התקציב, התשמ"ה–1985⟦footnote:budget⟧'
                    '; מבחנים לצורך תמיכה של משרד החינוך בתנועות נוער לפי חוק '
                    'יסודות התקציב, התשמ"ה-1985; מבחנים נוספים לחלוקת כספים '
                    'לצורך תמיכה של משרד החינוך, התרבות והספורט במוסדות ציבור '
                    'לפי חוק יסודות התקציב, התשמ"ה-1985'
                ),
            ),
        ),
        InsertAfter(
            section_number="1",
            anchor_id="kaytanot-1990/s1/p4",  # ההגדרה "השר" - האחרונה
            new_child=LegislativeNode(
                id="kaytanot-1990/s1/new-supervised",
                node_type="definition",
                number="",
                margin_title=None,
                text='"קייטנה מפוקחת" – פעילות קיץ שמנהל ארגון נוער או תנועת נוער.',
            ),
        ),
        InsertWordsAfter(
            target_id="kaytanot-1990/s2/p0",
            anchor_substring="לא ינהל אדם קייטנה",
            inserted_text=" שאינה קייטנה מפוקחת",
        ),
    ]
    return apply(before, transformations)


_BEFORE = load_before()
_AFTER = build_after(_BEFORE)

BILL = Bill(
    knesset="הכנסת העשרים וחמש",
    title='הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון – הגדרת קייטנה מפוקחת), התש"ף–2023',
    initiator="יעקב אשר",
    bill_number="פ/?????????",
    submitted_date="????????????????????????",
    lines=amend(_BEFORE, _AFTER, law_footnote_key="kaytanot"),
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
