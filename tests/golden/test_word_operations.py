"""ניסוח פעולות-מילים - שני באגים שהמשתמש מצא בבדיקת המוצר (22.9).

**מה המשתמש ראה, ומה הוא אמור לראות:**

| מה שעשה | מה שיצא (שגוי) | מה שצריך |
|---|---|---|
| הוסיף מילה בתחילת סעיף ומילה בסופו | `במקום "<כל הסעיף>" יבוא "<כל הסעיף>"` | `לפני "X" יבוא "Y" ובסופו יבוא "Z"` |
| מחק מילה | `במקום "X" יבוא "Y"` | `המילה "X" – תימחק` |

**שורש משותף אחד לשני הבאגים:** `diff_translate.translate_text_edit`
חישבה חלון יחיד של prefix/suffix משותפים. שני שינויים בקצוות פורשים
חלון שמשתרע על כל הטקסט (ומכאן "החלפת הסעיף כולו"), ומחיקה נפלה
לענף ההחלפה כי הוא היה היחיד שטיפל ב"משהו הוסר".

**זה לא היה במנגנון שורת-הפתיח.** האבחנה הראשונה הייתה שהמנגנון
ב-engine.py שמייצר שורת פתיח עם תת-הוראות אינו נכנס - אבל הוא נכנס
לפי **מספר ההוראות**, ומכיוון שמדובר בצומת אחד נוצרה הוראה אחת. שתי
ההוראות מעולם לא נולדו.

**המקורות לכל ניסוח:**

- `לפני "X" יבוא "Y"` — מדריך משפטים §7.10.2, עמ' 27 [PDF 56].
- `בסופו יבוא "Y"` — §7.10.2, עמ' 28 [PDF 57].
- `המילים "X" – יימחקו` — §7.10.3, עמ' 28 [PDF 57].
- חיבור כמה פעולות ב-ו' — §7.10.8, עמ' 30 [PDF 59],
  "תיקונים שלובים בסעיף אחד".

רץ אופליין על קובץ הזהב של קייטנות.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in ("packages/corpus", "packages/render", "packages/amend", "apps/api"):
    sys.path.insert(0, str(ROOT / _p))

from wikitext_parser import parse_wikitext  # noqa: E402
from apply_changes import apply_pending_changes  # noqa: E402
from engine import amend  # noqa: E402
from node import find_sections  # noqa: E402
from schemas import TextEditIn  # noqa: E402

LAW = ROOT / "tests/fixtures/wikitext/kaytanot.wikitext"
HEAD = 'בחוק הקייטנות (רישוי ופיקוח), התש"ן–1990, בסעיף 2, '


def _law():
    return parse_wikitext(LAW.read_text(encoding="utf-8"), law_id="kaytanot-1990",
                          as_of="2024-01-01T00:00:00Z")


def main() -> int:
    checks = []

    def check(name, passed, got=""):
        checks.append((name, bool(passed), str(got)))

    root = _law()
    node = find_sections(root)["2"].children[0]
    original = node.text

    cases = [
        # (שם, הנוסח החדש, הניסוח המלא הצפוי)
        ("שני תיקונים בסעיף אחד (§7.10.8)",
         "ואולם " + original[:-1] + " ובכפוף לכל דין.",
         HEAD + 'לפני "לא ינהל" יבוא "ואולם" ובסופו יבוא "ובכפוף לכל דין".'),
        ("מחיקת מילה יחידה (§7.10.3)",
         original.replace(" רישוי", ""),
         HEAD + 'המילה "רישוי" – תימחק.'),
        ("מחיקת ביטוי (§7.10.3)",
         original.replace(" לפי חוק רישוי עסקים", ""),
         HEAD + 'המילים "לפי חוק רישוי עסקים" – יימחקו.'),
        ("הוספה בתחילת הסעיף (§7.10.2)",
         "ואולם " + original,
         HEAD + 'לפני "לא ינהל" יבוא "ואולם".'),
        ("הוספה בסוף הסעיף (§7.10.2)",
         original[:-1] + " ובכפוף לכל דין.",
         HEAD + 'בסופו יבוא "ובכפוף לכל דין".'),
        # ללא רגרסיה: הדפוסים שעבדו קודם ממשיכים לעבוד בדיוק.
        ("החלפת מילים (§7.10.1) - ללא רגרסיה",
         original.replace("רשיון", "היתר"),
         HEAD + 'במקום "רשיון" יבוא "היתר".'),
        ("הוספה באמצע (§7.10.2) - ללא רגרסיה",
         original.replace("בידו", "בידו כדין"),
         HEAD + 'אחרי "בידו" יבוא "כדין".'),
    ]

    for name, new_text, want in cases:
        before = _law()
        target = find_sections(before)["2"].children[0]
        result = apply_pending_changes(
            before, [TextEditIn(node_id=target.id, field="text", text=new_text)], [])
        bad = [s for s in result.edit_statuses if not s.ok]
        check(f"{name}: העריכה התקבלה", not bad,
              str([s.reason for s in bad]))
        if bad:
            continue
        lines = amend(before, result.after, result.annotations, law_footnote_key="k")
        check(f"{name}: הוראה אחת", len(lines) == 1, str(len(lines)))
        if not lines:
            continue
        full = (lines[0].text or "") + (lines[0].text_after or "")
        check(f"{name}: הניסוח המלא", full == want, full)

    # הניסוח השגוי שהיה יוצא לפני התיקון, כשורה מפורשת שאסור לה לחזור.
    before = _law()
    target = find_sections(before)["2"].children[0]
    result = apply_pending_changes(before, [TextEditIn(
        node_id=target.id, field="text",
        text="ואולם " + original[:-1] + " ובכפוף לכל דין.")], [])
    lines = amend(before, result.after, result.annotations, law_footnote_key="k")
    full = (lines[0].text or "") + (lines[0].text_after or "") if lines else ""
    check("שני תיקונים אינם מייצרים החלפה של הסעיף כולו",
          f'במקום "{original[:-1]}"' not in full, full[:110])

    ok = all(passed for _, passed, _ in checks)
    for name, passed, got in checks:
        print(("OK   " if passed else "FAIL "), name)
        if not passed:
            print(f"        got: {got}")
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
