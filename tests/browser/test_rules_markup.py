"""ת1 (25.9.2026) - תשובות מומחה התקנון: בלי "#" ו-"**" על המסך.

התשובה מדומה (page.route) - בדיוק צורת התשובה שנמדדה לפני התיקון: פותחת
ב"# ..." ו"## ...", עם **הדגשות**. עד כאן הממשק הציג את הסימנים כמות שהם.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_rules_markup.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
ANSWER = ("# ההבדל בין הצעה לסדר היום להצעה דחופה\n\n## הצעה לסדר היום\n\n"
          "חבר הכנסת רשאי להציע **במסגרת מכסה סיעתית** נושא לסדר היום.\n"
          "* דיון ביום ד'\n- הצבעה על הכללה\n\n<b>לא HTML</b>")


def fake_stream(route):
    parts = [ANSWER[i:i + 7] for i in range(0, len(ANSWER), 7)]   # קטעים קטנים - גם "**" נחתך
    lines = [json.dumps({"delta": p}, ensure_ascii=False) for p in parts]
    lines.append(json.dumps({"done": {"text": ANSWER, "refused": False, "refusal_reason": None,
                                      "cited_sources": []}}, ensure_ascii=False))
    route.fulfill(status=200, content_type="application/x-ndjson", body="\n".join(lines) + "\n")


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/rules/ask/stream", fake_stream)
        page.goto(BASE)
        page.click('nav button[data-t="rules"]')
        page.fill("#rules-composer-input", "מה ההבדל בין הצעה לסדר היום להצעה דחופה?")
        page.keyboard.press("Enter")
        page.wait_for_selector("#rules-chat .msg.a .msg-copy", timeout=10000)
        page.wait_for_timeout(400)
        msg = page.locator("#rules-chat .msg.a").last
        text = msg.inner_text()
        results.append(("אין '#' בתשובה", "#" not in text, text[:120]))
        results.append(("אין '**' בתשובה", "**" not in text, text[:120]))
        bold = msg.evaluate("m => [...m.querySelectorAll('b')].map(e => e.textContent)")
        results.append(("ההדגשה - בולד אמיתי", bold == ["במסגרת מכסה סיעתית"], str(bold)))
        results.append(("רשימה - תבליטים", "• דיון ביום ד'" in text and "• הצבעה על הכללה" in text, text))
        results.append(("HTML מהמודל מוצג כטקסט, לא מפוענח", "<b>לא HTML</b>" in text, text[-40:]))
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
