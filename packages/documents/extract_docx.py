"""חילוץ הצעת חוק מקובץ Word (משימה 2.1, שלב א).

**זו הפעולה ההפוכה של `packages/render/render_bill.py`.** התבנית של
הכנסת מקודדת את מבנה ההצעה בטבלה בת 8 עמודות, לא בפסקאות
(`docs/template-spec.md` §3):

    עמודה 0  כותרת שוליים ("תיקון סעיף 1")
    עמודה 1  מספר הסעיף בהצעה ("1.")
    עמודות 2-6  חמש רמות הזחה
    עמודה 7  תוכן ברמה העמוקה ביותר

**עומק ההזחה = אינדקס העמודה הראשונה שיש בה תוכן, פחות 2.** הרינדור
בונה את זה עם `gridSpan = 6 - d`; החילוץ קורא את זה בחזרה.

**מלכודת של python-docx:** תא ממוזג חוזר על עצמו בכל העמודות שהוא
משתרע עליהן. טקסט שמופיע שש פעמים ברצף אינו שש שורות - הוא תא אחד
רחב. מזהים לפי זהות האובייקט (`tc`) ולא לפי השוואת מחרוזות, אחרת
שתי רמות שבמקרה נושאות אותו טקסט היו מתמזגות בטעות.

הפסקאות שמחוץ לטבלה נושאות **סגנונות בעלי שם** שמקודדים את
תפקידן (`Head HatzaotHok`, `Head DivreiHesber`, `Hesber`) - עדיף
בהרבה על ניחוש לפי תוכן, ולכן זה מה שמשמש לזיהוי.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_STYLE_TITLE = "Head HatzaotHok"
_STYLE_EXPLANATORY_HEAD = "Head DivreiHesber"
_STYLE_EXPLANATORY = "Hesber"

_SIDE_COL = 0
_NUMBER_COL = 1
_FIRST_DEPTH_COL = 2
_MAX_DEPTH = 5

_INTERNAL_RE = re.compile(r"מספר\s+פנימי:\s*(\S+)")
_BILL_NUMBER_RE = re.compile(r"(פ/\S+)")
_INITIATOR_RE = re.compile(r"יוזם:\s*(.*)")
_MARKER_RE = re.compile(r"^(\([^)]{1,4}\))\s*\t?\s*")


class DocumentExtractError(Exception):
    """הקובץ אינו הצעת חוק בתבנית המוכרת."""


@dataclass
class ExtractedLine:
    text: str = ""
    depth: int = 0
    side_heading: str = ""
    number: str = ""
    marker: str = ""
    inner_heading: str = ""   # כותרת שוליים של סעיף מצוטט (דפוס ההוספה)
    inner_number: str = ""


@dataclass
class ExtractedBill:
    title: str = ""
    knesset: str = ""
    initiator: str = ""
    internal_number: str = ""
    bill_number: str = ""
    lines: list[ExtractedLine] = field(default_factory=list)
    explanatory: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _row_cells(row) -> list:
    """תאי השורה בלי חזרות של תאים ממוזגים, עם אינדקס העמודה שבה
    כל תא מתחיל. ההשוואה היא על אובייקט ה-XML ולא על הטקסט."""
    out, seen = [], set()
    for idx, c in enumerate(row.cells):
        key = id(c._tc)
        if key in seen:
            continue
        seen.add(key)
        out.append((idx, c))
    return out


def _cell_text(cell) -> str:
    parts = [p.text.strip() for p in cell.paragraphs if p.text.strip()]
    return "\n".join(parts)


_INNER_NUMBER_RE = re.compile(r"^\d+[א-ת]?\d*\.$")


def _inner_section(cells, by_col) -> tuple[str, str, str] | None:
    """(כותרת הסעיף המצוטט, מספרו, נוסחו) - או None אם אין דפוס כזה.
    הזיהוי לפי *מיקום* התאים ולא לפי תוכן: מספר סעיף בעמודה 5 שאחריו
    נוסח, כפי שהרינדור בונה."""
    starts = {idx for idx, _ in cells}
    if not {_FIRST_DEPTH_COL, 5}.issubset(starts):
        return None
    inner_number = by_col.get(5, "").strip()
    if not _INNER_NUMBER_RE.match(inner_number):
        return None
    body_col = next((i for i in (6, 7) if by_col.get(i)), None)
    if body_col is None:
        return None
    return by_col.get(_FIRST_DEPTH_COL, ""), inner_number, by_col[body_col]


def _parse_table(table, warnings: list[str]) -> list[ExtractedLine]:
    lines: list[ExtractedLine] = []
    for row in table.rows:
        cells = _row_cells(row)
        by_col = {idx: _cell_text(c) for idx, c in cells}
        side = by_col.get(_SIDE_COL, "")
        number = by_col.get(_NUMBER_COL, "")

        # דפוס "הסעיף הפנימי" (render_bill: 3 + 1 + 2): כותרת שוליים
        # של הסעיף המצוטט משתרעת על 2-4, מספרו ב-5, והנוסח ב-6.
        # בלי זיהוי מפורש שלושתם היו נקראים כשלוש שורות שטוחות, וכך
        # נאבד בדיוק את המידע שהופך "הוספת סעיף" לניתנת לעריכה.
        inner = _inner_section(cells, by_col)
        if inner is not None:
            heading, inner_number, body = inner
            lines.append(ExtractedLine(
                text=body, depth=0, side_heading=side, number=number,
                inner_heading=heading, inner_number=inner_number,
            ))
            continue

        content_col = next(
            (idx for idx, _ in cells
             if idx >= _FIRST_DEPTH_COL and by_col.get(idx)),
            None,
        )
        if content_col is None:
            if side or number:
                warnings.append(f"שורה עם כותרת/מספר ובלי תוכן: {side or number!r}")
            continue

        depth = min(content_col - _FIRST_DEPTH_COL, _MAX_DEPTH)
        text = by_col[content_col]
        marker = ""
        m = _MARKER_RE.match(text)
        if m:
            marker, text = m.group(1), text[m.end():]

        # תא תוכן רב-פסקאות הוא כמה שורות לוגיות באותה רמה.
        for i, chunk in enumerate(text.split("\n")):
            chunk = chunk.strip()
            if not chunk:
                continue
            lines.append(ExtractedLine(
                text=chunk, depth=depth,
                side_heading=side if i == 0 else "",
                number=number if i == 0 else "",
                marker=marker if i == 0 else "",
            ))
    return lines


def extract_bill(path_or_stream) -> ExtractedBill:
    """הצעת חוק מקובץ docx. לא מניחה שהמסמך תקין: מה שלא נמצא
    מדווח ב-`warnings` ולא נזרק כשגיאה, כדי שגם מסמך חלקי ייתן
    ערך במקום כלום."""
    try:
        import docx  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        raise DocumentExtractError("python-docx אינו מותקן.") from None

    try:
        document = docx.Document(path_or_stream)
    except Exception as e:
        raise DocumentExtractError(f"לא ניתן לפתוח את הקובץ כמסמך Word: {e}") from None

    bill = ExtractedBill()
    heads: list[str] = []
    in_explanatory = False

    for p in document.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name

        if style == _STYLE_EXPLANATORY_HEAD:
            in_explanatory = True
            continue
        if style == _STYLE_EXPLANATORY or (in_explanatory and style.startswith("Hesber")):
            bill.explanatory.append(text)
            continue
        if style == _STYLE_TITLE:
            heads.append(text)
            continue

        if (m := _INTERNAL_RE.search(text)):
            bill.internal_number = m.group(1)
        if (m := _BILL_NUMBER_RE.search(text)):
            bill.bill_number = m.group(1)
        if (m := _INITIATOR_RE.search(text)):
            # "יוזם:  חבר הכנסת   צביקה פוגל" - השם הוא מה שאחרי
            # התואר, והפרדה היא טאבים בתבנית של הכנסת.
            rest = [x.strip() for x in m.group(1).split("\t") if x.strip()]
            bill.initiator = rest[-1] if rest else ""

    # שתי כותרות בסגנון הזה: הראשונה הכנסת, השנייה שם ההצעה.
    if heads:
        bill.knesset = heads[0]
        bill.title = heads[-1] if len(heads) > 1 else ""
    if not bill.title:
        bill.warnings.append("לא זוהה שם הצעת חוק (סגנון 'Head HatzaotHok').")

    if not document.tables:
        bill.warnings.append("לא נמצאה טבלת נוסח - המסמך אינו בתבנית הצעת חוק של הכנסת.")
    else:
        bill.lines = _parse_table(document.tables[0], bill.warnings)
        if len(document.tables) > 1:
            bill.warnings.append(f"נמצאו {len(document.tables)} טבלאות; חולצה הראשונה בלבד.")
    if not bill.lines and not bill.explanatory:
        raise DocumentExtractError("לא חולץ תוכן כלשהו מהמסמך.")
    return bill


__all__ = ["DocumentExtractError", "ExtractedBill", "ExtractedLine", "extract_bill"]
