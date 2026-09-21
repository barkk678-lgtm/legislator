"""חיווי הערת צ״ל בממשק - נבדק על ה-regex שבקובץ עצמו, לא על העתק.

**למה לחלץ מהקובץ ולא לשכפל:** העתק בבדיקה יעבור גם אחרי ש-app.js
ישתנה, ואז הבדיקה תדווח "עבר" על קוד שכבר לא קיים. הבדיקה קוראת את
הביטוי מתוך `apps/api/static/app.js` ומריצה אותו ב-node.

המקרים למטה הם **מחרוזות אמיתיות מהקורפוס**, לא המצאות:
- "[צ״ל: עונשין]" - חוק השימוש בהיפנוזה, שם כותרות השוליים של
  סעיפים 27 ו-28 הוחלפו במקור.
- "[צ״ל, 85 עד 86]" - הווריאנט היחיד עם פסיק בכל הקורפוס.
- אצ״ל / זצ״ל / דצ״ל - **חייבים לא להיתפס**. הם אינם הערות נוסח,
  וההגנה היחידה מפניהם היא הסוגר הפותח שצמוד ל-צ.
- "צ״ל עולה בקנה אחד" - פקודת בנין ערים 1921 משתמשת ב-"צ״ל" כמילה
  רגילה בנוסח עצמו. שישה מופעים.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[2] / "apps" / "api" / "static" / "app.js"

MUST_MATCH = [
    ('תקנות [צ״ל: עונשין]', '[צ״ל: עונשין]'),
    ('בסעיף [צ״ל 60]', '[צ״ל 60]'),
    ('בסעיפים [צ״ל, 85 עד 86]', '[צ״ל, 85 עד 86]'),
    ('פרק ז׳ [צ״ל: פרק זה]', '[צ״ל: פרק זה]'),
    ('[צ"ל: סעיף 2]', '[צ"ל: סעיף 2]'),
]

# הערה שהיא כל הצומת, בלי סוגר סוגר - חוק מס מינימלי גלובלי.
LONG_UNCLOSED = '[צ"ל: רישום הבחירות שנעשו בהתאם להוראות הרלוונטיות של כללי הגלוב; וכן'

MUST_NOT_MATCH = [
    'שירות בארגוני ההגנה, אצ״ל, לח״י וכל שירות אחר',
    'לציין את זכרו של מרן הרב עובדיה יוסף זצ״ל, בכיר הרבנים',
    'ובעלי ערך אלבומין שווה או נמוך מ־4.0 ג׳/דצ״ל:',
    'השמוש בתכנון כל הקרקעות צ״ל עולה בקנה אחד עם תכנית התכנון',
    'מספר החדרים שצ״ל בדירה או בבנין;',
]


def _pattern() -> str:
    source = APP_JS.read_text(encoding="utf-8")
    match = re.search(r"const SCRIVENER_NOTE_RE = (/.+/g);", source)
    if not match:
        raise AssertionError(
            "לא נמצא SCRIVENER_NOTE_RE ב-app.js. אם הוא שונה או הוסר - "
            "הבדיקה הזו חייבת להשתנות איתו, לא להימחק בשקט.")
    return match.group(1)


def _run(pattern: str, texts: list[str]) -> list[list[str]]:
    script = (
        "const RE = %s;\n"
        "const texts = JSON.parse(process.argv[1]);\n"
        "console.log(JSON.stringify(texts.map(t => t.match(RE) || [])));\n"
    ) % pattern
    out = subprocess.run(["node", "-e", script, json.dumps(texts)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main() -> int:
    if not shutil.which("node"):
        print("דילוג: node אינו מותקן - הבדיקה אינה יכולה לרוץ, ולכן")
        print("       היא **לא** מדווחת 'עבר'.")
        return 2

    pattern = _pattern()
    failures = 0

    got = _run(pattern, [t for t, _ in MUST_MATCH])
    for (text, expected), matches in zip(MUST_MATCH, got):
        if matches != [expected]:
            print(f"FAIL  {text!r} -> {matches!r}, ציפינו ל-[{expected!r}]")
            failures += 1
        else:
            print(f"OK    תופס: {expected}")

    (long_match,) = _run(pattern, [LONG_UNCLOSED])
    if long_match != [LONG_UNCLOSED]:
        print(f"FAIL  הערה בלי סוגר סוגר -> {long_match!r}")
        failures += 1
    else:
        print("OK    הערה שהיא כל הצומת, בלי ']' - נתפסת במלואה")

    for text, matches in zip(MUST_NOT_MATCH, _run(pattern, MUST_NOT_MATCH)):
        if matches:
            print(f"FAIL  תפס בטעות ב-{text!r}: {matches!r}")
            failures += 1
        else:
            print(f"OK    לא תופס: {text[:45]}…")

    print("\nתוצאה:", "עבר" if not failures else f"{failures} כשלים")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
