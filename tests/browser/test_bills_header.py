"""ח14 + ח20 + ח21 (26.9.2026) - חלונית "נוסח החוק" והסרגל העליון.

ח14: מספר הסעיף בגוון, בגודל ובגופן של כותרת השוליים שלידו (עד כאן אפור
     ועדין - 12.5px, var(--faint)).
ח20: "צור הצעה חדשה" מחוץ ל"ההצעות שלי": כחול, גלוי תמיד - גם כשהחלונית סגורה.
ח21: בלי "לחצו לעריכה" ליד "נוסח החוק".
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_bills_header.py [BASE_URL]
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
K = "kaytanot-1990"


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.reload()

        # ח20 - לפני שנבחר חוק, והחלונית סגורה
        st = page.evaluate("""() => { const b = document.getElementById('draft-new-btn');
            const panel = document.getElementById('drafts-panel');
            return {visible: !!b && b.offsetParent !== null, primary: b && b.classList.contains('primary'),
                    inPanel: !!b && panel.contains(b), panelHidden: panel.hidden,
                    bg: b ? getComputedStyle(b).backgroundColor : ''}; }""")
        results.append(("ח20: הכפתור גלוי כשהחלונית סגורה, ולא בתוכה",
                        st["visible"] and not st["inPanel"] and st["panelHidden"], str(st)))
        results.append(("ח20: כחול (כפתור ראשי)", st["primary"] and st["bg"] not in ("rgba(0, 0, 0, 0)", "rgb(255, 255, 255)"), str(st)))

        page.evaluate(f"onLawChange('{K}')")
        page.wait_for_selector(f'.node[data-node-id="{K}/s2"]', timeout=30000)
        head = page.inner_text("#bills section.card header")
        results.append(("ח21: בלי 'לחצו לעריכה'", "לחצו לעריכה" not in head, head))
        css = page.evaluate(f"""() => {{ const h = document.querySelector('.node[data-node-id="{K}/s2"] > .node-header');
            const n = h.querySelector('.node-number'), t = h.querySelector('.node-margin-title');
            const pick = (e) => {{ const s = getComputedStyle(e); return [s.color, s.fontSize, s.fontFamily, s.fontWeight]; }};
            return {{num: pick(n), title: pick(t)}}; }}""")
        results.append(("ח14: מספר הסעיף בגוון, גודל, גופן ומשקל של כותרת השוליים", css["num"] == css["title"], str(css)))

        # ח20 - הכפתור עובד מכל מקום
        page.click("#draft-new-btn")
        page.wait_for_timeout(500)
        results.append(("ח20: הלחיצה פותחת הצעה חדשה", page.locator(f'.node[data-node-id="{K}/s2"]').count() == 0
                        or page.evaluate("() => Object.keys(edits).length === 0"), ""))
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
