"""ת3 (25.9.2026) - מומחה התקנון במסך מפוצל: הצ'אט מימין, התקנון משמאל,
ומעליו תגיות לסעיפים שאוזכרו. לחיצה על תגית או על אזכור בתוך התשובה -
גוללת לסעיף ומסמנת אותו.

התשובה מדומה (page.route); התקנון עצמו - /api/rules/reading אמיתי (DB).
**לא רץ ב-CI** (דפדפן + שרת + DB). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_rules_split.py [BASE_URL] [screenshot.png]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
SHOT = sys.argv[2] if len(sys.argv) > 2 else None
TK = "law-tkanon-haknesset"
ANSWER = ("חבר הכנסת רשאי להציע נושא לסדר היום במסגרת מכסה סיעתית (תקנון הכנסת, סעיף 52; "
          "חוק הכנסת, סעיף 12). סעיף שאינו קיים (תקנון הכנסת, סעיף 9999).")


def fake_stream(route):
    lines = [json.dumps({"delta": ANSWER}, ensure_ascii=False),
             json.dumps({"done": {"text": ANSWER, "refused": False, "refusal_reason": None,
                                  "cited_sources": ["תקנון הכנסת, סעיף 52", "תקנון הכנסת, סעיף 99"],
                                  "cited_ids": [f"{TK}/52", f"{TK}/99"]}}, ensure_ascii=False)]
    route.fulfill(status=200, content_type="application/x-ndjson", body="\n".join(lines) + "\n")


VISIBLE = """(id) => {
    const el = [...document.querySelectorAll('#rules-doc .rules-sec[data-sec]')].find(e => e.dataset.sec === id);
    if (!el) return {found: false};
    const b = document.getElementById('rules-doc').getBoundingClientRect(), r = el.getBoundingClientRect();
    return {found: true, hit: el.classList.contains('rules-hit'),
            visible: r.top >= b.top - 1 && r.top < b.bottom - 20,
            hits: document.querySelectorAll('#rules-doc .rules-hit').length};
}"""


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/rules/ask/stream", fake_stream)
        page.goto(BASE)
        page.click('nav button[data-t="rules"]')
        page.wait_for_selector("#rules-doc .rules-sec[data-sec]", timeout=30000)

        geo = page.evaluate("""() => {
            const chat = document.getElementById('rules-chat').closest('.card').getBoundingClientRect();
            const doc = document.querySelector('.rules-source-card').getBoundingClientRect();
            return {chatLeft: chat.left, docRight: doc.right, chatW: chat.width, docW: doc.width};
        }""")
        results.append(("מסך מפוצל: הצ'אט מימין, התקנון משמאל",
                        geo["chatLeft"] >= geo["docRight"] - 1 and geo["docW"] > 400 and geo["chatW"] > 400, str(geo)))
        tabs = page.evaluate("() => [...document.querySelectorAll('#rules-doc-tabs button')].map(b => [b.textContent, b.classList.contains('on')])")
        results.append(("שלושת המקורות, תקנון הכנסת פתוח",
                        [t for t, _ in tabs] == ["תקנון הכנסת", "חוק הכנסת", "חוק-יסוד: הכנסת"] and tabs[0][1],
                        str(tabs)))
        head = page.evaluate(f"""() => {{ const e = document.querySelector('#rules-doc .rules-sec[data-sec="{TK}/52"] .rules-sec-head');
            return e ? e.textContent : null; }}""")
        results.append(("סעיף 52 בתקנון - עם כותרת השוליים", head and head.startswith("52.") and "לסדר היום" in head, str(head)))
        results.append(("לפני תשובה - אין שורת תגיות", not page.is_visible("#rules-cited"), ""))

        page.fill("#rules-composer-input", "מה ההליך להצעה לסדר היום?")
        page.keyboard.press("Enter")
        page.wait_for_selector("#rules-chat a.rules-cite", timeout=10000)
        chips = page.evaluate("() => [...document.querySelectorAll('#rules-cited-chips .pq-chip')].map(c => c.textContent)")
        results.append(("תגיות: הסעיפים שאוזכרו, בלי כפילות", chips == ["סעיף 52", "סעיף 99", "חוק הכנסת 12"], str(chips)))
        links = page.evaluate("() => [...document.querySelectorAll('#rules-chat a.rules-cite')].map(a => a.textContent)")
        results.append(("האזכורים בתשובה - קישורים; סעיף שאינו קיים - טקסט",
                        links == ["תקנון הכנסת, סעיף 52", "חוק הכנסת, סעיף 12"]
                        and "סעיף 9999" in page.inner_text("#rules-chat"), str(links)))

        page.locator("#rules-cited-chips .pq-chip", has_text="סעיף 99").click()
        page.wait_for_timeout(300)
        st = page.evaluate(VISIBLE, f"{TK}/99")
        results.append(("לחיצה על תגית: גלילה לסעיף 99 וסימונו",
                        st.get("hit") and st.get("visible") and st.get("hits") == 1, str(st)))
        results.append(("התגית שנלחצה מסומנת",
                        page.evaluate("() => [...document.querySelectorAll('#rules-cited-chips .pq-chip.on')].map(c => c.textContent)") == ["סעיף 99"], ""))

        page.locator("#rules-chat a.rules-cite", has_text="חוק הכנסת, סעיף 12").click()
        page.wait_for_timeout(300)
        st = page.evaluate(VISIBLE, "law-2000325/12")
        on = page.evaluate("() => [...document.querySelectorAll('#rules-doc-tabs button.on')].map(b => b.textContent)")
        results.append(("לחיצה על אזכור בתשובה: עובר לחוק הכנסת, גולל לסעיף 12 ומסמן",
                        on == ["חוק הכנסת"] and st.get("hit") and st.get("visible"), f"{on} {st}"))
        if SHOT:
            page.screenshot(path=SHOT)

        page.locator("#rules-chat a.rules-cite", has_text="תקנון הכנסת, סעיף 52").click()
        page.wait_for_timeout(300)
        st = page.evaluate(VISIBLE, f"{TK}/52")
        results.append(("וחזרה לתקנון - סעיף 52", st.get("hit") and st.get("visible") and st.get("hits") == 1, str(st)))
        results.append(("הדף עצמו לא נגלל", page.evaluate("() => scrollY") == 0, str(page.evaluate("() => scrollY"))))
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
