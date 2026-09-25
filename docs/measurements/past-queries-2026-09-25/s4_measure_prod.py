"""ש4: הלקוח האמיתי בדפדפן; כל /api/queries/* מנותב לאתר החי (IP של Vercel)."""
import json, sys, time, httpx
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
PROD = "https://legislator-tau.vercel.app"
OUT = sys.argv[1]
TOPICS = sys.argv[2:] or ["מחסור בכוח אדם במשטרת ישראל", "מחסור בשוטרים", "מחסור במורים בבתי ספר תיכוניים",
          "מצוקת הדיור בפריפריה", "אלימות במערכת החינוך", "זמני המתנה לניתוחים בפריפריה",
          "זיהום אוויר במפרץ חיפה", "תחבורה ציבורית בנגב"]
client = httpx.Client(timeout=60)
codes = []
def relay(route):
    u = urlparse(route.request.url)
    r = client.get(PROD + u.path + ("?" + u.query if u.query else ""))
    codes.append((u.path.rsplit("/", 1)[-1], r.status_code))
    route.fulfill(status=r.status_code, content_type="application/json", body=r.content)
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.route("**/api/queries/**", relay)
    page.goto("http://127.0.0.1:8010/"); page.evaluate("localStorage.clear()")
    page.click('nav button[data-t="query"]')
    page.wait_for_timeout(1500)
    for q in TOPICS:
        codes.clear()
        page.fill("#past-queries-input", q); page.locator("#past-queries-input").press("Enter")
        page.wait_for_function("() => document.getElementById('pq-status') === null && document.querySelector('#pq-done > *')", timeout=240000)
        titles = page.eval_on_selector_all("#pq-rows [data-qid] .pq-title", "els => els.map(e => e.textContent.trim())")
        done = page.inner_text("#pq-done")
        unit_codes = [c for n, c in codes if n.startswith("unit")]
        res[q] = {"titles": titles, "done": done, "units_ok": unit_codes.count(200), "units_total": len(unit_codes)}
        print(f"== {q}: {len(titles)} | units {unit_codes.count(200)}/{len(unit_codes)} | {done[:50]}", flush=True)
        for t in titles: print("   -", t)
        json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
        time.sleep(40)
    b.close()
