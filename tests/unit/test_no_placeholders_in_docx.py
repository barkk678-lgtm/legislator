"""ח16 (26.9.2026) - "פנימי ...." בקובץ ה-Word של הצעת החוק.

שוחזר מהקובץ שהמערכת ייצאה לברק (reference/law-2000037-הצעת-חוק (2).docx):
השורה הראשונה בקובץ היא `מספר פנימי: ????????`. **לא שארית של תבנית
ויקיטקסט** (החשד בתוכנית) - זו שורת הכותרת של render_bill, שמעתיקה את השלד
של הצעה אמיתית (skeleton-pshia.docx: `מספר פנימי: 2233987`). את המספר הפנימי
הכנסת נותנת; אצלנו הוא תמיד placeholder. כמו בשאילתות (ש1, הכרעת ברק 26.9 -
מה שהכנסת ממלאת, משמיטים), השורה יורדת כשאין מספר אמיתי.
"""

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "render"))

from render_bill import Bill, Line, write_docx  # noqa: E402


def _document_text(bill: Bill) -> str:
    out = ROOT / "tests" / "_placeholders.docx"
    try:
        write_docx(bill, {}, ROOT / "reference" / "skeleton-pshia.docx", out)
        with zipfile.ZipFile(io.BytesIO(out.read_bytes())) as z:
            import re
            xml = z.read("word/document.xml").decode("utf-8")
            return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))
    finally:
        out.unlink(missing_ok=True)


def _bill(**kw) -> Bill:
    return Bill(knesset="הכנסת העשרים וחמש", title='הצעת חוק לבדיקה, התשפ"ו–2026', initiator="",
                lines=[Line(text="בחוק לבדיקה, בסעיף 2, במקום \"א\" יבוא \"ב\".", number="1.",
                            side_heading="תיקון סעיף 2")],
                explanatory=["מוצע לתקן."], **kw)


def test_no_internal_number_placeholder():
    text = _document_text(_bill())
    assert "פנימי" not in text, text[:120]
    assert "????????" not in text.replace("פ/?????????", ""), text[:160]


def test_real_internal_number_is_kept():
    """מספר אמיתי (הצעה שהועלתה מקובץ) - נשאר, כמו בשלד."""
    text = _document_text(_bill(internal_number="2233987"))
    assert "מספר פנימי: 2233987" in text, text[:120]


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_no_placeholders_in_docx: כל הבדיקות עברו")
