"""ח12 + ח15 + ח11 (26.9.2026) - הפלוס, הפח ותפריט ההוספה בנוסח החוק.

ח12: "על כל סעיף וסעיף קטן מופיעים שני זוגות של פלוס ופח". שוחזר: יחידה
בלי טקסט משלה (סעיף 2 בחוק הקייטנות - כל תוכנו בפסקה בלי מספר; סעיף 6
בחוק-יסוד: הכנסת - כולו בסעיפים קטנים) קיבלה שורה ריקה עם זוג, ואחריה
הרישה עם זוג משלה. עכשיו - זוג אחד לכל יחידה (data-actor על הכפתור).

ח15: פח על הרישה של סעיף 7 בחוק-יסוד: הכנסת ("אלה לא יהיו מועמדים
לכנסת:", ואחריה (1)-(10) וסיפא) - מבטל את הסעיף כולו: כל השדות נמחקים,
וההוראה "סעיף 7 – בטל". עד כאן נמחקו רק הרישה והפסקאות שבתוכה, והסיפא נשארה.

ח11: התפריט מציע רק רמות תקינות במקום. בין 6(א) ל-6(ג) - לא סעיף ראשי;
מסעיף עם סעיפים קטנים - לא סעיף קטן (מוסיפים מהפלוס של האחרון); מהסיפא,
התוכן האחרון של סעיף 7 - כן סעיף ראשי. ואפשרות שהשרת לא תומך בה - לא מוצגת.

**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_unit_actions.py [BASE_URL]
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def pairs(page, root_id):
    """לכל יחידה בתת-העץ: כמה פלוסים וכמה פחים פועלים עליה."""
    return page.evaluate("""(root) => {
        const out = {};
        const w = document.querySelector(`.node[data-node-id="${root}"]`);
        for (const b of w.querySelectorAll('.node-add-btn, .node-del-btn')) {
            const k = b.dataset.actor, o = out[k] || (out[k] = {add: 0, del: 0});
            b.classList.contains('node-add-btn') ? o.add++ : o.del++;
        }
        return out;
    }""", root_id)


def menu_levels(page, actor_id):
    page.locator(f'.node-add-btn[data-actor="{actor_id}"]').click()
    page.wait_for_function("""() => { const m = document.querySelector('#law-tree .insert-menu');
        return m && ![...m.querySelectorAll('.insert-level-btn')].some(b => b.textContent.includes('בודק'))
            && (m.querySelector('.insert-level-btn') || m.querySelector('.insert-menu-none')); }""", timeout=30000)
    labels = page.eval_on_selector_all("#law-tree .insert-menu .insert-level-btn", "els => els.map(e => e.textContent)")
    page.locator(f'.node-add-btn[data-actor="{actor_id}"]').click()   # סגירה
    return labels


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)

        # ח12
        page.evaluate("onLawChange('kaytanot-1990')")
        page.wait_for_selector('.node[data-node-id="kaytanot-1990/s2"]', timeout=30000)
        k2 = pairs(page, "kaytanot-1990/s2")
        results.append(("ח12: סעיף 2 בחוק הקייטנות - זוג אחד, של הסעיף",
                        k2 == {"kaytanot-1990/s2": {"add": 1, "del": 1}}, str(k2)))
        lv = menu_levels(page, "kaytanot-1990/s2")
        results.append(("ח11: מהסעיף - סעיף ראשי וסעיף קטן ראשון",
                        len(lv) == 2 and "סעיף ראשי" in lv[0] and "סעיף קטן" in lv[1], str(lv)))

        page.evaluate("onLawChange('law-2000037')")
        page.wait_for_selector('.node[data-node-id="law-2000037/s7"]', timeout=30000)
        s6 = pairs(page, "law-2000037/s6")
        dup = {k: v for k, v in s6.items() if v["add"] != 1 or v["del"] > 1}
        results.append(("ח12: סעיף 6 בחוק-יסוד: הכנסת - כל יחידה זוג אחד", not dup and "law-2000037/s6" in s6, str(dup or s6)))
        s6_in_header = page.evaluate("""() => !!document.querySelector('.node[data-node-id="law-2000037/s6"] > .node-header .node-add-btn')""")
        results.append(("ח12: הזוג של סעיף 6 בכותרת, לא בשורה ריקה", s6_in_header, str(s6_in_header)))
        s7 = pairs(page, "law-2000037/s7")
        results.append(("ח12: הרישה של סעיף 7 נושאת את הזוג של הסעיף, בלי זוג משלה",
                        s7.get("law-2000037/s7") == {"add": 1, "del": 1} and "law-2000037/s7/p0" not in s7, str(s7)[:200]))

        # ח11
        lv = menu_levels(page, "law-2000037/s6/א")
        results.append(("ח11: בין 6(א) ל-6(ג) - בלי סעיף ראשי", lv and not any("סעיף ראשי" in x for x in lv)
                        and any("סעיף קטן" in x for x in lv), str(lv)))
        lv = menu_levels(page, "law-2000037/s6")
        results.append(("ח11: מסעיף 6 (יש לו סעיפים קטנים) - רק סעיף ראשי", len(lv) == 1 and "סעיף ראשי" in lv[0], str(lv)))
        last = page.evaluate("""() => { const w = document.querySelector('.node[data-node-id="law-2000037/s7"]');
            const btns = w.querySelectorAll('.node-add-btn'); return btns[btns.length - 1].dataset.actor; }""")
        lv = menu_levels(page, last)
        results.append(("ח11: מהתוכן האחרון של סעיף 7 - גם סעיף ראשי", any("סעיף ראשי" in x for x in lv), f"{last}: {lv}"))
        all_labels = page.evaluate("() => document.body.innerText.includes('לא נתמך')")
        results.append(("ח11: אין 'לא נתמך' בתפריט", not all_labels, str(all_labels)))

        # ח15
        page.locator('.node-del-btn[data-actor="law-2000037/s7"]').click()
        page.wait_for_selector("#preview-pending", state="hidden", timeout=30000)
        page.wait_for_timeout(500)
        left = page.evaluate("""() => [...document.querySelectorAll('.node[data-node-id="law-2000037/s7"] .node-text')]
            .filter(el => fieldPlainText(el).trim()).map(el => el.dataset.nodeId)""")
        results.append(("ח15: פח על הרישה - כל הסעיף נמחק, כולל הסיפא", left == [], str(left)))
        hint = page.inner_text("#docx-lines")
        results.append(("ח15: ההוראה - 'סעיף 7 – בטל'", "סעיף 7 – בטל" in hint, hint[:200]))
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
