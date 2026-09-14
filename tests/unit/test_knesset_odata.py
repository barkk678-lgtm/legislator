"""בדיקות ל-knesset_odata.py. ראו TASKS.md משימה 7 / docs/strategy/
decisions.md (2026-09-14) - סינון חוקים מבוטלים/פקעו/נושנו.

כל הבדיקות כאן סינתטיות (רשימות dict בזיכרון) - fetch_israel_laws
(הפונקציה היחידה שנוגעת ברשת) לא נבדקת כאן, בדיוק כמו
wikitext_client.fetch_wikitext. הדוגמאות משוחזרות מממצאים אמיתיים
(ראו decisions.md): "חפשי"/"חופשי" (כתיב חסר/מלא), "חוק הבחירות
לכנסת" (עמימות עם פישור), "חוק שירות נתוני אשראי" (בוטל בפועל).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from knesset_odata import (  # noqa: E402
    base_title,
    classify_validity,
    should_ingest,
    strip_matres_lectionis,
)


def _rec(name: str, validity: str) -> dict:
    return {"Name": name, "LawValidityDesc": validity}


def main():
    checks = []

    # base_title: מסיר סיומת שנה עברית + גרשיים/מקפים לא-אחידים
    checks.append(
        ("base_title מסיר סיומת שנה עברית", base_title('חוק אוויר נקי, התשס"ח-2008') == "חוק אוויר נקי")
    )
    checks.append(
        ("base_title מסיר '[נוסח משולב]' עם השנה", base_title('חוק הבחירות לכנסת [נוסח משולב], התשכ"ט-1969') == "חוק הבחירות לכנסת")
    )

    # strip_matres_lectionis: לא נוגע באות ראשונה של מילה
    checks.append(("strip_matres: 'חפשי' ו'חופשי' -> אותו שלד", strip_matres_lectionis("חפשי") == strip_matres_lectionis("חופשי")))
    checks.append(("strip_matres: לא נוגע באות הראשונה", strip_matres_lectionis("ויקיפדיה").startswith("ו")))

    kns = [
        _rec("חוק אוויר נקי, התשס\"ח-2008", "תקף"),
        _rec("חוק אזורי נמל חופשיים, התשכ\"ט-1969", "תקף"),
        _rec("חוק שירות נתוני אשראי, התשס\"ב-2002", "בטל"),
        _rec('חוק הבחירות לכנסת, התשי"ט-1959 [נוסח משולב]', "בטל"),
        _rec('חוק הבחירות לכנסת, התשט"ו-1955 [נוסח משולב]', "בטל"),
        _rec('חוק הבחירות לכנסת [נוסח משולב], התשכ"ט-1969', "תקף"),
        _rec("חוק להתפזרות הכנסת ה-18, התשע\"ג-2013", "נושן"),
        _rec("חוק דוגמה עם שתי גרסאות בטלות, התש\"א-1951", "בטל"),
        _rec("חוק דוגמה עם שתי גרסאות בטלות, התש\"ב-1952", "פקע"),
    ]

    # התאמה מדויקת, תקף
    m = classify_validity("חוק אוויר נקי", kns)
    checks.append(("התאמה מדויקת -> exact", m.match_method == "exact"))
    checks.append(("התאמה מדויקת -> תקף", m.law_validity_desc == "תקף"))
    checks.append(("התאמה מדויקת -> should_ingest True", should_ingest(m) is True))

    # התאמה רק אחרי הסרת אימות קריאה (חפשי/חופשי)
    m = classify_validity("חוק אזורי נמל חפשיים", kns)
    checks.append(("כתיב חסר -> normalized", m.match_method == "normalized"))
    checks.append(("כתיב חסר -> should_ingest True", should_ingest(m) is True))

    # התאמה מדויקת לחוק בטל בפועל
    m = classify_validity("חוק שירות נתוני אשראי", kns)
    checks.append(("חוק בטל -> exact", m.match_method == "exact"))
    checks.append(("חוק בטל -> should_ingest False", should_ingest(m) is False))

    # עמימות עם פישור: שלוש רשומות, אחת תקף בלבד -> נבחרת
    m = classify_validity("חוק הבחירות לכנסת", kns)
    checks.append(("עמימות עם פישור -> מוצאת את התקף", m.law_validity_desc == "תקף"))
    checks.append(("עמימות עם פישור -> should_ingest True", should_ingest(m) is True))

    # עמימות בלי פישור: שתי רשומות, אף אחת לא תקף -> ambiguous, לא נזרק
    m = classify_validity("חוק דוגמה עם שתי גרסאות בטלות", kns)
    checks.append(("עמימות בלי תקף -> ambiguous", m.match_method == "ambiguous"))
    checks.append(("עמימות בלי תקף -> validity_desc None", m.law_validity_desc is None))
    checks.append(("עמימות בלי תקף -> should_ingest True (לא נזרק)", should_ingest(m) is True))

    # לא נמצאה שום התאמה
    m = classify_validity("חוק שלא קיים בכלל בכנסת", kns)
    checks.append(("לא נמצא -> not_found", m.match_method == "not_found"))
    checks.append(("לא נמצא -> should_ingest True (לא נזרק)", should_ingest(m) is True))

    # נושן - לא נטען
    m = classify_validity("חוק להתפזרות הכנסת ה-18", kns)
    checks.append(("נושן -> should_ingest False", should_ingest(m) is False))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
