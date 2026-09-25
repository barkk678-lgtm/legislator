"""ח11-ב (26.9): "(א) הופך ל-(א)(1)" מתוך סעיף קטן בלי פסקאות - בממשק.

חוק-יסוד: הכנסת, סעיף 6(א) ("כל אזרח ישראלי, שביום הגשת רשימת המועמדים...")
- סעיף קטן אמיתי בלי פסקאות. עד כאן התפריט לא הציע שם "פסקה" (השרת החזיר
"הוספת פסקה זמינה רק כשעומדים על פסקה ממוספרת קיימת", והאפשרות הוסתרה).
עכשיו: "הוסף פסקה (יהיה (2))", ובהצעה - `בסעיף 6(א), האמור בו יסומן "(1)"
ואחריו יבוא:`, כמו התקדים ברשומות (הצעת חוק הממשלה 1924, עמ' 676, פריט (8)).

**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_first_paragraph.py [BASE_URL]
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
UNIT = "law-2000037/s6/א"
NEW_TEXT = "על אף האמור בפסקה (1), מי שנידון כאמור בסעיף קטן (ג) לא יהיה מועמד."


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.evaluate("onLawChange('law-2000037')")
        page.wait_for_selector(f'.node[data-node-id="{UNIT}"]', timeout=60000)

        page.locator(f'.node-add-btn[data-actor="{UNIT}"]').click()
        menu = page.locator(".insert-menu:not([hidden])").first
        btn = menu.locator(".insert-level-btn:not([disabled])", has_text="פסקה").first
        try:
            btn.wait_for(timeout=30000)
            label = btn.inner_text()
        except Exception:  # noqa: BLE001
            label = ""
        results.append(('התפריט על 6(א) מציע "פסקה" עם התווית (2)', "(2)" in label, label or "אין אפשרות"))
        if label:
            btn.click()
            menu.locator(".insert-text-input").fill(NEW_TEXT)
            menu.locator(".insert-submit-btn").click()
            page.wait_for_function(
                "() => document.querySelector('#docx-lines')?.innerText.includes('יסומן')", timeout=60000)
            hint = page.inner_text("#docx-lines")
            results.append(('ההצעה: "בסעיף 6(א), האמור בו יסומן "(1)" ואחריו יבוא:"',
                            'בסעיף 6(א), האמור בו יסומן "(1)" ואחריו יבוא:' in hint, hint[:300]))
            results.append(('ההצעה: "(2) <הנוסח החדש>" במרכאות', f'"(2) {NEW_TEXT}"' in hint, hint[:300]))
            results.append(("בלי מחיקה של הנוסח הקיים", "יימחק" not in hint and "במקום" not in hint, hint[:300]))
            labels = page.evaluate(f"""() => [...document.querySelectorAll('.node[data-node-id="{UNIT}"] .node')]
                .map(n => n.dataset.nodeId)""")
            results.append(("בעץ: (1) ו-(2) בתוך 6(א)", f"{UNIT}/1" in labels and len(labels) >= 2, str(labels)))
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
