"""נרמול שם הצעה לצורך איתור הצעות דומות - ברק, 22.9.

**למה זה חשוב יותר ממה שזה נראה:** הבדיקה הזו היא מה שהחוברת
הסגולה מחייבת לפני הנחת הצעה - לוודא שאין כבר הצעה זהה או דומה.
כל מילה שנשארת בהשוואה ואינה קשורה לנושא **מורידה** את הציון של
הצעה זהה, ועלולה להוריד אותה מתחת לסף ולהעלים אותה מהרשימה.

**מה שנמדד ותוקן:** שתי הצעות זהות לחלוטין משנים שונות קיבלו
ז'קארד **0.600 במקום 1.000** - השנה הלועזית שרדה כמילה בת ארבעה
תווים. מספר התיקון כבר היה מנוטרל.

הבדיקה טהורה - בלי רשת ובלי הפיד של הכנסת.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from knesset_bills import _core_terms, _words  # noqa: E402


def _jaccard(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    if not (wa | wb):
        return 0.0
    return len(wa & wb) / len(wa | wb)


KAYTANOT_2026 = 'הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון מס\' 12), התשפ"ו-2026'
KAYTANOT_2023 = 'הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון מס\' 3), התשפ"ג-2023'
KAYTANOT_1998 = 'הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון), התשנ"ח-1998'
YERUSHA_2026 = 'הצעת חוק הירושה (תיקון מס\' 23), התשפ"ו-2026'


def main() -> int:
    checks = []

    def check(name, passed, got=""):
        checks.append((name, bool(passed), str(got)))

    words = _words(KAYTANOT_2026)
    check("נשארות רק מילות הנושא", words == {"הקייטנות", "רישוי", "ופיקוח"}, str(sorted(words)))

    same_topic = _jaccard(KAYTANOT_2026, KAYTANOT_2023)
    check("הצעות זהות משנים שונות - התאמה מלאה", same_topic == 1.0, f"{same_topic:.3f}")

    old_knesset = _jaccard(KAYTANOT_2026, KAYTANOT_1998)
    check("גם מול כנסת ישנה בהרבה - התאמה מלאה", old_knesset == 1.0, f"{old_knesset:.3f}")

    # **הצד השני של הכלל**: נרמול-יתר היה גורם להצעות שאינן קשורות
    # להיראות דומות. מילות הנושא חייבות להישאר.
    other_topic = _jaccard(KAYTANOT_2026, YERUSHA_2026)
    check("נושא אחר לגמרי - אין התאמה", other_topic == 0.0, f"{other_topic:.3f}")

    # שנה לועזית ועברית - שתיהן. השנה העברית מגיעה בהטיות רבות.
    for year in ("2026", "1990", "1998", "התשפ", "התשנח", "התשעד"):
        check(f"השנה {year!r} אינה מילת תוכן", year not in _words(f"חוק הקייטנות {year}"), year)

    # מספר התיקון - היה מנוטרל כבר קודם, ונועל כאן שלא ייפול בעתיד.
    check("מספר התיקון אינו משתתף",
          _words("הצעת חוק הקייטנות (תיקון מס' 12)") == {"הקייטנות"},
          str(sorted(_words("הצעת חוק הקייטנות (תיקון מס' 12)"))))

    # **מחרוזת שאינה שנה חייבת לשרוד**: הסינון על שנים לא יכול
    # לבלוע מספרים שהם חלק מהנושא.
    check("מספר שאינו שנה נשאר (למשל 'ערוץ 2')",
          "2026" not in _words("חוק הקייטנות") and _core_terms(KAYTANOT_2026),
          str(_core_terms(KAYTANOT_2026)))

    ok = all(passed for _, passed, _ in checks)
    for name, passed, got in checks:
        print(("OK   " if passed else "FAIL "), name)
        if not passed:
            print(f"        got: {got}")
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
