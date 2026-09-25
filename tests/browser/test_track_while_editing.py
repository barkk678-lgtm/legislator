"""ח1 (25.9.2026) - "עקוב אחר שינויים" גם בזמן עריכת סעיף.

עד כאן: אחרי עריכה הסעיף הוצג באדום וירוק, אבל לחיצה עליו שוב הציגה רק
את הטקסט החדש. עכשיו בכל עת - גם בזמן ההקלדה - מה שנמחק מוצג מחוק (ואי
אפשר לערוך אותו), ומה שנוסף בירוק.
ועוד באג שנמצא בדרך: בשני שינויים באותו סעיף, אחרי היציאה מהשדה סומן רק
האחרון - הראשון לא הופיע כלל (השדה הציג את נוסח המקור באותו מקום).

חוק הקייטנות (fixture, בלי DB). /render אמיתי.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_track_while_editing.py [BASE_URL] [screenshot.png]
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
SHOT = sys.argv[2] if len(sys.argv) > 2 else None
LAW = "kaytanot-1990"
NID = f"{LAW}/s2/p0"
ORIG = "לא ינהל אדם קייטנה אלא אם כן יש בידו רשיון לפי חוק רישוי עסקים."
SEL = f'.node-text[data-node-id="{NID}"]'

STATE = """(sel) => {
    const el = document.querySelector(sel);
    const plain = [...el.childNodes].filter(n => n.nodeName !== 'DEL').map(n => n.textContent).join('');
    return {focused: document.activeElement === el,
            del: [...el.querySelectorAll('del')].map(e => e.textContent),
            ins: [...el.querySelectorAll('ins')].map(e => e.textContent),
            delEditable: [...el.querySelectorAll('del')].map(e => e.isContentEditable),
            plain, full: el.textContent};
}"""


def caret_to(page, offset):
    """מציב את הסמן בהיסט בטקסט הנוכחי (בלי המחוק)."""
    page.evaluate("""([sel, off]) => {
        const el = document.querySelector(sel);
        let acc = 0;
        const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        for (let t = w.nextNode(); t; t = w.nextNode()) {
            if (t.parentNode.closest('del')) continue;
            if (off <= acc + t.data.length) {
                const r = document.createRange(); r.setStart(t, off - acc); r.collapse(true);
                const s = getSelection(); s.removeAllRanges(); s.addRange(r); return;
            }
            acc += t.data.length;
        }
    }""", [SEL, offset])


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


def settle(page):
    page.wait_for_selector("#preview-pending", state="hidden", timeout=20000)
    page.wait_for_timeout(300)


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

        # הוספה בסוף - ירוק כבר בזמן ההקלדה
        el.click()
        page.keyboard.press("End")
        page.keyboard.type(" ובלבד")
        st = page.evaluate(STATE, SEL)
        results.append(("בזמן ההקלדה: התוספת בירוק (ins), והשדה עדיין בפוקוס",
                        st["focused"] and st["ins"] == [" ובלבד"], str(st)))

        # מחיקת מילה - מחוקה, לא נעלמת, ואי אפשר לערוך אותה
        select_word(page, "רשיון")
        page.keyboard.press("Backspace")
        st = page.evaluate(STATE, SEL)
        results.append(("מחיקת 'רשיון' בזמן העריכה: מוצגת מחוקה (del)", [d.strip() for d in st["del"]] == ["רשיון"] and not st["ins"][:-1], str(st)))
        results.append(("הטקסט המחוק אינו ניתן לעריכה", st["delEditable"] == [False], str(st["delEditable"])))
        results.append(("הטקסט הנוכחי - בלי המילה המחוקה",
                        st["plain"] == ORIG.replace("רשיון", "") + " ובלבד", st["plain"]))

        # הקלדה במקום המחיקה - החלפה: מחוק + ירוק צמודים
        page.keyboard.type("היתר")
        st = page.evaluate(STATE, SEL)
        results.append(("הקלדה במקום המחוק: 'רשיון' מחוק ו'היתר' בירוק",
                        [d.strip() for d in st["del"]] == ["רשיון"] and "היתר" in "".join(st["ins"]) and st["focused"], str(st)))
        results.append(("הסמן נשאר במקומו (ההקלדה נכנסה ברצף)",
                        st["plain"] == ORIG.replace("רשיון", "היתר") + " ובלבד", st["plain"]))

        # Backspace מיד אחרי קטע מחוק מוחק את התו שלפניו, ולא "נתקע" על המחוק
        caret_to(page, len("לא ינהל אדם"))   # אחרי "אדם"
        page.keyboard.press("Backspace")
        st = page.evaluate(STATE, SEL)
        results.append(("Backspace בטקסט רגיל מוחק תו אחד ומסמן אותו מחוק",
                        st["plain"].startswith("לא ינהל אד ") and "אדם" in "".join(st["del"]), str(st)))

        # יציאה מהשדה - אותו סימון בדיוק; חזרה לשדה - הסימון נשאר
        page.locator(f'.node-text[data-node-id="{LAW}/s4/p0"]').click()
        settle(page)
        after = page.evaluate(STATE, SEL)
        results.append(("אחרי היציאה מהשדה: שלושת השינויים מסומנים (לא רק האחרון)",
                        after["plain"] == st["plain"] and "רשיון" in "".join(after["del"])
                        and " ובלבד" in "".join(after["ins"]) and "היתר" in "".join(after["ins"]),
                        str(after)))
        if SHOT:
            page.locator(f'.node[data-node-id="{LAW}/s2"]').screenshot(path=SHOT)
        el.click()
        page.wait_for_timeout(200)
        again = page.evaluate(STATE, SEL)
        results.append(("לחיצה שוב על הסעיף: עדיין 'עקוב אחר שינויים' (לא רק הטקסט החדש)",
                        again["focused"] and again["del"] and again["ins"], str(again)))

        # מה שנשלח לשרת - הטקסט הנוכחי, בלי המחוק
        sent = page.evaluate(f"() => edits['{NID}:text'] && edits['{NID}:text'].text")
        results.append(("הטקסט שנשלח להוראת התיקון - בלי הטקסט המחוק", sent == st["plain"], str(sent)))

        # החזרה למקור: הסימון נעלם
        page.keyboard.press("Control+a")
        page.keyboard.type(ORIG)
        page.locator(f'.node-text[data-node-id="{LAW}/s4/p0"]').click()
        settle(page)
        back = page.evaluate(STATE, SEL)
        results.append(("החזרת הנוסח המקורי: בלי סימון ובלי עריכה",
                        not back["del"] and not back["ins"] and back["plain"] == ORIG
                        and page.evaluate(f"() => !('{NID}:text' in edits)"), str(back)))

        # כותרת שוליים - אותו מנגנון
        t = page.locator(f'.node-margin-title[data-node-id="{LAW}/s3"]')
        t.click()
        page.keyboard.press("End")
        page.keyboard.type(" ופיקוח")
        tins = t.evaluate("e => [...e.querySelectorAll('ins')].map(x => x.textContent)")
        results.append(("כותרת שוליים: התוספת בירוק כבר בזמן ההקלדה", tins == [" ופיקוח"], str(tins)))
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
