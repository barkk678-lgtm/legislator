"""קריאת הצעת חוק לקריאה שנייה ושלישית מ-PDF -> מבנה ההצעה (הסתייגויות 1, 26.9).

**המשתמש לא רואה את הפירוק** - הוא מעלה קובץ. הקריאה הנכונה היא אחריותנו,
ולכן היא נבנית ממיקום התווים בעמוד ולא מטקסט שטוח. בחילוץ טקסט רגיל של
reference/הצעת חוק טבריה.pdf נמצאו ארבעה כשלים, וכל אחד נפתר כאן במקום משלו:

| כשל בחילוץ רגיל | הסיבה | הפתרון |
|---|---|---|
| `)1(` במקום `(1)` | ה-PDF שומר את התווים **בסדר חזותי** (משמאל לימין) | `_logical`: אלגוריתם הכיוון - היפוך השורה, רצפי ספרות/לטינית נשארים משמאל לימין, וסוגריים בהקשר עברי מתהפכים |
| `התשכ"ה–11965` | מספר הערת השוליים (גופן 8.5, הגוף 13) נדבק לשנה | תו שגופנו קטן מ-80% מגופן הגוף - לא נכנס לטקסט |
| כותרת שוליים בתוך הגוף | הכותרת בעמודה נפרדת מימין, באותן שורות | כל תו משויך לעמודה לפי מיקומו: כותרת שוליים / מספר סעיף / גוף |
| שבירות שורה, `סעיף ,143` | שורות נקראו בנפרד, בסדר חזותי | השורות מחוברות ברווח; `התשי"ח–` בסוף שורה מתחבר לשנה בלי רווח |

**רק ההצעה.** עמוד השער (שממנו נלקחת הוועדה), ההערות בתחתית העמוד,
וההסתייגויות שאחרי שורת הכוכביות - אינם חלק מהמבנה.

**ודאות.** יחידה שקריאתה לא ודאית (תו שלא פוענח, שורה ששיוכה לא ברור) -
מסומנת `certain=False`, והמחוללים לא מעגנים בה הסתייגות.

**pdfminer.six (רישיון MIT)** ולא PyMuPDF (AGPL) - ברק, 26.9: המוצר בתשלום.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTChar

# ── הכיוון ────────────────────────────────────────────────────────────────

_SEPARATORS = set(",.:/-+")
_TERMINATORS = set("%₪$")


def _bidi_class(ch: str) -> str:
    if "֐" <= ch <= "׿" or "יִ" <= ch <= "ﭏ":
        return "R"
    if ch.isdigit():
        return "EN"
    if ch.isascii() and ch.isalpha():
        return "L"
    if ch in _SEPARATORS:
        return "CS"
    if ch in _TERMINATORS:
        return "ET"
    return "N"


def _logical(visual: list[str]) -> str:
    """תווי שורה אחת בסדר חזותי (משמאל לימין) -> הטקסט בסדר לוגי, בפסקה
    מימין לשמאל. גרסה מצומצמת של אלגוריתם הכיוון של יוניקוד (UAX #9) לשתי
    רמות: עברית ברמה 1, ספרות ולטינית ברמה 2.

    W4: מפריד יחיד בין שתי ספרות ("2023-000899", "3343/25", "1.1") - חלק
    מהמספר. W5: סימן אחוז/מטבע צמוד למספר - חלק ממנו. N1: תו ניטרלי (רווח,
    סוגריים, מרכאות, מקף) מקבל כיוון לטיני רק כשמשני צדדיו לטינית; ספרות
    נחשבות כאן כעברית (ימין לשמאל). L2: הופכים את הרצפים ברמה 2, ואז את כל
    השורה. **בלי היפוך סוגריים (L4):** Word כותב לכל גליף את התו הלוגי שלו -
    הגליף הימני ב-"(1)" נראה ")" אבל ממופה ל-"(" - ולכן סידור מחדש מספיק.
    (בגרסה הראשונה סוגריים הופכו, ויצא `)1(` - בדיוק הכשל של החילוץ הרגיל.)"""
    n = len(visual)
    cls = [_bidi_class(c) for c in visual]
    for i in range(1, n - 1):
        if cls[i] == "CS" and cls[i - 1] == "EN" and cls[i + 1] == "EN":
            cls[i] = "EN"
    for i in range(n):
        if cls[i] == "ET" and ((i > 0 and cls[i - 1] == "EN") or (i + 1 < n and cls[i + 1] == "EN")):
            cls[i] = "EN"
    strong = ["L" if c == "L" else ("R" if c in ("R", "EN") else None) for c in cls]
    level = [0] * n
    i = 0
    while i < n:
        if strong[i] is not None:
            level[i] = 2 if cls[i] in ("L", "EN") else 1
            i += 1
            continue
        j = i
        while j < n and strong[j] is None:
            j += 1
        left = strong[i - 1] if i > 0 else "R"
        right = strong[j] if j < n else "R"
        for k in range(i, j):
            level[k] = 2 if left == "L" and right == "L" else 1
        i = j
    chars = list(visual)
    i = 0
    while i < n:
        if level[i] == 2:
            j = i
            while j < n and level[j] == 2:
                j += 1
            chars[i:j] = chars[i:j][::-1]
            level[i:j] = level[i:j][::-1]
            i = j
        else:
            i += 1
    return "".join(reversed(chars))


# ── תווים ושורות ──────────────────────────────────────────────────────────


@dataclass
class _Char:
    text: str
    x0: float
    x1: float
    y0: float
    size: float
    bold: bool


@dataclass
class _Line:
    """שורה חזותית אחת, מחולקת לעמודות."""
    page: int
    y: float
    margin: str = ""
    number: str = ""
    body: str = ""
    body_x1: float = 0.0       # הקצה הימני של טקסט הגוף - ההזחה
    marker_x1: float = 0.0
    bold: bool = False
    size: float = 0.0
    uncertain: bool = False
    dropped_refs: list[str] = field(default_factory=list)


def _page_chars(page) -> list[_Char]:
    out: list[_Char] = []

    def walk(obj):
        if isinstance(obj, LTChar):
            out.append(_Char(obj.get_text(), obj.x0, obj.x1, obj.y0, round(obj.size, 1),
                             "Bold" in obj.fontname))
            return
        for child in getattr(obj, "_objs", None) or []:
            walk(child)

    walk(page)
    return out


def _join_visual(chars: list[_Char], refs: list[_Char] = ()) -> list[str]:
    """תווים של קטע שורה (ממוינים משמאל לימין) -> רשימת תווים חזותית, עם
    רווח במקום שיש פער בלי תו רווח. פער שמספר הערת שוליים יושב בו - אינו
    רווח (אחרת "התשכ"ד–1964²," נקרא "1964 ,")."""
    out: list[str] = []
    prev: _Char | None = None
    for ch in chars:
        gap_is_ref = prev is not None and any(prev.x1 - 1 <= r.x0 and r.x1 <= ch.x0 + 1 for r in refs)
        if prev is not None and ch.x0 - prev.x1 > 0.18 * ch.size and prev.text != " " and ch.text != " " \
                and not gap_is_ref:
            out.append(" ")
        out.append(ch.text)
        prev = ch
    return out


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_CID_RE = re.compile(r"\(cid:\d+\)|�")


def _lines(path: Path, *, body_size: float | None = None,
           columns: bool = True) -> tuple[list[_Line], float]:
    """columns=False - כל השורה גוף (החלק של ההסתייגויות, שאינו טבלה)."""
    pages = list(extract_pages(str(path), laparams=LAParams()))
    all_chars = [(i, c) for i, page in enumerate(pages) for c in _page_chars(page)]
    if body_size is None:
        sizes = Counter(c.size for _, c in all_chars if c.text.strip())
        body_size = sizes.most_common(1)[0][0] if sizes else 12.0
    lines: list[_Line] = []
    for page_index, page in enumerate(pages):
        width = page.width
        chars = [c for c in _page_chars(page)]
        # מספרי הערות שוליים בתוך השורה - גופן קטן, מורם. נשמרים בצד (לדוח).
        refs = [c for c in chars if c.size < 0.8 * body_size and c.text.strip()]
        text_chars = [c for c in chars if c.size >= 0.8 * body_size]
        rows: dict[int, list[_Char]] = {}
        for c in sorted(text_chars, key=lambda c: -c.y0):
            key = next((k for k in rows if abs(k - c.y0) <= 2.5), None)
            rows.setdefault(key if key is not None else round(c.y0), []).append(c)
        for y, row in sorted(rows.items(), key=lambda kv: -kv[0]):
            row.sort(key=lambda c: c.x0)
            # עמודות: כותרת שוליים מימין לקו ~0.745 מהרוחב, מספר הסעיף ברצועה
            # שלפניה, הגוף משמאל. ספרה/נקודה ברצועת המספר - מספר; אות עברית שם -
            # המשך כותרת השוליים (בסעיף 2 בטבריה הכותרת נוגעת במספר).
            margin_x, number_x = 0.745 * width, 0.705 * width
            margin, number, body = [], [], []
            # **עמודות רק כשיש ביניהן רווח אמיתי.** שורה רציפה שחוצה את הרצועה
            # (עמוד השער, כותרת ההצעה) - כולה גוף. בלי הבדיקה הזו "הצעת חוק זו
            # נדונה" נחתכה ל"הצעת | חוק זו נדונה".
            visible = [c for c in row if c.text.strip()]
            left_of_band = [c for c in visible if c.x1 <= number_x]
            gap = (min((c.x0 for c in visible if c.x0 >= number_x - 1), default=width)
                   - max((c.x1 for c in left_of_band), default=0.0))
            split = columns and (not left_of_band or gap > 0.9 * body_size)
            for c in row:
                if not split:
                    body.append(c)
                elif c.x0 >= margin_x:
                    margin.append(c)
                elif c.x0 >= number_x and (c.text.isdigit() or c.text in ". " or "א" <= c.text <= "ת"):
                    (number if (c.text.isdigit() or c.text in ". ") else margin).append(c)
                else:
                    body.append(c)
            line = _Line(page=page_index, y=y, size=Counter(c.size for c in row).most_common(1)[0][0],
                         bold=sum(c.bold for c in row) > len(row) / 2)
            line.margin = _clean(_logical(_join_visual(margin)))
            line.number = _clean(_logical(_join_visual(number)))
            body_visible = [c for c in body if c.text.strip()]
            row_refs = [r for r in refs if abs(r.y0 - y) < body_size]
            line.body = _clean(_logical(_join_visual(body, row_refs)))
            line.body_x1 = max((c.x1 for c in body_visible), default=0.0)
            line.dropped_refs = [r.text for r in row_refs]
            line.uncertain = bool(_CID_RE.search(line.body + line.margin + line.number))
            lines.append(line)
    return lines, body_size


# ── מבנה ההצעה ─────────────────────────────────────────────────────────────


@dataclass
class BillUnit:
    """יחידה בסעיף של ההצעה. label: "(1)", "(א)"; kind: "lead" (רישה),
    "paragraph"/"subsection"/"subparagraph", "tail" (סיפא)."""
    kind: str
    label: str
    text: str
    certain: bool = True
    children: list["BillUnit"] = field(default_factory=list)


@dataclass
class BillSection:
    number: str
    margin_title: str
    lead: BillUnit
    units: list[BillUnit] = field(default_factory=list)
    certain: bool = True

    @property
    def text(self) -> str:
        """כל הנוסח של הסעיף, לפי הסדר."""
        parts = [self.lead.text] if self.lead.text else []

        def walk(units):
            for u in units:
                parts.append(f"{u.label} {u.text}".strip())
                walk(u.children)

        walk(self.units)
        return " ".join(parts)


@dataclass
class ParsedBill:
    title: str
    committee: str
    sections: list[BillSection]
    warnings: list[str] = field(default_factory=list)
    body_size: float = 0.0


_SECTION_NO_RE = re.compile(r"^(\d{1,3}[א-ת]?)\.$")
_MARKER_RE = re.compile(r"^\(((?:\d{1,2}|[א-ת]{1,2})\d?)\)\s*")
_QUOTES = "\"״”“"
# "והועברה לוועדת הפנים והגנת הסביבה." - כתיב מלא ("לוועדת") וחסר ("לועדת").
_COMMITTEE_RE = re.compile(r"והועברה\s+לו?(ו?עדת\s+[^.]+?)\s*\.")
_END_RE = re.compile(r"^\*{10,}$")
_YEAR_BREAK_RE = re.compile(r"[א-ת][\"״]?[א-ת]?\s*[–-]$")


def _join(a: str, b: str) -> str:
    """שתי שורות של אותה יחידה. `התשי"ח–` בסוף שורה ו-`1958` בתחילת הבאה -
    בלי רווח (Word שובר שורה אחרי המקף)."""
    if not a:
        return b
    if _YEAR_BREAK_RE.search(a) and b[:1].isdigit():
        return a + b
    return f"{a} {b}"


_BARE_NO_RE = re.compile(r"^(\d{1,3}[א-ת]?)$")


def _section_number(line: "_Line") -> str | None:
    """מספר הסעיף בעמודת המספר: "3." - וגם "1" בלי נקודה כשבשורה יש כותרת שוליים
    (628446: הנקודה נפלה מהעמודה, סעיף 1 לא זוהה, וכל ההצעה סומנה "לא קריאה")."""
    m = _SECTION_NO_RE.match(line.number)
    if m:
        return m.group(1)
    m = _BARE_NO_RE.match(line.number)
    # כותרת שוליים אמיתית היא טקסט עברי; "27" + "06/2022/" בראש כל עמוד הוא תאריך
    return m.group(1) if m and re.search(r"[א-ת]", line.margin) else None


def _section_key(number: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([א-ת]?)$", number)
    return (int(m.group(1)), m.group(2)) if m else (0, "")


def _numbering_readable(numbers: list[str]) -> bool:
    """מספרי הסעיפים בהצעה עולים ברצף מ-1 ("1, 2, 3", ומדי פעם "3א"). בקובץ ששכבת
    הטקסט שלו ממפה ספרות שונות לאותו תו (263401: "4, 9, 0, 0, 9, 3..." במקום 1-9;
    גם pdftotext קורא כך) - הרצף שבור מההתחלה, ואי אפשר לדעת איזה סעיף הוא איזה."""
    keys = [_section_key(n) for n in numbers]
    if not keys or keys[0][0] != 1:
        return False
    steps = sum(1 for a, b in zip(keys, keys[1:])
                if b[0] == a[0] + 1 or (b[0] == a[0] and b[1] > a[1]))
    return steps >= (len(keys) - 1) / 2


def _label_kind(label: str) -> str:
    return "paragraph" if label[0].isdigit() else "subsection"


def parse_bill_pdf(path: Path | str) -> ParsedBill:
    path = Path(path)
    lines, body_size = _lines(path)
    warnings: list[str] = []

    # עמוד השער: הוועדה.
    cover = " ".join(l.body for l in lines if l.page == 0)
    m = _COMMITTEE_RE.search(cover)
    committee = re.sub(r"^ו?ועדת", "ועדת", m.group(1).strip()) if m else ""
    if not committee:
        warnings.append("לא נמצאה בעמוד השער הוועדה שאליה הועברה ההצעה.")

    # תחילת ההצעה: "הצעת חוק לקריאה השנייה ולקריאה השלישית", ואחריה שם החוק.
    start = next((i for i, l in enumerate(lines)
                  if "לקריאה השנייה ולקריאה השלישית" in l.body and l.page > 0), None)
    if start is None:
        start = next((i for i, l in enumerate(lines) if "לקריאה השנייה ולקריאה השלישית" in l.body), 0)
    title = ""
    first_section = None
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if _section_number(l):
            first_section = i
            break
        if not title and re.match(r"^(חוק|פקודת)\s", l.body):
            title = l.body
    if first_section is None:
        return ParsedBill(title, committee, [], warnings + ["לא נמצא סעיף ממוספר בהצעה."], body_size)

    sections: list[BillSection] = []
    current: BillSection | None = None
    open_units: list[tuple[BillUnit, float]] = []   # (יחידה, הקצה הימני של הטקסט שלה)
    in_quote = False
    section_edge = 0.0
    raw_numbers: list[str] = []
    for l in lines[first_section:]:
        if _END_RE.match(l.body.replace(" ", "")) or l.body.strip() in ("הסתייגויות", "הסתייגויות ובקשות רשות דיבור"):
            break
        if l.size < 0.8 * body_size or not (l.body or l.margin or l.number):
            continue
        if re.fullmatch(r"-\s*\d+\s*-|\d{2}/\d{2}/\d{4}|\d{1,2}:\d{2}\s+\d{2}/\d{2}/\d{4}", l.body):
            continue  # כותרת עמוד
        number = _section_number(l)
        body = l.body
        if number:
            raw_numbers.append(number)
        if number and current is not None and _section_key(number) <= _section_key(current.number):
            # **מספר שאינו עולה - אינו סעיף חדש** (הכרעה ז, 26.9): מספור של נוסח מצוטט
            # (4715569: "1-4" ו-"1-7" אחרי סעיף 38 - בלי זה הם דרסו את סעיפים 2 ו-4).
            # השורה נשארת בסעיף הנוכחי, והסעיף - לא ודאי: לא מנחשים את השיוך.
            current.certain = False
            body = _clean(f"{l.margin} {number}. {body}")
        elif number:
            current = BillSection(number, l.margin, BillUnit("lead", "", ""))
            sections.append(current)
            open_units, in_quote = [], False
            section_edge = l.body_x1
        elif current is None:
            continue
        elif l.margin:
            current.margin_title = _join(current.margin_title, l.margin)
        if not body:
            continue
        if l.uncertain:
            current.certain = False
        marker = _MARKER_RE.match(body)
        starts_quote = body[:1] in _QUOTES
        if marker and not in_quote and not starts_quote:
            label = f"({marker.group(1)})"
            unit = BillUnit(_label_kind(marker.group(1)), label, body[marker.end():].strip(),
                            certain=not l.uncertain)
            text_x1 = l.body_x1 - 0  # קצה הטקסט נמדד בשורה הבאה (הזחה תלויה)
            # קינון: תווית מסוג אחר מזו של היחידה הפתוחה - ילד שלה.
            while open_units and _label_kind(open_units[-1][0].label[1:-1]) == unit.kind \
                    and len(open_units) > 1:
                open_units.pop()
            if open_units and _label_kind(open_units[-1][0].label[1:-1]) != unit.kind:
                open_units[-1][0].children.append(unit)
            else:
                open_units = []
                current.units.append(unit)
            open_units.append((unit, text_x1))
        else:
            target = open_units[-1][0] if open_units else current.lead
            target.text = _join(target.text, body)
            if l.uncertain:
                target.certain = False
        # מרכאות: נוסח מצוטט (יחידה חדשה בתוך ההוראה) - תוויות בתוכו אינן מבנה.
        quote_count = sum(body.count(q) for q in _QUOTES)
        if starts_quote and not in_quote:
            in_quote = quote_count % 2 == 1 or not re.search(r"[\"״”][.;]$", body)
        elif in_quote and re.search(r"[\"״”][.;]?$", body):
            in_quote = False

    for s in sections:
        s.lead.text = _clean(s.lead.text)
        s.margin_title = _clean(s.margin_title)
    if sections and not _numbering_readable(raw_numbers):
        # מספרי הסעיפים לא קריאים - אי אפשר לדעת לאיזה סעיף שייך כל טקסט: כל ההצעה
        # לא ודאית, ואין עוגנים (ברק: "שיוך לא ודאי - לא ודאי, בלי עוגנים. לא לנחש").
        warnings.append("מספרי הסעיפים בקובץ אינם קריאים (הספרות בשכבת הטקסט של הקובץ "
                        "משובשות) - לא מעגנים בו הסתייגויות.")
        for s in sections:
            s.certain = False
    if not sections:
        warnings.append("לא נמצאו סעיפים בהצעה.")
    return ParsedBill(title=_clean(title), committee=committee, sections=sections,
                      warnings=warnings, body_size=body_size)


__all__ = ["BillSection", "BillUnit", "ParsedBill", "parse_bill_pdf"]
