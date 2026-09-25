"""ח4 (25.9.2026) - אייקון פח ליד הפלוס: מוחק סעיף, סעיף קטן או פסקה, ומפיק
הוראת תיקון תקנית; ושני האייקונים גלויים גם בלי ריחוף.

חוק הקייטנות (סעיף שלם) וחוק המאבק בארגוני פשיעה (סעיף קטן, פסקה) - שניהם
fixture, בלי DB. /render אמיתי.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_trash_icon.py [BASE_URL]
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
M = "maavak-2003/פרק ב/s2"


def lines(page):
    page.wait_for_selector("#preview-pending", state="hidden", timeout=20000)
    page.wait_for_timeout(300)
    return page.eval_on_selector_all("#docx-lines .line-row", "els => els.map(e => e.innerText.replace(/\\s+/g, ' ').trim())")


def trash(page, node_id):
    page.locator(f'.node-del-btn[data-actor="{node_id}"]').first.click()   # ח12: הפח של היחידה


def open_law(page, law_id, probe):
    page.goto(BASE)
    page.click('.nav button[data-t="bills"]')  # דף הבית הוא ברירת המחדל (27.9)
    page.evaluate(f"onLawChange('{law_id}')")
    page.wait_for_selector(f'.node-text[data-node-id="{probe}"]', timeout=20000)


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        open_law(page, "kaytanot-1990", "kaytanot-1990/s5/p0")
        st = page.evaluate("""() => {
            const a = document.querySelector('.node-add-btn'), d = document.querySelector('.node-del-btn');
            const ca = getComputedStyle(a), cd = getComputedStyle(d);
            return {addOp: parseFloat(ca.opacity), delOp: parseFloat(cd.opacity),
                    w: a.getBoundingClientRect().width, delW: d.getBoundingClientRect().width};
        }""")
        results.append(("הפלוס והפח גלויים בלי ריחוף", st["addOp"] >= 0.8 and st["delOp"] >= 0.8, str(st)))
        results.append(("גדולים יותר (28px)", st["w"] >= 27 and st["delW"] >= 27, str(st)))

        trash(page, "kaytanot-1990/s5")
        got = lines(page)
        results.append(("פח על סעיף 5 -> 'סעיף 5 – בטל'", any("סעיף 5 – בטל" in x for x in got), str(got)))

        open_law(page, "maavak-2003", f"{M}/ב")
        trash(page, f"{M}/ב")
        got = lines(page)
        results.append(("פח על סעיף קטן (ב) -> 'סעיף קטן (ב) – בטל'",
                        any("בסעיף 2, סעיף קטן (ב) – בטל" in x for x in got), str(got)))

        open_law(page, "maavak-2003", f"{M}/א/1")
        trash(page, f"{M}/א/1")
        got = lines(page)
        results.append(("פח על פסקה (1) -> 'בסעיף 2(א), פסקה (1) – תימחק'",
                        any("בסעיף 2(א), פסקה (1) – תימחק" in x for x in got), str(got)))

        open_law(page, "maavak-2003", f"{M}/א/1")
        trash(page, f"{M}/א")
        got = lines(page)
        results.append(("פח על סעיף קטן (א) עם פסקאותיו -> הוראה אחת 'סעיף קטן (א) – בטל'",
                        any("סעיף קטן (א) – בטל" in x for x in got) and not any("תימחק" in x for x in got),
                        str(got)))
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
