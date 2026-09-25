"""ח2 (25.9.2026): "הוספת סעיף שלא נשמרת" - בחוק בתי המשפט (עבירות
שענשן מוות), אחרי שני שינויים.

**המנגנון שנמצא:** כל עריכה מפעילה רענון של ההצעה, ו-refreshPreview
בונה את כל עץ העריכה מחדש (rebuildTree). תפריט ההוספה יושב בתוך העץ -
ולכן תשובה שחוזרת כשהתפריט פתוח **מוחקת אותו**, עם כל מה שהוקלד בו.
באתר החי התשובה לוקחת שניות, בדיוק הזמן שבו פותחים את התפריט אחרי
עריכה. אחרי רענון הדף אין עדכון בדרך - ולכן "אחרי רענון זה עבד".
והשערת הסעיפים שנמחקו נבדקה ונשללה: 16/16 הוספות הצליחו בחוק הזה,
כולל ליד סעיף 3 המבוטל, כשאין מרוץ.

**מסלול שקט שני:** "סעיף ראשי" בלי כותרת שוליים - הלחיצה על "הוסף"
רק העבירה פוקוס לשדה, בלי שום הודעה.

**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_insert_menu_survives.py [BASE_URL]
"""
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
LAW = "kaytanot-1990"   # fixture - נטען בלי DB
RENDER_DELAY = 3.0      # כמו באתר החי: Vercel + Supabase


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")

        # 1. התפריט שורד רענון שחוזר בזמן שהוא פתוח
        page = b.new_page()
        page.goto(BASE)
        page.evaluate(f"onLawChange('{LAW}')")
        page.wait_for_selector(f'.node-text[data-node-id="{LAW}/s2/p0"]', timeout=20000)
        page.route("**/render", lambda r: (time.sleep(RENDER_DELAY), r.continue_()))
        el = page.locator(f'.node-text[data-node-id="{LAW}/s2/p0"]')
        el.click(); page.keyboard.press("End"); page.keyboard.type(" בדיקה")
        w = page.locator(f'#law-tree .node[data-node-id="{LAW}/s2"]').first
        page.locator(f'.node-add-btn[data-actor="{LAW}/s2"]').click()   # ח12: הזוג של היחידה, לא מבנה ה-DOM
        menu = page.locator(".insert-menu:not([hidden])").first
        ok1 = False
        try:
            btn = menu.locator(".insert-level-btn:not([disabled])", has_text="הוסף סעיף ראשי").first
            btn.wait_for(timeout=10000)
            btn.click()
            menu.locator(".insert-margin-title-input").fill("כותרת חדשה")
            menu.locator(".insert-text-input").fill("תוכן הסעיף החדש.")
            page.wait_for_timeout(int(RENDER_DELAY * 1000) + 500)  # הרענון חוזר כשהטופס מלא
            typed_kept = menu.locator(".insert-text-input").input_value() == "תוכן הסעיף החדש." if menu.count() else False
            menu.locator(".insert-submit-btn").click(timeout=3000)
            page.wait_for_timeout(int(RENDER_DELAY * 1000) + 2500)
            ok1 = typed_kept and "תוכן הסעיף החדש" in page.inner_text("#docx-lines")
            detail = f"typed_kept={typed_kept}"
        except Exception as e:  # noqa: BLE001
            detail = f"{type(e).__name__}: {str(e).splitlines()[0][:100]}"
        results.append(("התפריט שורד רענון שחוזר כשהוא פתוח, וההוספה נכנסת להצעה", ok1, detail))
        page.close()

        # 2. סעיף ראשי בלי כותרת שוליים - הודעה גלויה, לא פוקוס שקט
        page = b.new_page()
        page.goto(BASE)
        page.evaluate(f"onLawChange('{LAW}')")
        page.wait_for_selector(f'.node-text[data-node-id="{LAW}/s2/p0"]', timeout=20000)
        w = page.locator(f'#law-tree .node[data-node-id="{LAW}/s2"]').first
        page.locator(f'.node-add-btn[data-actor="{LAW}/s2"]').click()   # ח12: הזוג של היחידה, לא מבנה ה-DOM
        menu = page.locator(".insert-menu:not([hidden])").first
        btn = menu.locator(".insert-level-btn:not([disabled])", has_text="הוסף סעיף ראשי").first
        btn.wait_for(timeout=10000)
        btn.click()
        menu.locator(".insert-text-input").fill("תוכן בלי כותרת.")
        menu.locator(".insert-submit-btn").click()
        page.wait_for_timeout(300)
        msg = menu.locator(".insert-form-error")
        shown = msg.count() and msg.is_visible() and "כותרת" in msg.inner_text()
        results.append(("בלי כותרת שוליים - הודעה גלויה", bool(shown),
                        msg.inner_text() if msg.count() else "אין הודעה"))
        page.close()
        b.close()

    failed = 0
    for name, ok, detail in results:
        print(("✓" if ok else "✗"), name, "" if ok else f"- {detail}")
        failed += not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
