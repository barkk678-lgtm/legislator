"""ש7 (25.9.2026) - סינון לפי כנסת בשאילתות קודמות: עדכון מיידי, בלי לבנות מחדש.

הוספת כנסת: התוצאות הקיימות נשארות, החיפוש רץ **רק** על הכנסת החדשה (בלי
קריאה נוספת לפירוק), ומה שנמצא מתווסף. הסרת כנסת: השורות שלה יורדות מיד,
בלי שום בקשה. הפיד והפירוק מדומים (page.route).
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_pq_knesset_toggle.py [BASE_URL]
"""
import json
import sys
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
PLAN = {"expanded": True, "domain": [["מחסור"], ["משטר"]],
        "units": [{"words": ["מחסור", "משטרה"], "kind": "phrase"}]}
ROWS = {25: "מחסור בשוטרים במשטרה בדרום", 24: "מחסור בחוקרים במשטרה", 23: "מחסור בסיירים במשטרה"}


def row(k):
    return {"query_id": 1000 + k, "title": ROWS[k], "kind": "רגילה", "knesset": k,
            "submitted_at": "01.01.2020", "person_id": None,
            "page_url": f"https://m.knesset.gov.il/apps/query/details/{1000 + k}"}


def main() -> int:
    results, calls = [], {"plan": 0, "unit": []}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def on_unit(route):
            qs = parse_qs(urlparse(route.request.url).query)
            ks = [int(k) for k in qs.get("knesset", [])]
            calls["unit"].append(ks)
            rows = [row(k) for k in ROWS if not ks or k in ks]
            route.fulfill(status=200, content_type="application/json", body=json.dumps(
                {"words": qs.get("w", []), "count": len(rows), "too_broad": False, "rows": rows},
                ensure_ascii=False))

        def on_plan(route):
            calls["plan"] += 1
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(PLAN, ensure_ascii=False))

        page.route("**/api/queries/knessets", lambda r: r.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"current": 25, "default": [25, 24], "available": list(range(1, 26))})))
        page.route("**/api/queries/unit?*", on_unit)
        page.route("**/api/queries/plan?*", on_plan)
        page.route("**/api/queries/enrich?*", lambda r: r.fulfill(
            status=200, content_type="application/json", body='{"docs":{},"names":{}}'))
        page.goto(BASE)
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.reload()
        page.click('nav button[data-t="query"]')
        page.wait_for_selector('#pq-knesset .pq-chip[data-k="24"]')

        def titles():
            return page.evaluate("() => [...document.querySelectorAll('#pq-rows .pq-title')].map(e => e.textContent)")

        def settle():
            page.wait_for_function("() => !document.getElementById('pq-status')", timeout=15000)
            page.wait_for_timeout(200)

        page.fill("#past-queries-input", "מחסור בשוטרים")
        page.click("#past-queries-btn")
        settle()
        results.append(("חיפוש ראשון: 25 ו-24", sorted(titles()) == sorted([ROWS[25], ROWS[24]]), str(titles())))

        # הסרה - בלי בקשה
        before = len(calls["unit"])
        page.click('#pq-knesset .pq-chip[data-k="24"]')
        page.wait_for_timeout(300)
        results.append(("הסרת 24: השורה שלה ירדה מיד", titles() == [ROWS[25]], str(titles())))
        results.append(("הסרת 24: אפס בקשות חדשות", len(calls["unit"]) == before, str(calls["unit"][before:])))
        results.append(("הסרת 24: שורת הספירה התעדכנה",
                        page.inner_text("#pq-done").startswith("1 תוצאות"), page.inner_text("#pq-done")))

        # הוספה - רק הכנסת החדשה, בלי פירוק נוסף
        before, plans = len(calls["unit"]), calls["plan"]
        page.click('#pq-knesset .pq-chip[data-k="23"]')
        settle()
        new_calls = calls["unit"][before:]
        results.append(("הוספת 23: התוצאה הקיימת נשארה והחדשה נוספה למטה",
                        titles() == [ROWS[25], ROWS[23]], str(titles())))
        results.append(("הוספת 23: הבקשות רק על כנסת 23",
                        bool(new_calls) and all(ks == [23] for ks in new_calls), str(new_calls)))
        results.append(("הוספת 23: בלי קריאה נוספת לפירוק", calls["plan"] == plans, str(calls["plan"])))
        results.append(("הוספת 23: שורת הספירה", page.inner_text("#pq-done").startswith("2 תוצאות"),
                        page.inner_text("#pq-done")))

        # "הכול" - מוסיף את מה שחסר, בלי כפילויות
        page.click('#pq-knesset .pq-chip[data-k="all"]')
        settle()
        t = titles()
        results.append(("'הכול': כל שלוש, בלי כפילות, הקיימות בראש",
                        t[:2] == [ROWS[25], ROWS[23]] and sorted(t) == sorted(ROWS.values()), str(t)))
        results.append(("אפס שגיאות JS", not errors, str(errors)))
        b.close()

    ok = True
    for label, passed, detail in results:
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), label, "" if passed else detail)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
