"""טסטים ל-sort_section_numbers. ראו TASKS.md משימה 2.

סיומות אות בסעיפים אינן ערך גימטרי - הן רצות לפי מיקום סידורי
(א, ב, ..., ט, י, יא, ..., יט, כ, כא, ...). המקרה השני למטה תופס
במפורש באג שבו מיון לפי סכימת ערכים (כ=20, ל=30) ולא לפי מיקום
סידורי (כ=11, ל=12) היה נותן תוצאה שגויה.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from numbering import sort_section_numbers  # noqa: E402

CASES = [
    (
        "הרצף מהגדרת הסיום של משימה 2",
        ["4", "3", "3יא", "3א", "3ב", "3י"],
        ["3", "3א", "3ב", "3י", "3יא", "4"],
    ),
    (
        "באג המיקום מול הערך: כד לפני לא",
        ["34לא", "34כד", "34", "34א"],
        ["34", "34א", "34כד", "34לא"],
    ),
    (
        "מספור מעורב בתוך אותו חוק",
        ["10", "2א", "2", "10א", "1", "2יא"],
        ["1", "2", "2א", "2יא", "10", "10א"],
    ),
]


def main():
    ok = True
    for name, given, expected in CASES:
        got = sort_section_numbers(given)
        passed = got == expected
        ok = ok and passed
        flag = "OK " if passed else "FAIL"
        print(f"{flag} {name}")
        if not passed:
            print(f"     קלט:   {given}")
            print(f"     צפוי:  {expected}")
            print(f"     התקבל: {got}")
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
