"""צ6 (26.9.2026) - כפתור ההעתקה בצ'אט מעתיק רק את הנוסח.

בהודעה עם נוסח שהמערכת ניסחה (שאילתה, הצעה לסדר) - רק מה שבתוך חלון
הנוסח: לא "ניסחתי טיוטה לפי הפורמט המקובל" ולא מונה המילים. בהודעה בלי
נוסח - ההודעה. ובשני המקרים שבירות השורה נשמרות: עד כאן הטקסט נקרא
מעותק מנותק של ההודעה, ששם innerText מתנהג כמו textContent - כל השורות
הודבקו לשורה אחת.

המודל מדומה (route); הלוח נקרא מהדפדפן (clipboard-read).
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_copy_draft.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
QUERY = {"kind": "רגילה", "minister": "השר לביטחון לאומי", "mk_name": "עדי עזוז", "subject": "מחסור בשוטרים",
         "body": "בשנה האחרונה נסגרו תחנות.\nרצוני לשאול:\n1. כמה תקנים חסרים?\n2. מה התוכנית?",
         "removed_addressee": "", "word_count": 14, "word_limit": 50, "within_limit": True}
AGENDA = {"subject": "המחסור בשוטרים", "reasoning": "בשנה האחרונה נסגרו תחנות משטרה.",
          "request_text": "אבקש לדון בנושא במליאה.", "mk_name": "עדי עזוז"}


def copied(page, chat_sel):
    page.evaluate("() => navigator.clipboard.writeText('')")
    page.locator(f"{chat_sel} .msg.a .msg-copy").last.click()
    page.wait_for_timeout(300)
    return page.evaluate("() => navigator.clipboard.readText()")


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/query/draft", lambda r: r.fulfill(status=200, content_type="application/json",
                                                               body=json.dumps(QUERY, ensure_ascii=False)))
        page.route("**/api/queries/**", lambda r: r.fulfill(status=200, content_type="application/json",
                                                            body='{"units":[],"expanded":false}'))
        page.route("**/api/agenda/draft", lambda r: r.fulfill(status=200, content_type="application/json",
                                                                body=json.dumps(AGENDA, ensure_ascii=False)))
        page.goto(BASE)
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")

        # שאילתה
        page.click('nav button[data-t="query"]')
        page.fill("#query-minister-input", "השר לביטחון לאומי")
        page.fill("#query-mk-input", "עדי עזוז")
        page.fill("#query-composer-input", "מחסור בשוטרים")
        page.keyboard.press("Enter")
        page.wait_for_selector("#query-chat .msg.a .draft", timeout=15000)
        text = copied(page, "#query-chat")
        results.append(("שאילתה - בלי 'ניסחתי טיוטה'", "ניסחתי" not in text, text))
        results.append(("שאילתה - בלי מונה המילים", "מילים" not in text, text))
        results.append(("שאילתה - שבירות שורה ומספור נשמרים",
                        "רצוני לשאול:\n1. כמה תקנים חסרים?\n2. מה התוכנית?" in text, repr(text)))
        results.append(("שאילתה - הנושא והנמען בנוסח", "מחסור בשוטרים" in text and "השר לביטחון לאומי" in text, text))

        # הצעה לסדר
        page.click('nav button[data-t="agenda"]')
        page.fill("#agenda-mk-input", "עדי עזוז")
        page.fill("#agenda-composer-input", "המחסור בשוטרים")
        page.keyboard.press("Enter")
        page.wait_for_selector("#agenda-chat .msg.a .draft", timeout=15000)
        text = copied(page, "#agenda-chat")
        results.append(("הצעה לסדר - בלי 'הנה נוסח מוצע'", "הנה נוסח" not in text, text))
        results.append(("הצעה לסדר - שורה לכל חלק", text.split("\n")[0] == "הצעה לסדר היום"
                        and "\nאבקש לדון בנושא במליאה." in text, repr(text)))

        # הודעה בלי נוסח - כל ההודעה, עם שבירות השורה
        page.evaluate("""() => appendMsg(document.getElementById('agenda-chat'), 'a', 'שורה ראשונה<br>שורה שנייה')""")
        text = copied(page, "#agenda-chat")
        results.append(("הודעה בלי נוסח - כולה, בשתי שורות", text == "שורה ראשונה\nשורה שנייה", repr(text)))
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
