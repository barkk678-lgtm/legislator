"""ת8 + ת9 (26.9.2026) - אזכורים בתשובות מומחה התקנון.

ת8: בלי קו מקווקו מתחת לאזכור - הכחול מספיק.
ת9: אזכורים רצופים מאותו מקור - "תקנון הכנסת סעיף 56, סעיף 57, סעיף 59
וסעיף 60" (השרת מקבץ, rules_expert.group_citation_labels) - וכל סעיף לחיץ
בנפרד ומוביל לסעיף שלו במסך השמאלי.

התקנון האמיתי (/api/rules/reading); התשובה מוזרקת כמו שהשרת מחזיר אותה.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_rules_cite_group.py [BASE_URL]
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
ANSWER = "הנוהל מפורט בתקנון (תקנון הכנסת סעיף 56, סעיף 57, סעיף 59 וסעיף 60; חוק הכנסת, סעיף 12)."
K = "law-tkanon-haknesset"


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.click('nav button[data-t="rules"]')
        page.wait_for_function("() => typeof rulesDocs !== 'undefined' && rulesDocs && rulesDocs.length === 3", timeout=30000)
        page.evaluate("""(t) => { const m = appendMsg(document.getElementById('rules-chat'), 'a', '');
            const body = document.createElement('div'); body.className = 'rules-answer'; body.textContent = t;
            m.appendChild(body); addRulesCited(linkifyRulesCitations(body)); }""", ANSWER)
        links = page.eval_on_selector_all("#rules-chat a.rules-cite", "els => els.map(e => [e.textContent, e.dataset.sec])")
        results.append(("ת9: ארבעה סעיפי תקנון, כל אחד קישור משלו",
                        [l[1] for l in links[:4]] == [f"{K}/{n}" for n in (56, 57, 59, 60)], str(links)))
        results.append(("ת9: שם המקור פעם אחת - בקישור הראשון",
                        links and links[0][0] == "תקנון הכנסת סעיף 56" and [l[0] for l in links[1:4]] == ["סעיף 57", "סעיף 59", "סעיף 60"],
                        str(links)))
        results.append(("ת9: הטקסט כמו שנכתב", ANSWER in page.inner_text("#rules-chat"), page.inner_text("#rules-chat")[-200:]))
        results.append(("ת9: מקור אחר אחרי ';' - קישור משלו", len(links) == 5 and links[4][1] == "law-2000325/12", str(links)))
        deco = page.evaluate("() => getComputedStyle(document.querySelector('#rules-chat a.rules-cite')).textDecorationLine")
        results.append(("ת8: בלי קו מתחת לאזכור", deco == "none", deco))
        page.locator("#rules-chat a.rules-cite").nth(2).click()
        page.wait_for_timeout(600)
        hit = page.evaluate("() => [...document.querySelectorAll('#rules-doc .rules-hit')].map(e => e.dataset.sec)")
        results.append(("ת9: לחיצה על 'סעיף 59' מובילה לסעיף 59", hit == [f"{K}/59"], str(hit)))
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
