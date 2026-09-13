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

import json
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
WIKITEXT_META = ROOT / "tests" / "fixtures" / "wikitext" / "kaytanot.meta.json"

REFS = {
    "kaytanot": "ס\"ח התש\"ן, עמ' 155.",
    "budget": "ס\"ח התשמ\"ח, עמ' 60.",
}


def load_before() -> LegislativeNode:
    """טוען את עץ 'לפני' האמיתי מ-fixture ויקיטקסט (task 3, ingest) -
    לא בנוי ביד, לא מהקובץ הזהב עצמו. as_of (משימה 5א) מגיע מ-
    revision_timestamp האמיתי שנשמר ב-.meta.json בזמן שליפת ה-fixture -
    לא ממציא ערך, ולא משאיר את השדה ריק כשיש לנו את הערך האמיתי."""
    text = WIKITEXT_FIXTURE.read_text(encoding="utf-8")
    meta = json.loads(WIKITEXT_META.read_text(encoding="utf-8"))
    return parse_wikitext(text, law_id="kaytanot-1990", as_of=meta["revision_timestamp"])


def build_after(before: LegislativeNode) -> tuple[LegislativeNode, list]:
    """בונה את עץ 'אחרי' כטרנספורמציה מפורשת ומתועדת על ה'לפני' האמיתי
    (ולא ככתיבה עצמאית של עץ שלם - זה היה מחזיר את בעיית המעגליות).
    שלושה שינויים: שתי הגדרות חדשות בסעיף 1 (בשתי נקודות שונות ברשימה),
    ותוספת מילים בתוך הפסקה הקיימת של סעיף 2. footnotes=[(...)] בהגדרה
    החדשה השנייה מסמן היכן הערת השוליים החיצונית נכנסת - כאנוטציה
    נפרדת, לא כסמן מוטבע בתוך .text (ראו transform.py)."""
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
                    'התקציב, התשמ"ה–1985'
                    '; מבחנים לצורך תמיכה של משרד החינוך בתנועות נוער לפי חוק '
                    'יסודות התקציב, התשמ"ה-1985; מבחנים נוספים לחלוקת כספים '
                    'לצורך תמיכה של משרד החינוך, התרבות והספורט במוסדות ציבור '
                    'לפי חוק יסודות התקציב, התשמ"ה-1985'
                ),
            ),
            # העוגן משתמש ב-en dash (–), ולכן ייחודי מול שני האזכורים
            # החוזרים של אותה שנה עם מקף רגיל (-) בהמשך אותו טקסט.
            footnotes=[('התשמ"ה–1985', "budget")],
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
_AFTER, _ANNOTATIONS = build_after(_BEFORE)

BILL = Bill(
    knesset="הכנסת העשרים וחמש",
    title='הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון – הגדרת קייטנה מפוקחת), התש"ף–2023',
    initiator="יעקב אשר",
    bill_number="פ/?????????",
    submitted_date="????????????????????????",
    lines=amend(_BEFORE, _AFTER, _ANNOTATIONS, law_footnote_key="kaytanot"),
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


def _known_source_typo_correction(rows):
    """מתקנת שגיאת הקלדה **מתועדת** אחת בקובץ המקור, לא סטייה כללית
    ממנו: golden-kaytanot.docx כותב את שנת החוק בשורה הראשונה של
    הטבלה עם מקף רגיל ('התש"ן-1990'), בעוד ששלושה אזכורים עצמאיים
    אחרים של שנה עברית באותו מסמך (כותרת ההצעה, דברי ההסבר, שמזכירים
    את אותה שנה 1990 בנפרד) משתמשים ב-en-dash. הוכרע במשימה 6א (ראו
    docs/drafting-rules.md §5.7) שזו שגיאת הקלדה חד-פעמית במקור, לא
    מוסכמה - engine.py לא משחזר אותה יותר. כדי שמבחן הזהב הזה ימשיך
    להשוות תוכן אמיתי (לא רק "עבר תמיד"), אנחנו מתקנים את ה-*ציפייה*
    בנקודה המתועדת הזו בלבד, ולא בשום מקום אחר - כל סטייה נוספת
    מ-ORIGINAL עדיין תיכשל כרגיל."""
    fixed = []
    for row in rows:
        fixed.append(
            [
                (w, sp, st, text.replace('התש"ן-1990', 'התש"ן–1990'))
                for (w, sp, st, text) in row
            ]
        )
    return fixed


def _known_missing_first_number_correction(rows):
    """מתקנת פער **מתועד** נוסף במקור, לא סטייה כללית: golden-kaytanot.docx
    משאיר את הוראת התיקון הראשונה (סעיף 1, שורה 0) בלי מספר סידורי
    בכלל בעמודת המספור (תא 1 בשורה), בעוד שהוראות ההמשך ממוספרות
    כרגיל ("2.", "3."...). הוכח שגוי מול reference/skeleton-pshia.docx -
    הצעה פרטית טרומית *אמיתית* שאומתה מול ה-API של הכנסת (BillID
    2233987) - שם הוראת התיקון הראשונה ממוספרת "1." בדיוק כמו כל
    הוראה אחרת. אושר גם ישירות על ידי המשתמש, שמכיר את התהליך בפועל.
    golden-kaytanot.docx כנראה הוקלד ידנית עם השמטה זו - לא תבנית
    מכוונת. engine.py תוקן (2026-09) למספר תמיד מ-1; מתקנים כאן את
    ה-*ציפייה* בנקודה המתועדת הזו בלבד."""
    fixed = []
    for i, row in enumerate(rows):
        if i == 0 and len(row) > 1:
            w, sp, st, text = row[1]
            row = [row[0], (w, sp, st, "1.")] + list(row[2:])
        fixed.append(row)
    return fixed


def main():
    out = Path("/tmp/kaytanot_rebuilt.docx")
    write_docx(BILL, REFS, SKELETON, out)

    got = table_shape(out)
    want = _known_missing_first_number_correction(
        _known_source_typo_correction(table_shape(ORIGINAL))
    )

    print(f"שורות: נוצרו {len(got)}, במקור {len(want)}\n")
    print("(השוואה מול ORIGINAL עם שני תיקונים מתועדים - ראו _known_source_typo_correction "
          "ו-_known_missing_first_number_correction)\n")
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
