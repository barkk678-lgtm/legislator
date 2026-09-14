"""בדיקות ל-law_id.build_law_id ו-manual_law_ids - נקודת האכיפה
היחידה לבניית law_id (ברק, 2026-09-14: "התחילית חייבת להיאכף בקוד,
לא במוסכמה"). ראו TASKS.md משימה 7."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from law_id import build_law_id  # noqa: E402
from manual_law_ids import MANUAL_LAW_IDS, get_manual_law_id  # noqa: E402


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
            "get_manual_law_id: מרכיב תחילית manual-",
            get_manual_law_id("חוק הפרוצדורה האזרחית העותומני") == "manual-ottoman-civil-procedure-1879",
        )
    )
    checks.append(("get_manual_law_id: None לחוק לא-קיים במיפוי", get_manual_law_id("חוק שלא קיים") is None))
    checks.append(
        (
            "מיפוי ידני: כל ה-slug-ים בלי תחילית (לא מתחילים ב-manual-)",
            all(not slug.startswith("manual-") for slug, _ in MANUAL_LAW_IDS.values()),
        )
    )

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
