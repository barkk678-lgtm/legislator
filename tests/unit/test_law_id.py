"""בדיקות ל-law_id.build_law_id/resolve_law_id ו-manual_law_ids -
נקודת האכיפה היחידה לבניית law_id, כולל סדר הקדימות המחייב
(ברק, 2026-09-14: "התחילית חייבת להיאכף בקוד, לא במוסכמה"; "סדר
הקדימות הוא IsraelLaw, ואז Bill, ואז מיפוי ידני - bill- הוא נפילה
אחורה כשאין רשומת IsraelLaw, לא בחירה מקבילה"). ראו TASKS.md משימה 7."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from law_id import LawIdResolutionError, build_law_id, resolve_law_id  # noqa: E402
from manual_law_ids import MANUAL_LAW_IDS, get_manual_slug  # noqa: E402


def main():
    checks = []

    checks.append(("israel_law: תחילית law-", build_law_id("israel_law", "2000516") == "law-2000516"))
    checks.append(("bill: תחילית bill-", build_law_id("bill", "2204149") == "bill-2204149"))
    checks.append(("manual: תחילית manual-", build_law_id("manual", "ottoman-civil-procedure-1879") == "manual-ottoman-civil-procedure-1879"))
    checks.append(("int כקלט (לא רק str)", build_law_id("israel_law", 2000516) == "law-2000516"))

    try:
        build_law_id("wikipedia", "123")  # type: ignore[arg-type]
        checks.append(("מקור לא מוכר -> ValueError", False))
    except ValueError:
        checks.append(("מקור לא מוכר -> ValueError", True))

    try:
        build_law_id("manual", "")
        checks.append(("identifier ריק -> ValueError", False))
    except ValueError:
        checks.append(("identifier ריק -> ValueError", True))

    checks.append(("מיפוי ידני: 4 ערכים", len(MANUAL_LAW_IDS) == 4))
    checks.append(
        (
            "get_manual_slug: מחזיר slug גולמי בלי תחילית",
            get_manual_slug("חוק הפרוצדורה האזרחית העותומני") == "ottoman-civil-procedure-1879",
        )
    )
    checks.append(("get_manual_slug: None לחוק לא-קיים במיפוי", get_manual_slug("חוק שלא קיים") is None))
    checks.append(
        (
            "מיפוי ידני: כל ה-slug-ים בלי תחילית (לא מתחילים ב-manual-)",
            all(not slug.startswith("manual-") for slug, _ in MANUAL_LAW_IDS.values()),
        )
    )

    # resolve_law_id - סדר קדימות. kns_records סינתטי: חוק אחד עם
    # Id ידוע ("קייטנות לדוגמה"), אחר עם שם שונה במקצת (לבדיקת
    # ההתאמה המנורמלת של classify_validity/find_israel_law_id).
    kns_records = [
        {"Id": 2000516, "Name": 'חוק הקייטנות (רישוי ופיקוח), התש"ן-1990', "LawValidityDesc": "תקף"},
        {"Id": 2245276, "Name": 'חוק הבחירות לכנסת העשרים ושש (הוראות מיוחדות ותיקוני חקיקה), התשפ"ו-2026', "LawValidityDesc": "תקף"},
    ]

    # מקרה 1: magar1 תקף - הנתיב הרגיל.
    r1 = resolve_law_id(wikitext_title="חוק הקייטנות (רישוי ופיקוח)", magar1="2000516", magar2=None, kns_records=kns_records)
    checks.append(("resolve: magar1 תקף -> law-", r1 == "law-2000516"))

    # מקרה 2 - הקריטי: יש magar2 (נראה כמו Bill), אבל גם התאמת שם
    # מדויקת ל-IsraelLaw. חייב להעדיף law-, לא bill-, בלי קשר לכך
    # שרק ח:מאגר2 מופיע בוויקיטקסט (בדיוק המקרה שברק גילה בפועל -
    # 4 מתוך 15 חוקי ה-Bill).
    r2 = resolve_law_id(
        wikitext_title="חוק הבחירות לכנסת העשרים ושש (הוראות מיוחדות ותיקוני חקיקה)",
        magar1=None, magar2="2244462", kns_records=kns_records,
    )
    checks.append(("resolve: magar2 קיים אבל יש התאמת IsraelLaw בשם -> law- (לא bill-)", r2 == "law-2245276"))

    # מקרה 3: אין magar1, אין התאמת שם, יש magar2 - נפילה אחורה ל-bill-.
    r3 = resolve_law_id(wikitext_title="חוק שלא קיים ב-KNS בכלל", magar1=None, magar2="9999999", kns_records=kns_records)
    checks.append(("resolve: אין IsraelLaw, יש magar2 -> bill-", r3 == "bill-9999999"))

    # מקרה 4: כלום - נופל למיפוי הידני.
    r4 = resolve_law_id(wikitext_title="חוק הפרוצדורה האזרחית העותומני", magar1=None, magar2=None, kns_records=kns_records)
    checks.append(("resolve: כלום, יש במיפוי הידני -> manual-", r4 == "manual-ottoman-civil-procedure-1879"))

    # מקרה 5: כלום, גם לא במיפוי - חריגה מפורשת, בלי fallback שקט.
    try:
        resolve_law_id(wikitext_title="חוק לגמרי לא ידוע", magar1=None, magar2=None, kns_records=kns_records)
        checks.append(("resolve: אין שום מקור -> LawIdResolutionError", False))
    except LawIdResolutionError:
        checks.append(("resolve: אין שום מקור -> LawIdResolutionError", True))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
