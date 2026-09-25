"""צ1 + צ2 + צ3 (25.9.2026) - השכבה המשותפת לחלונות הצ'אט, בדפדפן.

התשובה של מומחה התקנון מדומה (page.route) - בלי קריאה למודל.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_chat_kit.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
LONG = "\n".join(f"שורה {i} של תשובה ארוכה מאוד על תקנון הכנסת, כדי שתהיה גלילה." for i in range(80))


def fake_stream(route):
    lines = [json.dumps({"delta": LONG[i:i + 200]}, ensure_ascii=False) for i in range(0, len(LONG), 200)]
    lines.append(json.dumps({"done": {"text": LONG, "refused": False, "refusal_reason": None,
                                      "cited_sources": []}}, ensure_ascii=False))
    route.fulfill(status=200, content_type="application/x-ndjson", body="\n".join(lines) + "\n")


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1280, "height": 800})
        page.route("**/api/rules/ask/stream", fake_stream)
        page.goto(BASE)
        page.click('nav button[data-t="rules"]')
        box = page.locator("#rules-composer-input")

        # צ3: Shift+Enter יורד שורה ולא שולח
        box.click()
        page.keyboard.type("שורה ראשונה")
        page.keyboard.press("Shift+Enter")
        page.keyboard.type("שורה שנייה")
        sent_early = page.locator("#rules-chat .msg.u").count()
        results.append(("צ3: Shift+Enter יורד שורה", box.input_value() == "שורה ראשונה\nשורה שנייה"
                        and sent_early == 0, repr(box.input_value())))
        # ... ו-Enter שולח
        page.keyboard.press("Enter")
        page.wait_for_selector("#rules-chat .msg.a .msg-copy", timeout=10000)
        page.wait_for_timeout(500)
        results.append(("צ3: Enter שולח", page.locator("#rules-chat .msg.u").count() == 1, ""))

        # צ1: תשובה ארוכה מהחלון - המסך נשאר על ראש ההודעה
        pos = page.evaluate("""() => {
            const chat = document.getElementById('rules-chat');
            const a = [...chat.querySelectorAll('.msg.a')].pop();
            const top = a.getBoundingClientRect().top - chat.getBoundingClientRect().top;
            return {top, atBottom: chat.scrollHeight - chat.scrollTop - chat.clientHeight < 5,
                    tall: a.offsetHeight > chat.clientHeight};
        }""")
        results.append(("צ1: ראש התשובה בראש החלון, לא בתחתית",
                        pos["tall"] and 0 <= pos["top"] <= 40 and not pos["atBottom"], str(pos)))

        # צ2: אייקון העתקה בפינה הימנית העליונה
        geo = page.evaluate("""() => {
            const a = [...document.querySelectorAll('#rules-chat .msg.a')].pop();
            const btn = a.querySelector('.msg-copy');
            const r = btn.getBoundingClientRect(), br = a.getBoundingClientRect();
            return {rightGap: br.right - r.right, topGap: r.top - br.top};
        }""")
        results.append(("צ2: אייקון העתקה בפינה הימנית העליונה",
                        0 <= geo["rightGap"] <= 30 and 0 <= geo["topGap"] <= 30, str(geo)))
        # ... ונשאר גלוי כשגוללים לאמצע ההודעה
        vis = page.evaluate("""() => {
            const chat = document.getElementById('rules-chat');
            chat.scrollTop += 900;
            const btn = [...chat.querySelectorAll('.msg.a')].pop().querySelector('.msg-copy');
            const r = btn.getBoundingClientRect(), c = chat.getBoundingClientRect();
            return r.top >= c.top - 1 && r.bottom <= c.bottom + 1;
        }""")
        results.append(("צ2: האייקון גלוי גם באמצע הודעה ארוכה", bool(vis), ""))

        # צ2: העתקה מעתיקה את הטקסט, בלי האייקון
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        page.locator("#rules-chat .msg.a .msg-copy").last.click()
        clip = page.evaluate("navigator.clipboard.readText()")
        results.append(("צ2: ההעתקה מעתיקה את התשובה", clip.startswith("שורה 0") and "שורה 79" in clip,
                        clip[:40]))

        # צ1: המשתמש גלל לתחתית בעצמו - ממשיכים לעקוב
        follow = page.evaluate("""async () => {
            const chat = document.getElementById('rules-chat');
            const bubble = appendMsg(chat, 'a', '');
            const span = document.createElement('span'); bubble.appendChild(span);
            const f = followStream(chat, bubble);
            for (let i = 0; i < 30; i++) { span.textContent += 'שורה\\n'.repeat(3); f.update(); }
            chat.scrollTop = chat.scrollHeight;              // המשתמש גולל לתחתית
            await new Promise(r => setTimeout(r, 50));
            for (let i = 0; i < 30; i++) { span.textContent += 'עוד\\n'.repeat(3); f.update(); }
            await new Promise(r => setTimeout(r, 50));
            f.stop();
            return chat.scrollHeight - chat.scrollTop - chat.clientHeight < 5;
        }""")
        results.append(("צ1: אחרי שהמשתמש גלל למטה - ממשיכים לעקוב אחרי הסוף", bool(follow), ""))
        b.close()

    failed = 0
    for name, ok, detail in results:
        print(("✓" if ok else "✗"), name, "" if ok else f"- {detail}")
        failed += not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
