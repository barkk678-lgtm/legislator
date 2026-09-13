"""
רנדרר הצעת חוק -> docx בתבנית החקיקה הרשמית.

עיקרון: לא בונים docx מאפס. לוקחים חבילת docx קיימת שנוצרה בתבנית
(skeleton), מחליפים רק את word/document.xml ואת word/footnotes.xml,
ומשמרים את כל שאר הבייטים — ובראשם styles.xml.

הרנדרר דטרמיניסטי לחלוטין: אין רשת, אין LLM, אין אקראיות.
אותו קלט -> אותם בייטים.
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from bill_title import PLACEHOLDER  # noqa: E402

# ── קבועי התבנית (ראו docs/template-spec.md) ─────────────────────────────
SIDE_W = 1871          # עמודת כותרת שוליים
STEP_W = 624           # עמודת מספר / עמודת הזחה
TAIL_W = 4023          # עמודת התוכן האחרונה
MAX_DEPTH = 5          # חמש רמות הזחה אפשריות (תקרה)
# רוחב הטבלה. נמדד 9638 בקובץ אחד ו-9641 באחר — הפרש של 3 dxa, כנראה
# תוצאה של עריכה ידנית. להשאיר כפרמטר עד שתושג התבנית המקורית.
TABLE_W = 9641

NBSP_TABS = (
    '<w:tabs><w:tab w:val="left" w:pos="624"/>'
    '<w:tab w:val="left" w:pos="1247"/></w:tabs>'
)

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
    'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
    'xmlns:w16se="http://schemas.microsoft.com/office/word/2015/wordml/symex" '
    'mc:Ignorable="w14 w15 w16se"'
)

EN_DASH = "\u2013"


# ── בניית runs ───────────────────────────────────────────────────────────
def _t(text: str) -> str:
    sp = ' xml:space="preserve"' if text != text.strip() else ""
    return f"<w:t{sp}>{escape(text)}</w:t>"


def run(text: str, highlight: bool = False) -> str:
    """
    run עברי. מפצל אוטומטית סביב en-dash, כי בקבצים המקוריים ה-en-dash
    יושב ב-run נפרד ללא hint="cs" — וזה משנה את הרינדור בוורד.

    highlight: מוסיף <w:highlight w:val="yellow"/> - לשימוש בטקסט
    placeholder שהמערכת לא ידעה לנסח בעצמה (ראו
    run_with_placeholder_highlight), לא לעיצוב תוכן רגיל.
    """
    if not text:
        return ""
    hl = '<w:highlight w:val="yellow"/>' if highlight else ""
    out = []
    for i, part in enumerate(text.split(EN_DASH)):
        if i:
            out.append(f'<w:r><w:rPr>{hl}<w:rtl/></w:rPr>{_t(EN_DASH)}</w:r>')
        if part:
            out.append(
                f'<w:r><w:rPr><w:rFonts w:hint="cs"/>{hl}<w:rtl/></w:rPr>{_t(part)}</w:r>'
            )
    return "".join(out)


def run_with_placeholder_highlight(text: str) -> str:
    """כמו run(), אבל אם bill_title.PLACEHOLDER מופיע בתוך text - המקטע
    הזה בלבד מודגש ברקע צהוב, כדי שהמשתמש ישים לב שיש להשלים אותו
    ידנית (ראו bill_title.default_bill_title)."""
    if PLACEHOLDER not in text:
        return run(text)
    before, _, after = text.partition(PLACEHOLDER)
    return run(before) + run(PLACEHOLDER, highlight=True) + run(after)


def run_fnref(fid: int) -> str:
    return (
        f'<w:r><w:rPr><w:rStyle w:val="a5"/><w:rFonts w:hint="cs"/><w:rtl/></w:rPr>'
        f'<w:footnoteReference w:id="{fid}"/></w:r>'
    )


def para(style: str, content: str, tabs: bool = False) -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/>'
        f'{NBSP_TABS if tabs else ""}</w:pPr>{content}</w:p>'
    )


def cell(width: int, style: str, content: str = "", span: int = 1,
         tabs: bool = False) -> str:
    gs = f'<w:gridSpan w:val="{span}"/>' if span > 1 else ""
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{gs}</w:tcPr>'
        f'{para(style, content, tabs)}</w:tc>'
    )


# ── מודל הקלט ────────────────────────────────────────────────────────────
@dataclass
class Line:
    """שורה אחת בטבלת החקיקה."""
    text: str = ""
    depth: int = 0                    # 0..5
    side_heading: str = ""            # כותרת שוליים (רק בשורה ראשונה של סעיף)
    number: str = ""                  # "1." — מספר הסעיף בהצעה
    marker: str = ""                  # "(1)" / "(א)" — מקבל tab אחריו
    text_after: str = ""              # המשך הטקסט אחרי סימן הערת השוליים
    style: str = "TableBlock"         # TableBlock | TableBlockOutdent | TableHead
    footnotes: list[str] = field(default_factory=list)
    # דפוס "סעיף פנימי": כותרת שוליים + מספר של סעיף מצוטט
    inner_heading: str = ""
    inner_number: str = ""
    # provenance (חוק ברזל 3, משימה 5א) - ממולא על ידי amend(), לא
    # קורא אף פעם על ידי render_line/write_docx. אופציונלי: None
    # תקין לשורות שאינן מצטטות נוסח קיים (למשל שם הצעה/דברי הסבר,
    # שמנוסחים בחופשיות לפי CLAUDE.md - חוק ברזל 4).
    source_node_id: str | None = None
    as_of: str | None = None


@dataclass
class Bill:
    knesset: str                      # "הכנסת העשרים וחמש"
    title: str                        # שם הצעת החוק המלא
    initiator: str                    # "צביקה פוגל"
    internal_number: str = "????????"
    bill_number: str = "פ/?????????"
    lines: list[Line] = field(default_factory=list)
    explanatory: list[str] = field(default_factory=list)
    # לא מודפס בכלל ב-docx (ראו render_document.tail) - מזכירות הכנסת
    # היא שכותבת את פסקת ההגשה, ורק אחרי שההצעה אושרה והונחה בפועל.
    # נשאר כאן רק לצורך validator._check_8 (בדיקת עקביות שנה מול שם
    # ההצעה, לשימוש עתידי כשהתאריך האמיתי יהיה ידוע) - לא שדה קלט
    # למשתמש (ראו 10ב).
    submitted_date: str = "????????????????????????"


# ── רינדור שורה ──────────────────────────────────────────────────────────
def render_line(ln: Line, fn_ids: dict[str, int], n_steps: int, tail_w: int) -> str:
    """n_steps = מספר עמודות ה-624 בטבלה; tail_w = רוחב עמודת הזנב."""
    d = ln.depth
    if not 0 <= d < n_steps:
        raise ValueError(f"depth {d} מחוץ לטווח 0..{n_steps - 1}")

    body = ""
    if ln.marker:
        body += run(ln.marker)
        body += (
            f'<w:r><w:rPr><w:rFonts w:hint="cs"/><w:rtl/></w:rPr>'
            f'<w:tab/>{_t(ln.text)}</w:r>'
        )
    else:
        body += run(ln.text)
    for key in ln.footnotes:
        body += run_fnref(fn_ids[key])
    if ln.text_after:
        body += run(ln.text_after)

    cells = [cell(SIDE_W, "TableSideHeading", run(ln.side_heading) if ln.side_heading else "")]
    cells.append(cell(STEP_W, "TableText", run(ln.number) if ln.number else ""))

    if ln.inner_heading or ln.inner_number:
        # דפוס הסעיף הפנימי: 3 + 1 + 2
        cells.append(cell(STEP_W * 3, "TableInnerSideHeading", run(ln.inner_heading), span=3))
        cells.append(cell(STEP_W, "TableText", run(ln.inner_number)))
        cells.append(cell(tail_w + STEP_W, ln.style, body, span=2, tabs=True))
    else:
        for _ in range(d):
            cells.append(cell(STEP_W, "TableText"))
        span = n_steps - d
        width = tail_w + STEP_W * (n_steps - 1 - d)
        cells.append(cell(width, ln.style, body, span=span, tabs=True))

    return f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{''.join(cells)}</w:tr>"


def render_document(bill: Bill, fn_ids: dict[str, int]) -> str:
    # הטבלה נבנית לרוחב המינימלי הנדרש: עמודות ההזחה נוצרות רק עד העומק
    # שבו המסמך משתמש בפועל. כך נבנו שני הקבצים המקוריים.
    deepest = max((l.depth for l in bill.lines), default=0)
    if any(l.inner_heading or l.inner_number for l in bill.lines):
        deepest = max(deepest, 4)
    n_steps = deepest + 1
    tail_w = TABLE_W - SIDE_W - STEP_W * n_steps
    grid = (
        f'<w:gridCol w:w="{SIDE_W}"/>'
        + f'<w:gridCol w:w="{STEP_W}"/>' * n_steps
        + f'<w:gridCol w:w="{tail_w}"/>'
    )
    tbl = (
        "<w:tbl><w:tblPr><w:bidiVisual/>"
        f'<w:tblW w:w="{TABLE_W}" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/>'
        '<w:tblCellMar><w:top w:w="57" w:type="dxa"/><w:left w:w="0" w:type="dxa"/>'
        '<w:bottom w:w="57" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tblCellMar>'
        '<w:tblLook w:val="01E0" w:firstRow="1" w:lastRow="1" w:firstColumn="1"'
        ' w:lastColumn="1" w:noHBand="0" w:noVBand="0"/></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>"
        + "".join(render_line(l, fn_ids, n_steps, tail_w) for l in bill.lines)
        + "</w:tbl>"
    )

    head = (
        para("a", run(f"מספר פנימי: {bill.internal_number}"))
        + para("HeadHatzaotHok", run(bill.knesset))
        + para("a", "")
        + para("David", run("יוזם:") + '<w:r><w:rPr><w:rtl/></w:rPr><w:tab/></w:r>'
               + run("חבר הכנסת") + '<w:r><w:rPr><w:rtl/></w:rPr><w:tab/></w:r>'
               + run(bill.initiator))
        + para("David", run("_" * 46))
        + para("David", run(bill.bill_number))
        + para("David", "")
        + para("HeadHatzaotHok", run_with_placeholder_highlight(bill.title))
    )

    # אין כאן פסקת "הוגשה ליו"ר הכנסת והסגנים והונחה על שולחן הכנסת
    # ביום ..." - זו לא הוראה שהמנסח (או המשתמש) כותבים: מזכירות
    # הכנסת היא שמוסיפה אותה, ורק לאחר שההצעה אושרה והונחה בפועל.
    # אישר המשתמש (2026-09) אחרי בדיקה ידנית - golden-kaytanot.docx
    # כלל אותה עם placeholder, אבל זה תיעוד של מסמך שכבר קיבל את
    # השורה הזו בדיעבד, לא תבנית לשלב הניסוח.
    tail = (
        para("HeadDivreiHesber", run("דברי הסבר"))
        + "".join(para("Hesber", run(p)) for p in bill.explanatory)
    )

    sect = (
        '<w:sectPr><w:footerReference w:type="even" r:id="rId11"/>'
        '<w:footerReference w:type="default" r:id="rId12"/>'
        '<w:pgSz w:w="11907" w:h="16840" w:code="9"/>'
        '<w:pgMar w:top="1701" w:right="1134" w:bottom="1417" w:left="1134"'
        ' w:header="680" w:footer="680" w:gutter="0"/>'
        '<w:cols w:space="720"/><w:noEndnote/><w:titlePg/><w:bidi/><w:rtlGutter/>'
        '<w:docGrid w:linePitch="326"/></w:sectPr>'
    )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {NS}><w:body>{head}{tbl}{tail}{sect}</w:body></w:document>"
    )


def render_footnotes(refs: dict[str, str]) -> tuple[str, dict[str, int]]:
    """refs: {key: 'ס\"ח התשע\"ו, עמ\\' 898.'} -> (xml, {key: id})"""
    sep = (
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0"'
        ' w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p>'
        "</w:footnote>"
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr>'
        '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
        "<w:r><w:continuationSeparator/></w:r></w:p></w:footnote>"
    )
    ids, body = {}, []
    for i, (key, text) in enumerate(refs.items(), start=2):
        ids[key] = i
        body.append(
            f'<w:footnote w:id="{i}"><w:p><w:pPr><w:pStyle w:val="a4"/>'
            "<w:rPr><w:rtl/></w:rPr></w:pPr>"
            '<w:r><w:rPr><w:rStyle w:val="a5"/></w:rPr><w:footnoteRef/></w:r>'
            '<w:r><w:rPr><w:rtl/></w:rPr><w:t xml:space="preserve"> </w:t></w:r>'
            f"{run(text + ' ')}</w:p></w:footnote>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:footnotes {NS}>{sep}{''.join(body)}</w:footnotes>"
    )
    return xml, ids


# ── כתיבת החבילה ─────────────────────────────────────────────────────────
def write_docx(bill: Bill, refs: dict[str, str], skeleton: Path, out: Path) -> Path:
    fn_xml, fn_ids = render_footnotes(refs)
    doc_xml = render_document(bill, fn_ids)

    replace = {
        "word/document.xml": doc_xml.encode("utf-8"),
        "word/footnotes.xml": fn_xml.encode("utf-8"),
    }
    with zipfile.ZipFile(skeleton) as zin, zipfile.ZipFile(
        out, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = replace.get(item.filename) or zin.read(item.filename)
            zout.writestr(item, data)
    return out
