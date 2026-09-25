"""ש4 (25.9.2026) - שאילתות קודמות: כל שורה חייבת להתאים לגוף/לתחום, בדפדפן.

הפיד והפירוק מדומים (page.route) - בלי קריאה לכנסת ובלי מודל. הכותרות
אמיתיות: שלוש השורות על בריאות הן בדיוק מה שהוצג לברק על "מחסור בכוח
אדם במשטרת ישראל" (תמונה 2).
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_past_queries_domain.py [BASE_URL]
"""
import json
import sys
import time
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
TOPIC = "מחסור בכוח אדם במשטרת ישראל"
HEALTH = ["פערים בהתחסנות ילדים לשפעת בין המרכז לפריפריה כתוצאה ממחסור בכוח סיעודי",
          "מחסור בכוח אדם בתוכנית תיאום טיפול",
          "מחסור בכוח אדם רפואי במרכז הרפואי לגליל"]
POLICE = ["מחסור בכוח אדם במשטרת ישראל בדרום", "ירידה עקבית באיכות השוטרים וחשש מהורדת תנאי הקבלה"]
PLAN = {"expanded": True,
        "domain": [["משטר", "שוטר", "שיטור", 'מג"ב', "משמר הגבול"]],
        "units": [{"words": ["כוח", "אדם", "משטר"], "kind": "phrase"},
                  {"words": ["איכות", "שוטר"], "kind": "alt"}]}


def rows(titles, base):
    return [{"query_id": base + i, "title": t, "kind": "רגילה", "knesset": 25,
             "submitted_at": "01.01.2026", "person_id": None,
             "page_url": f"https://m.knesset.gov.il/apps/query/details/{base + i}"}
            for i, t in enumerate(titles)]


def unit_body(words):
    key = " ".join(words)
    if key == "מחסור בכוח":            # בדיקת הפתיחה - מחזירה את הבריאות, מיד
        r = rows(HEALTH + POLICE[:1], 100)
    elif key == "כוח אדם משטר":
        r = rows(POLICE[:1], 103)
    elif key == "איכות שוטר":
        r = rows(POLICE[1:], 200)
    else:
        r = []
    return {"words": words, "count": len(r), "too_broad": False, "rows": r}


def run_search(page, *, blocked=False, plan_delay=1.5):
    seen_before_plan = {"titles": None}

    def on_unit(route):
        if blocked:
            route.fulfill(status=503, content_type="application/json",
                          body=json.dumps({"detail": "474"}))
            return
        words = parse_qs(urlparse(route.request.url).query).get("w", [])
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(unit_body(words), ensure_ascii=False))

    def on_plan(route):
        time.sleep(plan_delay)   # הפירוק איטי מבדיקת הפתיחה - כמו במציאות
        seen_before_plan["titles"] = page.evaluate(
            "() => [...document.querySelectorAll('#pq-rows .pq-title')].map(e => e.textContent)")
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(PLAN, ensure_ascii=False))

    page.unroute("**/api/queries/**")
    page.route("**/api/queries/unit?*", on_unit)
    page.route("**/api/queries/plan?*", on_plan)
    page.route("**/api/queries/enrich?*", lambda r: r.fulfill(
        status=200, content_type="application/json", body='{"docs":{},"names":{}}'))
    page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
    page.fill("#past-queries-input", TOPIC)
    page.click("#past-queries-btn")
    page.wait_for_selector("#pq-done > *", timeout=20000)
    titles = page.evaluate(
        "() => [...document.querySelectorAll('#pq-rows .pq-title')].map(e => e.textContent)")
    done = page.inner_text("#pq-done")
    return titles, done, seen_before_plan["titles"]


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.click('nav button[data-t="query"]')

        titles, done, before = run_search(page)
        results.append(("אף שורת בריאות לא הוצגה", not any(t in HEALTH for t in titles), str(titles)))
        results.append(("שורות המשטרה הוצגו", all(t in titles for t in POLICE), str(titles)))
        results.append(("שום שורה לא הוצגה לפני שהפירוק חזר", before == [], str(before)))
        results.append(("שורת הסיום", done.startswith("2 תוצאות"), done))
        # החיפוש לא "מסתיים" לפני שיחידות הפירוק חזרו: כל שורה עברה השלמה
        page.wait_for_timeout(300)
        pending = page.evaluate(
            "() => [...document.querySelectorAll('#pq-rows .pq-asked')].filter(e => e.textContent === '…').length")
        results.append(("כל השורות נכנסו לפני שורת הסיום (אין '…' תלוי)", pending == 0, str(pending)))

        titles, done, _ = run_search(page, blocked=True, plan_delay=0.2)
        results.append(("פיד חסום: 'לא זמין כרגע', לא 'לא נמצא'",
                        "לא זמין כרגע" in done and "לא מצא" not in done, done))
        results.append(("פיד חסום: כפתור 'נסה שוב'", page.locator("#pq-retry").count() == 1, ""))
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
