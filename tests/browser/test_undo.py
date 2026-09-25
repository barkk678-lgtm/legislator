"""ח7 (25.9.2026) - ביטול פעולה: Ctrl+Z וכפתור, גם למחיקת סעיף וגם לביטוי.

מחסנית ביטול אחת לכל העריכה: הקלדה ברצף באותו שדה היא צעד אחד, מחיקת
סעיף בפח היא צעד אחד. Ctrl+Z / Ctrl+Y (גם בפריסה עברית - לפי המקש, לא
האות), וכפתורי "ביטול" ו"חזרה" בכותרת נוסח החוק. בתיבות טקסט רגילות (שם
ההצעה) - הביטול של הדפדפן, לא נוגעים.

חוק הקייטנות (fixture, בלי DB). /render אמיתי.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_undo.py [BASE_URL]
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
LAW = "kaytanot-1990"
NID = f"{LAW}/s2/p0"
ORIG = "לא ינהל אדם קייטנה אלא אם כן יש בידו רשיון לפי חוק רישוי עסקים."
SEL = f'.node-text[data-node-id="{NID}"]'
PLAIN = """(sel) => { const el = document.querySelector(sel);
    return [...el.childNodes].filter(n => n.nodeName !== 'DEL').map(n => n.textContent).join(''); }"""


def settle(page):
    page.wait_for_selector("#preview-pending", state="hidden", timeout=20000)
    page.wait_for_timeout(300)


def lines(page):
    return page.eval_on_selector_all("#docx-lines .line-row", "els => els.map(e => e.innerText.replace(/\\s+/g, ' ').trim())")


def select_word(page, word):
    page.evaluate("""([sel, word]) => {
        const el = document.querySelector(sel);
        const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        for (let t = w.nextNode(); t; t = w.nextNode()) {
            const i = t.data.indexOf(word);
            if (i < 0 || t.parentNode.closest('del')) continue;
            const r = document.createRange(); r.setStart(t, i); r.setEnd(t, i + word.length);
            const s = getSelection(); s.removeAllRanges(); s.addRange(r); return;
        }
    }""", [SEL, word])


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.evaluate(f"onLawChange('{LAW}')")
        el = page.locator(SEL)
        el.wait_for(timeout=20000)
        undo_btn, redo_btn = page.locator("#undo-btn"), page.locator("#redo-btn")
        results.append(("כפתורי ביטול וחזרה בכותרת נוסח החוק, מושבתים בהתחלה",
                        undo_btn.count() == 1 and redo_btn.count() == 1
                        and undo_btn.is_disabled() and redo_btn.is_disabled(), ""))

        # הקלדה ברצף = צעד אחד
        el.click()
        page.keyboard.press("End")
        page.keyboard.type(" ובלבד שהוא")
        results.append(("אחרי הקלדה - 'ביטול' פעיל", undo_btn.is_enabled(), ""))
        page.keyboard.press("Control+z")
        results.append(("Ctrl+Z מבטל את כל ההקלדה הרציפה בצעד אחד",
                        page.evaluate(PLAIN, SEL) == ORIG, page.evaluate(PLAIN, SEL)))
        results.append(("אחרי הביטול - השדה בפוקוס, בלי סימון",
                        page.evaluate(f"() => document.activeElement === document.querySelector('{SEL}')")
                        and el.evaluate("e => !e.querySelector('ins, del')"), el.inner_html()))
        results.append(("אחרי הביטול - אין עריכה", page.evaluate(f"() => !('{NID}:text' in edits)"), ""))
        page.keyboard.press("Control+y")
        results.append(("Ctrl+Y מחזיר", page.evaluate(PLAIN, SEL) == ORIG + " ובלבד שהוא",
                        page.evaluate(PLAIN, SEL)))
        page.keyboard.press("Control+Shift+z")
        results.append(("Ctrl+Shift+Z בלי מה להחזיר - לא משנה דבר",
                        page.evaluate(PLAIN, SEL) == ORIG + " ובלבד שהוא", page.evaluate(PLAIN, SEL)))

        # מחיקת ביטוי, ואחר כך הקלדה - שני צעדים נפרדים
        page.wait_for_timeout(1400)
        select_word(page, "רשיון")
        page.keyboard.press("Backspace")
        after_del = page.evaluate(PLAIN, SEL)
        page.wait_for_timeout(1400)
        page.keyboard.type("היתר")
        page.keyboard.press("Control+z")
        results.append(("Ctrl+Z אחרי מחיקה+הקלדה - מבטל רק את ההקלדה",
                        page.evaluate(PLAIN, SEL) == after_del, page.evaluate(PLAIN, SEL)))
        page.keyboard.press("Control+z")
        results.append(("Ctrl+Z נוסף - הביטוי שנמחק חוזר",
                        page.evaluate(PLAIN, SEL) == ORIG + " ובלבד שהוא", page.evaluate(PLAIN, SEL)))

        # פריסה עברית: המקש Z הוא "ז"
        page.evaluate("""() => document.activeElement.dispatchEvent(new KeyboardEvent('keydown',
            {key: 'ז', code: 'KeyZ', ctrlKey: true, bubbles: true, cancelable: true}))""")
        results.append(("Ctrl+ז (פריסה עברית) - גם מבטל", page.evaluate(PLAIN, SEL) == ORIG,
                        page.evaluate(PLAIN, SEL)))

        # מחיקת סעיף שלם בפח - וביטול בכפתור
        page.locator(f'.node[data-node-id="{LAW}/s5"] > .node-body-row > .node-del-btn').first.click()
        settle(page)
        results.append(("פח על סעיף 5 - 'סעיף 5 – בטל' בהצעה", any("סעיף 5 – בטל" in x for x in lines(page)),
                        str(lines(page))))
        undo_btn.click()
        settle(page)
        s5 = page.evaluate(f"""() => [...document.querySelectorAll('.node[data-node-id="{LAW}/s5"] .node-text')]
            .map(e => e.textContent).join('')""")
        results.append(("כפתור 'ביטול' - הסעיף חוזר, וההוראה יורדת מההצעה",
                        not any("סעיף 5 – בטל" in x for x in lines(page)) and len(s5) > 20
                        and page.evaluate(f"() => !Object.keys(edits).some(k => k.startsWith('{LAW}/s5'))"),
                        str(lines(page)) + " / " + s5[:40]))
        redo_btn.click()
        settle(page)
        results.append(("כפתור 'חזרה' - הסעיף נמחק שוב", any("סעיף 5 – בטל" in x for x in lines(page)),
                        str(lines(page))))
        undo_btn.click()
        settle(page)

        # הוספת סעיף חדש - וביטולה
        w = page.locator(f'.node[data-node-id="{LAW}/s6"]')
        w.locator(":scope > .node-body-row > .node-add-btn").click()
        menu = page.locator(".insert-menu:not([hidden])").first
        menu.locator(".insert-level-btn:not([disabled])", has_text="הוסף סעיף ראשי").first.click()
        menu.locator(".insert-margin-title-input").fill("סעיף בדיקה")
        menu.locator(".insert-text-input").fill("תוכן הסעיף החדש.")
        menu.locator(".insert-submit-btn").click()
        settle(page)
        added = page.locator(".node.inserted").count()
        page.keyboard.press("Control+z")
        settle(page)
        results.append(("הוספת סעיף ואז Ctrl+Z - הסעיף החדש יורד מהעץ ומההצעה",
                        added == 1 and page.locator(".node.inserted").count() == 0
                        and not any("סעיף בדיקה" in x for x in lines(page))
                        and page.evaluate("() => insertions.length === 0"), f"{added} / {lines(page)}"))
        page.keyboard.press("Control+y")
        settle(page)
        results.append(("Ctrl+Y - הסעיף החדש חוזר", page.locator(".node.inserted").count() == 1,
                        str(page.locator(".node.inserted").count())))
        page.keyboard.press("Control+z")
        settle(page)

        # פעולה חדשה מוחקת את מחסנית החזרה
        el.click()
        page.keyboard.press("End")
        page.keyboard.type(" א")
        results.append(("פעולה חדשה אחרי ביטול - 'חזרה' מושבת", redo_btn.is_disabled(), ""))

        # תיבת טקסט רגילה - הביטול של הדפדפן, המחסנית שלנו לא נוגעת
        before = page.evaluate(PLAIN, SEL)
        page.click("#bill-title-input")
        page.keyboard.type("הצעה")
        page.keyboard.press("Control+z")
        results.append(("Ctrl+Z בשם ההצעה - לא נוגע בעריכות נוסח החוק",
                        page.evaluate(PLAIN, SEL) == before, page.evaluate(PLAIN, SEL)))

        # החלפת חוק - המחסנית מתאפסת
        page.evaluate(f"onLawChange('{LAW}')")
        el.wait_for(timeout=20000)
        page.wait_for_timeout(300)
        results.append(("פתיחת חוק מחדש - 'ביטול' מושבת", undo_btn.is_disabled(), ""))
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
