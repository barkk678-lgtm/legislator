"""צ7 (26.9.2026) - הלקוח שולח לשרת את מזהה המשתמש האנונימי ואת מזהה השיחה.

אין הרשמה: מזהה אנונימי נוצר בדפדפן פעם אחת (localStorage) ונשלח בכותרת
X-Chat-User בשלושת הצ'אטים - אותו מזהה. X-Chat-Conv הוא מזהה השיחה כפי
שהיא נשמרת בהיסטוריה (mountConvHistory), כבר מההודעה הראשונה, ונשאר זהה
לאורך השיחה; "שיחה חדשה" מקבלת מזהה חדש. הלקוח לא ניגש לטבלה בעצמו.
המודל מדומה (route).
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_chat_log_headers.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def main() -> int:
    results = []
    seen = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def grab(body, ctype="application/json"):
            def handler(route):
                h = route.request.headers
                seen.append((route.request.url.split("/api/")[1], h.get("x-chat-user"), h.get("x-chat-conv")))
                route.fulfill(status=200, content_type=ctype, body=body)
            return handler
        page.route("**/api/query/draft", grab(json.dumps({"chat_reply": "בשמחה!", "chat_kind": "chitchat"}, ensure_ascii=False)))
        page.route("**/api/agenda/draft", grab(json.dumps({"chat_reply": "בשמחה!", "chat_kind": "chitchat"}, ensure_ascii=False)))
        page.route("**/api/rules/ask/stream", grab(json.dumps({"done": {"text": "בשמחה!", "refused": False}}, ensure_ascii=False) + "\n",
                                                   "application/x-ndjson"))
        page.goto(BASE)
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.reload()

        def send(tab, sel, extra=None):
            page.click(f'nav button[data-t="{tab}"]')
            for k, v in (extra or {}).items():
                page.fill(k, v)
            page.fill(sel, "תודה")
            page.keyboard.press("Enter")
            page.wait_for_timeout(700)
        send("query", "#query-composer-input", {"#query-minister-input": "השר", "#query-mk-input": "עדי"})
        send("query", "#query-composer-input")
        send("agenda", "#agenda-composer-input", {"#agenda-mk-input": "עדי"})
        send("rules", "#rules-composer-input")
        users = {u for _, u, _ in seen}
        results.append(("מזהה משתמש אחד בשלושת הצ'אטים", len(seen) == 4 and len(users) == 1 and all(users), str(seen)))
        q = [c for path, _, c in seen if path.startswith("query")]
        saved = page.evaluate("() => JSON.parse(localStorage.getItem('legislator.queryConversations.v1') || '[]').map(c => c.id)")
        results.append(("מזהה השיחה - מההודעה הראשונה, זהה לאורכה ולשמור בהיסטוריה",
                        len(q) == 2 and q[0] == q[1] and q[0] in saved, f"{q} / {saved}"))
        stored = page.evaluate("() => localStorage.getItem('legislator.anonUserId')")
        results.append(("המזהה האנונימי נשמר בדפדפן", stored == next(iter(users)), str(stored)))
        page.click('nav button[data-t="query"]')
        page.click("#qconv-new")
        send("query", "#query-composer-input")
        results.append(("שיחה חדשה - מזהה שיחה חדש", seen[-1][2] and seen[-1][2] != q[0], str(seen[-1])))
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
