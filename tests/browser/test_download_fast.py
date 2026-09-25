"""ח17 + צ5 (26.9.2026) - הורדת Word תוך שניות: דברי ההסבר נכתבים ברקע אחרי
העריכה, והמגדר של חבר/ת הכנסת נשלף כשממלאים את השם.

המודל מדומה (/explanatory מושהה 3 שניות, כמו באתר ~11) ונספר. הבדיקה מודדת
את הזמן מהלחיצה על "הורדה" עד שהבקשה ל-/docx יוצאת, ובודקת שהיא נושאת את
דברי ההסבר שכבר נכתבו. חוק הקייטנות (fixture); /render ו-/docx אמיתיים.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_download_fast.py [BASE_URL]
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
LAW = "kaytanot-1990"
EXPL = ["מוצע לקבוע כי לניהול קייטנה יידרש היתר."]


def main() -> int:
    results = []
    calls = {"expl": [], "docx": [], "gender": [], "export": []}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def on_expl(route):
            calls["expl"].append(time.time())
            time.sleep(3)
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"explanatory": EXPL}, ensure_ascii=False))

        def on_docx(route):
            calls["docx"].append((time.time(), json.loads(route.request.post_data)))
            route.continue_()

        page.route("**/explanatory", on_expl)
        page.route("**/docx", on_docx)
        page.goto(BASE)
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.evaluate(f"onLawChange('{LAW}')")
        el = page.locator(f'.node-text[data-node-id="{LAW}/s2/p0"]')
        el.wait_for(timeout=20000)
        el.click()
        page.keyboard.press("End")
        page.keyboard.type(" בלבד")
        page.locator(f'.node-text[data-node-id="{LAW}/s4/p0"]').click()   # יציאה מהשדה
        page.wait_for_timeout(7000)   # 2.5 שניות רגיעה + 3 שניות "מודל"
        results.append(("דברי ההסבר נכתבו ברקע - בקשה אחת למצב אחד", len(calls["expl"]) == 1, str(len(calls["expl"]))))

        t0 = time.time()
        with page.expect_download(timeout=20000):
            page.click("#download-btn")
        took = calls["docx"][0][0] - t0 if calls["docx"] else 99
        sent = calls["docx"][0][1]["bill"]["explanatory"] if calls["docx"] else None
        results.append(("הלחיצה על 'הורדה' שולחת מיד (פחות משנייה)", took < 1.0, f"{took:.2f}s"))
        results.append(("ההורדה נושאת את דברי ההסבר שנכתבו ברקע", sent == EXPL, str(sent)))
        results.append(("בלי קריאה נוספת למודל בלחיצה", len(calls["expl"]) == 1, str(len(calls["expl"]))))

        # עריכה נוספת ומיד הורדה: מחכים רק ליתרה של הניסוח למצב החדש
        el.click()
        page.keyboard.press("End")
        page.keyboard.type(" ועוד")
        page.locator(f'.node-text[data-node-id="{LAW}/s4/p0"]').click()
        page.wait_for_selector("#preview-pending", state="hidden", timeout=20000)
        with page.expect_download(timeout=30000):
            page.click("#download-btn")
        results.append(("מצב חדש - ניסוח חדש (בדיוק אחד נוסף)", len(calls["expl"]) == 2, str(len(calls["expl"]))))
        results.append(("וההורדה נושאת אותו", len(calls["docx"]) == 2 and calls["docx"][1][1]["bill"]["explanatory"] == EXPL,
                        str(calls["docx"][-1][1]["bill"]["explanatory"]) if calls["docx"] else ""))

        # שאילתה: המגדר נשלף כשממלאים את השם, לא בהורדה
        page.route("**/api/queries/mk-gender?*", lambda r: (calls["gender"].append(r.request.url),
                   r.fulfill(status=200, content_type="application/json",
                             body=json.dumps({"name": "x", "gender": "נקבה"}))))
        page.route("**/api/query/export", lambda r: (calls["export"].append(json.loads(r.request.post_data)),
                   r.continue_()))
        page.route("**/api/query/draft", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(
            {"kind": "רגילה", "minister": "השר", "mk_name": "עדי עזוז", "subject": "נושא", "body": "רקע.\nרצוני לשאול:\nמה?",
             "removed_addressee": "", "word_count": 5, "word_limit": 50, "within_limit": True}, ensure_ascii=False)))
        page.route("**/api/queries/**", lambda r: r.fulfill(status=200, content_type="application/json",
                   body='{"units":[],"expanded":false}') if "mk-gender" not in r.request.url else r.fallback())
        page.click('nav button[data-t="query"]')
        page.fill("#query-minister-input", "השר לביטחון לאומי")
        page.fill("#query-mk-input", "עדי עזוז")
        page.press("#query-mk-input", "Tab")
        page.wait_for_timeout(300)
        results.append(("המגדר נשלף כשממלאים את השם", len(calls["gender"]) == 1, str(calls["gender"])))
        page.fill("#query-composer-input", "מחסור בשוטרים")
        page.keyboard.press("Enter")
        page.wait_for_selector("#query-chat .msg.a .msg-action", timeout=10000)
        with page.expect_download(timeout=20000):
            page.locator("#query-chat .msg-action").first.click()
        results.append(("הייצוא נושא את המגדר, בלי שליפה נוספת",
                        calls["export"] and calls["export"][0].get("gender") == "נקבה" and len(calls["gender"]) == 1,
                        str(calls["export"][:1]) + str(len(calls["gender"]))))
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
