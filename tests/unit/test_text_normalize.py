"""טסטים ל-normalize_text. ראו TASKS.md משימה 3.

נרמול הוא תווים בלבד, לא תיקון נוסח - ראו CASES האחרון: שגיאת הקלדה
אמיתית ("ערב תתילתו" במקום "ערב תחילתו", מסעיף 8 בחוק הקייטנות) חייבת
לעבור ללא שינוי.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from text_normalize import normalize_text  # noqa: E402

FORBIDDEN = ["”", "“", "״", "־"]  # ” “ ״ ־

CASES = [
    ("גרשיים כפולים מסולסלים", "”ילד“ – מי שטרם מלאו לו", '"ילד" – מי שטרם מלאו לו'),
    ("גרש עברי בודד (גרשיים U+05F4)", 'ס״ח תש״ן, 155', 'ס"ח תש"ן, 155'),
    ("מקף עברי (מקף U+05BE)", "מבית־הספר", "מבית-הספר"),
    (
        "שגיאת הקלדה אמיתית לא מתוקנת",
        "שהיה בר תוקף ערב תתילתו של חוק זה",
        "שהיה בר תוקף ערב תתילתו של חוק זה",
    ),
    (
        "en-dash בשנה עברית נשאר כמו שהוא",
        "חוק הקייטנות (רישוי ופיקוח), התש”ן–1990".replace("”", "״"),
        'חוק הקייטנות (רישוי ופיקוח), התש"ן–1990',
    ),
]


FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wikitext" / "kaytanot.wikitext"
)


def section_1_raw_text() -> str:
    """מחלץ את הבלוק הגולמי של סעיף 1 מתוך fixture אמיתי, בלי לפרסר."""
    full = FIXTURE.read_text(encoding="utf-8")
    start = full.index("{{ח:סעיף|1|")
    end = full.index("{{ח:סעיף|2|")
    return full[start:end]


def main():
    ok = True
    for name, given, expected in CASES:
        got = normalize_text(given)
        passed = got == expected
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name)
        if not passed:
            print(f"     קלט:   {given!r}")
            print(f"     צפוי:  {expected!r}")
            print(f"     התקבל: {got!r}")

    # בדיקה 5 בוולידטור: שום תו אסור לא שורד נרמול
    for ch in FORBIDDEN:
        found = ch in normalize_text(f"בדיקה {ch} של תו אסור")
        passed = not found
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), f"תו אסור U+{ord(ch):04X} לא שורד נרמול")

    # דרישת המשתמש: סעיף 1 האמיתי של הקייטנות, אחרי נרמול, עובר בדיקה 5
    section_1 = section_1_raw_text()
    assert any(ch in section_1 for ch in FORBIDDEN), (
        "ה-fixture עצמו לא מכיל תווים אסורים - הטסט לא בודק כלום"
    )
    normalized = normalize_text(section_1)
    passed = not any(ch in normalized for ch in FORBIDDEN)
    ok = ok and passed
    print(("OK  " if passed else "FAIL"), "סעיף 1 האמיתי מ-kaytanot.wikitext עובר בדיקה 5 אחרי נרמול")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
