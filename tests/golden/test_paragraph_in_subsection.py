"""מקרה זהב: הוספת פסקה **בתוך סעיף קטן קיים** - משימה 58.

עד למשימה הזו הדפוס הזה לא נתמך בכלל בשלוש שכבות נפרדות:
`transform.InsertAfter` חיפש את העוגן רק בין הילדים הישירים של הסעיף
(ולכן זרק ValueError על פסקה שיושבת בתוך סעיף קטן), `insert_preview`
חסם אותו במפורש ב-reason, ו-`engine.amend()` לא ידע לכתוב את המכולה
בכתובת ההוראה.

**הבדיקה היא על הניסוח המלא של ההוראה, לא רק על מיקום הצומת בעץ** -
זו הדרישה המפורשת של המשימה. צומת שנכנס למקום הנכון אבל מנוסח
"בסעיף 18" במקום "בסעיף 18(א)" הוא עדיין הוראת תיקון שגויה.

**החוק:** `tests/fixtures/wikitext/maavak-birgunei-plisha.wikitext` -
חוק מאבק בארגוני פשיעה, התשס"ג–2003. חוק אמיתי מ-he.wikisource.org,
לא מומצא, ורץ אופליין. סעיף 18 יושב **בתוך פרק ה'** (לא ילד ישיר של
שורש החוק), כך שהמקרה מכסה גם את איתור הסעיף הרקורסיבי.

**הניסוח הצפוי** נגזר מהכלל שנמדד ב-docs/drafting-rules.md §8.7 מול
40 הצעות אמיתיות, ולא מניחוש:

- **מכולה** - השינוי קורה *בתוך* סעיף קטן (א), ולכן (א) נכתב בסוגריים
  על מספר הסעיף: `בסעיף 18(א)`. תואם מילה במילה ל-
  `בסעיף 17(א) לחוק העיקרי, אחרי פסקה (4) יבוא:` (13948365.docx).
- **עוגן** - פסקה (2) היא היעד, ולכן היא נכתבת במילים אחרי הפסיק
  ו*אינה* נכנסת לסוגריים (ha-hoveret-ha-sgula.pdf §7.10.6(ב), עמ' 29).
- **הוראה יחידה מתלכדת לשורה אחת** - בלי שורת פתיח עם מקף. שש שורות
  הפתיח שנמצאו ב-40 ההצעות כולן עם שתי הוראות ומעלה, ואין ולו אחת
  עם הוראה יחידה.
- **התווית (2א)** - שילוב מספר ואות להוספה באמצע, §7.10.6(ב), ובתוך
  המרכאות כי היא חלק מנוסח החוק המצוטט.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))
sys.path.insert(0, str(ROOT / "packages" / "render"))
sys.path.insert(0, str(ROOT / "packages" / "amend"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from wikitext_parser import parse_wikitext  # noqa: E402
from node import LegislativeNode  # noqa: E402
from transform import InsertAfter, apply  # noqa: E402
from engine import amend  # noqa: E402
from insert_preview import preview_insertion_label  # noqa: E402

ANCHOR_ID = "maavak-2003/פרק ה/s18/א/2"
NEW_TEXT = "בחילוט לפי סעיף 6א – הטוען לזכות ברכוש הוכיח כי פעל בתום לב;"

# בלי "(להלן – החוק העיקרי)": הקיצור נועד לחסוך חזרה על שם החוק,
# ולכן מוגדר רק כשיש יותר מהוראת תיקון אחת - drafting-rules.md §5.8,
# שנמדד על 22 ההצעות המתקנות מתוך 40. כאן יש הוראה אחת בלבד.
WANT_ADDRESS = ", בסעיף 18(א), אחרי פסקה (2) יבוא:"
WANT_LAW = 'בחוק מאבק בארגוני פשיעה, התשס"ג–2003'
WANT_CONTENT = f'"(2א) {NEW_TEXT}".'


def _load() -> LegislativeNode:
    text = (ROOT / "tests/fixtures/wikitext/maavak-birgunei-plisha.wikitext").read_text(
        encoding="utf-8"
    )
    return parse_wikitext(text, law_id="maavak-2003", as_of="2026-09-02T07:30:18Z")


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    before = _load()

    # שכבה 1 - התצוגה המקדימה בממשק: המשתמש עומד על פסקה (2) בתוך
    # סעיף קטן (א) ולוחץ "הוסף פסקה". התווית שמוצגת לו לפני הלחיצה
    # חייבת להיות בדיוק זו שתיווצר אחריה.
    preview = preview_insertion_label(before, ANCHOR_ID, "paragraph")
    checks.append(("תצוגה מקדימה: נתמך", preview.supported, str(preview.reason)))
    checks.append(('תצוגה מקדימה: התווית היא "(2א)"', preview.label == "(2א)", str(preview.label)))

    # שכבה 2 - הטרנספורמציה בפועל: הצומת החדש נכנס אל **הסעיף הקטן**,
    # לא אל הסעיף. קודם למשימה 58 זה זרק ValueError.
    after, annotations = apply(
        before,
        [
            InsertAfter(
                section_number="18",
                anchor_id=ANCHOR_ID,
                new_child=LegislativeNode(
                    id="maavak-2003/פרק ה/s18/א/2א",
                    node_type="paragraph",
                    number="(2א)",
                    margin_title=None,
                    text=NEW_TEXT,
                ),
            )
        ],
    )

    def _find(node: LegislativeNode, node_id: str) -> LegislativeNode | None:
        if node.id == node_id:
            return node
        for child in node.children:
            found = _find(child, node_id)
            if found is not None:
                return found
        return None

    subsection = _find(after, "maavak-2003/פרק ה/s18/א")
    labels = [c.number for c in subsection.children] if subsection else []
    checks.append(
        (
            "הפסקה החדשה נכנסה אל תוך סעיף קטן (א), במקום הנכון",
            labels == ["(1)", "(2)", "(2א)", "(3)"],
            str(labels),
        )
    )

    # שכבה 3 - הניסוח. זו הבדיקה שהמשימה נדרשה בה: הוראה שלמה, לא
    # רק מיקום בעץ.
    lines = amend(before, after, annotations, law_footnote_key="maavak")
    checks.append(("ההוראה היא שתי שורות (מתולכדת + תוכן)", len(lines) == 2, str(len(lines))))
    if len(lines) != 2:
        # בלי המחסום הזה, רגרסיה שמחזירה רשימה ריקה (בדיוק הפער
        # שהמשימה תיקנה - עריכה ש"מצליחה" בלי להפיק הוראה) מפילה את
        # הטסט ב-IndexError במקום לדווח מה נשבר.
        for name, passed, got in checks:
            print(("OK   " if passed else "FAIL "), name)
            if not passed:
                print(f"        got: {got}")
        print(f"\nתוצאה: נכשל — התקבלו {len(lines)} שורות, אי אפשר להמשיך לבדוק ניסוח")
        return 1

    head = lines[0]
    checks.append(('כותרת השוליים: "תיקון סעיף 18" (בלי המכולה)',
                   head.side_heading == "תיקון סעיף 18", str(head.side_heading)))
    checks.append(("מספר ההוראה: 1.", head.number == "1.", str(head.number)))
    checks.append(("שם החוק המלא בפעם הראשונה", head.text == WANT_LAW, str(head.text)))
    checks.append(
        ('הכתובת: "בסעיף 18(א), אחרי פסקה (2) יבוא:"',
         head.text_after == WANT_ADDRESS, repr(head.text_after)),
    )
    # ההוכחה הישירה שהמכולה לא נשמטה - הניסוח השגוי שהמערכת ייצרה
    # לפני התיקון, כשורה מפורשת שאסור לה לחזור.
    full = (head.text or "") + (head.text_after or "")
    checks.append(
        ('לא "בסעיף 18," בלי המכולה (הניסוח שלפני התיקון)',
         "בסעיף 18," not in full, full),
    )
    checks.append(
        ('העוגן במילים ולא בסוגריים: אין "בסעיף 18(א)(2)"',
         "18(א)(2)" not in full, full),
    )
    checks.append(
        ('הוראה יחידה: בלי "(להלן – החוק העיקרי)" (§5.8)',
         "להלן" not in full, full),
    )

    content = lines[1]
    got_content = (content.text or "") + (content.text_after or "")
    checks.append(
        ('התוכן המצוטט כולל את התווית "(2א)" בתוך המרכאות',
         got_content == WANT_CONTENT, got_content),
    )
    checks.append(
        ("provenance: שתי השורות מצביעות על העוגן",
         all(ln.source_node_id == ANCHOR_ID for ln in lines),
         str([ln.source_node_id for ln in lines])),
    )

    ok = all(passed for _, passed, _ in checks)
    for name, passed, got in checks:
        print(("OK   " if passed else "FAIL "), name)
        if not passed:
            print(f"        got: {got}")
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
