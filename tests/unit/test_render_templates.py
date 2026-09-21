"""בדיקות ל-packages/corpus/render_templates.py.

**המודול אינו מחובר לפרסר.** ברק ביקש לראות שלושה מקרים לפני
שמחילים. הטסטים כאן נועלים את ההתנהגות על נוסחים **אמיתיים**
מהקורפוס, כדי שההכרעה תילקח על מה שבאמת יוצא.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from render_templates import render, unrendered_templates  # noqa: E402


def main() -> int:
    checks: list[tuple[str, bool]] = []

    # נוסחים אמיתיים מה-DB
    checks.append(("עיצוב: {{מוקטן}} מוסר, התוכן נשאר",
                   render('דוחות כספיים מאוחדים {{מוקטן|(Consolidated Financial Statements)}} כהגדרתם')
                   == 'דוחות כספיים מאוחדים (Consolidated Financial Statements) כהגדרתם'))
    # **שורות ממש ולא `|`** (ברק, 2026-09-19): הטקסט מוצג למשתמש
    # בלשונית החוק, ו-`|` באמצע נוסח נראה כמו תקלה.
    checks.append(("מבנה: {{טורים שווים}} -> שורות ממש",
                   render("{{טורים שווים | {{מוקטן|שנות שירות}} | {{מוקטן|אחוזים}}}}")
                   == "שנות שירות\nאחוזים"))
    checks.append(("מבנה: אין `|` בפלט",
                   "|" not in render("{{טורים שווים |א|ב}}")))
    checks.append(("{{ש}} -> שורה חדשה", "\n" in render("א {{ש}} ב")))
    checks.append(("דו-לשוני: עברית (English)",
                   render("{{דוכיווני|ניתן לזרום|allowed to escape}}")
                   == "ניתן לזרום (allowed to escape)"))
    checks.append(("{{עמודות|2|...}}: מספר העמודות אינו תא",
                   render("{{עמודות|2|אָבוֹת|אַגוּדַת אַחִים}}") == "אָבוֹת\nאַגוּדַת אַחִים"))
    checks.append(("{{=}} -> סימן שווה", render("א{{=}}ב") == "א=ב"))

    # **תבנית לא מוכרת נשארת כפי שהיא** - אותו עיקרון כמו _flatten:
    # לא ממציאים רינדור למה שלא זיהינו.
    unknown = "{{תבנית שלא ראינו|ערך}}"
    checks.append(("תבנית לא מוכרת נשארת גולמית", render(unknown) == unknown))
    checks.append(("unrendered_templates מדווחת עליה",
                   unrendered_templates(unknown) == ["תבנית שלא ראינו"]))

    # טסטים שליליים
    checks.append(("טקסט בלי תבניות אינו משתנה",
                   render("סעיף רגיל לגמרי, בלי כלום.") == "סעיף רגיל לגמרי, בלי כלום."))
    checks.append(("תבנית לא סגורה אינה מפילה ואינה בולעת",
                   render("לפני {{מוקטן|בלי סוף") == "לפני {{מוקטן|בלי סוף"))
    checks.append(("'|' בתוך תבנית מקוננת אינו מפריד תאים",
                   render("{{טורים שווים|{{דוכיווני|א|b}}|ג}}") == "א (b)\nג"))
    # קינון עמוק: עיצוב בתוך מבנה בתוך מבנה
    checks.append(("קינון עמוק מפורק עד הסוף",
                   "{{" not in render(
                       "{{טורים שווים|{{ממורכז|{{מוקטן|א}}}}|{{מוקטן|ב}}}}")))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
