"""ש3 + ש6 (25.9.2026) - אייקון הוורד בשאילתות: בפינה השמאלית העליונה, ועל כל
שאילתה מנוסחת - גם בשיחה שנפתחת מחדש מ"שיחות קודמות".

הסיבה ל"לפעמים הוא לא מופיע": openConv הציג את תור הטיוטה כטקסט גולמי,
בלי אייקון. הניסוח והחיפוש מדומים (page.route) - בלי מודל ובלי פיד.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_query_word_icon.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
DRAFT = {"kind": "רגילה", "minister": "השר לביטחון לאומי", "mk_name": "עדי עזוז",
         "subject": "מצבת כוח האדם במשטרה",
         "body": "קיימים פערים בין המחוזות.\nרצוני לשאול:\nמהי המצבה בכל מחוז?",
         "removed_addressee": "", "word_count": 12, "word_limit": 50, "within_limit": True}
OLD_CONV = {"id": "c1", "title": "שיחה ישנה", "at": 1758700000000, "minister": "שר הפנים",
            "mk": "נועם כהן", "kind": "דחופה",
            "turns": [{"role": "user", "content": "תנסח לי"},
                      {"role": "assistant", "content": "נושא: תור ישן\nגוף: רקע.\nרצוני לשאול:\nלמה?"},
                      {"role": "user", "content": "תודה"},
                      {"role": "assistant", "content": "בשמחה!"}]}


def icons(page):
    return page.locator("#query-chat .msg.a .msg-action").count()


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/query/draft", lambda r: r.fulfill(
            status=200, content_type="application/json", body=json.dumps(DRAFT, ensure_ascii=False)))
        page.route("**/api/queries/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body='{"units":[],"expanded":false}'))
        page.goto(BASE)
        page.evaluate("() => localStorage.clear()")
        page.reload()
        page.click('nav button[data-t="query"]')
        page.fill("#query-minister-input", DRAFT["minister"])
        page.fill("#query-mk-input", DRAFT["mk_name"])
        page.fill("#query-composer-input", "מחסור בשוטרים")
        page.keyboard.press("Enter")
        page.wait_for_selector("#query-chat .msg.a .msg-action", timeout=10000)
        results.append(("טיוטה חיה - אייקון", icons(page) == 1, str(icons(page))))
        bold = page.evaluate("() => [...document.querySelectorAll('#query-chat .draft b')].map(e => e.textContent)")
        # ש9 (26.9.2026): התווית "גוף" ירדה מהתצוגה (החלטת ברק) - נשארו שתיים.
        results.append(("ש6+ש9: 'נושא' ו'רצוני לשאול' בבולד, בלי 'גוף'",
                        bold == ["נושא:", "רצוני לשאול:"], str(bold)))

        results.append(("ש5: אחרי הניסוח - שם השיחה ליד הכותרת, והמונה 1",
                        page.inner_text("#qconv-current").strip() == DRAFT["subject"]
                        and page.inner_text("#qconv-count") == "1",
                        page.inner_text("#qconv-current") + " / " + page.inner_text("#qconv-count")))

        geo = page.evaluate("""() => {
            const m = document.querySelector('#query-chat .msg.a.has-action');
            const i = m.querySelector('.msg-action').getBoundingClientRect(), r = m.getBoundingClientRect();
            return {left: i.left - r.left, top: i.top - r.top, right: r.right - i.right};
        }""")
        results.append(("האייקון בפינה השמאלית העליונה",
                        geo["left"] < 30 and geo["top"] < 30 and geo["right"] > 100, str(geo)))

        # שיחה חדשה ואז פתיחה מחדש של הקודמת מההיסטוריה
        page.click("#qconv-new")
        page.click("#qconv-history-btn")   # ש5: השיחות ברשימה הנפתחת
        page.locator("#qconv-list .qconv-item").first.click()
        page.wait_for_timeout(300)
        results.append(("שיחה שנפתחה מחדש - האייקון עדיין שם", icons(page) == 1, str(icons(page))))
        results.append(("שיחה שנפתחה מחדש - תיבת הטיוטה, לא 'נושא:' גולמי",
                        page.locator("#query-chat .draft").count() == 1
                        # הצורה הגולמית: "גוף: <הטקסט>" באותה שורה.
                        and "גוף: " + DRAFT["body"].split("\n")[0] not in page.inner_text("#query-chat"),
                        page.inner_text("#query-chat")[:200]))

        # שיחה שנשמרה לפני ש3 (בלי השדה draft)
        page.evaluate("(c) => localStorage.setItem('legislator.queryConversations.v1', JSON.stringify([c]))",
                      OLD_CONV)
        page.reload()
        page.click('nav button[data-t="query"]')
        page.click("#qconv-history-btn")   # ש5: השיחות ברשימה הנפתחת
        page.locator("#qconv-list .qconv-item").first.click()
        page.wait_for_timeout(300)
        results.append(("שיחה ישנה - אייקון על הטיוטה בלבד, לא על 'בשמחה!'", icons(page) == 1,
                        str(icons(page))))
        sent = {}
        if icons(page):
            with page.expect_request("**/api/query/export") as req:
                page.locator("#query-chat .msg-action").first.click()
            sent = json.loads(req.value.post_data)
        results.append(("שיחה ישנה - הייצוא שולח את הסוג, השר והשואל מהשיחה",
                        sent.get("kind") == "דחופה" and sent.get("minister") == "שר הפנים"
                        and sent.get("mk_name") == "נועם כהן" and sent.get("subject") == "תור ישן",
                        str(sent)))
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
