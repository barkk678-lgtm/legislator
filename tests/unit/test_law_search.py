"""בדיקות ל-law_search.search_laws - חיפוש חוקים לפי שם, משימה A
(ברק 2026-09-14). פונקציה טהורה - בלי DB/רשת."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from law_search import search_laws  # noqa: E402

_LAWS = [
    {"id": "law-2000516", "title": 'חוק הקייטנות (רישוי ופיקוח), התש"ן-1990'},
    {"id": "law-2000055", "title": "חוק אוויר נקי"},
    {"id": "law-2002355", "title": "חוק אומנה לילדים"},
    {"id": "law-2000722", "title": 'חוק להגברת האכיפה של דיני העבודה, התשע"ב-2011'},
    {"id": "law-2000492", "title": 'חוק הפטנטים, תשכ"ז-1967'},
]


def main():
    checks = []

    # התאמה מדויקת (אחרי נורמליזציה) מדורגת ראשונה
    r1 = search_laws("חוק אוויר נקי", _LAWS)
    checks.append(("התאמה מדויקת: תוצאה יחידה", len(r1) == 1 and r1[0]["id"] == "law-2000055"))

    # תת-מחרוזת חלקית - שם בלי השנה/הסיומת המשפטית
    r2 = search_laws("קייטנות", _LAWS)
    checks.append(("תת-מחרוזת חלקית מוצאת את חוק הקייטנות", len(r2) == 1 and r2[0]["id"] == "law-2000516"))

    # נורמליזציית matres lectionis - "קיטנות" (בלי י') לעומת "קייטנות" בקורפוס
    r3 = search_laws("קיטנות", _LAWS)
    checks.append(("matres lectionis: 'קיטנות' (בלי י') מוצא 'קייטנות'", len(r3) == 1 and r3[0]["id"] == "law-2000516"))

    # ריבוי מילים, לא ברצף בכותרת המקורית אבל שתיהן מופיעות
    r4 = search_laws("האכיפה דיני עבודה", _LAWS)
    checks.append(("ריבוי טוקנים לא-רציפים -> עדיין נמצא", len(r4) == 1 and r4[0]["id"] == "law-2000722"))

    # "חוק" לבדו - מילה משותפת לכל הכותרות, כל 5 חוזרים (ALL_TOKENS/SUBSTRING)
    r5 = search_laws("חוק", _LAWS)
    checks.append(("'חוק' לבדו מחזיר את כל 5 (מילה משותפת)", len(r5) == 5))

    # אין התאמה כלל
    r6 = search_laws("משהו שלא קיים בכלל", _LAWS)
    checks.append(("אין התאמה -> רשימה ריקה", r6 == []))

    # query ריק/רווחים בלבד -> ריק, לא "הכול תואם"
    r7 = search_laws("   ", _LAWS)
    checks.append(("query ריק -> רשימה ריקה (לא 'הכול')", r7 == []))

    # limit נאכף
    r8 = search_laws("חוק", _LAWS, limit=2)
    checks.append(("limit נאכף", len(r8) == 2))

    # דירוג: prefix לפני substring-לא-בתחילה
    laws_prefix_test = [
        {"id": "a", "title": "חוק הפטנטים"},
        {"id": "b", "title": "חוק לתיקון חוק הפטנטים"},
    ]
    r9 = search_laws("חוק הפטנטים", laws_prefix_test)
    checks.append(("דירוג: prefix-match (a) לפני מוכל-באמצע (b)", [law["id"] for law in r9] == ["a", "b"]))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
