"""מקרה זהב: "(א) הופך ל-(א)(1)" - פסקה ראשונה בסעיף קטן שאין בו פסקאות (ח11-ב, 26.9).

**הבדיקה היא על הניסוח המלא** - תצוגה מקדימה בממשק, העץ אחרי השינוי,
וההוראה עצמה, מילה במילה.

**המקור לניסוח.** בחוברת הסגולה הדפוס קיים רק ברמת הסעיף - §7.10.6(ד),
עמ' 29-30: `בסעיף 6, האמור בו יסומן "(א)" ואחריו יבוא: "(ב) ..."`. ברמת
הסעיף הקטן - **תקדים אמיתי מרשומות**: הצעת חוק הממשלה 1924, עמ' 676
(reference/reshumot-1924-government-bills.pdf, עמ' PDF 71), פריט (8):

    בסעיף 34(א), האמור בו יסומן "(1)" ואחריו יבוא:
    "(2) על אף האמור בפסקה (1), היה התאגיד הבנקאי בנק קטן ..."

כלומר: הסעיף הקטן הוא המכולה (בסוגריים על מספר הסעיף, כמו §8.7 ב-
drafting-rules), "האמור בו יסומן "(1)"", והפסקה החדשה (2) במרכאות.
ב-40 ההצעות האמיתיות אין מופע של הדפוס הזה (יש אחד ברמת הסעיף, 13948380).

**החוק:** חוק הקייטנות (רישוי ופיקוח) (tests/fixtures/wikitext/kaytanot.wikitext),
סעיף 6(א) - "השר ממונה על ביצוע חוק זה והוא רשאי להתקין תקנות..." - סעיף
קטן אמיתי בלי פסקאות. הוראה יחידה - שורה אחת, בלי "(להלן – החוק העיקרי)"
(drafting-rules §5.8).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))
sys.path.insert(0, str(ROOT / "packages" / "render"))
sys.path.insert(0, str(ROOT / "packages" / "amend"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

import json  # noqa: E402

from wikitext_parser import parse_wikitext  # noqa: E402
from engine import amend  # noqa: E402
from transform import apply  # noqa: E402
from insert_preview import build_insertion_transform, preview_insertion_label  # noqa: E402

UNIT_ID = "kaytanot-1990/s6/א"
NEW_TEXT = "על אף האמור בפסקה (1), תקנות לפי סעיף קטן זה טעונות אישור ועדת החינוך של הכנסת."


def _load():
    fx = ROOT / "tests/fixtures/wikitext"
    meta = json.loads((fx / "kaytanot.meta.json").read_text(encoding="utf-8"))
    text = (fx / "kaytanot.wikitext").read_text(encoding="utf-8")
    return parse_wikitext(text, law_id="kaytanot-1990", as_of=meta["revision_timestamp"])


def _find(node, node_id):
    if node.id == node_id:
        return node
    for c in node.children:
        f = _find(c, node_id)
        if f is not None:
            return f
    return None


def main() -> int:
    checks = []
    before = _load()
    unit = _find(before, UNIT_ID)
    old_text = unit.text
    checks.append(("סעיף 6(א) קיים, בלי פסקאות", unit is not None and not unit.children, UNIT_ID))

    # שכבה 1 - התפריט: המשתמש עומד על (א) ובוחר "פסקה". עד כאן - לא נתמך.
    preview = preview_insertion_label(before, UNIT_ID, "paragraph")
    checks.append(("תצוגה מקדימה: נתמך", preview.supported, str(preview.reason)))
    checks.append(('תצוגה מקדימה: התווית "(2)"', preview.label == "(2)", str(preview.label)))

    # שכבה 2 - העץ: הנוסח הקיים עבר לפסקה (1) בלי שינוי, (2) חדשה אחריה.
    transform, reason = build_insertion_transform(before, UNIT_ID, "paragraph", text=NEW_TEXT,
                                                  new_id="kaytanot-1990/s6/א/2")
    checks.append(("נבנתה טרנספורמציה", transform is not None, str(reason)))
    after, annotations = apply(before, [transform])
    unit_after = _find(after, UNIT_ID)
    kids = [(c.number, c.text) for c in unit_after.children]
    checks.append(("(א) ריק, ובתוכו (1) = הנוסח הקיים, (2) = החדש",
                   unit_after.text == "" and kids == [("(1)", old_text), ("(2)", NEW_TEXT)], str(kids)[:200]))
    checks.append(("'לפני' לא השתנה", _find(before, UNIT_ID).text == old_text, ""))

    # שכבה 3 - הניסוח המלא.
    lines = amend(before, after, annotations, law_footnote_key="kaytanot")
    got = [(ln.number, ln.side_heading, ln.text, ln.text_after) for ln in lines]
    want = [
        ("1.", "תיקון סעיף 6", "בחוק הקייטנות (רישוי ופיקוח), התש\"ן–1990",
         ', בסעיף 6(א), האמור בו יסומן "(1)" ואחריו יבוא:'),
        ("", None, f'"(2) {NEW_TEXT}".', ""),
    ]
    checks.append(("שתי שורות: הכתובת והתוכן המצוטט", len(lines) == 2, str(len(lines))))
    if len(lines) == 2:
        checks.append(("הכתובת", got[0] == want[0], repr(got[0])))
        checks.append(("התוכן המצוטט", (lines[1].text, lines[1].text_after) == want[1][2:], repr(got[1])))
        checks.append(("בלי ניסוח שגוי: מחיקה/החלפה של הנוסח הקיים",
                       not any("יימחק" in (ln.text + ln.text_after) or "במקום" in (ln.text + ln.text_after)
                               for ln in lines), ""))

    # שכבה 4 - הנוסח המשולב: ההוראה שהמערכת כתבה נקראת בחזרה, ומייצרת את
    # אותו עץ. עד כאן merge עצר על "(1)/(2)" - הדפוס הוגדר רק על (א)/(ב).
    from parse_instructions import parse_instructions  # noqa: E402
    from merge import build_merged_text  # noqa: E402
    plan = parse_instructions([(ln.number or "", ln.text + ln.text_after) for ln in lines])
    merged = build_merged_text(before, plan)
    unit_merged = _find(merged.tree, UNIT_ID) if merged.tree else None
    got_kids = [(c.number, c.text) for c in unit_merged.children] if unit_merged else []
    checks.append(("הנוסח המשולב: (1) הקיים ו-(2) החדש, כמו בעץ",
                   got_kids == [("(1)", old_text), ("(2)", NEW_TEXT)], repr(merged.error or got_kids[-1:])))

    bad = [c for c in checks if not c[1]]
    for name, ok, info in checks:
        print(("OK   " if ok else "FAIL "), name, "" if ok else f"-- {info}")
    print("\nתוצאה:", "עבר" if not bad else f"נכשל ({len(bad)})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
