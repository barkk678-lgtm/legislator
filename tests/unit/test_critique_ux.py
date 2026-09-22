"""א3 + א7 - מה שהמשתמש רואה בבודק הניסוח. אופליין.

א3: "שורה 0" הוא אינדקס במערך פנימי. אין לו ביטוי במסמך, אי אפשר
לחפש לפיו, והוא חסר משמעות למי שכתב את ההצעה.

א7: שינויים שטרם התקבלו ב"עקוב אחר שינויים" עברו נקי - **וזה היה
מסוכן יותר מהיעדר בדיקה.** python-docx מחזיר את תוכן ה-<w:ins>
כאילו הוא חלק מהנוסח ומשמיט את ה-<w:del> כאילו כבר בוצע, כלומר
המסמך נקרא בדיוק כאילו כל השינויים אושרו.
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "validate"))
sys.path.insert(0, str(ROOT / "packages" / "render"))
sys.path.insert(0, str(ROOT / "packages" / "documents"))

from extract_docx import find_tracked_changes  # noqa: E402
from render_bill import Bill, Line  # noqa: E402
from validator import locate  # noqa: E402

BILL = Bill(
    knesset="הכנסת העשרים וחמש", title="הצעת חוק כלשהי", initiator="פלוני",
    lines=[
        Line(text="בחוק לימוד חובה, בסעיף 1 –", number="1.", depth=0),
        Line(text="במקום ההגדרה יבוא", marker="(1)", depth=1),
        Line(text="אחרי סעיף קטן (א) יבוא", marker="(2)", depth=1),
        Line(text="תחילתו של חוק זה...", number="2.", depth=0),
    ],
)


def test_first_section_opening_is_the_rishe():
    assert locate(BILL, 0) == "ברישה של סעיף 1"


def test_marker_line_is_reported_with_its_marker():
    assert locate(BILL, 1) == "בסעיף 1(1)"
    assert locate(BILL, 2) == "בסעיף 1(2)"


def test_section_number_advances():
    assert locate(BILL, 3) == "ברישה של סעיף 2"


def test_before_any_section_is_the_title():
    b = Bill(knesset="", title="ת", initiator="", lines=[Line(text="שם ההצעה", depth=0)])
    assert locate(b, 0) == "בכותרת"


def test_out_of_range_says_so_instead_of_crashing():
    assert "לא מזוהה" in locate(BILL, 99)


def _docx_with(extra_xml, dest):
    src = ROOT / "reference" / "skeleton-pshia.docx"
    with zipfile.ZipFile(src) as z:
        names, data = z.namelist(), {n: z.read(n) for n in z.namelist()}
    xml = data["word/document.xml"].decode("utf-8").replace("</w:body>", extra_xml + "</w:body>", 1)
    data["word/document.xml"] = xml.encode("utf-8")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.writestr(n, data[n])
    return dest


def test_clean_document_reports_nothing():
    assert find_tracked_changes(str(ROOT / "reference" / "skeleton-pshia.docx")) == {}


def test_unaccepted_insertion_and_deletion_are_both_found(tmp=Path("/tmp")):
    dest = tmp / "_tc_test.docx"
    _docx_with(
        '<w:p><w:ins w:id="9" w:author="a" w:date="2026-01-01T00:00:00Z">'
        '<w:r><w:t>נוסף</w:t></w:r></w:ins>'
        '<w:del w:id="10" w:author="a" w:date="2026-01-01T00:00:00Z">'
        '<w:r><w:delText>נמחק</w:delText></w:r></w:del></w:p>', dest)
    found = find_tracked_changes(str(dest))
    assert found.get("total") == 2, found
    assert found["by_kind"] == {"הוספות": 1, "מחיקות": 1}, found
    dest.unlink()


def test_moves_are_found_too():
    dest = Path("/tmp/_tc_move.docx")
    _docx_with(
        '<w:p><w:moveFrom w:id="11" w:author="a" w:date="2026-01-01T00:00:00Z">'
        '<w:r><w:t>הועבר</w:t></w:r></w:moveFrom></w:p>', dest)
    found = find_tracked_changes(str(dest))
    assert found.get("total") == 1, found
    assert "העברות (מקור)" in found["by_kind"], found
    dest.unlink()


def test_unreadable_file_is_unknown_not_clean():
    """**"לא הצלחתי לבדוק" אינו "אין שינויים".** קובץ פגום שמחזיר
    {} היה נראה בדיוק כמו מסמך נקי."""
    bad = Path("/tmp/_tc_bad.docx")
    bad.write_bytes(b"not a zip at all")
    assert find_tracked_changes(str(bad)) == {"unknown": True}
    bad.unlink()


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_critique_ux: כל הבדיקות עברו")
