"""מסמך RTL פשוט (כותרת + פסקאות רגילות) - למסמכים שאינם הצעת חוק:
שאילתה (משימה ו), הצעה לסדר (משימה ז). **אותה טכניקה בדיוק** כמו
render_bill.write_docx - לא בונים docx מאפס ולא מוסיפים תלות
python-docx חדשה (לא זמינה בסביבה, ועקבי עם "אל תוסיף תלויות").
לוקחים את אותו skeleton (reference/skeleton-pshia.docx), מחליפים
רק את word/document.xml (בלי טבלה הפעם - פסקאות פשוטות), שומרים כל
שאר חלקי החבילה (styles/footers/rels) בדיוק כמו שהם - אותה ערובה
לתקינות שכבר קיימת ומוכחת ב-render_bill.

משתמשת בסגנון הפסקה "David" (כבר קיים ומוגדר ב-skeleton - משמש שם
לשורות מידע רגילות כמו "יוזם:"/מספר ההצעה, לא רק לטבלת הסעיפים) -
לא ממציאה pStyle חדש שאולי לא מוגדר.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)

_SECT = (
    '<w:sectPr><w:footerReference w:type="even" r:id="rId11"/>'
    '<w:footerReference w:type="default" r:id="rId12"/>'
    '<w:pgSz w:w="11907" w:h="16840" w:code="9"/>'
    '<w:pgMar w:top="1701" w:right="1134" w:bottom="1417" w:left="1134"'
    ' w:header="680" w:footer="680" w:gutter="0"/>'
    '<w:cols w:space="720"/><w:noEndnote/><w:titlePg/><w:bidi/><w:rtlGutter/>'
    '<w:docGrid w:linePitch="326"/></w:sectPr>'
)


def _t(text: str) -> str:
    return f'<w:t xml:space="preserve">{escape(text)}</w:t>'


def _run(text: str, *, bold: bool = False) -> str:
    if not text:
        return ""
    b = "<w:b/>" if bold else ""
    return f'<w:r><w:rPr><w:rFonts w:hint="cs"/>{b}<w:rtl/></w:rPr>{_t(text)}</w:r>'


def _para(text: str, *, bold: bool = False, centered: bool = False) -> str:
    jc = '<w:jc w:val="center"/>' if centered else ""
    return f'<w:p><w:pPr><w:pStyle w:val="David"/><w:bidi/>{jc}</w:pPr>{_run(text, bold=bold)}</w:p>'


def render_document(*, title: str, meta_lines: list[str], paragraphs: list[str]) -> str:
    """title: כותרת ראשית (מודגשת, ממורכזת). meta_lines: שורות מידע
    לפני הגוף (למשל 'נושא: ...', 'אל: ...', 'מאת: ...'). paragraphs:
    גוף המסמך, פסקה לכל איבר."""
    body = (
        _para(title, bold=True, centered=True)
        + _para("")
        + "".join(_para(line, bold=True) for line in meta_lines)
        + _para("")
        + "".join(_para(p) for p in paragraphs)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {NS}><w:body>{body}{_SECT}</w:body></w:document>"
    )


def write_simple_docx(
    *, title: str, meta_lines: list[str], paragraphs: list[str], skeleton: Path, out: Path
) -> Path:
    # footnotes.xml נשאר כפי שהוא מה-skeleton, בלי שינוי - document.xml
    # החדש לא מכיל אף <w:footnoteReference>, כך שתוכנו לא מוצג/רלוונטי,
    # אבל document.xml.rels עדיין מצביע אליו (כמו בכל קובץ מה-skeleton) -
    # להסיר את החלק הזה בלי לגעת גם ב-rels היה משאיר relationship-target
    # חסר, שזה בדיוק סוג הקובץ ש-Word מסמן כ"פגום, נדרש תיקון".
    doc_xml = render_document(title=title, meta_lines=meta_lines, paragraphs=paragraphs).encode("utf-8")
    with zipfile.ZipFile(skeleton) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = doc_xml if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, data)
    return out
