"""מבחן זהב: הכלי החדש (בנייה מחדש, 26.9) מול 484 הסתייגויות שהוגשו בפועל לכנסת.

**המקור:** הצעת חוק חומרי נפץ (תיקון מס' 4 – הוראת שעה) (תיקון), התש"ף–2020,
שהונחה לקריאה שנייה ושלישית ב-16.6.2020 בצירוף 484 הסתייגויות מקבוצת ח"כים
אחת, כולן לסעיף 1. `tests/fixtures/reservations/573919.docx` - **קלט Word**
(הכלי קורא PDF בעיקר; Word נשאר נתמך - זה המבחן שלו).

**הטענה שנבדקת, וניתן להפריך אותה:** כל עוגן שהכלי מחליף ("במקום X") הוא עוגן
שבני אדם בחרו בפועל בהצעה הזו - או תחילית שלו שמופיעה בנוסח מילה במילה
("22" מול "22ב" של המסתייגים; בנוסח כתוב "סעיף 22(ב)", ו-"22ב" אינו מופיע
כצורתו). ושום עוגן לא יושב בתוך ציטוט שם חוק (86(ד)(3)) - איש מ-484 לא עשה זאת.

**מה לא נבדק:** אם ייצרנו *מספיק* - זו תשואה, לא תקינות.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

from anchors import find_anchors  # noqa: E402
from bill_input import read_bill  # noqa: E402
import families  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "reservations"
_REPLACE_RE = re.compile(r'^במקום "(?P<old>[^"]+)" יבוא "(?P<new>[^"]+)"\.$')


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("‏", "").replace("‎", "")).strip()


def main():
    data = json.loads((FIXTURE / "573919.json").read_text(encoding="utf-8"))
    real = {_normalize(r) for r in data["reservations"]}
    human = {m.group("old") for m in map(_REPLACE_RE.match, real) if m}
    bill = read_bill("573919.docx", (FIXTURE / "573919.docx").read_bytes())
    text = " ".join(s.text for s in bill.sections)

    ok = True

    def check(name, passed, detail=""):
        nonlocal ok
        ok = ok and bool(passed)
        print(("OK  " if passed else "FAIL"), name, detail if not passed else "")

    check("Word: נקרא סעיף 1, עם שם ההצעה", [s.number for s in bill.sections] == ["1"]
          and bill.title.startswith("חוק חומרי נפץ"), f"{bill.title!r} {[s.number for s in bill.sections]}")
    in_citation = {a.text for a in find_anchors(text) if a.in_law_citation}
    for level in families.bank_mod.LEVELS:
        p = families.plan(bill, level, list(families.FAMILIES), 1000)
        check(f"{level}: נוצרו הסתייגויות", p.items, "0")
        replaced = [m.group("old") for m in (_REPLACE_RE.match(it.text) for it in p.items) if m]
        check(f"{level}: כל הסתייגות בצורה 'במקום \"X\" יבוא \"Y\".'", len(replaced) == len(p.items),
              str([it.text for it in p.items if not _REPLACE_RE.match(it.text)][:3]))
        check(f"{level}: כל עוגן מופיע בנוסח מילה במילה", all(a in text for a in replaced),
              str([a for a in replaced if a not in text]))
        foreign = sorted({a for a in replaced if a not in human and not any(h.startswith(a) for h in human)})
        check(f"{level}: כל עוגן - עוגן שבני אדם בחרו (או תחילית שלו)", not foreign, str(foreign))
        leaked = sorted(set(replaced) & in_citation)
        check(f"{level}: אף עוגן בתוך ציטוט שם חוק ({sorted(in_citation)})", not leaked, str(leaked))
        same = len({it.text for it in p.items} & real)
        print(f"     מידע: {same} מתוך {len(p.items)} הוגשו בפועל מילה במילה")
    check("ושאיש מהמסתייגים לא עגן בציטוט שם חוק - הראיה לכלל", not (in_citation & human))

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
