"""דף הבית (27.9.2026) - שלושת המצבים ויצירת קשר, בדפדפן אמיתי.

**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_home.py [BASE_URL] [--send]

--send שולח פנייה אמיתית (מסומנת "[בדיקה חיה]") - נשמרת בטבלה.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (ARGS[0] if ARGS else "http://127.0.0.1:8010").rstrip("/")
SEND = "--send" in sys.argv
NOW = int(time.time() * 1000)

SEED = {
    "legislator.drafts.v1": [{
        "id": "dhome1", "law_id": "law-2000257", "law_title": "חוק הסדרים במשק המדינה",
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 7200)),
        "title": "הצעת בדיקה לדף הבית", "edits": [], "insertions": []}],
    "legislator.queryConversations.v1": [{
        "id": "chome1", "title": "מחסור בשוטרים בנגב", "at": NOW - 86400000 - 3600000, "kind": "רגילה",
        "turns": [{"role": "user", "content": "מחסור בשוטרים בנגב"}]}],
    "legislator.rulesConversations.v1": [{
        "id": "chome2", "title": "כמה חתימות להצעת אי-אמון?", "at": NOW - 600000,
        "turns": [{"role": "user", "content": "כמה חתימות להצעת אי-אמון?"},
                  {"role": "assistant", "content": "תשובה לדוגמה", "refused": True}]}],
}


def main() -> int:
    results = []

    def check(name, ok, info=""):
        results.append((name, bool(ok), info))

    with sync_playwright() as p:
        # מול האתר החי מתוך סביבת הסוכן: PW_PROXY (ה-HTTPS_PROXY) ו-PW_TRUST_SPKI -
        # טביעת המפתח של ה-CA של הפרוקסי בלבד (לא ביטול בדיקת תעודות)
        kw = {"executable_path": "/opt/pw-browsers/chromium"}
        if os.environ.get("PW_PROXY"):
            kw["proxy"] = {"server": os.environ["PW_PROXY"]}
        if os.environ.get("PW_TRUST_SPKI"):
            kw["args"] = [f"--ignore-certificate-errors-spki-list={os.environ['PW_TRUST_SPKI']}"]
        b = p.chromium.launch(**kw)
        errors = []

        def page_for(view=None, seed=None):
            pg = b.new_page(viewport={"width": 1400, "height": 900})
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(BASE + "/")
            pg.evaluate("() => localStorage.clear()")
            if seed:
                pg.evaluate("s => { for (const [k, v] of Object.entries(s)) localStorage.setItem(k, JSON.stringify(v)); }", seed)
                # "אתמול" לפי לוח השנה של הדפדפן: אתמול בצהריים (25 שעות אחורה אחרי חצות = שלשום)
                pg.evaluate("""() => { const k = 'legislator.queryConversations.v1';
                    const list = JSON.parse(localStorage.getItem(k) || '[]');
                    const d = new Date(); d.setHours(0, 0, 0, 0);
                    for (const c of list) if (c.id === 'chome1') c.at = d.getTime() - 12 * 3600000;
                    localStorage.setItem(k, JSON.stringify(list)); }""")
            pg.goto(BASE + "/" + (f"?view={view}" if view else ""))
            pg.wait_for_selector("#home.tab.on")
            return pg

        # ── אורח ────────────────────────────────────────────────────────
        pg = page_for("guest")
        check("אורח: נוחת בדף הבית", pg.is_visible("#home") and pg.inner_text("#home-greeting") == "ברוכים הבאים")
        check("אורח: אין פריטי ניווט בתפריט", not pg.is_visible("#nav")
              and pg.eval_on_selector_all(".nav button", "els => els.filter(e => e.offsetParent).length") == 0)
        check("אורח: 'הרשמה' ו'כניסה' בתפריט", pg.is_visible("#rail-guest .btn-mint") and "כניסה" in pg.inner_text("#rail-guest"))
        bg = pg.eval_on_selector("#rail-guest .btn-mint", "e => getComputedStyle(e).backgroundColor")
        check("אורח: כפתור ההרשמה במנטה (#5EE0A8)", bg == "rgb(94, 224, 168)", bg)
        check("אורח: פס ההרשמה בנייבי", pg.is_visible("#home-signup")
              and pg.eval_on_selector("#home-signup", "e => getComputedStyle(e).backgroundColor") == "rgb(14, 42, 90)")
        check("אורח: 'יצירת קשר' בתחתית התפריט", pg.is_visible("#contact-open"))
        check("אורח: 8 כרטיסי כלים", pg.eval_on_selector_all(".tool-card", "els => els.length") == 8)
        check("אורח: אין 'המשך מאיפה שעצרת'", not pg.is_visible("#home-recent"))
        pg.click('.tool-card[data-tool="query"]')
        check("אורח: לחיצה על כלי פותחת חלון הרשמה", pg.is_visible("#signup-modal")
              and "כדי להשתמש בשאילתות — נרשמים" in pg.inner_text("#signup-modal"))
        check("אורח: ... ולא את הכלי", not pg.is_visible("#query") and pg.is_visible("#home"))
        pg.keyboard.press("Escape")
        check("אורח: Esc סוגר את החלון", not pg.is_visible("#signup-modal"))
        pg.click("#contact-open")
        visible = pg.eval_on_selector_all("#contact-form input:not([tabindex='-1']), #contact-form textarea",
                                          "els => els.filter(e => e.offsetParent).map(e => e.id)")
        check("יצירת קשר, אורח: שלושה שדות", visible == ["contact-name", "contact-email", "contact-message"], str(visible))
        check("יצירת קשר: השדה הנסתר אינו נראה", pg.eval_on_selector(
            "#contact-website", "e => { const r = e.getBoundingClientRect(); return r.right < 0 || r.left > innerWidth || r.width <= 1; }"))
        pg.click("#contact-send")
        errs = pg.eval_on_selector_all("#contact-form .fld-err:not([hidden])", "els => els.length")
        check("יצירת קשר, אורח: שליחה ריקה - שלוש שגיאות", errs == 3, str(errs))
        pg.fill("#contact-name", "בדיקת דפדפן")
        pg.fill("#contact-email", "not-an-email")
        pg.fill("#contact-message", "[בדיקה חיה] פנייה מבדיקת הדפדפן")
        pg.click("#contact-send")
        check("יצירת קשר, אורח: אימייל לא תקין נתפס", "אינה תקינה" in pg.inner_text("#contact-form"))
        if SEND:
            pg.fill("#contact-email", "browser-test@example.com")
            pg.click("#contact-send")
            pg.wait_for_selector("#contact-done:not([hidden])", timeout=15000)
            check("יצירת קשר, אורח: 'הפנייה נשלחה'", "הפנייה נשלחה" in pg.inner_text("#contact-done"))
        pg.close()

        # ── נרשם, כניסה ראשונה ────────────────────────────────────────
        pg = page_for("new")
        check("נרשם: 'שלום, [שם פרטי]'", pg.inner_text("#home-greeting").startswith("שלום, "), pg.inner_text("#home-greeting"))
        items = pg.eval_on_selector_all(".nav button[data-t]", "els => els.map(e => e.dataset.t)")
        check("נרשם: תפריט מלא ו'דף הבית' בראשו", items[:1] == ["home"] and len(items) == 9, str(items))
        check("נרשם: 'הצעת חוק חדשה'", pg.is_visible("#home-new-bill"))
        check("נרשם: מצב ריק", "כאן תופיע העבודה האחרונה שלך" in pg.inner_text("#home-recent"))
        check("נרשם: אין פס הרשמה", not pg.is_visible("#home-signup") and not pg.is_visible("#rail-guest"))
        pg.click('.tool-card[data-tool="critique"]')
        check("נרשם: לחיצה על כלי נכנסת לכלי", pg.is_visible("#critique") and not pg.is_visible("#signup-modal"))
        pg.click("#contact-open")
        visible = pg.eval_on_selector_all("#contact-form input:not([tabindex='-1']), #contact-form textarea",
                                          "els => els.filter(e => e.offsetParent).map(e => e.id)")
        check("יצירת קשר, רשום: שדה אחד", visible == ["contact-message"], str(visible))
        check("יצירת קשר, רשום: 'הפנייה תישלח בשם ... · ...'",
              pg.inner_text("#contact-as").startswith("הפנייה תישלח בשם ") and "·" in pg.inner_text("#contact-as"))
        pg.click("#contact-modal .modal-x")
        check("יצירת קשר: כפתור הסגירה", not pg.is_visible("#contact-modal"))
        pg.click('.nav button[data-t="home"]')
        pg.click("#home-new-bill")
        check("'הצעת חוק חדשה' פותח את הצעות חוק", pg.is_visible("#bills"))
        pg.close()

        # ── חוזר ─────────────────────────────────────────────────────
        pg = page_for(None, SEED)   # בלי מתג: יש היסטוריה -> חוזר
        greet = pg.inner_text("#home-greeting")
        check("חוזר (בלי מתג): ברכה לפי שעה", greet.split(",")[0] in ("בוקר טוב", "צהריים טובים", "ערב טוב"), greet)
        cards = pg.eval_on_selector_all(".recent-item", "els => els.map(e => e.innerText.replace(/\\s+/g, ' '))")
        check("חוזר: הפריטים האחרונים מכל הכלים, מהחדש לישן", len(cards) == 3
              and "מומחה התקנון" in cards[0] and "הצעות חוק" in cards[1] and "שאילתות" in cards[2], str(cards))
        check("חוזר: פרט וזמן יחסי", "לפני 10 דקות" in cards[0] and "0 שינויים · לפני שעתיים" in cards[1]
              and "שאילתה רגילה · אתמול" in cards[2], str(cards))
        pg.click(".recent-item >> nth=0")
        check("חוזר: לחיצה פותחת את השיחה בכלי שלה", pg.is_visible("#rules")
              and "כמה חתימות להצעת אי-אמון?" in pg.inner_text("#rules-chat"))
        pg.click('.nav button[data-t="home"]')
        pg.click(".recent-item >> nth=2")
        check("חוזר: שאילתה נפתחת בשאילתות", pg.is_visible("#query") and "מחסור בשוטרים בנגב" in pg.inner_text("#query-chat"))
        pg.click('.nav button[data-t="home"]')
        pg.click(".recent-item >> nth=1")
        pg.wait_for_function("() => document.getElementById('bill-title-input').value === 'הצעת בדיקה לדף הבית'", timeout=30000)
        check("חוזר: הצעה נפתחת בהצעות חוק", pg.is_visible("#bills"))
        pg.close()

        # ── חמישה פריטים -> ארבעה ────────────────────────────────────
        many = dict(SEED)
        many["legislator.agendaConversations.v1"] = [
            {"id": f"a{i}", "title": f"הצעה {i}", "at": NOW - i * 1000, "kind": "דחופה",
             "turns": [{"role": "user", "content": "x"}]} for i in range(3)]
        pg = page_for("returning", many)
        check("חוזר: ארבעה פריטים בדיוק", pg.eval_on_selector_all(".recent-item", "els => els.length") == 4)
        pg.close()
        check("בלי שגיאות בדף", not errors, str(errors))
        b.close()

    for name, ok, info in results:
        print(("OK  " if ok else "FAIL"), name, "" if ok else f"-- {info}")
    bad = [r for r in results if not r[1]]
    print("test_home:", "כל הבדיקות עברו" if not bad else f"נכשלו {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
