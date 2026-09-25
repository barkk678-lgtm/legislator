"""קובץ הוורד של שאילתה - במבנה של שאילתה אמיתית של הכנסת (ש1, 25.9.2026).

**הבסיס הוא שאילתה אמיתית** (reference/query-template.docx, נבנה ב-
tools/build_query_template.py מ-reference/sheiltot/25_pq_5753896.docx).
הסגנונות, המספור, הגופנים וסמל המדינה מגיעים ממנה כמות שהם; כאן נכתב
רק הגוף, **באותן תבניות XML בדיוק** כמו בשש הדוגמאות של הכנסת ה-25
(נבדקו כולן, ברמת ה-XML):

| שורה | סגנון | מה רואים |
|---|---|---|
| "הכנסת" | caption (מהתבנית) | ממורכז, בולד, 14, כחול כהה |
| "שאילתה" / "שאילתה דחופה" | heading 1 | ממורכז, בולד, 14, David |
| הנושא | heading 2 | ממורכז, 14, David, **קו תחתון** |
| "חבר הכנסת X שאל את Y" | Normal | **כל השורה בקו תחתון**, 12, David |
| הרקע | Normal | 12, ריווח 1.5 |
| "רצוני לשאול:" | heading 3 | **36pt לפניו** |
| השאלות | Normal | **מספור אוטומטי של וורד** ("1."), ריווח 1.5 |

**עברית נכתבת ב-David:** Tahoma בדוגמאות הוא הגופן הלטיני בלבד
(`w:ascii`), והעברית מוצגת לפי `w:cs="David"`.

**מה לא נכנס - הכנסת מוסיפה אחרי ההגשה:** המספר הסידורי ("4822."),
שורת התאריך העברי, ו"מועד אחרון למתן תשובה". שלושתם יושבים בדוגמאות
בסימניות שהמערכת של הכנסת ממלאת (QUR_Num, QUR_Create_Date,
QUR_Reply_Date).
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

TEMPLATE = Path(__file__).resolve().parents[2] / "reference" / "query-template.docx"
RETSONI = "רצוני לשאול:"

_RPR = ('<w:rPr><w:rFonts w:hint="cs" w:ascii="Tahoma" w:hAnsi="Tahoma" w:cs="David"/>'
        '<w:rtl/></w:rPr>')
_PPR_RPR = '<w:rPr><w:rFonts w:ascii="Tahoma" w:hAnsi="Tahoma" w:cs="David"/><w:rtl/></w:rPr>'
_LINE15 = '<w:spacing w:line="360" w:lineRule="auto"/>'
# מספור שהמודל כתב בעצמו ("1.", "2)", "א.") - וורד ממספר לבד.
_LEADING_NUMBER = re.compile(r"^\s*(?:\d{1,2}|[א-י])\s*[.)\-–]\s+")


def _t(text: str) -> str:
    from render_bill import xml_safe  # noqa: PLC0415 - אותו סינון תווים (ח8)
    return f'<w:t xml:space="preserve">{escape(xml_safe(text))}</w:t>'


def _heading(style: str, runs: str, extra_ppr: str = "") -> str:
    return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{extra_ppr}<w:rPr><w:rtl/></w:rPr></w:pPr>'
            f"{runs}</w:p>")


def _hrun(text: str, *, underline: bool = False) -> str:
    u = '<w:u w:val="single"/>' if underline else ""
    return f'<w:r><w:rPr><w:rFonts w:hint="cs"/>{u}<w:rtl/></w:rPr>{_t(text)}</w:r>'


def _para(text: str = "", *, spacing: str = _LINE15, numbered: bool = False) -> str:
    num = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="3"/></w:numPr>' if numbered else ""
    run = f"<w:r>{_RPR}{_t(text)}</w:r>" if text else ""
    return f"<w:p><w:pPr>{num}{spacing}{_PPR_RPR}</w:pPr>{run}</w:p>"


def asker_line(mk_name: str, minister: str, gender: str | None) -> str:
    """"חבר הכנסת X שאל את Y". **המגדר מהמאגר של הכנסת, לא מהשם** -
    ובלעדיו הצורה הכפולה, לא ניחוש."""
    if gender == "נקבה":
        who, asked = "חברת הכנסת", "שאלה"
    elif gender == "זכר":
        who, asked = "חבר הכנסת", "שאל"
    else:
        who, asked = "חבר/ת הכנסת", "שאל/ה"
    return f"{who} {mk_name.strip()} {asked} את {minister.strip()}"


def split_body(body: str) -> tuple[list[str], list[str]]:
    """(פסקאות הרקע, השאלות). השאלות מתחילות אחרי "רצוני לשאול:"."""
    lines = [ln.strip() for ln in (body or "").split("\n") if ln.strip()]
    if RETSONI not in lines:
        return lines, []
    i = lines.index(RETSONI)
    return lines[:i], [_LEADING_NUMBER.sub("", q) for q in lines[i + 1:]]


def query_body_xml(*, kind: str, subject: str, asker: str, body: str) -> str:
    background, questions = split_body(body)
    kind_word = "" if kind == "רגילה" else kind
    parts = [
        _heading("Heading1", _hrun("שאילתה ") + _hrun(kind_word or " ")),
        _heading("Heading2", _hrun(subject.strip(), underline=True)),
        '<w:p><w:pPr><w:rPr><w:rFonts w:cs="David"/><w:rtl/></w:rPr></w:pPr></w:p>',
        ('<w:p><w:pPr><w:rPr><w:rFonts w:ascii="Tahoma" w:hAnsi="Tahoma" w:cs="David"/>'
         '<w:u w:val="single"/><w:rtl/></w:rPr></w:pPr>'
         '<w:r><w:rPr><w:rFonts w:hint="cs" w:ascii="Tahoma" w:hAnsi="Tahoma" w:cs="David"/>'
         f'<w:u w:val="single"/><w:rtl/></w:rPr>{_t(asker)}</w:r></w:p>'),
        _para(),
        *(_para(b) for b in background),
    ]
    if questions:
        parts.append(_heading("Heading3", _hrun(RETSONI), '<w:spacing w:before="720"/>'))
        parts.extend(_para(q, numbered=True) for q in questions)
    return "".join(parts)


def write_query_docx_knesset(*, kind: str, subject: str, asker: str, body: str,
                             out: Path, template: Path = TEMPLATE) -> Path:
    src = zipfile.ZipFile(template)
    doc = src.read("word/document.xml").decode("utf-8")
    # הפתיח (סמל המדינה, "הכנסת", שורות הרווח) נשאר מהתבנית כמות שהוא;
    # מ-heading 1 ועד סוף הגוף - נכתב מחדש.
    h1 = doc.index('<w:pStyle w:val="Heading1"')
    head_end = doc.rindex("<w:p ", 0, h1)
    tail_start = doc.index("<w:sectPr")
    new_doc = doc[:head_end] + query_body_xml(kind=kind, subject=subject, asker=asker,
                                              body=body) + doc[tail_start:]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            data = new_doc.encode("utf-8") if item.filename == "word/document.xml" \
                else src.read(item.filename)
            z.writestr(item.filename, data)
    return out
