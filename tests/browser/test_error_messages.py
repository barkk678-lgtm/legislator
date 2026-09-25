"""ח18 + ח19 (26.9.2026) - הודעות הכשל בהצעות חוק.

ח19: המיקום ההיררכי המדויק ("בסעיף 2(א)(1)", לא "בסעיף 2"), והסיבה במילים של
משתמש כשהיא ידועה. ובדרך: החלפת סדר של שתי מילים ("אדם קייטנה" -> "קייטנה
אדם") הפילה את השרת (500, "השרת לא הצליח לעדכן") - עכשיו זו הודעת כשל רגילה.

ח18: הודעה על כשל יורדת ברגע שהשינוי נקלט - גם כשהמשתמש עובד בשדה אחר. עד
כאן רענון בזמן פוקוס בשדה דילג על הסימון של כל השדות, ושדה שנכשל נשאר אדום.

חוק הקייטנות וחוק המאבק בארגוני פשיעה (fixtures). /render אמיתי; במקרה של
הסעיף הקטן מוזרקת סיבה של השרת (כמו ב-test_failure_lines).
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_error_messages.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
K = "kaytanot-1990"
S2 = f'.node-text[data-node-id="{K}/s2/p0"]'
S4 = f'.node-text[data-node-id="{K}/s4/p0"]'
M = "maavak-2003/פרק ב/s2"


def settle(page):
    page.wait_for_selector("#preview-pending", state="hidden", timeout=20000)
    page.wait_for_timeout(300)


def set_text(page, sel, text):
    page.evaluate("""([s, t]) => { const el = document.querySelector(s);
        renderTracked(el, fieldOriginal(el), t); recordField(el); return refreshPreview(); }""", [sel, text])
    settle(page)


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.evaluate(f"onLawChange('{K}')")
        page.wait_for_selector(S2, timeout=20000)
        orig = page.evaluate(f"() => fieldOriginal(document.querySelector('{S2}'))")

        # החלפת סדר מילים: לא 500, אלא הודעת כשל
        set_text(page, S2, orig.replace("אדם קייטנה", "קייטנה אדם"))
        err_visible = page.is_visible("#preview-error")
        hint = page.inner_text("#download-hint")
        results.append(("החלפת סדר מילים - בלי 'השרת לא הצליח'", not err_visible,
                        page.inner_text("#preview-error") if err_visible else ""))
        results.append(("במקומה - הודעת כשל עם סיבה", hint.startswith("לא הצלחתי לקלוט את התיקון שביקשת לעשות בסעיף 2:")
                        and "יותר מפעם אחת" in hint, hint))

        # חיבור מילים - סיבה במילים של משתמש
        set_text(page, S2, orig.replace("לא ינהל", "לאינהל"))
        hint = page.inner_text("#download-hint")
        results.append(("חיבור מילים - 'השינוי חיבר, פיצל או שינה חלק ממילה'", "חלק ממילה" in hint, hint))

        # ח18: כשל -> אדום; עבודה בשדה אחר; השינוי בשדה שנכשל נקלט -> האדום יורד
        page.click("h2")
        settle(page)
        red = page.evaluate(f"() => document.querySelector('{S2}').classList.contains('edit-unsupported')")
        results.append(("הכשל מסומן באדום", red, str(red)))
        page.locator(S4).click()
        page.keyboard.press("End")
        page.keyboard.type(" בלבד")
        settle(page)
        set_text(page, S2, orig.replace("קייטנה", "קייטנה מפוקחת"))   # הפוקוס עדיין ב-s4
        st = page.evaluate(f"""() => ({{red: document.querySelector('{S2}').classList.contains('edit-unsupported'),
            focusS4: document.activeElement === document.querySelector('{S4}'),
            hint: document.getElementById('download-hint').innerText}})""")
        results.append(("השינוי נקלט בזמן עבודה בשדה אחר - האדום יורד וההודעה יורדת",
                        st["focusS4"] and not st["red"] and st["hint"] == "", str(st)))

        # ח19: המיקום ההיררכי - סעיף קטן בתוך פרק
        def inject(route):
            resp = route.fetch()
            data = resp.json()
            data["edit_statuses"] = [{"node_id": f"{M}/א/1", "ok": False, "field": "text",
                                      "reason": "לא נמצא ביטוי ייחודי להחלפה (אפילו אחרי הרחבה)"},
                                     {"node_id": f"{M}/ב", "ok": False, "field": "text", "reason": "x"}]
            route.fulfill(response=resp, body=json.dumps(data, ensure_ascii=False),
                          headers={**resp.headers, "content-type": "application/json"})
        page.evaluate("onLawChange('maavak-2003')")
        page.wait_for_selector(f'.node-text[data-node-id="{M}/א/1"]', timeout=20000)
        page.route("**/render", inject)
        page.evaluate("refreshPreview()")
        page.wait_for_selector("#download-hint .failure-line", timeout=20000)
        lines = page.eval_on_selector_all("#download-hint .failure-line", "els => els.map(e => e.textContent)")
        results.append(("מיקום מדויק + סיבה: 'בסעיף 2(א)(1): הביטוי שערכת מופיע שם יותר מפעם אחת'",
                        len(lines) == 2 and lines[0].startswith("לא הצלחתי לקלוט את התיקון שביקשת לעשות בסעיף 2(א)(1): הביטוי שערכת מופיע"),
                        str(lines)))
        results.append(("סיבה לא ידועה - בלי מונח פנימי, רק המיקום 'בסעיף 2(ב)'",
                        len(lines) == 2 and lines[1] == "לא הצלחתי לקלוט את התיקון שביקשת לעשות בסעיף 2(ב)", str(lines)))
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
