"""לשונית ההסתייגויות (בנייה מחדש, 26.9) - מקצה לקצה בדפדפן, על PDF טבריה.

**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_reservations_ui.py [BASE_URL] [SCREENSHOT]
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
PDF = Path(__file__).resolve().parents[2] / "reference" / "הצעת חוק טבריה.pdf"

# שדות תשלום שאסור שיופיעו (ברק: אין לאסוף פרטי תשלום לפני שיש חברת סליקה).
_PAYMENT_WORDS = ("card", "credit", "cvv", "cvc", "iban", "כרטיס", "אשראי", "תוקף", "מספר חשבון")


def main() -> int:
    results = []
    with sync_playwright() as p:
        kw = {"executable_path": "/opt/pw-browsers/chromium"}   # מול האתר החי: ראו tests/browser/test_home.py
        if os.environ.get("PW_PROXY"):
            kw["proxy"] = {"server": os.environ["PW_PROXY"]}
        if os.environ.get("PW_TRUST_SPKI"):
            kw["args"] = [f"--ignore-certificate-errors-spki-list={os.environ['PW_TRUST_SPKI']}"]
        b = p.chromium.launch(**kw)
        page = b.new_page(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.click('.nav button[data-t="reservations"]')
        page.set_input_files("#res-file", str(PDF))
        page.wait_for_selector("#res-controls:not([hidden])", timeout=60000)
        head = page.inner_text("#res-analysis")
        results.append(("שם ההצעה ומקסימום לכל רמה", "הרשויות המקומיות" in head and "רציני" in head
                        and "הזוי" in head, head[:200]))
        fams = page.eval_on_selector_all("#res-families input", "els => els.map(e => e.checked)")
        results.append(("כל המשפחות מסומנות כברירת מחדל", len(fams) == 8 and all(fams), str(fams)))
        # אישורי הבנק §6 (ברק 26.9.2026): "תוספת לפועל" - בממשק, מסומנת כברירת מחדל
        mod = page.eval_on_selector_all('#res-families input[value="verb_modifier"]',
                                        "els => els.map(e => [e.checked, e.parentElement.innerText])")
        results.append(("'תוספת לפועל' בממשק ומסומנת", len(mod) == 1 and mod[0][0] and "תוספת לפועל" in mod[0][1], str(mod)))
        quote = page.inner_text("#res-quote")
        results.append(("50 - כלול, ו'לפחות X' ייספרו בנפרד", "כלול" in quote and "לפחות" in quote, quote[:200]))
        page.fill("#res-count", "400")   # טבריה ברציני: 241 לכל היותר (אחרי אישורי הבנק)
        quote = page.inner_text("#res-quote")
        results.append(("400 - יותר ממה שההצעה מאפשרת: נאמר, בלי השלמה", "לא נשלים בחזרות" in quote, quote[:240]))
        results.append(("מצב הדגמה - סימון גלוי", page.is_visible("#res-demo") and "הדגמה" in page.inner_text("#res-demo"), ""))
        fields = page.eval_on_selector_all(
            "input, select, textarea",
            "els => els.map(e => [e.name, e.id, e.placeholder, e.getAttribute('autocomplete') || '', "
            "(e.labels && e.labels[0] ? e.labels[0].innerText : '')].join(' ').toLowerCase())")
        bad = [f for f in fields if any(w in f for w in _PAYMENT_WORDS) or "cc-" in f]
        results.append(("אין בדף אף שדה של פרטי תשלום", not bad, str(bad)))
        page.fill("#res-count", "8")
        page.click("#res-pay-btn")
        page.wait_for_selector("#res-preview", timeout=60000)
        preview = page.inner_text("#res-preview")
        results.append(("תצוגה מקדימה: כותרות מיקום ומספור רציף",
                        "לסעיף 1" in preview and "לסעיף 3" in preview and "1." in preview and "8." in preview,
                        preview[:300]))
        results.append(("בלי 'קבוצת ... מציעה'", "מציעה" not in preview, ""))
        with page.expect_download() as dl:
            page.click("#res-download")
        path = dl.value.path()
        results.append(("הורדת Word", path is not None and Path(path).read_bytes()[:2] == b"PK", str(path)))
        results.append(("בלי שגיאות בדף", not errors, str(errors)))
        if len(sys.argv) > 2:
            page.screenshot(path=sys.argv[2], full_page=False)
        b.close()
    for name, ok, info in results:
        print(("OK  " if ok else "FAIL"), name, "" if ok else f"-- {info}")
    bad = [r for r in results if not r[1]]
    print("test_reservations_ui:", "כל הבדיקות עברו" if not bad else f"נכשלו {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
