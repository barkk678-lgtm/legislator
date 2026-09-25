"""ס3 (26.9.2026) - קובץ Word של הצעה לסדר היום, על השלד של הדוגמה עצמה.

הדוגמאות (reference/הצעה לסדר יום (8).docx, (10).docx) הן טופס של הכנסת עם
סימניות לכל שדה: Heb_Date, Eng_Date, AGN_Num, AGN_Yor_Name, AGN_Yor_Gender,
AGN_Type, AGN_Subject, AGN_Description, PM_Gender, PM_Name. **לכן הקובץ נבנה
מהדוגמה עצמה, והקוד ממלא רק את מה שבין הסימניות** - כל השאר (סגנונות,
גופנים, גדלים, קו תחתון בנושא, יישור, ריווח, הסמל) נשאר אחד לאחד. בתוך
סימנייה נשמר ה-rPr של ה-run הראשון שבה.

- התאריך העברי, הלועזי ומספר ההצעה - **ריקים**: הכנסת מוסיפה אותם אחרי
  שההצעה מתקבלת (ברק, 26.9). הפסקאות עצמן נשארות, כדי שהפריסה לא תזוז.
- AGN_Type: "דחופה" או ריק (הצעה רגילה). **שתי הדוגמאות דחופות** - איך
  נראית רגילה לא ידוע; ההנחה כאן (בלי המילה) ממתינה לאישור ברק.
- דברי ההסבר: פסקה אחת בקובץ, והפסקאות מופרדות ב-<w:br/> - כמו בדוגמה.
- מטא-דאטה: שם היוצר והעורך האחרון של הדוגמה נמחקים.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

TEMPLATE = Path(__file__).resolve().parents[2] / "reference" / "הצעה לסדר יום (8).docx"

_W_NS = ' xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _bookmark_span(doc: str, name: str) -> tuple[int, int, str]:
    """(התחלה, סוף, rPr) של התוכן שבין bookmarkStart ל-bookmarkEnd."""
    m = re.search(rf'<w:bookmarkStart w:name="{re.escape(name)}" w:id="(\d+)" />', doc)
    if not m:
        raise ValueError(f"אין סימנייה {name} בתבנית")
    end = doc.index(f'<w:bookmarkEnd w:id="{m.group(1)}" />', m.end())
    inner = doc[m.end():end]
    rpr = re.search(r"<w:rPr[ >].*?</w:rPr>", inner, re.S)
    return m.end(), end, rpr.group(0) if rpr else ""


def _run(rpr: str, text: str) -> str:
    return f'<w:r{_W_NS}>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _fill(doc: str, name: str, text: str | list[str]) -> str:
    start, end, rpr = _bookmark_span(doc, name)
    parts = [text] if isinstance(text, str) else text
    runs = f"<w:r{_W_NS}><w:br /></w:r>".join(_run(rpr, p) for p in parts if p) if any(parts) else ""
    return doc[:start] + runs + doc[end:]


def _drop_space_before(doc: str, name: str) -> str:
    """הצעה רגילה: בלי AGN_Type נשאר "הצעה  בנושא" - הרווח שלפני הסימנייה יורד."""
    m = re.search(rf'<w:r>(?:(?!</w:r>).)*<w:t xml:space="preserve"> </w:t></w:r>(?=<w:bookmarkStart w:name="{name}")',
                  doc, re.S)
    return doc[:m.start()] + doc[m.end():] if m else doc


def salutation(gender: str | None) -> str:
    return "גבירתי היושבת ראש" if gender == "נקבה" else "אדוני היושב ראש"


def mk_title(gender: str | None) -> str:
    return {"זכר": "חבר הכנסת", "נקבה": "חברת הכנסת"}.get(gender or "", "חבר/ת הכנסת")


def agenda_body_xml(doc: str, *, kind: str, subject: str, explanation: list[str],
                    speaker_name: str, speaker_gender: str | None,
                    mk_name: str, mk_gender: str | None) -> str:
    for name in ("Heb_Date", "Eng_Date", "AGN_Num"):
        doc = _fill(doc, name, "")
    doc = _fill(doc, "AGN_Yor_Name", speaker_name)
    doc = _fill(doc, "AGN_Yor_Gender", salutation(speaker_gender))
    if kind == "דחופה":
        doc = _fill(doc, "AGN_Type", "דחופה")
    else:
        doc = _drop_space_before(_fill(doc, "AGN_Type", ""), "AGN_Type")
    doc = _fill(doc, "AGN_Subject", subject)
    doc = _fill(doc, "AGN_Description", [p.strip() for p in explanation if p.strip()])
    doc = _fill(doc, "PM_Gender", mk_title(mk_gender))
    doc = _fill(doc, "PM_Name", mk_name)
    return doc


def _clean_core(xml: str) -> str:
    xml = re.sub(r"<dc:creator>.*?</dc:creator>", "<dc:creator></dc:creator>", xml)
    return re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy></cp:lastModifiedBy>", xml)


def write_agenda_docx(*, out: Path, template: Path = TEMPLATE, **fields) -> Path:
    src = zipfile.ZipFile(template)
    doc = agenda_body_xml(src.read("word/document.xml").decode("utf-8"), **fields)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            if item.filename.startswith("[trash]/"):
                continue      # שאריות ש-Word השאיר בדוגמה; שום חלק לא מפנה אליהן
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                data = doc.encode("utf-8")
            elif item.filename == "docProps/core.xml":
                data = _clean_core(data.decode("utf-8")).encode("utf-8")
            z.writestr(item, data)
    return out
