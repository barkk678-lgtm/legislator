"""ח5 (25.9.2026) - "מעדכן..." בחלונית הצעת החוק: בולט, ולא 12px באפור בהיר.

חוק הקייטנות (fixture, בלי DB). /render מושהה 2.5 שניות, כמו באתר החי.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_preview_pending_visible.py [BASE_URL] [screenshot.png]
"""
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
SHOT = sys.argv[2] if len(sys.argv) > 2 else None
LAW = "kaytanot-1990"


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        page.goto(BASE)
        page.click('.nav button[data-t="bills"]')  # דף הבית הוא ברירת המחדל (27.9)
        page.evaluate(f"onLawChange('{LAW}')")
        el = page.locator(f'.node-text[data-node-id="{LAW}/s2/p0"]')
        el.wait_for(timeout=20000)
        page.route("**/render", lambda r: (time.sleep(2.5), r.continue_()))
        el.click()
        page.keyboard.press("End")
        page.keyboard.type(" בדיקה")
        page.wait_for_selector("#preview-pending:not([hidden])", timeout=5000)
        page.wait_for_timeout(300)   # המעבר (transition) של העמעום
        st = page.evaluate("""() => {
            const e = document.getElementById('preview-pending'), cs = getComputedStyle(e);
            const lines = getComputedStyle(document.getElementById('docx-lines'));
            return {size: parseFloat(cs.fontSize), weight: cs.fontWeight, bg: cs.backgroundColor,
                    pos: cs.position, text: e.textContent.trim(), dim: parseFloat(lines.opacity),
                    spinner: !!e.querySelector('.spinner')};
        }""")
        if SHOT:
            page.locator("#docx-approx").screenshot(path=SHOT)
        results.append(("גלוי בזמן ההמתנה, עם 'מעדכן'", st["text"].startswith("מעדכן"), str(st)))
        results.append(("גודל 14px ומעלה, מודגש", st["size"] >= 14 and int(st["weight"]) >= 600, str(st)))
        results.append(("רקע צבעוני, לא שקוף", st["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"), st["bg"]))
        results.append(("ספינר", st["spinner"], ""))
        results.append(("דביק לראש החלונית", st["pos"] == "sticky", st["pos"]))
        results.append(("התוכן מעומעם בזמן העדכון", st["dim"] < 0.6, str(st["dim"])))
        page.wait_for_selector("#preview-pending", state="hidden", timeout=15000)
        after = page.evaluate("() => parseFloat(getComputedStyle(document.getElementById('docx-lines')).opacity)")
        results.append(("אחרי העדכון - החיווי נעלם והתוכן חוזר", after == 1.0, str(after)))
        b.close()
    ok = True
    for label, passed, detail in results:
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), label, "" if passed else detail)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
