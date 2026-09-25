"""ס3 + ס4 (26.9.2026) - ההצעה לסדר בצ'אט ובקובץ, לפי הטופס של הכנסת.

בצ'אט - אותו מבנה כמו בקובץ: לכבוד / יו"ר הכנסת, ח"כ <יו"ר> / אדוני היושב
ראש, / אבקש להעלות ... הצעה דחופה בנושא: / <נושא> / דברי הסבר: / ... / בכבוד
רב, / חבר/ת הכנסת <שם>. בלי תאריך ומספר. הסוג (דחופה/רגילה) נשלח לשרת;
אייקון הוורד מוריד קובץ אמיתי מ-/api/agenda/export (השרת האמיתי), עם היו"ר
שהגיע עם הטיוטה - בלי פנייה נוספת למאגר. המודל מדומה.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_agenda_form.py [BASE_URL]
"""
import io
import json
import re
import sys
import zipfile

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
DRAFT = {"kind": "דחופה", "mk_name": "עדי עזוז", "subject": "המחסור בשוטרים בנגב",
         "explanation": ["בשנה האחרונה נסגרו תחנות.", "התושבים ממתינים שעות."],
         "speaker": {"name": "אמיר אוחנה", "gender": "זכר", "source": "feed"}}


def main() -> int:
    results = []
    sent = {"draft": [], "export": []}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True,
                            permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def on_draft(route):
            req = json.loads(route.request.post_data)
            sent["draft"].append(req)
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({**DRAFT, "kind": req.get("kind", "דחופה")}, ensure_ascii=False))

        def on_export(route):
            sent["export"].append(json.loads(route.request.post_data))
            route.continue_()
        page.route("**/api/agenda/draft", on_draft)
        page.route("**/api/agenda/export", on_export)
        page.route("**/api/queries/mk-gender?*", lambda r: r.fulfill(status=200, content_type="application/json",
                                                                     body=json.dumps({"name": "x", "gender": "נקבה"})))
        page.goto(BASE)
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.click('nav button[data-t="agenda"]')
        page.fill("#agenda-mk-input", "עדי עזוז")
        page.fill("#agenda-composer-input", "מחסור בשוטרים בנגב")
        page.keyboard.press("Enter")
        page.wait_for_selector("#agenda-chat .msg.a .agenda-draft", timeout=15000)
        lines = [l for l in page.inner_text("#agenda-chat .agenda-draft").split("\n") if l.strip()]
        want = ["לכבוד", 'יו"ר הכנסת, ח"כ אמיר אוחנה', "אדוני היושב ראש,",
                "אבקש להעלות על סדר יומה של הכנסת הצעה דחופה בנושא:", "המחסור בשוטרים בנגב", "דברי הסבר:",
                "בשנה האחרונה נסגרו תחנות.", "התושבים ממתינים שעות.", "בכבוד רב,", "חברת הכנסת עדי עזוז"]
        results.append(("ס3: בצ'אט - המבנה של הטופס, בלי תאריך ומספר", lines == want, str(lines)))
        results.append(("ס3: הסוג נשלח לשרת", sent["draft"][-1].get("kind") == "דחופה", str(sent["draft"][-1])))

        with page.expect_download(timeout=20000) as dl:
            page.locator("#agenda-chat .msg.a .msg-action").last.click()
        data = open(dl.value.path(), "rb").read()
        doc = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
        text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", doc))
        exp = sent["export"][-1]
        results.append(("ס4: הייצוא נושא את היו\"ר שהגיע עם הטיוטה", exp.get("speaker_name") == "אמיר אוחנה"
                        and exp.get("gender") == "נקבה", str(exp)))
        results.append(("ס3: הקובץ מהשרת - נושא, דברי הסבר וחתימה", "המחסור בשוטרים בנגב" in text
                        and "התושבים ממתינים שעות." in text and "חברת הכנסת" in text and "עדי עזוז" in text, text[:200]))
        results.append(("ס3: בקובץ - בלי תאריך ובלי מספר", not re.search(r"\d{4}|התשפ", text), text[:200]))

        # רגילה
        page.select_option("#agenda-kind-input", "רגילה")
        page.fill("#agenda-composer-input", "נסח שוב")
        page.keyboard.press("Enter")
        page.wait_for_function("() => document.querySelectorAll('#agenda-chat .agenda-draft').length === 2", timeout=15000)
        last = page.locator("#agenda-chat .agenda-draft").last.inner_text()
        results.append(("ס3: הצעה רגילה - בלי 'דחופה'", "הצעה בנושא:" in last and "דחופה" not in last, last[:200]))

        # צ6: ההעתקה - רק הנוסח
        page.evaluate("() => navigator.clipboard.writeText('')")
        page.locator("#agenda-chat .msg.a .msg-copy").last.click()
        page.wait_for_timeout(300)
        copied = page.evaluate("() => navigator.clipboard.readText()")
        results.append(("צ6: ההעתקה - הנוסח בלבד, בשורות", copied.startswith("לכבוד\n") and "ניסחתי" not in copied, repr(copied[:80])))
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
