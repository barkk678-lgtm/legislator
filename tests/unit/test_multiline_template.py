"""תבנית שנפתחת בשורה אחת ונסגרת בשורה אחרת (הבאג הרב-שורתי).

עד 2026-09-17 `parse_wikitext` הניח שכל קריאת תבנית שלמה בשורה אחת,
ו-`_find_template` קרס ב-`IndexError` עירום כשה-`}}` הסוגר לא נמצא.
**15 חוקים בקורפוס נפלו בגלל זה, ובהם פקודת מס הכנסה, פקודת התעבורה
ופקודת החברות** - החוק כולו לא נטען.

הטסט הזה מחזיק שלושה דברים:
1. הבלוק הרב-שורתי לא מפיל את הפרסר.
2. **תכונת הזהות** - קלט בלי אף שורה לא-מאוזנת מוחזר זהה לחלוטין.
   זו ההוכחה שהתיקון אינו יכול לגעת באף חוק שכבר נטען היום.
3. גבול אזור (`{{ח:סוגר}}`, `</div>`) לעולם לא נבלע לתוך בלוק
   מאוחד - בליעה כזו הייתה משאירה אזור דילוג פתוח לנצח ומאבדת חוק
   שלם בשקט.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))

from wikitext_parser import _join_unclosed_templates, parse_wikitext  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "wikitext"

# מבוסס על הצורה האמיתית בפקודת הנזיקין (מילון מונחים עברי-אנגלי)
MULTILINE = """{{ח:כותרת|פקודת דוגמה}}
{{ח:סעיף|1|כותרת}}
{{ח:ת}} תוכן רגיל.
{{עמודות|2|{{דוכיווני|אֲמָרָה|statement}}
{{דוכיווני|תְּרוּפָה|remedy}}}}
{{ח:סעיף|2|כותרת שנייה}}
{{ח:ת}} תוכן שני.
"""


def main():
    ok = True

    def check(name, passed, extra=""):
        nonlocal ok
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name, extra if not passed else "")

    # 1. לא קורס, ושני הסעיפים שאחרי הבלוק עדיין נמצאים
    try:
        tree = parse_wikitext(MULTILINE, law_id="law-test")
        crashed = None
    except Exception as exc:  # noqa: BLE001
        tree, crashed = None, f"{type(exc).__name__}: {exc}"
    check("בלוק רב-שורתי לא מפיל את הפרסר", crashed is None, crashed or "")
    if tree is not None:
        numbers = [c.number for c in tree.children if c.node_type == "section"]
        check("הסעיף שאחרי הבלוק לא אבד", numbers == ["1", "2"], str(numbers))

    # 2. תכונת הזהות על כל הפיקסצ'רים האמיתיים
    for path in sorted(FIXTURES.glob("*.wikitext")):
        lines = path.read_text(encoding="utf-8").splitlines()
        check(f"זהות: {path.stem}", _join_unclosed_templates(lines) == lines)

    # 3. גבול אזור לא נבלע
    with_boundary = ["{{עמודות|2|{{דוכיווני|א|a}}", "{{ח:סוגר}}", "{{דוכיווני|ב|b}}}}"]
    check("{{ח:סוגר}} לא נבלע לבלוק", _join_unclosed_templates(with_boundary) == with_boundary)
    toc = ["{{עמודות|2|{{דוכיווני|א|a}}", "</div>", "{{דוכיווני|ב|b}}}}"]
    check("</div> לא נבלע לבלוק", _join_unclosed_templates(toc) == toc)

    # 4. בלוק שלא נסגר עד סוף הדף - לא מאוחד, ונופל בשגיאה מתוארת
    never = ["{{עמודות|2|{{דוכיווני|א|a}}", "עוד טקסט"]
    check("בלוק שלא נסגר - לא מאוחד", _join_unclosed_templates(never) == never)
    try:
        parse_wikitext("{{ח:כותרת|x}}\n{{עמודות|2|לא נסגר", law_id="law-test")
        described = False
    except ValueError as exc:
        described = "שאינה נסגרת" in str(exc)
    except Exception:  # noqa: BLE001
        described = False
    check("קלט פגום -> שגיאה מתוארת ולא IndexError", described)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
