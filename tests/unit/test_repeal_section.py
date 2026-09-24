"""ח3 (25.9.2026): "אי אפשר למחוק סעיף".

ברק מחק את כל הטקסט של סעיף ואת כותרת השוליים שלו. מה שקרה עד כאן:
- מחיקת כל הטקסט - הוראת התיקון **נעלמה בשקט** (אפס שורות בהצעה);
- מחיקת כותרת השוליים - `בכותרת השוליים, במקום "הרכב" יבוא ""`,
  ניסוח שאינו קיים.
מחיקת סעיף שלם היא ביטול: "סעיף N – בטל" (מדריך משפטים §7.13, עמ' 32;
drafting-rules.md §1.1 שורה 8), וכותרת השוליים "ביטול סעיף N".
בהוראה יחידה - פותחים בשם החוק, בלי "(להלן – החוק העיקרי)":
`בחוק הגנת הצרכן, התשמ"א–1981, סעיף 39 – בטל.` (הצעה אמיתית, §5.8).
"""

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("apps/api", "packages/corpus", "packages/amend", "packages/render"):
    sys.path.insert(0, str(ROOT / sub))

from node import LegislativeNode  # noqa: E402
from apply_changes import apply_pending_changes  # noqa: E402
from engine import amend  # noqa: E402


@dataclass
class _Edit:
    node_id: str
    text: str
    field: str = "text"


def _tree() -> LegislativeNode:
    def sec(n, title, *children):
        return LegislativeNode(id=f"law/s{n}", node_type="section", number=str(n),
                               margin_title=title, text="", children=list(children))

    def par(id_, text, number=""):
        return LegislativeNode(id=id_, node_type="paragraph" if not number else "subsection",
                               number=number, margin_title=None, text=text)

    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, full_title='חוק לדוגמה, התש"ף–2020',
        children=[
            sec(1, "הגדרות", par("law/s1/p0", "בחוק זה - קייטנה היא מקום נופש.")),
            sec(2, "הרכב", par("law/s2/p0", "בית המשפט ידון בשלושה שופטים.")),
            sec(3, "סמכות",
                par("law/s3/a", "השר רשאי לקבוע כללים.", "(א)"),
                par("law/s3/b", "הכללים יפורסמו ברשומות.", "(ב)")),
        ],
    )


def _lines(edits):
    before = _tree()
    result = apply_pending_changes(before, edits, [])
    lines = amend(before, result.after, result.annotations, law_footnote_key="law")
    return result, lines


def _full(line):
    return line.text + line.text_after


def main() -> int:
    checks = []

    # 1. כל הטקסט + כותרת השוליים נמחקו - הוראה יחידה
    result, lines = _lines([_Edit("law/s2/p0", ""), _Edit("law/s2", "", "margin_title")])
    checks.append(("מחיקת סעיף שלם מפיקה שורה אחת", len(lines) == 1, [_full(l) for l in lines]))
    if lines:
        checks.append(("הוראה יחידה: 'בחוק X, סעיף 2 – בטל.'",
                       _full(lines[0]) == 'בחוק לדוגמה, התש"ף–2020, סעיף 2 – בטל.', _full(lines[0])))
        checks.append(("כותרת השוליים: 'ביטול סעיף 2'", lines[0].side_heading == "ביטול סעיף 2",
                       lines[0].side_heading))
        checks.append(("לא 'יבוא \"\"' בשום מקום", 'יבוא ""' not in _full(lines[0]), _full(lines[0])))
    checks.append(("כל העריכות סומנו כמוצלחות (לא 'לא ניתן')",
                   all(s.ok for s in result.edit_statuses), [(s.node_id, s.reason) for s in result.edit_statuses]))

    # 2. רק הטקסט נמחק (כותרת השוליים נשארה) - גם זה ביטול: סעיף בלי תוכן אינו סעיף
    _, lines = _lines([_Edit("law/s2/p0", "")])
    checks.append(("רק הטקסט נמחק - גם ביטול", len(lines) == 1 and _full(lines[0]).endswith("סעיף 2 – בטל."),
                   [_full(l) for l in lines]))

    # 3. ביטול + תיקון נוסף: "(להלן – החוק העיקרי)" ואז "סעיף 2 לחוק העיקרי – בטל."
    _, lines = _lines([_Edit("law/s1/p0", "בחוק זה - קייטנה היא מקום נופש מפוקח."),
                       _Edit("law/s2/p0", "")])
    checks.append(("שתי הוראות", len(lines) == 2, [_full(l) for l in lines]))
    if len(lines) == 2:
        checks.append(("השנייה: 'סעיף 2 לחוק העיקרי – בטל.'",
                       _full(lines[1]) == "סעיף 2 לחוק העיקרי – בטל.", _full(lines[1])))
        checks.append(("ממוספרת 2.", lines[1].number == "2.", lines[1].number))

    # 4. סעיף עם סעיפים קטנים - כולם נמחקו
    _, lines = _lines([_Edit("law/s3/a", ""), _Edit("law/s3/b", "")])
    checks.append(("סעיף עם סעיפים קטנים שכולם נמחקו - ביטול הסעיף",
                   len(lines) == 1 and _full(lines[0]).endswith("סעיף 3 – בטל."), [_full(l) for l in lines]))

    # 5. בקרה שלילית: רק חלק מהסעיפים הקטנים נמחק - **לא** ביטול הסעיף כולו
    result, lines = _lines([_Edit("law/s3/a", "")])
    checks.append(("בקרה: סעיף קטן אחד מתוך שניים - אינו ביטול של סעיף 3",
                   not any("סעיף 3 – בטל" in _full(l) for l in lines), [_full(l) for l in lines]))

    failed = 0
    for name, ok, detail in checks:
        print(("✓" if ok else "✗"), name)
        if not ok:
            failed += 1
            print("     ", detail)
    print(f"\n{len(checks) - failed}/{len(checks)} עברו")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
