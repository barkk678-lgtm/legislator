"""ת7 + ס2 (26.9.2026) - היסטוריית שיחות במומחה התקנון ובהצעה לסדר.

אותו רכיב שבנה את ההיסטוריה של השאילתות (mountConvHistory) - "היסטוריה"
עם רשימה צפה ו"שיחה חדשה" שמאפס - מחובר עכשיו גם לתקנון ולהצעה לסדר.
נבדק: שיחה נשמרת אחרי כל תור; "חדשה" מנקה (בתקנון - גם תגיות הסעיפים
וההצעה לדוגמה); פתיחה מההיסטוריה משחזרת את השיחה, כולל הקישורים לסעיפים
והטיוטה; ולכל צ'אט שיחות משלו. המודל מדומה (route).
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_conv_history_shared.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
ANSWER = "הצעה לסדר היום נדונה לפי הכללים [מקור:law-tkanon-haknesset/52]."
SHOWN = "הצעה לסדר היום נדונה לפי הכללים (תקנון הכנסת, סעיף 52)."
AGENDA = {"subject": "המחסור בשוטרים", "reasoning": "נסגרו תחנות.", "request_text": "אבקש לדון.", "mk_name": "עדי עזוז"}


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        stream = "\n".join(json.dumps(x, ensure_ascii=False) for x in [
            {"delta": SHOWN}, {"done": {"text": SHOWN, "refused": False, "cited_ids": ["law-tkanon-haknesset/52"]}}]) + "\n"
        page.route("**/api/rules/ask/stream", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=stream))
        page.route("**/api/agenda/draft", lambda r: r.fulfill(status=200, content_type="application/json",
                                                                body=json.dumps(AGENDA, ensure_ascii=False)))
        page.goto(BASE)
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.reload()

        same = page.evaluate("""() => ['qconv', 'rconv', 'aconv'].every(p =>
            document.getElementById(p + '-history-btn') && document.getElementById(p + '-new')
            && document.getElementById(p + '-menu').classList.contains('qconv-menu'))""")
        results.append(("רכיב אחד בשלושת הצ'אטים (אותם אלמנטים ומחלקות)", same, str(same)))

        # --- תקנון ---
        page.click('nav button[data-t="rules"]')
        page.wait_for_function("() => typeof rulesDocs !== 'undefined' && rulesDocs && rulesDocs.length === 3", timeout=30000)
        placeholder = page.get_attribute("#rules-composer-input", "placeholder")
        page.fill("#rules-composer-input", "איך דנים בהצעה לסדר?")
        page.keyboard.press("Enter")
        page.wait_for_selector("#rules-chat .rules-answer a.rules-cite", timeout=15000)
        results.append(("תקנון: השיחה נשמרה", page.inner_text("#rconv-count") == "1", page.inner_text("#rconv-count")))
        page.click("#rconv-new")
        page.wait_for_timeout(200)
        st = page.evaluate("""() => ({msgs: document.querySelectorAll('#rules-chat .msg').length,
            chips: document.getElementById('rules-cited').hidden,
            ph: document.getElementById('rules-composer-input').placeholder})""")
        results.append(("תקנון: 'שיחה חדשה' מנקה - הודעות, תגיות, הצעה לדוגמה",
                        st["msgs"] == 0 and st["chips"] and st["ph"] == placeholder, str(st)))
        page.click("#rconv-history-btn")
        page.locator("#rconv-list .qconv-item").first.click()
        page.wait_for_timeout(300)
        txt = page.inner_text("#rules-chat")
        link = page.evaluate("() => (document.querySelector('#rules-chat a.rules-cite') || {}).dataset?.sec")
        results.append(("תקנון: פתיחה מההיסטוריה משחזרת שאלה ותשובה", "איך דנים בהצעה לסדר?" in txt and SHOWN in txt, txt[-200:]))
        results.append(("תקנון: הקישור לסעיף 52 חזר", link == "law-tkanon-haknesset/52", str(link)))
        results.append(("תקנון: שם השיחה בכותרת", page.inner_text("#rconv-current") == "איך דנים בהצעה לסדר?", page.inner_text("#rconv-current")))

        # --- הצעה לסדר ---
        page.click('nav button[data-t="agenda"]')
        page.fill("#agenda-mk-input", "עדי עזוז")
        page.fill("#agenda-composer-input", "המחסור בשוטרים")
        page.keyboard.press("Enter")
        page.wait_for_selector("#agenda-chat .msg.a .draft", timeout=15000)
        results.append(("הצעה לסדר: השיחה נשמרה, בשם הנושא", page.inner_text("#aconv-count") == "1"
                        and page.inner_text("#aconv-current") == "המחסור בשוטרים", page.inner_text("#aconv-current")))
        page.click("#aconv-new")
        page.wait_for_timeout(200)
        results.append(("הצעה לסדר: 'חדשה' מנקה", page.locator("#agenda-chat .msg").count() == 0, ""))
        page.fill("#agenda-mk-input", "")
        page.click("#aconv-history-btn")
        page.locator("#aconv-list .qconv-item").first.click()
        page.wait_for_timeout(300)
        results.append(("הצעה לסדר: הטיוטה ושם חבר/ת הכנסת חזרו",
                        page.locator("#agenda-chat .msg.a .draft").count() == 1
                        and page.input_value("#agenda-mk-input") == "עדי עזוז", page.inner_text("#agenda-chat")[-120:]))

        # כל צ'אט - שיחות משלו
        counts = page.evaluate("() => ['qconv','rconv','aconv'].map(p => document.getElementById(p + '-count').textContent)")
        results.append(("לכל צ'אט שיחות משלו", counts == ["0", "1", "1"], str(counts)))
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
