"""הלוגו בראש תפריט הצד (26.9.2026) - במקום הטקסט "Legislator AI / ארגז הכלים הפרלמנטרי".

**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_logo.py [BASE_URL]
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.wait_for_function("() => { const i = document.querySelector('.rail .brand img'); return i && i.complete; }")
        st = page.evaluate("""() => { const brand = document.querySelector('.rail .brand');
            const img = brand.querySelector('img'); const r = img.getBoundingClientRect();
            return {natural: img.naturalWidth, w: r.width, h: r.height, alt: img.alt,
                    text: brand.innerText.trim(), railW: document.querySelector('.rail').getBoundingClientRect().width}; }""")
        results.append(("הלוגו נטען (לא תמונה שבורה)", st["natural"] == 2000, str(st)))
        results.append(("ממלא את רוחב התפריט, ביחס המקורי", st["w"] > 200 and abs(st["w"] / st["h"] - 2000 / 727) < 0.05, str(st)))
        results.append(("בלי הטקסט הישן לצידו", st["text"] == "", repr(st["text"])))
        results.append(("טקסט חלופי לקוראי מסך", "Legislator AI" in st["alt"], st["alt"]))
        results.append(("בלי שגיאות בדף", not errors, str(errors)))
        page.screenshot(path=sys.argv[2] if len(sys.argv) > 2 else "/tmp/logo.png", clip={"x": 1400 - 260, "y": 0, "width": 260, "height": 220})
        b.close()
    for name, ok, info in results:
        print(("OK  " if ok else "FAIL"), name, "" if ok else f"-- {info}")
    bad = [r for r in results if not r[1]]
    print("test_logo:", "כל הבדיקות עברו" if not bad else f"נכשלו {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
