"""בודק ש-_render_insertion מעגן עוגן ממוספר (סעיף קטן/פסקה) לפי
תוויתו ולא לפי ציטוט טקסטו המלא - ha-hoveret-ha-sgula.pdf §7.10.6(ב),
עמ' 29: "אחרי סעיף קטן (ג) יבוא: '(ג1)...'" ו"אחרי פסקה (2) יבוא:
'(2א)...'".

**זהו טסט לתיקון באג, לא לפיצ'ר**: עד לתיקון, _render_insertion ציטט
תמיד את טקסט העוגן המלא (f'אחרי "{phrase}" יבוא:') גם כשלעוגן היה
מספר - ניסוח שגוי. מקרה הזהב של קייטנות (test_amend_kaytanot.py) לא
תפס את זה כי שני העוגנים היחידים שם היו בלי מספר (פתיח והגדרה) - לכן
נדרש עץ סינתטי כאן, לא מבוסס על קובץ זהב אמיתי.

**עדכון:** תוויות סעיף קטן/פסקה כוללות תמיד סוגריים משלהן כחלק
מ-number (בדיוק כפי שהן מגיעות בפועל מ-wikitext_parser - הארגומנט
הגולמי בתבנית, {{ח:תת|(א)}}, כבר כולל את הסוגריים - ראו
_SUBSECTION_LABEL/_PARAGRAPH_LABEL). הפיקסצ'ר כאן משתמש בסוגריים כדי
לשקף את זה במדויק - גרסה קודמת של הטסט השתמשה בתוויות בלי סוגריים
("א"/"1"), מה שהחביא באג אמיתי (סוגריים כפולים, "((ג))") שנתפס רק
כשמשתמש אמיתי בדק את המערכת מול חוק אמיתי.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from transform import InsertAfter, apply  # noqa: E402
from engine import amend  # noqa: E402


def _law_with_section_5() -> LegislativeNode:
    subsections = [
        LegislativeNode(id="law/s5/a", node_type="subsection", number="(א)", margin_title=None, text="תוכן א."),
        LegislativeNode(id="law/s5/b", node_type="subsection", number="(ב)", margin_title=None, text="תוכן ב."),
        LegislativeNode(id="law/s5/c", node_type="subsection", number="(ג)", margin_title=None, text="תוכן ג."),
    ]
    paragraphs = [
        LegislativeNode(id="law/s6/p1", node_type="paragraph", number="(1)", margin_title=None, text="פרט 1."),
        LegislativeNode(id="law/s6/p2", node_type="paragraph", number="(2)", margin_title=None, text="פרט 2."),
    ]
    section5 = LegislativeNode(
        id="law/s5", node_type="section", number="5", margin_title="כותרת 5", text="", children=subsections
    )
    section6 = LegislativeNode(
        id="law/s6", node_type="section", number="6", margin_title="כותרת 6", text="", children=paragraphs
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, full_title="חוק לדוגמה, התש\"ף–2020",
        children=[section5, section6],
    )



def _anchor_phrase(line):
    """מחלצת את ניסוח העוגן מתוך שורה מלאה, בלי תלות בשאלה אם ההוראה
    התלכדה לשורה אחת עם כתובת הסעיף או קיבלה שורת פתיח נפרדת."""
    full = (line.text or "") + (line.text_after or "")
    idx = full.find("אחרי ")
    return full[idx:] if idx != -1 else None


def main():
    ok = True
    before = _law_with_section_5()

    # מקרה 1: הוספה אחרי סעיף קטן (ב) - עוגן ממוספר, לא הילד האחרון
    # (ג נשאר אחריו) - כדי שהענף הרלוונטי (עוגן עם phrase, לא "בסופו
    # יבוא") אכן ירוץ.
    after, annotations = apply(before, [
        InsertAfter(
            section_number="5",
            anchor_id="law/s5/b",
            new_child=LegislativeNode(
                id="law/s5/b1", node_type="subsection", number="(ב1)",
                margin_title=None, text="תוכן חדש.",
            ),
        ),
    ])
    lines = amend(before, after, annotations, law_footnote_key="fake")
    # הוראה יחידה מתלכדת לשורה אחת עם כתובת הסעיף (משימה 58) -
    # "בסעיף 5 לחוק העיקרי, אחרי סעיף קטן (ב) יבוא:". הטסט בודק את
    # **ניסוח העוגן**, ולכן מחפש את הביטוי בתוך השורה המלאה ולא
    # כשורה שמתחילה בו.
    phrase_lines = [p for p in (_anchor_phrase(x) for x in lines) if p]
    got = phrase_lines[0] if phrase_lines else None
    want = "אחרי סעיף קטן (ב) יבוא:"
    passed = got == want
    ok = ok and passed
    print(("OK  " if passed else "FAIL"), "עוגן ממוספר - סעיף קטן (ב)", "" if passed else f"-> {got!r}")

    # התווית של הסעיף הקטן החדש עצמו ("(ב1)") צריכה להופיע בתוך התוכן
    # המצוטט - "(ב1) תוכן חדש.";" - לא רק "תוכן חדש." בלי תווית.
    content_lines = [line.text for line in lines if line.style == "TableBlockOutdent"]
    got_content = content_lines[0] if content_lines else None
    want_content = '"(ב1) תוכן חדש.".'
    passed_content = got_content == want_content
    ok = ok and passed_content
    print(("OK  " if passed_content else "FAIL"), "תווית הסעיף הקטן החדש מופיעה בתוכן המצוטט",
          "" if passed_content else f"-> {got_content!r}")

    # מקרה 2: הוספה אחרי פסקה (1) - עוגן ממוספר, לא הילד האחרון (2
    # נשאר אחריו).
    after2, annotations2 = apply(before, [
        InsertAfter(
            section_number="6",
            anchor_id="law/s6/p1",
            new_child=LegislativeNode(
                id="law/s6/p1a", node_type="paragraph", number="(1א)",
                margin_title=None, text="תוכן חדש.",
            ),
        ),
    ])
    lines2 = amend(before, after2, annotations2, law_footnote_key="fake")
    # הוראה יחידה מתלכדת לשורה אחת עם כתובת הסעיף (משימה 58) -
    # "בסעיף 5 לחוק העיקרי, אחרי סעיף קטן (ב) יבוא:". הטסט בודק את
    # **ניסוח העוגן**, ולכן מחפש את הביטוי בתוך השורה המלאה ולא
    # כשורה שמתחילה בו.
    phrase_lines2 = [p for p in (_anchor_phrase(x) for x in lines2) if p]
    got2 = phrase_lines2[0] if phrase_lines2 else None
    want2 = "אחרי פסקה (1) יבוא:"
    passed2 = got2 == want2
    ok = ok and passed2
    print(("OK  " if passed2 else "FAIL"), "עוגן ממוספר - פסקה (1)", "" if passed2 else f"-> {got2!r}")

    content_lines2 = [line.text for line in lines2 if line.style == "TableBlockOutdent"]
    got_content2 = content_lines2[0] if content_lines2 else None
    want_content2 = '"(1א) תוכן חדש.".'
    passed_content2 = got_content2 == want_content2
    ok = ok and passed_content2
    print(("OK  " if passed_content2 else "FAIL"), "תווית הפסקה החדשה מופיעה בתוכן המצוטט",
          "" if passed_content2 else f"-> {got_content2!r}")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
