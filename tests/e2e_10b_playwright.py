"""אימות end-to-end אמיתי בדפדפן (Playwright) של משימה 10ב, מול ארבעת
קריטריוני הקבלה שהמשתמש הגדיר במפורש:
1. צד ימין מציג נוסח חוק בלבד - בלי תיוגי סוג ("פסקה"/"הגדרה"/"סעיף
   קטן"), ובלי צמתים לא-נורמטיביים בשום צורה.
2. עריכה חופשית שלא קופצת - הסמן נשאר איפה שהוא בזמן הקלדה.
3. הטבלה משמאל מתעדכנת בזמן אמת ונראית כמו הצעת חוק.
4. ייצוא ל-docx נותן קובץ תקין.

לא טסט unit רגיל (לא ב-tests/unit/) - סקריפט הרצה חד-פעמי מול שרת חי.
"""

import sys
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8010"


def main():
    ok = True

    def check(name, passed, extra=""):
        nonlocal ok
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name, extra if not passed else "")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page()
        page.goto(BASE_URL)
        page.select_option("#law-select", "kaytanot-1990")
        page.wait_for_selector("#law-tree .node-text", timeout=5000)

        # --- קריטריון 1: בלי תיוגי סוג, בלי לא-נורמטיבי ---
        tree_text = page.inner_text("#law-tree")
        # "סעיף קטן" לא נבדק כאן: הוא מופיע באופן לגיטימי בקייטנות עצמו
        # (סעיף 3(ב): "...לפי סעיף קטן (א)...") כחלק מנוסח החוק האמיתי,
        # לא כתיוג-סוג של הממשק - בדיוק ההבדל שהקריטריון מתכוון אליו.
        for forbidden in ["פסקה", "הגדרה", "פסקת משנה"]:
            check(f"אין תיוג סוג '{forbidden}' בעץ", forbidden not in tree_text)
        # קייטנות סעיף 2 מכיל הערות עורך במקור (is_normative=False) -
        # מתחילות ב"ראו" בוויקיטקסט. בודקים שאין להן זכר בטקסט המוצג.
        check("אין עקבות להערת עורך ('ראו ...') בעץ", "ראו " not in tree_text)

        # --- קריטריון 2: עריכה שלא קופצת ---
        # במקום להסתמך על סמנטיקת Home/ArrowRight (לא אמינה בטקסט RTL -
        # תלוית דפדפן/כיווניות), ממקמים את הסמן במדויק דרך Selection API
        # ואז מקלידים עם page.keyboard.type() - זה בודק בדיוק את מה
        # שחשוב: שהקוד שלנו (בעיקר ה-handler של focus) לא מזיז את הסמן
        # שהמשתמש/הדפדפן כבר קבעו.
        # data-node-id מופיע גם על מעטפת ה-.node וגם על שדה הטקסט/כותרת
        # השוליים שבתוכה (10ב) - הסלקטור חייב לפרט .node-text כדי
        # לפגוע דווקא בשדה הניתן-לעריכה, לא במעטפת החיצונית.
        node_id = "kaytanot-1990/s2/p0"
        node = page.locator(f'.node-text[data-node-id="{node_id}"]')
        original_text = node.inner_text()
        split_point = original_text.index("קייטנה")  # אחרי "לא ינהל אדם "
        page.evaluate(
            """([nodeId, offset]) => {
                const el = document.querySelector(`.node-text[data-node-id="${nodeId}"]`);
                el.focus();
                const textNode = el.firstChild;
                const range = document.createRange();
                range.setStart(textNode, offset);
                range.setEnd(textNode, offset);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            }""",
            [node_id, split_point],
        )
        page.keyboard.type("XYZ")
        text_after_typing = node.inner_text()
        expected = original_text[:split_point] + "XYZ" + original_text[split_point:]
        check(
            "הטקסט המוקלד נכנס בדיוק במקום שהוקלד (הסמן לא קפץ לסוף/התחלה)",
            text_after_typing == expected,
            f"-> got={text_after_typing!r} expected={expected!r}",
        )
        node.blur()
        page.wait_for_timeout(500)

        # --- קריטריון 3: הטבלה משמאל מתעדכנת ---
        docx_lines_text = page.inner_text("#docx-lines")
        check(
            "טבלת ההצעה משמאל השתנתה (לא ריקה, לא ההודעה 'אין שינויים')",
            "אין עדיין שינויים" not in docx_lines_text and len(docx_lines_text.strip()) > 0,
            f"-> {docx_lines_text!r}",
        )
        check("טבלת ההצעה מכילה כותרת שוליים 'תיקון סעיף'", "תיקון סעיף" in docx_lines_text)

        # --- בדיקת סדר כותרת: מספר לפני כותרת שוליים (לא ההפך) ---
        # ".node-header" (בניגוד ל-".node") לא "בולע" טקסט של צאצאים -
        # לכן אפשר לסנן לפיו בבטחה, ואז לעלות למעטפת ה-.node שלו כדי
        # להגיע לשורת הטקסט/כפתור ה-"+" (אחים של הכותרת, לא בתוכה).
        section5_header = page.locator(".node-header").filter(has_text="עונשין").first
        section5_node = section5_header.locator("xpath=..")
        header_children_classes = section5_header.locator(":scope > *").evaluate_all(
            "els => els.map(e => e.className)"
        )
        first_is_number = len(header_children_classes) > 0 and "node-number" in header_children_classes[0]
        title_after_number = any("node-margin-title" in c for c in header_children_classes[1:])
        check(
            "בכותרת הסעיף: מספר קודם לכותרת שוליים (סדר קריאה נכון מימין לשמאל)",
            first_is_number and title_after_number,
            f"-> {header_children_classes}",
        )

        # --- כפתור "+" בסוף שורת הטקסט (לא ליד הכותרת) ---
        add_btn_in_body_row = section5_node.locator(":scope > .node-body-row > .node-add-btn").count() == 1
        add_btn_in_header = section5_header.locator(".node-add-btn").count() == 0
        check(
            "כפתור '+' יושב בשורת הטקסט של הסעיף, לא ליד הכותרת",
            add_btn_in_body_row and add_btn_in_header,
        )

        # --- כותרת שוליים ניתנת לעריכה (§7.8) ---
        title_el = section5_header.locator('.node-margin-title[contenteditable="true"]').first
        title_el.click()
        page.keyboard.press("Control+A")
        page.keyboard.type("עונשין חמורים")
        title_el.blur()
        page.wait_for_timeout(600)
        docx_after_title_edit = page.inner_text("#docx-lines")
        check(
            "עריכת כותרת שוליים מתועדת בטבלה לפי §7.8 ('בכותרת השוליים')",
            "בכותרת השוליים" in docx_after_title_edit,
            f"-> {docx_after_title_edit!r}",
        )

        # --- בונוס: תפריט ההוספה (היררכיה + תצוגה מקדימה של מספור) ---
        add_btn = section5_node.locator(":scope > .node-body-row > .node-add-btn")
        section5_node.locator(":scope > .node-body-row").hover()
        add_btn.click(force=True)
        page.wait_for_selector(".insert-menu .insert-level-btn", timeout=3000)
        page.wait_for_timeout(600)  # ממתינים לתשובות ה-preview המקבילות
        level_btns_text = page.locator(".insert-menu .insert-level-btn").all_inner_texts()
        check(
            "תפריט ההוספה מציג תווית מחושבת (יהיה ...) לפני לחיצה",
            any("יהיה" in t for t in level_btns_text),
            f"-> {level_btns_text}",
        )
        section_btn = page.locator(".insert-menu .insert-level-btn", has_text="סעיף ראשי")
        section_btn.click()
        page.fill(".insert-margin-title-input", "ביצוע")
        page.fill(".insert-text-input", "השר ממונה על ביצועו של חוק זה.")
        page.click(".insert-submit-btn")
        page.wait_for_timeout(600)
        docx_lines_after_insert = page.inner_text("#docx-lines")
        check(
            "הוספת סעיף ראשי חדש מופיעה בטבלה (כותרת שוליים 'הוספת סעיף')",
            "הוספת סעיף" in docx_lines_after_insert,
            f"-> {docx_lines_after_insert!r}",
        )
        check(
            "כותרת השוליים שהוקלדה ('ביצוע') מופיעה בטבלה",
            "ביצוע" in docx_lines_after_insert,
        )

        # --- הצומת שהוכנס: מופיע כצומת אמיתי, מודגש בצהוב, וניתן
        # להמשיך ולערוך אותו (לא נעול, לא רק תקציר סטטי) ---
        inserted_node = page.locator(".node.inserted").first
        check("הצומת שהוכנס מופיע בעץ עם מחלקת 'inserted' (רקע צהוב)", inserted_node.count() == 1)
        inserted_text_el = inserted_node.locator(".node-text").first
        check(
            "הצומת שהוכנס עדיין ניתן לעריכה (contenteditable)",
            inserted_text_el.get_attribute("contenteditable") == "true",
        )
        inserted_text_el.click()
        page.keyboard.press("Control+A")
        page.keyboard.type("השר הנוגע בדבר ממונה על ביצועו של חוק זה.")
        inserted_text_el.blur()
        page.wait_for_timeout(600)
        docx_after_editing_inserted = page.inner_text("#docx-lines")
        check(
            "עריכת התוכן שהוכנס משתקפת בטבלה (הצומת החדש לא נעול)",
            "הנוגע בדבר" in docx_after_editing_inserted,
            f"-> {docx_after_editing_inserted!r}",
        )

        # --- פאנל הולידציה אינו מוצג למשתמש (docs/design/README.md #4) -
        # 15 הבדיקות ממשיכות לרוץ בשרת (נבדק ב-tests/unit/test_api.py),
        # אין להן שום ייצוג ב-DOM כאן בכוונה.
        check("אין פאנל ולידציה גלוי ב-DOM", page.locator("#findings-table").count() == 0)

        # --- קריטריון 4: ייצוא docx תקין ---
        page.fill("#bill-title-input", "הצעת חוק בדיקה")
        page.fill("#bill-initiator-input", "בודק/ת")
        with page.expect_download() as download_info:
            page.click("#download-btn")
        download = download_info.value
        out_path = Path("/tmp/e2e-10b-export.docx")
        download.save_as(out_path)
        check("הקובץ שהורד לא ריק", out_path.stat().st_size > 1000, f"-> {out_path.stat().st_size} bytes")
        try:
            with zipfile.ZipFile(out_path) as z:
                names = z.namelist()
                check("הקובץ הוא zip תקין עם word/document.xml", "word/document.xml" in names)
        except zipfile.BadZipFile:
            check("הקובץ הוא zip תקין עם word/document.xml", False, "-> BadZipFile")

        browser.close()

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
