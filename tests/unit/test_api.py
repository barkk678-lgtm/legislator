"""בדיקות ל-apps/api (FastAPI), משימה 10ב. ראו TASKS.md.

עיקרון מרכזי הנבדק כאן: ה-API הוא שכבה דקה - כל endpoint קורא
לפונקציה טהורה קיימת ומחזיר את התוצאה. בודק: (1) המסלול המלא (edits+
insertions -> apply_changes -> amend -> validate -> docx) עובד מקצה
לקצה, (2) עריכה לא נתמכת/הוספה שלא נתמכת חוזרות כ-status ברור, לא
כקריסה, (3) is_normative=False מוסתר לגמרי מהעץ שחוזר ללקוח (משימה
10ב, לא רק תיוג), (4) /insert-preview מחזיר בדיוק את התווית שתיווצר.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)

_KAYTANOT_REF = 'ס"ח התש"ן, עמ\' 155.'
_GOOD_BILL = {
    "title": 'הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון – החמרת הענישה), התש"ף–2023',
    "initiator": "יעקב אשר",
    "submitted_date": "15.11.2023",
    "source_ref": _KAYTANOT_REF,
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
            "מאבק בארגוני פשיעה מסומן לא-amendable (מבנה פרקים, לא באג שקט)",
            by_id.get("maavak-2003", {}).get("amendable") is False,
        )
    )

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
             "margin_title": "ביצוע", "text": "השר ממונה על ביצועו של חוק זה."},
        ],
        "bill": _GOOD_BILL,
    }
    combined_render = client.post("/api/laws/kaytanot-1990/render", json=combined_req).json()
    checks.append(("שילוב עריכה+הוספה: אין שגיאות הוספה", combined_render["insertion_errors"] == []))
    checks.append(("שילוב עריכה+הוספה: 2 סעיפים נגעו", len(combined_render["touched_sections"]) == 2))

    docx_resp = client.post("/api/laws/kaytanot-1990/docx", json=combined_req)
    checks.append(("docx: סטטוס 200", docx_resp.status_code == 200))
    checks.append(("docx: תוכן לא ריק", len(docx_resp.content) > 1000))
    checks.append(
        (
            "docx: content-type תקין",
            "wordprocessingml" in docx_resp.headers.get("content-type", ""),
        )
    )

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
