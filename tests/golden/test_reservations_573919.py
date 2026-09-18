"""מבחן זהב: הגנרטור מול 484 הסתייגויות שהוגשו בפועל לכנסת.

**נכתב לפני הגנרטור, במכוון** (ברק, 2026-09-18). זה המבחן שקובע אם
מצב הכמות מייצר הסתייגויות אמיתיות ולא משהו שנראה סביר.

**המקור:** הצעת חוק חומרי נפץ (תיקון מס' 4 – הוראת שעה) (תיקון),
התש"ף–2020, שהונחה לקריאה שנייה ושלישית ב-16.6.2020 בצירוף 484
הסתייגויות מקבוצת ח"כים אחת, כולן לסעיף 1.
`tests/fixtures/reservations/573919.docx`.

**הטענה שנבדקת, וניתן להפריך אותה:** כל הסתייגות שהגנרטור שלנו
מייצר בדפוסים `במקום`/`אחרי` חייבת להופיע **בפועל** ברשימה שהוגשה
לכנסת. כלומר הגנרטור הוא **תת-קבוצה** של מה שבן אדם כתב.

למה תת-קבוצה ולא שוויון: רשימת הערכים שהמסתייגים בחרו (2 עד 50,
99, שנים 1948–1996) היא בחירה שלהם, לא כלל. אנחנו לא מתיימרים
לשחזר אותה — אנחנו מתיימרים שלא להמציא הסתייגות שאדם לא היה כותב.

**מה שהטסט הזה לא בודק:** האם ייצרנו *מספיק*. זו שאלה של תשואה
(`מדידת שני המספרים`), לא של תקינות.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

FIXTURE = ROOT / "tests" / "fixtures" / "reservations" / "573919.json"

# שני הדפוסים שהגנרטור אמור לכסות. השאר ("בסופו יבוא" - טקסט חופשי;
# "המילה X - תימחק" - מחיקת מילה) מחוץ להיקף בכוונה: הראשון הוצא
# מהמנוע לפי CLAUDE.md חוק ברזל 8, השני נמדד כשולי (מילה אחת מתוך 43).
_REPLACE_RE = re.compile(r'^במקום "(?P<old>[^"]+)" יבוא "(?P<new>[^"]+)"\.$')
_AFTER_RE = re.compile(r'^אחרי "(?P<anchor>[^"]+)" יבוא "(?P<new>[^"]+)"\.$')


def _normalize(text: str) -> str:
    """השוואה עמידה לרווחים כפולים ולתווי כיווניות, שנפוצים במסמכי
    Word אמיתיים ואינם הבדל אמיתי בין שתי הסתייגויות."""
    return re.sub(r"\s+", " ", text.replace("‏", "").replace("‎", "")).strip()


def main():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    section = data["section_text"]
    real = {_normalize(r) for r in data["reservations"]}

    human_anchors = set()
    for item in real:
        m = _REPLACE_RE.match(item) or _AFTER_RE.match(item)
        if m:
            human_anchors.add(m.group(1))
    in_scope = {r for r in real if _REPLACE_RE.match(r) or _AFTER_RE.match(r)}
    print(f"הוגשו בפועל: {len(real)}, מהן {len(in_scope)} בדפוסים שבהיקף")
    print(f"עוגנים אנושיים: {sorted(human_anchors)}")

    from anchors import find_anchors  # noqa: PLC0415
    from generate import quantity_reservations  # noqa: PLC0415

    generated = quantity_reservations(section)
    print(f"נוצרו: {len(generated)} מתוך {len({g.anchor for g in generated})} עוגנים")

    ok = True

    def check(name, passed, detail=""):
        nonlocal ok
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name, detail if not passed else "")

    # ── תנאי 1: פורמט ──────────────────────────────────────────────
    bad_format = [g.text for g in generated
                  if not (_REPLACE_RE.match(g.text) or _AFTER_RE.match(g.text))]
    check("פורמט: כל הסתייגות תואמת לאחד משני הדפוסים",
          not bad_format, f"{len(bad_format)} חריגות, למשל {bad_format[:2]}")

    # ── תנאי 2: עיגון ──────────────────────────────────────────────
    ungrounded = sorted({g.anchor for g in generated if g.anchor not in section})
    check("עיגון: כל עוגן מופיע בנוסח מילה במילה",
          not ungrounded, f"לא נמצאו בנוסח: {ungrounded}")

    # ── תנאי 3: שומר הציטוט ────────────────────────────────────────
    # **מנוסח צר יותר מ"תת-קבוצה של העוגנים האנושיים", ובכוונה.**
    # בדיקת תת-קבוצה מלאה נכשלת על מקרה תקין: בנוסח כתוב "סעיף 22(ב)",
    # אנחנו עוגנים ב-"22" (שקיים מילה במילה) ואילו המסתייגים כתבו
    # "22ב" (שאינו קיים בנוסח כצורתו). העוגן שלנו מעוגן *יותר* משלהם,
    # ולכן כישלון כזה היה מודד את הדבר הלא נכון.
    # מה שכן נבדק הוא הליבה שניתנת להפרכה: חמשת הערכים שיושבים בתוך
    # ציטוטי שם החוק - ואיש מ-484 המסתייגים לא נגע באף אחד מהם.
    in_citation = {a.text for a in find_anchors(section) if a.in_law_citation}
    used = {g.anchor for g in generated}
    leaked = sorted(in_citation & used)
    check(f"שומר הציטוט: לא עוגן באף אחד מ-{len(in_citation)} הערכים שבתוך ציטוט שם חוק",
          not leaked, f"דלפו: {leaked}")
    print(f"     (הערכים שבציטוט: {sorted(in_citation)})")
    check("ושאיש מהמסתייגים לא עגן בהם - הראיה לכלל",
          not (in_citation & human_anchors))

    # ── מידע, לא תנאי מעבר ─────────────────────────────────────────
    texts = {_normalize(g.text) for g in generated}
    print(f"\nמידע: {len(texts & real)} מההסתייגויות שיצרנו הוגשו בפועל "
          f"({len(texts & real) * 100 // max(len(texts), 1)}%)")
    print(f"מידע: העוגנים שלנו {sorted(used)} מול האנושיים {sorted(human_anchors)}")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
