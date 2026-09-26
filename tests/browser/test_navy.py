"""הכרעה ו (ברק, 26.9.2026): **גוון נייבי אחד בכל המערכת - #0B2A5B**, בדפדפן אמיתי.

עובר על כל המצבים (אורח, נרשם, חוזר), על כל לשונית ועל החלונות הקופצים, ובכל
אלמנט (כולל ::before/::after) קורא את הצבעים המחושבים - טקסט, רקע, מסגרות, קו
מתאר, fill/stroke, צל. כל צבע "נייבי" (אותו מסווג כמו tests/unit/test_single_navy.py)
חייב להיות rgb(11, 42, 91), בכל שקיפות.

**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_navy.py [BASE_URL]
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_single_navy import NAVY, is_navy  # noqa: E402

BASE = (next((a for a in sys.argv[1:] if not a.startswith("--")), "http://127.0.0.1:8010")).rstrip("/")

COLLECT = """() => {
  const props = ['color', 'backgroundColor', 'borderTopColor', 'borderRightColor', 'borderBottomColor',
                 'borderLeftColor', 'outlineColor', 'fill', 'stroke', 'boxShadow', 'textDecorationColor',
                 'caretColor', 'columnRuleColor', 'backgroundImage'];
  const out = [];
  const re = /rgba?\\(\\s*(\\d+)[,\\s]+(\\d+)[,\\s]+(\\d+)/g;
  for (const el of document.querySelectorAll('*')) {
    if (!el.getClientRects().length) continue;              // רק מה שמוצג
    for (const pseudo of [null, '::before', '::after']) {
      const cs = getComputedStyle(el, pseudo);
      if (pseudo && (cs.content === 'none' || cs.content === 'normal')) continue;
      for (const p of props) {
        const v = cs[p] || '';
        for (const m of v.matchAll(re)) {
          const tag = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '') + (pseudo || '');
          out.push([tag, p, +m[1], +m[2], +m[3]]);
        }
      }
    }
  }
  return out;
}"""


def main() -> int:
    bad, seen, navy_hits = {}, 0, 0
    with sync_playwright() as p:
        kw = {"executable_path": "/opt/pw-browsers/chromium"}
        if os.environ.get("PW_PROXY"):
            kw["proxy"] = {"server": os.environ["PW_PROXY"]}
        if os.environ.get("PW_TRUST_SPKI"):
            kw["args"] = [f"--ignore-certificate-errors-spki-list={os.environ['PW_TRUST_SPKI']}"]
        b = p.chromium.launch(**kw)
        pg = b.new_page(viewport={"width": 1400, "height": 900})

        def scan(where):
            nonlocal seen, navy_hits
            for tag, prop, r, g, bl in pg.evaluate(COLLECT):
                seen += 1
                if is_navy((r, g, bl)):
                    navy_hits += 1
                    if (r, g, bl) != NAVY:
                        bad.setdefault(f"rgb({r}, {g}, {bl})", []).append(f"{where}: {tag} {prop}")

        pg.goto(BASE + "/?view=guest")
        pg.wait_for_selector("#home.tab.on")
        scan("אורח / דף הבית")
        pg.click('.tool-card[data-tool="query"]')
        scan("אורח / חלון הרשמה")
        pg.keyboard.press("Escape")
        pg.click("#contact-open")
        scan("אורח / יצירת קשר")

        pg.goto(BASE + "/?view=new")
        pg.wait_for_selector("#home.tab.on")
        scan("נרשם / דף הבית")
        tabs = pg.eval_on_selector_all(".nav button[data-t]", "els => els.map(e => e.dataset.t)")
        for t in tabs:
            pg.click(f'.nav button[data-t="{t}"]')
            pg.wait_for_timeout(400)
            scan(f"לשונית {t}")
            if t != "home":
                pg.hover(f'.nav button[data-t="{t}"]')
        pg.click("#contact-open")
        scan("נרשם / יצירת קשר")
        b.close()

    print(f"נסרקו {seen} צבעים מחושבים; נייבי: {navy_hits}")
    for color, where in bad.items():
        print("FAIL", color, f"({len(where)})", "; ".join(where[:4]))
    ok = not bad and navy_hits > 0
    print("test_navy:", "כל הבדיקות עברו - נייבי אחד (#0B2A5B)" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
