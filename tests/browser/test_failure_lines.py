"""ח10 (25.9.2026) - הודעת כשל שמובנת: כל כשל בשורה, בגוף ראשון.

עד כאן: "שים לב: 1 הוספות לא בוצעו (ראו כרטיסי השגיאה בעץ)". עכשיו:
"לא הצלחתי לקלוט את התיקון שביקשת לעשות בסעיף 5", "לא הצלחתי לקלוט את
הוספת סעיף 6א כפי שביקשת" - כולם, כל אחד בשורה.

חוק הקייטנות (fixture, בלי DB). תשובת /render אמיתית, ולתוכה מוזרקים
שני כשלים: עריכה שלא נקלטה בסעיף 5, והוספה שלא נקלטה אחרי סעיף 6.
**לא רץ ב-CI** (דפדפן + שרת). הרצה:
    uvicorn main:app --app-dir apps/api --port 8010 &
    python3 tests/browser/test_failure_lines.py [BASE_URL]
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
LAW = "kaytanot-1990"


def inject(route):
    resp = route.fetch()
    data = resp.json()
    data["edit_statuses"] = data.get("edit_statuses", []) + [
        {"node_id": f"{LAW}/s5", "ok": False, "field": "text", "reason": "x"},
        {"node_id": f"{LAW}/s2", "ok": False, "field": "margin_title", "reason": "x"}]
    data["insertion_errors"] = [
        {"anchor_node_id": f"{LAW}/s6", "kind": "section", "reason": "x", "client_id": "ins-t1"},
        {"anchor_node_id": f"{LAW}/s4", "kind": "subsection", "reason": "x", "client_id": "ins-t2"}]
    route.fulfill(response=resp, body=json.dumps(data, ensure_ascii=False),
                  headers={**resp.headers, "content-type": "application/json"})


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.click('.nav button[data-t="bills"]')  # דף הבית הוא ברירת המחדל (27.9)
        page.evaluate(f"onLawChange('{LAW}')")
        page.wait_for_selector(f'.node-text[data-node-id="{LAW}/s2/p0"]', timeout=20000)
        page.route("**/render", inject)
        page.evaluate(f"""() => {{
            insertions.push({{clientId: "ins-t1", kind: "section", anchor_node_id: "{LAW}/s6",
                              text: "x", margin_title: "y", label: "6א"}});
            insertions.push({{clientId: "ins-t2", kind: "subsection", anchor_node_id: "{LAW}/s4",
                              text: "x", label: "(ג)"}});
            return refreshPreview();
        }}""")
        page.wait_for_selector("#download-hint .failure-line", timeout=20000)
        lines = page.eval_on_selector_all("#download-hint .failure-line", "els => els.map(e => e.textContent)")
        expected = ["לא הצלחתי לקלוט את התיקון שביקשת לעשות בסעיף 5",
                    "לא הצלחתי לקלוט את התיקון שביקשת בכותרת השוליים של סעיף 2",
                    "לא הצלחתי לקלוט את הוספת סעיף 6א כפי שביקשת",
                    "לא הצלחתי לקלוט את הוספת סעיף קטן (ג) לסעיף 4 כפי שביקשת"]
        results.append(("כל כשל בשורה, בגוף ראשון ובמונחי המשתמש", lines == expected, str(lines)))
        hint = page.inner_text("#download-hint")
        results.append(("בלי 'כרטיסי השגיאה בעץ'", "כרטיסי" not in hint and "הוספות לא בוצעו" not in hint, hint))
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
