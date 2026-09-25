"""קלט הכלי: PDF (העיקר - כך המשתמשים מקבלים נוסח לקריאה שנייה ושלישית) או
Word (.docx, נשאר מהכלי הקודם). שניהם -> אותו מבנה (pdf_bill.ParsedBill)."""

from __future__ import annotations

import io
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "documents"))

from pdf_bill import BillSection, BillUnit, ParsedBill, parse_bill_pdf  # noqa: E402

_INVISIBLE = re.compile("[‎‏‪-‮⁦-⁩]")
_MARKER_RE = re.compile(r"^\(((?:\d{1,2}|[א-ת]{1,2})\d?)\)$")


class BillInputError(ValueError):
    """הקובץ אינו הצעת חוק שאפשר לקרוא - הודעה למשתמש."""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _INVISIBLE.sub("", text or "")).strip()


def read_bill(filename: str, data: bytes) -> ParsedBill:
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:4] == b"%PDF":
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(data)
            tmp.flush()
            try:
                bill = parse_bill_pdf(Path(tmp.name))
            except Exception as exc:  # noqa: BLE001
                raise BillInputError(f"לא הצלחתי לקרוא את קובץ ה-PDF ({type(exc).__name__}).") from None
    elif name.endswith(".docx"):
        bill = _read_docx(data)
    else:
        raise BillInputError("נתמכים קובצי PDF ו-Word (.docx).")
    if not bill.sections:
        raise BillInputError("לא נמצאו בקובץ סעיפי הצעת חוק. ודאו שזה נוסח לקריאה שנייה ושלישית.")
    return bill


def _read_docx(data: bytes) -> ParsedBill:
    from extract_docx import DocumentExtractError, extract_bill  # noqa: PLC0415

    try:
        doc = extract_bill(io.BytesIO(data))
    except DocumentExtractError as exc:
        raise BillInputError(str(exc)) from None
    title = _clean(doc.title).split(" להצעת ")[0]
    sections: list[BillSection] = []
    current: BillSection | None = None
    open_units: list[BillUnit] = []
    lead_lines: list[str] = []
    for line in doc.lines:
        text = _clean(line.text)
        number = _clean(line.number).rstrip(".")
        if number and re.fullmatch(r"\d{1,3}[א-ת]?", number):
            current = BillSection(number, _clean(line.side_heading), BillUnit("lead", "", ""))
            sections.append(current)
            open_units = []
        elif current is None:
            if text:
                lead_lines.append(text)
            continue
        elif line.side_heading and not current.units and not current.lead.text:
            current.margin_title = _clean(f"{current.margin_title} {line.side_heading}")
        if not text:
            continue
        marker = _MARKER_RE.match(_clean(line.marker))
        if marker:
            label = f"({marker.group(1)})"
            kind = "paragraph" if marker.group(1)[0].isdigit() else "subsection"
            unit = BillUnit(kind, label, text)
            if open_units and open_units[-1].kind != kind:
                open_units[-1].children.append(unit)
                open_units = [open_units[-1], unit] if len(open_units) == 1 else open_units[:-1] + [unit]
            else:
                current.units.append(unit)
                open_units = [unit]
        else:
            target = open_units[-1] if open_units else current.lead
            target.text = _clean(f"{target.text} {text}")
    warnings = list(doc.warnings)
    # **טקסט לפני הסעיף הממוספר הראשון אינו נזרק** (ברק, 19.9). בהצעות אמיתיות
    # סעיף 1 הוא לעתים היחיד שממוספר אוטומטית ב-Word (w:numPr) - בקובץ אין לזה
    # טקסט, ובלי זה חצי מההצעה (13948363) נעלם בשקט. tests/unit/test_leading_section.py.
    if lead_lines:
        text = " ".join(lead_lines).strip()
        first = sections[0].number if sections else ""
        if first.isdigit() and int(first) > 1:
            inferred = str(int(first) - 1)
            sections.insert(0, BillSection(inferred, "", BillUnit("lead", "", text)))
            warnings.append(
                f"סעיף {inferred} לא נשא מספר במסמך (כנראה מספור אוטומטי של Word, שאינו "
                f"טקסט) - שוחזר מהמיקום ומהסעיף שאחריו. ודאו שהמספור נכון.")
        else:
            warnings.append(
                f"נמצא טקסט לפני הסעיף הממוספר הראשון ולא ניתן להסיק את מספרו (הסעיף "
                f"הראשון שזוהה: {first or 'אין'}). {len(lead_lines)} שורות אינן משויכות "
                f"לאף סעיף: {text[:120]!r}")
    return ParsedBill(title=title, committee="", sections=sections, warnings=warnings)


def user_notices(bill: ParsedBill) -> list[str]:
    """מה מהאזהרות המשתמש צריך לראות: סעיף ששוחזר או טקסט שלא שויך. אזהרות
    טכניות של החילוץ ("טבלה שטוחה", "לא זוהה מגיש") - לא ("המשתמש לא רואה את
    הפירוק", ברק 26.9)."""
    return [w for w in bill.warnings if w.startswith(("סעיף ", "נמצא טקסט"))]


__all__ = ["BillInputError", "read_bill", "user_notices"]
