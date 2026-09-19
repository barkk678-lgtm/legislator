"""בדיקות ל-apps/api (FastAPI), משימה 10ב. ראו TASKS.md.

עיקרון מרכזי הנבדק כאן: ה-API הוא שכבה דקה - כל endpoint קורא
לפונקציה טהורה קיימת ומחזיר את התוצאה. בודק: (1) המסלול המלא (edits+
insertions -> apply_changes -> amend -> validate -> docx) עובד מקצה
לקצה, (2) עריכה לא נתמכת/הוספה שלא נתמכת חוזרות כ-status ברור, לא
כקריסה, (3) is_normative=False מוסתר לגמרי מהעץ שחוזר ללקוח (משימה
10ב, לא רק תיוג), (4) /insert-preview מחזיר בדיוק את התווית שתיווצר.
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "support"))
from isolate_env import clear_secret, isolate, set_secret  # noqa: E402

# **הרמטיות.** עד 2026-09-19 הטסט הזה הסתמך על כך שבמקרה אין מפתחות
# בסביבה. מרגע שהם נטענים מקובץ, ההסתמכות הזו נשברה - ראו
# tests/support/isolate_env.py.
isolate()


import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)

_KAYTANOT_REF = 'ס"ח התש"ן, עמ\' 155.'
_GOOD_BILL = {
    # אין submitted_date/source_ref כאן בכוונה (10ב): שניהם לא שדות
    # קלט מהמשתמש יותר - ראו schemas.BillMetaIn.
    "title": 'הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון – החמרת הענישה), התש"ף–2023',
    "initiator": "יעקב אשר",
    "explanatory": ["מטרת הצעת החוק להחמיר את הענישה."],
}


def main():
    checks = []

    # GET /api/laws - שני חוקים, אחד amendable ואחד לא
    laws = client.get("/api/laws").json()
    by_id = {law["id"]: law for law in laws}
    checks.append(("GET /api/laws מחזיר 2 חוקים", len(laws) == 2))
    checks.append(("קייטנות מסומן amendable", by_id.get("kaytanot-1990", {}).get("amendable") is True))
    checks.append(
        (
            # תוקן (2026-09-16): amend()/transform.py/insert_preview.py
            # עכשיו מוצאים סעיפים רקורסיבית בכל עומק (node.find_sections) -
            # מאבק (מבנה פרקים) הופך ל-amendable, כצפוי מהתיקון עצמו,
            # לא רגרסיה. ראו TASKS.md ותיעוד law_registry.py._is_amendable.
            "מאבק בארגוני פשיעה מסומן amendable (מבנה פרקים - נמצא רקורסיבית)",
            by_id.get("maavak-2003", {}).get("amendable") is True,
        )
    )

    # GET /api/laws/search - משימה A. ראו law_registry.search_law_titles/
    # law_search.search_laws (הלוגיקה עצמה נבדקת ב-test_law_search.py).
    search_r1 = client.get("/api/laws/search", params={"q": "קייטנות"}).json()
    checks.append(
        ("GET /api/laws/search: תת-מחרוזת מוצאת את חוק הקייטנות בלבד",
         [law["id"] for law in search_r1] == ["kaytanot-1990"]),
    )
    search_r2 = client.get("/api/laws/search", params={"q": "מאבק ארגוני"}).json()
    checks.append(
        ("GET /api/laws/search: ריבוי טוקנים מוצא את חוק מאבק בארגוני פשיעה",
         [law["id"] for law in search_r2] == ["maavak-2003"]),
    )
    search_r3 = client.get("/api/laws/search", params={"q": "לא קיים בכלל"}).json()
    checks.append(("GET /api/laws/search: אין התאמה -> רשימה ריקה", search_r3 == []))
    search_r4 = client.get("/api/laws/search").json()
    checks.append(("GET /api/laws/search: בלי q כלל -> רשימה ריקה, לא שגיאה", search_r4 == []))

    # GET /api/laws/{id} - as_of בניסוח הנכון, עץ מלא, בלי is_normative=False
    law_detail = client.get("/api/laws/kaytanot-1990").json()
    checks.append(
        (
            "as_of_display בניסוח הנכון ('נוסח כפי שהופיע...')",
            law_detail["as_of_display"] is not None
            and law_detail["as_of_display"].startswith("נוסח כפי שהופיע בוויקיטקסט ביום"),
        )
    )
    checks.append(("as_of_display לא כתוב 'מעודכן ליום'", "מעודכן" not in law_detail["as_of_display"]))
    checks.append(("תשובת החוק כוללת עץ עם ילדים", len(law_detail["tree"]["children"]) > 0))

    def _walk(node):
        yield node
        for c in node["children"]:
            yield from _walk(c)

    all_nodes = list(_walk(law_detail["tree"]))
    checks.append(("is_normative לא מופיע בכלל בתשובה", all("is_normative" not in n for n in all_nodes)))
    # קייטנות סעיף 2 מכיל הערות עורך (הערות {{ח:הערה}}) - is_normative=False
    # במקור; אחרי הסינון בשרת, לאף צומת שם אין להיות עם טקסט שמתחיל "ראו"
    # (ניסוח ההערות במקור) - בדיקה עקיפה שהערות אכן לא הגיעו לעץ בכלל.
    checks.append(
        ("אין הערות עורך (טקסט 'ראו ...') בעץ שחוזר ללקוח",
         not any(n["text"] and n["text"].startswith("ראו ") for n in all_nodes))
    )

    # POST /render - עריכת טקסט נתמכת (מקרה זהב סעיף 5, כמו ReplaceWords)
    good_req = {
        "edits": [
            {
                "node_id": "kaytanot-1990/s5/p0",
                "text": "המנהל קייטנה בניגוד להוראות סעיפים 2 או 4, דינו – מאסר שנה.",
            }
        ],
        "insertions": [],
        "bill": _GOOD_BILL,
    }
    render_resp = client.post("/api/laws/kaytanot-1990/render", json=good_req).json()
    checks.append(("render מחזיר שורה אחת", len(render_resp["lines"]) == 1))
    checks.append(
        (
            "עריכת הטקסט מדווחת כ-ok",
            len(render_resp["edit_statuses"]) == 1 and render_resp["edit_statuses"][0]["ok"] is True,
        )
    )
    checks.append(("render מחזיר 15 ממצאי ולידציה תמיד", len(render_resp["findings"]) == 15))
    checks.append(("touched_sections כולל סעיף 5", render_resp["touched_sections"] == ["5"]))

    # מראה מקום נשלף אוטומטית מ-law_registry (לא מהמשתמש, ראו schemas.
    # BillMetaIn) - בדיקה 2 בוולידטור (מראה מקום) אמורה לעבור בלי שום
    # קלט מהמשתמש לגבי זה.
    check2 = next((f for f in render_resp["findings"] if f["check_number"] == 2), None)
    checks.append(
        ("מראה מקום אוטומטי -> בדיקה 2 עוברת בלי קלט מהמשתמש",
         check2 is not None and check2["status"] == "עבר"),
    )

    # מקרה שבור: "עריכה" בלי שום שינוי בפועל (טקסט זהה למקור) - מדווחת
    # כ-ok=False עם סיבה, לא קורסת ולא מנחשת (תרחיש "לא נתמך" הפשוט
    # ביותר; דוגמאות מורכבות יותר - "משפט חוזר על עצמו" וכו' - כבר
    # מכוסות בעומק ב-tests/unit/test_diff_translate.py).
    original_s5_text = "המנהל קייטנה בניגוד להוראות סעיפים 2 או 4, דינו – מאסר ששה חדשים."
    bad_edit_req = {
        "edits": [{"node_id": "kaytanot-1990/s5/p0", "text": original_s5_text}],
        "insertions": [],
        "bill": _GOOD_BILL,
    }
    bad_render = client.post("/api/laws/kaytanot-1990/render", json=bad_edit_req).json()
    checks.append(
        (
            "עריכה בלי שינוי בפועל -> ok=False + סיבה, לא קריסה",
            len(bad_render["edit_statuses"]) == 1
            and bad_render["edit_statuses"][0]["ok"] is False
            and bad_render["edit_statuses"][0]["reason"],
        )
    )

    # עריכת כותרת שוליים (§7.8) - field="margin_title", לא "text".
    title_edit_req = {
        "edits": [{"node_id": "kaytanot-1990/s5", "text": "עונשין חמורים", "field": "margin_title"}],
        "insertions": [],
        "bill": _GOOD_BILL,
    }
    title_render = client.post("/api/laws/kaytanot-1990/render", json=title_edit_req).json()
    checks.append(
        ("עריכת כותרת שוליים מדווחת כ-ok",
         len(title_render["edit_statuses"]) == 1 and title_render["edit_statuses"][0]["ok"] is True),
    )
    checks.append(
        ("עריכת כותרת שוליים מנוסחת לפי §7.8",
         len(title_render["lines"]) == 1
         and "בכותרת השוליים"
         in title_render["lines"][0]["text"] + title_render["lines"][0]["text_after"]),
    )

    # POST /insert-preview - תצוגה מקדימה של תווית לפני ביצוע
    preview_req = {
        "edits": [], "insertions": [],
        "anchor_node_id": "kaytanot-1990/s5", "level": "section",
    }
    insert_preview_resp = client.post("/api/laws/kaytanot-1990/insert-preview", json=preview_req).json()
    checks.append(
        ("insert-preview מחזיר תווית נתמכת לסעיף חדש אחרי 5",
         insert_preview_resp["supported"] is True and insert_preview_resp["label"]),
    )

    # הוספת הגדרה (kind="definition") - אחרי הגדרת "חוק רישוי עסקים"
    # בסעיף 1 (ראו משוב המשתמש: "אין לי אפשרות להוסיף הגדרות").
    def_preview_req = {
        "edits": [], "insertions": [],
        "anchor_node_id": "kaytanot-1990/s1/p1", "level": "definition",
    }
    def_preview_resp = client.post(
        "/api/laws/kaytanot-1990/insert-preview", json=def_preview_req
    ).json()
    checks.append(
        ("insert-preview: הוספת הגדרה נתמכת (בלי מספור)",
         def_preview_resp["supported"] is True),
    )
    def_insert_req = {
        "edits": [],
        "insertions": [
            {"kind": "definition", "anchor_node_id": "kaytanot-1990/s1/p1",
             "text": '"מונח בדיקה" – פירוש בדיקה.', "client_id": "def-test-1"},
        ],
        "bill": _GOOD_BILL,
    }
    def_render = client.post("/api/laws/kaytanot-1990/render", json=def_insert_req).json()
    checks.append(
        ("הוספת הגדרה: אין שגיאות הוספה", def_render["insertion_errors"] == []),
    )
    checks.append(
        ("הוספת הגדרה: מנוסחת כ'אחרי ההגדרה ... יבוא'",
         any('אחרי ההגדרה "חוק רישוי עסקים" יבוא' in ln["text"] for ln in def_render["lines"])),
    )

    # שילוב: עריכה + הוספת סעיף ראשי חדש יחד, ואז /docx על אותה בקשה בדיוק.
    combined_req = {
        "edits": [
            {
                "node_id": "kaytanot-1990/s5/p0",
                "text": "המנהל קייטנה בניגוד להוראות סעיפים 2 או 4, דינו – מאסר שנה.",
            }
        ],
        "insertions": [
            {"kind": "section", "anchor_node_id": "kaytanot-1990/s5",
             "margin_title": "ביצוע", "text": "השר ממונה על ביצועו של חוק זה.",
             "client_id": "test-ins-1"},
        ],
        "bill": _GOOD_BILL,
    }
    combined_render = client.post("/api/laws/kaytanot-1990/render", json=combined_req).json()
    checks.append(("שילוב עריכה+הוספה: אין שגיאות הוספה", combined_render["insertion_errors"] == []))
    checks.append(("שילוב עריכה+הוספה: 2 סעיפים נגעו", len(combined_render["touched_sections"]) == 2))

    def _walk2(node):
        yield node
        for c in node["children"]:
            yield from _walk2(c)

    combined_nodes = list(_walk2(combined_render["tree"]))
    inserted_node = next((n for n in combined_nodes if n["id"] == "test-ins-1"), None)
    checks.append(
        ("עץ ה-render כולל את הצומת שהוכנס, עם ה-client_id היציב שנשלח",
         inserted_node is not None and inserted_node["margin_title"] == "ביצוע"),
    )

    docx_resp = client.post("/api/laws/kaytanot-1990/docx", json=combined_req)
    checks.append(("docx: סטטוס 200", docx_resp.status_code == 200))
    checks.append(("docx: תוכן לא ריק", len(docx_resp.content) > 1000))
    checks.append(
        (
            "docx: content-type תקין",
            "wordprocessingml" in docx_resp.headers.get("content-type", ""),
        )
    )

    # שם הצעה ריק + דברי הסבר ריקים (המשתמש לא מילא) -> המערכת בונה
    # ברירת מחדל דטרמיניסטית לשניהם, לא משאירה ריק (ראו משוב המשתמש:
    # "אתה ממש העלמת את כל הכותרת").
    import io
    import re
    import zipfile

    blank_meta_req = {
        "edits": [
            {
                "node_id": "kaytanot-1990/s5/p0",
                "text": "המנהל קייטנה בניגוד להוראות סעיפים 2 או 4, דינו – מאסר שנה.",
            }
        ],
        "insertions": [],
        "bill": {"title": "", "initiator": "בודק/ת", "explanatory": []},
    }
    blank_docx_resp = client.post("/api/laws/kaytanot-1990/docx", json=blank_meta_req)
    with zipfile.ZipFile(io.BytesIO(blank_docx_resp.content)) as z:
        blank_xml = z.read("word/document.xml").decode("utf-8")
    checks.append(
        ("כותרת ברירת מחדל: כוללת את שם החוק", "הקייטנות (רישוי ופיקוח)" in blank_xml),
    )
    checks.append(
        ("כותרת ברירת מחדל: תיאור התיקון מסומן 'יש להשלים' עם רקע צהוב",
         bool(re.search(r'<w:highlight w:val="yellow"/>[^<]*<w:rtl/></w:rPr><w:t>יש להשלים</w:t>', blank_xml))),
    )
    checks.append(
        ("דברי הסבר ריקים -> נבנתה טיוטה אוטומטית", "מוצע ל" in blank_xml),
    )

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
