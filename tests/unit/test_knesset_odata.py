"""OData של הכנסת (משימה 1.4) - בלי רשת.

הפיד עצמו נבדק חי (ראו ROADMAP/night-report); כאן נבדקת הלוגיקה
שסביבו, ובראשה **העימוד**: הפיד מחזיר 100 שורות לכל בקשה ומתעלם
בשקט מ-$top גדול יותר - אותה מלכודת בדיוק כמו PostgREST. בנוסף
נבדקת ההגנה מפני חיתוך שקט: חריגה מתקרת העמודים זורקת שגיאה ולא
מחזירה תוצאה חלקית (זה קרה בפועל בזמן הפיתוח).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "knesset"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

import odata  # noqa: E402
from odata import OdataError, escape  # noqa: E402


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeClient:
    """מחקה את הפיד: 100 שורות לכל בקשה + nextLink עד שנגמר."""

    def __init__(self, total, page=100):
        self.total, self.page, self.calls = total, page, 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None):
        start = self.calls * self.page
        self.calls += 1
        rows = [{"Id": i} for i in range(start, min(start + self.page, self.total))]
        payload = {"value": rows}
        if start + self.page < self.total:
            payload["@odata.nextLink"] = f"next?skip={start + self.page}"
        return _Resp(payload)


def main():
    ok = True
    saved_client, saved_pages = odata._client, odata._MAX_PAGES

    try:
        # --- עימוד מלא מעבר ל-100 ---
        fake = _FakeClient(total=300)
        odata._client = lambda: fake
        rows = odata.fetch("KNS_LawBinding", filter="IsraelLawID eq 2000198")
        checks = [
            (len(rows) == 300, f"300 שורות נשלפו, לא 100 (התקבלו {len(rows)})"),
            (fake.calls == 3, f"שלוש בקשות דרך nextLink (היו {fake.calls})"),
        ]

        # --- תקרה שלנו על סך השורות ---
        fake2 = _FakeClient(total=1000)
        odata._client = lambda: fake2
        checks.append((len(odata.fetch("KNS_Bill", top=7)) == 7, "top=7 מחזיר 7 שורות"))

        # --- חריגה מתקרת העמודים זורקת, לא מחזירה חלקי ---
        fake3 = _FakeClient(total=10_000)
        odata._client = lambda: fake3
        odata._MAX_PAGES = 3
        threw = False
        try:
            odata.fetch("KNS_Bill")
        except OdataError:
            threw = True
        checks.append((threw, "חריגה מתקרת העמודים -> שגיאה, לא 300 שורות מתוך 10,000 בשקט"))
        # --- 474 (חסימת IP): מפסק - אחרי 474 אחד אין עוד בקשות לרשת ---
        class _Blocked(_FakeClient):
            def get(self, url, params=None):
                self.calls += 1
                r = _Resp({})
                r.status_code = 474
                return r
        odata._MAX_PAGES = saved_pages
        blocked = _Blocked(total=0)
        odata._client = lambda: blocked
        errs = []
        for _ in range(3):
            try:
                odata.fetch("KNS_Query", filter="KnessetNum eq 25")
            except odata.FeedBlockedError as e:
                errs.append(e)
        checks.append((len(errs) == 3, "474 -> FeedBlockedError בכל קריאה"))
        checks.append((isinstance(errs[0], OdataError), "FeedBlockedError הוא OdataError - קוראים קיימים תופסים אותו"))
        checks.append((blocked.calls == 1, f"אחרי 474 אחד - אפס בקשות נוספות לפיד (היו {blocked.calls})"))
        # כשהחסימה פגה - חוזרים לרשת
        odata._blocked_until = 0.0
        fake4 = _FakeClient(total=5)
        odata._client = lambda: fake4
        checks.append((len(odata.fetch("KNS_Query")) == 5 and fake4.calls == 1,
                       "אחרי תום החסימה - הבקשה יוצאת שוב"))
    finally:
        odata._client, odata._MAX_PAGES = saved_client, saved_pages
        odata._blocked_until = 0.0

    # --- escape מונע שבירת ה-filter על גרש (נפוץ בשמות חוקים) ---
    checks.append((escape("התשס'ו") == "התשס''ו", "גרש בודד מוכפל"))

    # --- דמיון שמות: מילות מילוי לא יוצרות התאמה מזויפת ---
    from knesset_bills import _words  # noqa: PLC0415

    filler = _words("הצעת חוק לתיקון חוק (תיקון מס' 3)")
    checks.append((not filler, f"שם שכולו מילות מילוי -> אין מילות תוכן (התקבל {filler})"))
    real = _words("חוק תובענות ייצוגיות (תיקון - הרחבת עילות)")
    checks.append(({"תובענות", "ייצוגיות"} <= real, "מילות התוכן האמיתיות מזוהות"))

    # --- מזהה bill- אינו חוק עצמאי במאגר הכנסת ---
    from knesset_citations import _israel_law_id  # noqa: PLC0415

    checks.append((_israel_law_id("law-2000613") == 2000613, "law-2000613 -> 2000613"))
    checks.append((_israel_law_id("bill-1046679") is None, "bill- -> אין IsraelLawID (לא שגיאה)"))
    checks.append((_israel_law_id("law-tkanon-haknesset") is None, "מזהה לא-מספרי -> None"))

    for passed, label in checks:
        ok = ok and passed
        print(("OK " if passed else "FAIL"), label)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
