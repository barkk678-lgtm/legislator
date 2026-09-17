"""עימוד ל-PostgREST (apps/api/supabase_rest.py) - בלי רשת.

המגבלה הזו הכתה פעמיים בשקט (חוק העונשין עם 1,000 מתוך 2,682 צמתים;
94 חוקים שלא נרשמו לתור והריצה דיווחה "הושלם"). הבדיקה נועלת את שתי
ההתנהגויות שמונעות חזרה שלישית: fetch_all ממשיכה מעבר לעמוד הראשון,
ו-count_rows קוראת את הסכום האמיתי ולא סופרת שורות חתוכות.

בנוסף: סריקה של כל קריאות ה-GET ל-PostgREST בקוד, כדי שקריאה חדשה
בלי עימוד תיפול כאן ולא בפרודקשן.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from supabase_rest import count_rows, fetch_all  # noqa: E402


class _Response:
    def __init__(self, rows, headers=None):
        self._rows = rows
        self.headers = headers or {}

    def json(self):
        return self._rows

    def raise_for_status(self):
        return None


class _PagingClient:
    """מחקה את ההתנהגות האמיתית: לכל היותר `cap` שורות לתשובה."""

    def __init__(self, total, cap=1000):
        self._total = total
        self._cap = cap
        self.requested_ranges = []

    def get(self, path, params=None, headers=None):
        rng = (headers or {}).get("Range", "0-999")
        start, end = (int(x) for x in rng.split("-"))
        self.requested_ranges.append((start, end))
        window = min(end - start + 1, self._cap)
        rows = [{"i": i} for i in range(start, min(start + window, self._total))]
        if params and params.get("select") == "count":
            return _Response([], {"content-range": f"0-0/{self._total}"})
        return _Response(rows)


def main():
    ok = True

    # --- fetch_all חוצה את תקרת 1,000 השורות ---
    client = _PagingClient(total=2682)  # חוק העונשין
    rows = fetch_all(client, "/nodes", {"select": "id"})
    checks = [
        (len(rows) == 2682, f"2,682 שורות נשלפו במלואן (התקבלו {len(rows)})"),
        (len(client.requested_ranges) == 3, "שלוש בקשות Range, לא אחת"),
        (client.requested_ranges[0] == (0, 999), "העמוד הראשון מבקש 0-999"),
        (client.requested_ranges[1] == (1000, 1999), "העמוד השני ממשיך מ-1000"),
    ]

    # --- עמוד אחרון מלא בדיוק: חייבת עוד בקשה כדי לדעת שנגמר ---
    exact = _PagingClient(total=2000)
    rows_exact = fetch_all(exact, "/nodes", {"select": "id"})
    checks.append((len(rows_exact) == 2000, "טבלה בגודל כפולה מדויקת של העמוד נשלפת במלואה"))
    checks.append((len(exact.requested_ranges) == 3, "נשלחת בקשה נוספת כדי לזהות סוף, לא מניחים"))

    # --- count_rows מחזירה את הסכום האמיתי, לא את מספר השורות שחזרו ---
    counting = _PagingClient(total=5000)
    checks.append((count_rows(counting, "/ingest_log", {}) == 5000,
                   "count_rows מחזירה 5,000 ולא 1,000 (הסכום מ-content-range)"))

    # --- אף קריאת GET ל-PostgREST בקוד לא עוקפת את העוזר ---
    # קריאה ישירה מותרת רק כששולפים שורה אחת מפורשות (limit=1); כל
    # יתר הקריאות חייבות לעבור דרך fetch_all/count_rows. הבדיקה מסתכלת
    # על גוף הקריאה עצמו ולא על מספרי שורות, כדי שלא תישבר מעריכות.
    # מזהים קריאות PostgREST לפי הצורה שלהן בקוד: הארגומנט הראשון
    # הוא נתיב-מחרוזת שמתחיל ב-"/" (יחסית ל-base_url של Supabase).
    # קריאה ל-API חיצוני מקבלת URL מלא במשתנה ואינה רלוונטית לכלל הזה.
    unexpected = []
    for path in sorted((ROOT / "apps" / "api").glob("*.py")):
        if path.name == "supabase_rest.py":
            continue
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r'client\.get\(\s*\n?\s*"/', source):
            call = source[match.start():match.start() + 500]
            if '"limit": "1"' not in call.split(")")[0] + ")":
                # מרחיבים מעט: הפרמטרים עשויים להתפרס על כמה שורות
                head = call[:call.find("\n    )") + 6] if "\n    )" in call else call[:300]
                if '"limit": "1"' not in head:
                    line_no = source[:match.start()].count("\n") + 1
                    unexpected.append(f"{path.name}:{line_no}")
    checks.append((not unexpected,
                   f"כל קריאת GET ישירה שולפת שורה אחת מפורשות; השאר דרך העוזר (חריגות: {unexpected})"))

    for passed, label in checks:
        ok = ok and passed
        print(("OK " if passed else "FAIL"), label)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
