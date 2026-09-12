"""טסטים ל-sort_section_numbers. ראו TASKS.md משימה 2.

סיומות אות בסעיפים אינן ערך גימטרי - הן רצות לפי מיקום סידורי
(א, ב, ..., ט, י, יא, ..., יט, כ, כא, ...). המקרה השני למטה תופס
במפורש באג שבו מיון לפי סכימת ערכים (כ=20, ל=30) ולא לפי מיקום
סידורי (כ=11, ל=12) היה נותן תוצאה שגויה.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from numbering import next_appended_label, next_inserted_label, sort_section_numbers  # noqa: E402

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

    # next_inserted_label / next_appended_label: משימה 10ב (מנוע+מספור).
    # מקור: ha-hoveret-ha-sgula.pdf, כמצוטט מדויק בקוד להלן.
    insert_checks = [
        (
            # §7.12, עמ' 31: "בחוק הבוררות... אחרי סעיף 12 יבוא 12א"
            "§7.12 - סעיף ראשי: 6 -> 6א",
            next_inserted_label("6", set()),
            "6א",
        ),
        (
            "§7.12 - התנגשות: 6 עם 6א תפוס -> 6ב",
            next_inserted_label("6", {"6א"}),
            "6ב",
        ),
        (
            # §7.10.6(ב), עמ' 29: "אחרי סעיף קטן (ג) יבוא: '(ג1)...'"
            "§7.10.6(ב) - סעיף קטן: ג -> ג1",
            next_inserted_label("ג", set()),
            "ג1",
        ),
        (
            # §7.10.6(ב), עמ' 29: "אחרי פסקה (2) יבוא: '(2א)...'"
            "§7.10.6(ב) - פסקה: 2 -> 2א",
            next_inserted_label("2", set()),
            "2א",
        ),
        (
            # מוכלל (לא מדוגמה בחוברת): רקורסיה לשלוש רמות לפחות,
            # לסירוגין ספרה/אות בכל שלב - ראו ההערה על "מוכלל ממקרה
            # יחיד" בתיעוד next_inserted_label.
            "רקורסיה 3 רמות: 6 -> 6א -> 6א1 -> 6א1א",
            [
                (x := next_inserted_label("6", set())),
                (y := next_inserted_label(x, set())),
                (z := next_inserted_label(y, set())),
            ],
            ["6א", "6א1", "6א1א"],
        ),
    ]
    for name, got, expected in insert_checks:
        passed = got == expected
        ok = ok and passed
        print(("OK " if passed else "FAIL"), name, "->", got if not passed else "")

    append_checks = [
        (
            # §7.10.6(ג), עמ' 29: "בסעיף 22 לחוק העיקרי, בסופו יבוא: '(ה)...'"
            "§7.10.6(ג) - המשך רצף אותיות: (א)(ב)(ג)(ד) -> ה",
            next_appended_label(["א", "ב", "ג", "ד"]),
            "ה",
        ),
        (
            "המשך רצף מספרים: 6 (בלי 7) -> 7",
            next_appended_label(["6"]),
            "7",
        ),
    ]
    for name, got, expected in append_checks:
        passed = got == expected
        ok = ok and passed
        print(("OK " if passed else "FAIL"), name, "->", got if not passed else "")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
