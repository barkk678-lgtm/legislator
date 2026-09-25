"""ש8-ש11 + ש14 (26.9.2026) - תצוגת השאילתה בצ'אט.

ש8: השאלות ממוספרות גם בצ'אט (1., 2.) - כמו בקובץ.
ש9: בלי המילה "גוף", ושורה ריקה בין הנושא לגוף.
ש10: שינוי סוג כשיש כבר טיוטה - נשלחת "נסח לי אותה כשאילתה דחופה", כאילו
     המשתמש כתב אותה, עם הסוג החדש. לפני הטיוטה הראשונה - לא נשלח כלום.
ש11: המונה אומר מה הוא סופר: "(בלי הכותרת והנושא)".
ש14: בחריגה - בלי "!", ולידו "התכנס למגבלת המילים", שנשלח כהודעה עם
     fit_limit; ואם גם אחרי הניסיון הנוסף בשרת עדיין חורג - הודעה גלויה.

המודל מדומה (route על /api/query/draft, לפי הבקשה).
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_query_draft_ui.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
BODY = "בשנה האחרונה נסגרו תחנות.\nרצוני לשאול:\nכמה תקנים חסרים?\nמה התוכנית?"


def draft(kind, wc, limit):
    return {"kind": kind, "minister": "השר לביטחון לאומי", "mk_name": "עדי עזוז", "subject": "מחסור בשוטרים",
            "body": BODY, "removed_addressee": "", "word_count": wc, "word_limit": limit, "within_limit": wc <= limit}


def main() -> int:
    results = []
    sent = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def on_draft(route):
            req = json.loads(route.request.post_data)
            sent.append(req)
            wc = 44 if req["kind"] == "דחופה" else 12    # דחופה: חורגת מ-40, גם אחרי "התכנס"
            limit = 40 if req["kind"] == "דחופה" else 50
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(draft(req["kind"], wc, limit), ensure_ascii=False))
        page.route("**/api/query/draft", on_draft)
        page.route("**/api/queries/**", lambda r: r.fulfill(status=200, content_type="application/json",
                                                            body='{"units":[],"expanded":false}'))
        page.goto(BASE)
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.click('nav button[data-t="query"]')
        page.fill("#query-minister-input", "השר לביטחון לאומי")
        page.fill("#query-mk-input", "עדי עזוז")

        page.select_option("#query-kind-input", "רגילה")
        page.wait_for_timeout(300)
        results.append(("ש10: שינוי סוג לפני טיוטה - לא נשלח כלום", sent == [], str(sent)))

        page.fill("#query-composer-input", "מחסור בשוטרים")
        page.keyboard.press("Enter")
        page.wait_for_selector("#query-chat .msg.a .draft", timeout=15000)
        txt = page.inner_text("#query-chat .msg.a .draft")
        results.append(("ש8: השאלות ממוספרות", "1. כמה תקנים חסרים?" in txt and "2. מה התוכנית?" in txt, txt))
        results.append(("ש9: בלי 'גוף'", "גוף" not in txt, txt))
        lines = txt.split("\n")
        i = next((k for k, ln in enumerate(lines) if ln.startswith("נושא:")), -1)
        results.append(("ש9: שורה ריקה בין הנושא לגוף", i >= 0 and lines[i + 1].strip() == "" and lines[i + 2].startswith("בשנה"),
                        repr(lines[i:i + 3])))
        results.append(("ש11: המונה אומר שהכותרת והנושא לא נספרים", "(בלי הכותרת והנושא)" in txt, txt))
        results.append(("ש14: בלי חריגה - בלי כפתור התכנסות", page.locator("#query-chat .fit-limit-btn").count() == 0, ""))

        # ש10: שינוי סוג אחרי טיוטה
        page.select_option("#query-kind-input", "דחופה")
        page.wait_for_function("() => document.querySelectorAll('#query-chat .msg.a .draft').length === 2", timeout=15000)
        users = page.eval_on_selector_all("#query-chat .msg.u", "els => els.map(e => e.innerText.trim())")
        results.append(("ש10: נשלח 'נסח לי אותה כשאילתה דחופה', עם הסוג החדש",
                        users[-1].endswith("נסח לי אותה כשאילתה דחופה") and sent[-1]["kind"] == "דחופה"
                        and sent[-1]["turns"][-1]["content"] == "נסח לי אותה כשאילתה דחופה", f"{users} / {sent[-1]['kind']}"))

        # ש14: חריגה
        wc_txt = page.locator("#query-chat .msg.a .word-count").last.inner_text()
        results.append(("ש14: 'חורג מהמגבלה' בלי סימן קריאה", "חורג מהמגבלה" in wc_txt and "!" not in wc_txt, wc_txt))
        page.locator("#query-chat .fit-limit-btn").last.click()
        page.wait_for_function("() => document.querySelectorAll('#query-chat .msg.a .draft').length === 3", timeout=15000)
        page.wait_for_timeout(300)
        results.append(("ש14: הלחיצה שולחת הודעה עם fit_limit", sent[-1].get("fit_limit") is True
                        and "עד 40 מילים" in sent[-1]["turns"][-1]["content"], str(sent[-1])[:200]))
        errs = page.eval_on_selector_all("#query-chat .msg.err", "els => els.map(e => e.innerText)")
        results.append(("ש14: גם אחרי הניסיון הנוסף חורג - נאמר במפורש", any("גם אחרי ניסיון נוסף" in e and "44/40" in e for e in errs), str(errs)))
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
