"""ח3 (25.9.2026): "מעדכן..." נתקע לנצח כש-/render נכשל.

שלושה מצבי כשל אמיתיים, מוזרקים דרך page.route: 500 מהשרת (JSON),
504 של Vercel (דף HTML, לא JSON), וניתוק רשת. על הקוד שלפני התיקון -
שלושתם נתקעו, בלי שום הודעה. אחרי - החיווי נעלם והודעה בעברית מופיעה.

**לא רץ ב-CI** (צריך דפדפן ושרת חי). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_preview_failure.py [BASE_URL]
kaytanot-1990 הוא fixture שנטען בלי DB.
"""
import sys
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
ok_all = True
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for mode in ("500", "504html", "abort"):
        page = b.new_page()
        page.goto(BASE)
        page.evaluate("onLawChange('kaytanot-1990')")
        sel = '.node-text[data-node-id="kaytanot-1990/s2/p0"]'
        page.wait_for_selector(sel, timeout=20000)
        def handler(route):
            if mode == "500":
                route.fulfill(status=500, content_type="application/json", body='{"detail":"Internal Server Error"}')
            elif mode == "504html":
                route.fulfill(status=504, content_type="text/html", body="<html>An error occurred with your deployment FUNCTION_INVOCATION_TIMEOUT</html>")
            else:
                route.abort()
        page.route("**/render", handler)
        page.click(sel); page.keyboard.press("End"); page.keyboard.type(" בדיקה")
        page.click("#docx-lines")
        page.wait_for_timeout(3000)
        stuck = not page.is_hidden("#preview-pending")
        err_box = page.locator("#preview-error")
        err = err_box.inner_text() if err_box.count() and err_box.is_visible() else ""
        good = (not stuck) and bool(err) and "Error" not in err
        ok_all &= good
        print(f"{'✓' if good else '✗'} {mode}: stuck={stuck} error_shown={err!r}")
        page.close()
    b.close()
sys.exit(0 if ok_all else 1)
