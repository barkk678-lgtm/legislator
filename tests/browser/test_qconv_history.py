"""ש5 (25.9.2026) - השיחות הקודמות בשאילתות: כפתור "היסטוריה" ורשימה נפתחת,
כמו במוקאפ (reference/2026-09-25.docx.docx, תמונה 3).

עד כאן השיחות הופיעו בכרטיס שלישי מתחת לשני הכרטיסים ותפסו הרבה מקום.
עכשיו: כפתור "היסטוריה" עם מספר השיחות ליד "צור שאילתה חדשה", רשימה
נפתחת עם שדה חיפוש, קיבוץ לפי זמן, שם ותאריך לכל שיחה, "כל N השיחות ←"
בתחתית, ושם השיחה הנוכחית ליד "ניסוח השאילתה".
12 שיחות מוזרקות ל-localStorage - בלי מודל ובלי פיד.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_qconv_history.py [BASE_URL] [screenshot.png]
"""
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
SHOT = sys.argv[2] if len(sys.argv) > 2 else None
DAY = 86400 * 1000
TITLES = ["מחסור בכוח אדם במשטרת ישראל", "זמני המתנה בחדרי מיון", "תקציב החינוך המיוחד",
          "הנגשת תחבורה ציבורית בפריפריה", "פיצויים לחקלאים בעוטף עזה", "שוטרי תנועה בכבישים",
          "דיור ציבורי בנגב", "מחסור ברופאים בגליל", "תשלומי ביטוח לאומי", "רישוי עסקים",
          "איכות המים בכנרת", "פיקוח על מעונות יום"]
AGES = [0, 1, 3, 5, 6, 9, 12, 20, 25, 40, 70, 120]   # ימים אחורה


def convs():
    now = int(time.time() * 1000)
    return [{"id": f"c{i}", "title": t, "at": now - AGES[i] * DAY - 60000, "minister": "השר",
             "mk": "חבר הכנסת", "kind": "רגילה",
             "turns": [{"role": "user", "content": f"בקשה על {t}"},
                       {"role": "assistant", "content": f"נושא: {t}\nגוף: רקע.\nרצוני לשאול:\nמה?"}]}
            for i, t in enumerate(TITLES)]


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1355, "height": 822})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/queries/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body='{"units":[],"expanded":false}'))
        page.goto(BASE)
        page.evaluate("(c) => localStorage.setItem('legislator.queryConversations.v1', JSON.stringify(c))",
                      convs())
        page.reload()
        page.click('nav button[data-t="query"]')

        cards = page.evaluate("() => [...document.querySelectorAll('#query .card')].filter(c => c.offsetParent).length")
        results.append(("אין כרטיס 'שיחות קודמות' נפרד - שני כרטיסים בלבד", cards == 2, str(cards)))

        btn = page.locator("#qconv-history-btn")
        results.append(("כפתור 'היסטוריה' בכותרת חלונית הניסוח",
                         btn.count() == 1 and page.locator("#query .card header #qconv-history-btn").count() == 1,
                         str(btn.count())))
        results.append(("על הכפתור - מספר השיחות (12)",
                         btn.count() == 1 and "היסטוריה" in btn.inner_text()
                         and page.inner_text("#qconv-count") == "12",
                         btn.inner_text() if btn.count() else ""))
        results.append(("הרשימה סגורה עד שלוחצים", not page.is_visible("#qconv-menu"), ""))

        btn.click()
        page.wait_for_selector("#qconv-menu", state="visible", timeout=3000)
        results.append(("לחיצה - הרשימה נפתחת, ושדה החיפוש בפוקוס",
                         page.evaluate("() => document.activeElement && document.activeElement.id") == "qconv-search",
                         str(page.evaluate("() => document.activeElement && document.activeElement.id"))))
        groups = page.evaluate("() => [...document.querySelectorAll('#qconv-list .qconv-group')].map(e => e.textContent.trim())")
        results.append(("מקובצות לפי זמן: היום, השבוע (הראשונות)", groups[:2] == ["היום", "השבוע"], str(groups)))
        items = page.evaluate("""() => [...document.querySelectorAll('#qconv-list .qconv-item')].map(e => ({
            t: e.querySelector('.qconv-title').textContent, d: e.querySelector('.qconv-date').textContent}))""")
        d0 = time.localtime(time.time() - 60)
        results.append(("כל שיחה - שם ותאריך קצר עם נקודה",
                         bool(items) and items[0]["t"] == TITLES[0]
                         and items[0]["d"] == f"{d0.tm_mday}.{d0.tm_mon}", str(items[:2])))
        results.append(("לא כל ה-12 מוצגות מיד", 0 < len(items) < 12, str(len(items))))
        foot = page.locator("#qconv-all")
        results.append(("בתחתית: 'כל 12 השיחות ←'",
                         foot.count() == 1 and foot.inner_text().strip() == "כל 12 השיחות ←",
                         foot.inner_text() if foot.count() else ""))

        # הרשימה צפה מעל התוכן - לא נחתכת ולא דוחפת את הצ'אט
        geo = page.evaluate("""() => {
            const m = document.getElementById('qconv-menu').getBoundingClientRect();
            const x = m.left + m.width / 2, y = m.bottom - 12;
            const hit = document.elementFromPoint(x, y);
            return {top: m.top, bottom: m.bottom, w: m.width, inside: !!(hit && hit.closest('#qconv-menu')),
                    vh: innerHeight};
        }""")
        results.append(("הרשימה צפה מעל התוכן ונראית במלואה",
                         geo["inside"] and geo["bottom"] <= geo["vh"] and geo["w"] >= 280, str(geo)))
        if SHOT:
            page.screenshot(path=SHOT)

        foot.click()
        n = page.locator("#qconv-list .qconv-item").count()
        results.append(("'כל השיחות' - כל ה-12", n == 12, str(n)))
        groups = page.evaluate("() => [...document.querySelectorAll('#qconv-list .qconv-group')].map(e => e.textContent.trim())")
        results.append(("הקבוצות: היום, השבוע, החודש, קודם", groups == ["היום", "השבוע", "החודש", "קודם"], str(groups)))

        page.fill("#qconv-search", "מחסור")
        t = page.evaluate("() => [...document.querySelectorAll('#qconv-list .qconv-title')].map(e => e.textContent)")
        results.append(("חיפוש 'מחסור' - רק השיחות המתאימות",
                         sorted(t) == sorted(["מחסור בכוח אדם במשטרת ישראל", "מחסור ברופאים בגליל"]), str(t)))
        page.fill("#qconv-search", "כנרת")
        t = page.evaluate("() => [...document.querySelectorAll('#qconv-list .qconv-title')].map(e => e.textContent)")
        results.append(("חיפוש בחלק ממילה ('כנרת' מוצא 'בכנרת')", t == ["איכות המים בכנרת"], str(t)))
        page.fill("#qconv-search", "מחסור רופאים")
        t = page.evaluate("() => [...document.querySelectorAll('#qconv-list .qconv-title')].map(e => e.textContent)")
        results.append(("כמה מילים - כל אחת בנפרד", t == ["מחסור ברופאים בגליל"], str(t)))
        page.fill("#qconv-search", "אבטיח")
        results.append(("חיפוש בלי תוצאה - הודעה", "לא נמצאו" in page.inner_text("#qconv-list"),
                         page.inner_text("#qconv-list")))
        page.fill("#qconv-search", "")

        page.locator("#qconv-list .qconv-item", has_text="זמני המתנה בחדרי מיון").click()
        page.wait_for_timeout(300)
        results.append(("בחירת שיחה - הרשימה נסגרת", not page.is_visible("#qconv-menu"), ""))
        results.append(("השיחה נפתחה בצ'אט", "זמני המתנה בחדרי מיון" in page.inner_text("#query-chat"),
                         page.inner_text("#query-chat")[:120]))
        results.append(("שם השיחה הנוכחית ליד 'ניסוח השאילתה'",
                         page.inner_text("#qconv-current").strip() == "זמני המתנה בחדרי מיון",
                         page.inner_text("#qconv-current")))

        btn.click()
        page.wait_for_selector("#qconv-menu", state="visible")
        on = page.evaluate("() => [...document.querySelectorAll('#qconv-list .qconv-item.on .qconv-title')].map(e => e.textContent)")
        results.append(("השיחה הפתוחה מסומנת ברשימה", on == ["זמני המתנה בחדרי מיון"], str(on)))
        page.keyboard.press("Escape")
        results.append(("Escape סוגר", not page.is_visible("#qconv-menu"), ""))
        btn.click()
        page.mouse.click(700, 700)
        results.append(("לחיצה מחוץ לרשימה סוגרת", not page.is_visible("#qconv-menu"), ""))

        page.click("#qconv-new")
        results.append(("'צור שאילתה חדשה' - שם השיחה מתאפס", page.inner_text("#qconv-current").strip() == "",
                         page.inner_text("#qconv-current")))

        page.evaluate("() => localStorage.clear()")
        page.reload()
        page.click('nav button[data-t="query"]')
        page.click("#qconv-history-btn")
        results.append(("אין שיחות - הודעה ברשימה, והמונה 0",
                         "אין עדיין שיחות" in page.inner_text("#qconv-list") and page.inner_text("#qconv-count") == "0",
                         page.inner_text("#qconv-list")))
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
