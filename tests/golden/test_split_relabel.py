"""מקרה זהב: התוכן הקיים מקבל תווית **וגם** משתנה - שתי הוראות (ח11-ג, 26.9).

**המקור - החוברת הסגולה, §7.10.6(ד), עמ' 29 [PDF 58], ההערה, מילה במילה:**

    לעתים רוצים להוסיף סעיף קטן לסעיף שאינו כולל סעיפים קטנים וכן לתקן את
    תוכן הסעיף הקיים. במקרה כזה יש לפצל את התיקון כלהלן:
    בסעיף מס' הסעיף לחוק העיקרי -
    (1) האמור בו יסומן "(א)", ובו, במקום "טקסט בסעיף הקיים" יבוא "טקסט חדש";
    (2) אחרי סעיף קטן (א) יבוא:
    "(ב) תוכן הסעיף הקטן החדש".
    דוגמה: בחוק רשות הספנות והנמלים, התשס"ד-2004, בסעיף 6 -
    (1) האמור בו יסומן "(א)", ובו, במקום "בתחום פעולה" יבוא "בתחומי פעולה";
    (2) אחרי סעיף קטן (א) יבוא:
    "(ב) על אף הוראות סעיף קטן (א) לא יינתן רישיון לתקופה העולה על חמש שנים".

**ומרשומות** (reference/reshumot-1924-government-bills.pdf):
- עמ' 694 [PDF 89], סעיף 59 - אותו פיצול ברמת הסעיף:
  `בסעיף 28א - (1) האמור בו יסומן "(א)" ובו, בפסקה (5), בסופה יבוא "..."; (2) אחרי סעיף קטן (א) יבוא: "(ב) ..."`
- עמ' 897 [PDF 292], (יט) - ברמה שמתחת לסעיף, בהגדרה:
  `בהגדרה "פרט מזהה" - (1) האמור בה יסומן כפסקה (1), ובה, לפני "שם פרטי" יבוא "..."; ... (3) אחרי פסקה (1) יבוא: "(2) ..."`
- עמ' 672 [PDF 67], (3) - הפיצול כתת-פריטים בתוך הוראה של כמה פריטים:
  `(3) בסעיף 10 - (א) האמור בו יסומן "(א)", ובו, בפסקה (7), אחרי "..." יבוא "..."; (ב) בסופו יבוא:`
- עמ' 676 [PDF 71], (8) - התווית "(1)" ברמת הסעיף הקטן (ח11-ב):
  `בסעיף 34(א), האמור בו יסומן "(1)" ואחריו יבוא: "(2) ..."`

**ההבדל היחיד מהדוגמה:** המנוע מצטט את המילה שהשתנתה בלבד - `במקום "בתחום"
יבוא "בתחומי"` - כמו בכל החלפת מילים במערכת; החוברת מצטטת "בתחום פעולה".

**ארבעה מקרים, כולם דרך apply_pending_changes - אותו מסלול כמו הממשק** (עריכת
מילים ביחידה + הוספה שהופכת אותה ל-(א)/(1)):
1. **הדוגמה של החוברת עצמה** - חוק רשות הספנות והנמלים, סעיף 6, שבמאגר עדיין
   בנוסח שהחוברת מתקנת (tests/fixtures/wikitext/sapanut-2004.wikitext, אותה גרסה
   כמו ב-DB, 2923586). הפלט חייב להיות הדוגמה.
2. ברמת הסעיף הקטן - חוק הקייטנות, 6(א) הופך ל-6(א)(1) וגם משתנה.
3. אותו דבר בתוך הוראה של כמה פריטים (גם 6(ב) משתנה) - תת-פריטים (א)/(ב).
4. ברמת הסעיף בתוך הוראה של כמה פריטים (גם כותרת השוליים משתנה) - הפריטים
   שטוחים, כמו בהגדרה בעמ' 897.

**על הקוד הקודם:** מקרים 2-3 נדחו ("לא נתמך בכלי העריכה"), ומקרים 1 ו-4
**איבדו את העריכה בשקט** - "האמור בו יסומן "(א)" ואחריו יבוא", בלי "בתחומי".
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
for sub in ("packages/corpus", "packages/render", "packages/amend", "apps/api"):
    sys.path.insert(0, str(ROOT / sub))

from wikitext_parser import parse_wikitext  # noqa: E402
from engine import amend  # noqa: E402
from apply_changes import apply_pending_changes  # noqa: E402
from parse_instructions import parse_instructions  # noqa: E402
from merge import build_merged_text  # noqa: E402

FX = ROOT / "tests/fixtures/wikitext"
BOOKLET_NEW = "על אף הוראות סעיף קטן (א) לא יינתן רישיון לתקופה העולה על חמש שנים"
KAYTANOT_NEW = "על אף האמור בפסקה (1), תקנות לפי סעיף קטן זה טעונות אישור ועדת החינוך של הכנסת."


def _load(name: str, law_id: str):
    meta = json.loads((FX / f"{name}.meta.json").read_text(encoding="utf-8"))
    return parse_wikitext((FX / f"{name}.wikitext").read_text(encoding="utf-8"),
                          law_id=law_id, as_of=meta["revision_timestamp"])


def _find(node, node_id):
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find(child, node_id)
        if found is not None:
            return found
    return None


def _edit(node, old: str, new: str, field: str = "text"):
    source = node.margin_title if field == "margin_title" else node.text
    assert old in source, (old, source)
    return NS(node_id=node.id, text=source.replace(old, new, 1), field=field)


def _insert(anchor_id: str, kind: str, text: str):
    return NS(kind=kind, anchor_node_id=anchor_id, text=text, client_id="new-1", margin_title=None)


def _run(before, edits, insertions):
    result = apply_pending_changes(before, edits, insertions)
    problems = [e.reason for e in result.edit_statuses if not e.ok] + \
        [e.reason for e in result.insertion_errors]
    assert not problems, problems
    return result, amend(before, result.after, result.annotations, law_footnote_key="law")


def _rows(lines):
    """(מספר, תווית פריט, עומק, הטקסט המלא) לכל שורה."""
    return [(ln.number, ln.marker, ln.depth, (ln.text + ln.text_after).strip()) for ln in lines]


def _merged_units(before, lines, unit_id):
    plan = parse_instructions([(ln.marker or ln.number or "", ln.text + ln.text_after) for ln in lines])
    if not plan.ok:
        return None, plan.blocking_reason
    merged = build_merged_text(before, plan)
    if merged.tree is None:
        return None, merged.error
    unit = _find(merged.tree, unit_id)
    return unit, ""


def main() -> int:
    checks = []

    # ── 1. הדוגמה של החוברת: חוק רשות הספנות והנמלים, סעיף 6 ─────────────
    sap = _load("sapanut-2004", "law-2001205")
    s6_body = _find(sap, "law-2001205/פרק ב/s6/p0")
    _, lines = _run(sap, [_edit(s6_body, "בתחום פעולה", "בתחומי פעולה")],
                    [_insert(s6_body.id, "subsection", BOOKLET_NEW)])
    want = [
        ("1.", "", 0, 'בחוק רשות הספנות והנמלים, התשס"ד–2004, בסעיף 6 –'),
        # ההבדל היחיד מהחוברת: המנוע מצטט את המילה שהשתנתה בלבד ("בתחום"), כמו
        # בכל החלפת מילים (diff_translate - השוואה על מילים); החוברת מצטטת
        # "בתחום פעולה". זו מוסכמת הציטוט הקיימת, לא חלק מהפיצול.
        ("", "(1)", 0, 'האמור בו יסומן "(א)", ובו, במקום "בתחום" יבוא "בתחומי";'),
        ("", "(2)", 0, "אחרי סעיף קטן (א) יבוא:"),
        ("", "", 0, f'"(ב) {BOOKLET_NEW}".'),
    ]
    got = _rows(lines)
    checks.append(("1. הדוגמה של החוברת, מילה במילה", got == want, "\n      ".join(map(repr, got))))
    checks.append(("1. כותרת השוליים", lines and lines[0].side_heading == "תיקון סעיף 6",
                   lines[0].side_heading if lines else ""))
    unit, why = _merged_units(sap, lines, "law-2001205/פרק ב/s6")
    kids = [(c.number, c.text) for c in unit.children if c.is_normative] if unit else []
    checks.append(("1. הנוסח המשולב קורא את ההוראה: (א) מתוקן, (ב) חדש",
                   kids == [("(א)", s6_body.text.replace("בתחום פעולה", "בתחומי פעולה")),
                            ("(ב)", BOOKLET_NEW)], why or repr(kids)))

    # ── 2. ברמת הסעיף הקטן: קייטנות 6(א) -> 6(א)(1) וגם משתנה ─────────────
    kay = _load("kaytanot", "kaytanot-1990")
    sub_a = _find(kay, "kaytanot-1990/s6/א")
    _, lines = _run(kay, [_edit(sub_a, "ובטחון", "וביטחון")],
                    [_insert(sub_a.id, "paragraph", KAYTANOT_NEW)])
    want = [
        ("1.", "", 0, 'בחוק הקייטנות (רישוי ופיקוח), התש"ן–1990, בסעיף 6(א) –'),
        ("", "(1)", 0, 'האמור בו יסומן "(1)", ובו, במקום "ובטחון" יבוא "וביטחון";'),
        ("", "(2)", 0, "אחרי פסקה (1) יבוא:"),
        ("", "", 0, f'"(2) {KAYTANOT_NEW}".'),
    ]
    got = _rows(lines)
    checks.append(("2. סעיף קטן: שתי הוראות", got == want, "\n      ".join(map(repr, got))))
    unit, why = _merged_units(kay, lines, sub_a.id)
    kids = [(c.number, c.text) for c in unit.children if c.is_normative] if unit else []
    checks.append(("2. הנוסח המשולב: (1) מתוקן, (2) חדש",
                   kids == [("(1)", sub_a.text.replace("ובטחון", "וביטחון")), ("(2)", KAYTANOT_NEW)],
                   why or repr(kids)))

    # ── 3. אותו דבר בתוך הוראה של כמה פריטים (גם 6(ב) משתנה) ──────────────
    sub_b = _find(kay, "kaytanot-1990/s6/ב")
    _, lines = _run(kay, [_edit(sub_a, "ובטחון", "וביטחון"), _edit(sub_b, "יחולו", "יחולו גם")],
                    [_insert(sub_a.id, "paragraph", KAYTANOT_NEW)])
    got = _rows(lines)
    want_head = [
        ("1.", "", 0, 'בחוק הקייטנות (רישוי ופיקוח), התש"ן–1990, בסעיף 6 –'),
        ("", "(1)", 0, "בסעיף קטן (א) –"),
        ("", "(א)", 1, 'האמור בו יסומן "(1)", ובו, במקום "ובטחון" יבוא "וביטחון";'),
        ("", "(ב)", 1, "אחרי פסקה (1) יבוא:"),
        ("", "", 1, f'"(2) {KAYTANOT_NEW}";'),
    ]
    checks.append(("3. כמה פריטים: (1) בסעיף קטן (א) – ותת-פריטים (א)/(ב)",
                   got[:5] == want_head, "\n      ".join(map(repr, got))))
    checks.append(("3. הפריט הבא ממוספר (2) ומסתיים בנקודה",
                   len(got) == 6 and got[5][1] == "(2)" and got[5][3].startswith("בסעיף קטן (ב),")
                   and got[5][3].endswith("."), repr(got[5:])))

    # ── 4. ברמת הסעיף בתוך כמה פריטים (גם כותרת השוליים) - פריטים שטוחים ───
    section6 = _find(sap, "law-2001205/פרק ב/s6")
    _, lines = _run(sap, [_edit(section6, "תקציב הרשות", "תקציב הרשות ומימונה", field="margin_title"),
                          _edit(s6_body, "בתחום פעולה", "בתחומי פעולה")],
                    [_insert(s6_body.id, "subsection", BOOKLET_NEW)])
    got = _rows(lines)
    markers = [row[1] for row in got]
    checks.append(("4. ברמת הסעיף: (1) כותרת, (2) יסומן, (3) אחרי סעיף קטן (א)",
                   markers == ["", "(1)", "(2)", "(3)", ""]
                   and got[2][3] == 'האמור בו יסומן "(א)", ובו, במקום "בתחום" יבוא "בתחומי";'
                   and got[3][3] == "אחרי סעיף קטן (א) יבוא:"
                   and got[4][3] == f'"(ב) {BOOKLET_NEW}".', "\n      ".join(map(repr, got))))

    # ── בלי ניסוח שגוי בשום מקרה ─────────────────────────────────────────
    checks.append(('בלי "ואחריו יבוא" כשהתוכן גם משתנה (הניסוח שבלע את העריכה)',
                   not any("ואחריו יבוא" in r[3] for r in got), ""))

    bad = [c for c in checks if not c[1]]
    for name, ok, info in checks:
        print(("OK   " if ok else "FAIL "), name, "" if ok else f"\n      {info}")
    print("\nתוצאה:", "עבר" if not bad else f"נכשל ({len(bad)})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
