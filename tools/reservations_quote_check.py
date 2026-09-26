#!/usr/bin/env python3
"""המדידה של קריאת ה-PDF (הסתייגויות 1, 26.9): כל ביטוי שהסתייגות אמיתית
מצטטת **מנוסח ההצעה** - נמצא בחילוץ שלנו, מילה במילה?

    python3 tools/reservations_quote_check.py "reference/הצעת חוק טבריה.pdf" [...]
    python3 tools/reservations_quote_check.py --dir DIR --json out.json

**מה נספר כציטוט מההצעה:** הביטוי שאחרי `במקום`, `אחרי`, `לפני`, `המילים`
(במחיקה), `החל במילים`, `עד המילים` - **בשורת ההוראה** של ההסתייגות בלבד.
לא נספרים: הנוסח החדש (שאחרי "יבוא"), וכל מה שבתוך נוסח מצוטט של סעיף
מוצע (למשל "בחוק העיקרי, בסעיף 16(ד), בסופו יבוא" - שם מדובר בחוק העיקרי).

**איפה מחפשים:** בסעיף שתחת הכותרת ("לסעיף 1"), וביחידה שההסתייגות מציינת
("ברישה", "בפסקה (2)") כשיש כזו.

**רמות התאמה** - כל ציטוט מסווג לאחת:
- `exact` - הביטוי נמצא בחילוץ כמו שהוא.
- `typography` - נמצא אחרי איחוד מרכאות/גרשיים/מקפים בלבד (״ " ” / ׳ ' / – -).
- `inner_quotes` - נמצא אחרי השמטת מרכאות פנימיות: ההצעה אומרת `יבוא "(א2)"`,
  וההסתייגות מצטטת `יבוא (א2)` - מרכאות אינן מקוננות (טבריה, הסתייגות 9).
- `section_only` - נמצא בסעיף, אבל לא ביחידה שצוינה (כשל שיוך או כשל ההסתייגות).
- `missing` - לא נמצא.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

from pdf_bill import _lines, parse_bill_pdf  # noqa: E402

Q = "\"״”“"
_ANCHOR_RES = [
    ("replace", re.compile(rf"במקום\s+[{Q}](.+?)[{Q}]\s*,?\s+יבוא")),
    ("after", re.compile(rf"אחרי\s+(?:המילים\s+)?[{Q}](.+?)[{Q}]\s*,?\s+יבוא")),
    ("before", re.compile(rf"לפני\s+(?:המילים\s+)?[{Q}](.+?)[{Q}]\s*,?\s+יבוא")),
    ("delete", re.compile(rf"המיל(?:ים|ה)\s+[{Q}](.+?)[{Q}]\s*[–-]?\s*(?:יימחקו|ימחקו|תימחק|יימחק)")),
    ("from", re.compile(rf"החל\s+במילים\s+[{Q}](.+?)[{Q}]")),
    ("until", re.compile(rf"עד\s+המילים\s+[{Q}](.+?)[{Q}]")),
]
# "לסעיף 2", וגם עם יחידה: "לסעיף 2(1)", "לאחרי סעיף 2(2)", "לסעיף 15(2) עד (12)" (491290).
# בלי היחידה הכותרת לא זוהתה, וכל ההסתייגויות שאחריה נספרו תחת "לסעיף 1" (הכרעה ז, 26.9).
_HEADING_RE = re.compile(r"^(לפני\s+|לאחרי\s+|ל)סעיף\s+(\d{1,3}[א-ת]?)((?:\([^()\s]{1,4}\))*)(\s+עד\s+\([^()\s]{1,4}\))?$")
_ITEM_RE = re.compile(r"^(\d{1,3}|[א-ת]{1,2})\.\s+(.*)$")
_UNIT_RE = re.compile(r"^(ברישה|בסיפה|בפסקה\s+\(([^)]+)\)|בסעיף\s+קטן\s+\(([^)]+)\)|בפסקת\s+משנה\s+\(([^)]+)\))")


@dataclass
class Quote:
    file: str
    reservation: str          # "9", "16/א"
    heading: str              # "לסעיף 1"
    section: str
    unit: str                 # "lead" / "(2)" / ""
    kind: str
    phrase: str
    result: str = ""


def _typo(s: str) -> str:
    s = re.sub(f"[{Q}]", '"', s)
    s = re.sub("[׳']", "'", s)
    s = re.sub("[–—־-]", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def _no_quotes(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(f"[{Q}]", "", _typo(s))).strip()


def reservation_quotes(path: Path) -> list[Quote]:
    """הציטוטים מההצעה, מתוך החלק של ההסתייגויות."""
    lines, _ = _lines(path, columns=False)
    texts = [l.body for l in lines if l.body.strip()]
    try:
        start = next(i for i, t in enumerate(texts) if t == "הסתייגויות")
    except StopIteration:
        return []
    quotes: list[Quote] = []
    heading, section, heading_unit = "", "", ""
    number, letter = "", ""
    item_lines: list[str] = []

    def flush():
        if not item_lines:
            return
        instruction = []
        for t in item_lines:
            if t[:1] in Q and instruction:
                break          # מכאן נוסח חדש מצוטט
            instruction.append(t)
        text = " ".join(instruction)
        unit = ""
        m = _UNIT_RE.match(text)
        if m:
            unit = "lead" if m.group(1) == "ברישה" else ("tail" if m.group(1) == "בסיפה" else
                                                         f"({m.group(2) or m.group(3) or m.group(4)})")
        if heading_unit and unit not in ("lead", "tail"):
            # "לסעיף 2(1)" - ההסתייגות היא לפסקה (1); "לסעיף 24(2)" + "בסעיף קטן (ב)" -
            # (ב) שבתוך (2), לא ה-(ב) הראשון בסעיף (491290)
            unit = heading_unit + unit
        if re.match(r"^בתוספת", text):
            unit = "schedule"         # "בתוספת הראשונה, בפרטים 1 ו־2" (4690270) - לא בסעיף עצמו
        rid = number + (f"/{letter}" if letter else "")
        for kind, rx in _ANCHOR_RES:
            for am in rx.finditer(text):
                quotes.append(Quote(path.name, rid, heading, section, unit, kind, am.group(1).strip()))
        item_lines.clear()

    in_note = False
    for t in texts[start + 1:]:
        if t.startswith("בקשות רשות דיבור") or re.fullmatch(r"\*{10,}", t.replace(" ", "")):
            flush()
            break
        if re.fullmatch(r"-\s*\d+\s*-|\d{2}/\d{2}/\d{4}|נספח מס.*|\(פ/[\d/]+\)", t):
            continue
        # "* הערה: הסתייגות זו קשורה להסתייגות של ... | לסעיף 10" - הזנב של ההערה נשבר
        # לשורה משלו ונראה ככותרת (175006: ההסתייגות לסעיף 11 נספרה תחת 10). הכרעה ז.
        was_note, in_note = in_note, t.startswith("*")
        if was_note and not in_note and _HEADING_RE.match(t):
            in_note = True
            continue
        h = _HEADING_RE.match(t)
        if h:
            flush()
            heading, section = t, h.group(2)
            units = re.findall(r"\([^()]+\)", h.group(3) or "")
            heading_unit = units[0] if units and not h.group(4) else ""
            continue
        if re.match(r"^קבוצת .* מציע(ה|ים|ות)?:?$", t) or t.startswith("לחלופין"):
            flush()
            continue
        m = _ITEM_RE.match(t)
        if m:
            flush()
            if m.group(1).isdigit():
                number, letter = m.group(1), ""
            else:
                letter = m.group(1)
            item_lines.append(m.group(2))
            continue
        if item_lines:
            item_lines.append(t)
        elif letter or number:
            # "לחלופין:" בלי אות (הסתייגות 50) - חלופה אחת
            letter = letter or "חלופה"
            item_lines.append(t)
    flush()
    return quotes


def _unit_text(section, unit: str) -> str | None:
    if unit == "schedule":
        return None
    if unit == "lead":
        return section.lead.text
    if not unit or unit == "tail":
        return None

    path = re.findall(r"\([^()]+\)", unit)      # "(2)(ב)" - (ב) בתוך (2)

    def find(units, label):
        for u in units:
            if u.label == label:
                return u
            found = find(u.children, label)
            if found is not None:
                return found
        return None

    node, units = None, section.units
    for label in path:
        node = find(units, label)
        if node is None:
            return None
        units = node.children
    return node.text if node is not None else None


def check(path: Path) -> tuple[list[Quote], dict]:
    bill = parse_bill_pdf(path)
    by_number = {s.number: s for s in bill.sections}
    quotes = [q for q in reservation_quotes(path) if q.heading.startswith("לסעיף")]
    for q in quotes:
        section = by_number.get(q.section)
        if section is None:
            q.result = "missing"
            continue
        if q.unit == "schedule":
            # התוספת יושבת אחרי הסעיף האחרון בהצעה - מחפשים בכל ההצעה
            scope = " ".join(s.text for s in bill.sections)
        else:
            scope = _unit_text(section, q.unit) if q.unit else None
        haystacks = [scope] if scope is not None else [section.text]
        if scope is not None:
            haystacks.append(section.text)
        result = "missing"
        for idx, hay in enumerate(haystacks):
            if q.phrase in hay:
                result = "exact"
            elif _typo(q.phrase) in _typo(hay):
                result = "typography"
            elif _no_quotes(q.phrase) in _no_quotes(hay):
                result = "inner_quotes"
            else:
                continue
            if idx == 1:
                result = "section_only"
            break
        q.result = result
    counts: dict[str, int] = {}
    for q in quotes:
        counts[q.result] = counts.get(q.result, 0) + 1
    return quotes, {"file": path.name, "quotes": len(quotes), "counts": counts,
                    "sections": len(bill.sections), "section_numbers": [s.number for s in bill.sections],
                    "title": bill.title, "warnings": bill.warnings}


_DIGITS = re.compile(r"\d[\d.,/%]*\d|\d%|%\d|\d")


def _squash(s: str) -> str:
    return re.sub(r"[\s\-־–—\"״”“'׳,.;:()]", "", s)


def _digits_flipped(s: str) -> str:
    return _DIGITS.sub(lambda m: m.group(0)[::-1], s)


def _best_window(phrase: str, text: str) -> tuple[float, str]:
    """הקטע הדומה ביותר בחילוץ (לפי מילים), ויחס הדמיון."""
    import difflib  # noqa: PLC0415
    words, n = text.split(), max(1, len(phrase.split()))
    best, snippet = 0.0, ""
    for i in range(max(1, len(words) - n + 1)):
        cand = " ".join(words[i:i + n])
        r = difflib.SequenceMatcher(None, phrase, cand).ratio()
        if r > best:
            best, snippet = r, cand
    return best, snippet


def diagnose(path: Path, quotes: list[Quote]) -> list[dict]:
    """לכל ציטוט שלא נמצא (או נמצא רק בסעיף) - סוג הכשל המשוער:
    - `spacing` - נמצא אחרי הסרת רווחים ופיסוק: שבירת שורה/מקף/רווח בחילוץ.
    - `digits_order` - נמצא כשסדר הספרות הפוך ("%5" מול "5%"): כיווניות.
    - `other_section` - מופיע בהצעה, אבל בסעיף אחר (מספור כפול / שיוך שגוי).
    - `outside_bill` - מופיע במסמך, אבל מחוץ לחלק של ההצעה (למשל בנספח החוק העיקרי).
    - `no_section` - הסעיף שהכותרת מפנה אליו לא זוהה בכלל.
    - `unit` - נמצא בסעיף אבל לא ביחידה שצוינה (section_only).
    - `near_miss` - קטע דומה מאוד (0.8 ומעלה): ציטוט לא מדויק בהסתייגות, או שגיאת קריאה קטנה.
    - `absent` - שום דבר דומה בהצעה.
    """
    bill = parse_bill_pdf(path)
    by_number = {s.number: s for s in bill.sections}
    texts = [l.body for l in _lines(path, columns=False)[0] if l.body.strip()]
    # בלי חלק ההסתייגויות עצמו - אחרת כל ציטוט "נמצא" בנוסח של ההסתייגות שמצטטת אותו
    start = next((i for i, t in enumerate(texts) if t == "הסתייגויות"), len(texts))
    end = next((i for i, t in enumerate(texts) if i > start and t.startswith("בקשות רשות דיבור")), len(texts))
    whole = " ".join(texts[:start] + texts[end:])
    out = []
    for q in quotes:
        if q.result not in ("missing", "section_only"):
            continue
        section = by_number.get(q.section)
        text = section.text if section else ""
        ratio, snippet = _best_window(q.phrase, text) if text else (0.0, "")
        if q.result == "section_only":
            kind = "unit"
        elif section is None:
            kind = "no_section"
        elif _squash(q.phrase) and _squash(q.phrase) in _squash(text):
            kind = "spacing"
        elif _digits_flipped(q.phrase) != q.phrase and _digits_flipped(q.phrase) in text:
            kind = "digits_order"
        elif ratio >= 0.8:
            kind = "near_miss"
        elif any(_typo(q.phrase) in _typo(o.text) for o in bill.sections if o is not section):
            kind = "other_section"
        elif _typo(q.phrase) in _typo(whole):
            kind = "outside_bill"
        else:
            kind = "absent"
        where = ""
        if kind in ("other_section", "outside_bill"):
            hits = [o.number for o in bill.sections if _typo(q.phrase) in _typo(o.text)]
            i = _typo(whole).find(_typo(q.phrase))
            where = f"סעיפים: {hits[:6]} | הקשר: {_typo(whole)[max(0, i - 60):i + 60]}" if i >= 0 else f"סעיפים: {hits[:6]}"
        out.append({**asdict(q), "diagnosis": kind, "ratio": round(ratio, 2), "closest": snippet[:160],
                    "where": where})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    files = list(args.files) + (sorted(args.dir.glob("*.pdf")) if args.dir else [])
    all_quotes, summaries = [], []
    for f in files:
        try:
            quotes, summary = check(f)
        except Exception as exc:  # noqa: BLE001
            summaries.append({"file": f.name, "error": f"{type(exc).__name__}: {exc}"[:300]})
            print(f"{f.name}: שגיאה - {exc}")
            continue
        all_quotes += quotes
        summaries.append(summary)
        print(f"{f.name}: {summary['quotes']} ציטוטים - {summary['counts']}")
        if args.verbose:
            for q in quotes:
                if q.result != "exact":
                    print(f"   [{q.result}] הסתייגות {q.reservation} ({q.heading}, {q.unit or '-'}, {q.kind}): {q.phrase}")
    total = len(all_quotes)
    found = sum(q.result in ("exact", "typography", "inner_quotes") for q in all_quotes)
    exact = sum(q.result == "exact" for q in all_quotes)
    if total:
        print(f"\nסה\"כ: {total} ציטוטים ב-{len(files)} קבצים - נמצאו {found} ({100 * found / total:.1f}%), "
              f"מתוכם מילה במילה {exact} ({100 * exact / total:.1f}%)")
    if args.json:
        args.json.write_text(json.dumps({"summaries": summaries,
                                         "quotes": [asdict(q) for q in all_quotes]},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
