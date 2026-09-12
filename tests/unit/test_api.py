"""בדיקות ל-apps/api (FastAPI). ראו TASKS.md משימה 10.

עיקרון מרכזי הנבדק כאן: ה-API הוא שכבה דקה - כל endpoint קורא
לפונקציה טהורה קיימת ומחזיר את התוצאה. הטסטים האלה בודקים בדיוק את
זה: (1) שהמסלול המלא (parse -> apply -> amend -> validate -> docx)
עובד מקצה לקצה דרך ה-API, (2) ששגיאת apply() (ביטוי לא ייחודי) עוברת
ל-API כמו שהיא, בלי שה-API "מתקן" או מנחש, (3) שהחוק המקונן בפרקים
(מאבק בארגוני פשיעה) מסומן amendable=False ולא נכשל בשקט.
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

    # GET /api/laws/{id} - as_of בניסוח הנכון, עץ מלא
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

    # POST /preview - מקרה זהב סעיף 5, זהה בדיוק לפלט amend() הישיר
    good_req = {
        "transformations": [
            {
                "kind": "replace_words",
                "target_id": "kaytanot-1990/s5/p0",
                "old_phrase": "מאסר ששה חדשים",
                "new_phrase": "מאסר שנה",
            }
        ],
        "bill": _GOOD_BILL,
    }
    preview = client.post("/api/laws/kaytanot-1990/preview", json=good_req).json()
    checks.append(("preview תקין: אין שגיאה", preview["error"] is None))
    checks.append(("preview מחזיר שורה אחת", len(preview["lines"]) == 1))
    checks.append(
        (
            "טקסט השורה זהה בדיוק לפלט amend() (כולל en-dash, ראו משימה 6א)",
            preview["lines"][0]["text"]
            == 'בחוק הקייטנות (רישוי ופיקוח), התש"ן–1990 (להלן – החוק העיקרי), '
            'בסעיף 5, במקום "מאסר ששה חדשים" יבוא "מאסר שנה".',
        )
    )
    checks.append(("preview מחזיר 15 ממצאי ולידציה תמיד", len(preview["findings"]) == 15))
    checks.append(("touched_sections כולל סעיף 5", preview["touched_sections"] == ["5"]))
    checks.append(("after_tree מוחזר (לא None)", preview["after_tree"] is not None))

    # מקרה שבור: ביטוי לא ייחודי/לא קיים - שגיאת apply() חוזרת כמו שהיא
    bad_req = {
        "transformations": [
            {
                "kind": "replace_words",
                "target_id": "kaytanot-1990/s5/p0",
                "old_phrase": "טקסט שלא קיים בכלל",
                "new_phrase": "x",
            }
        ],
        "bill": _GOOD_BILL,
    }
    bad_preview = client.post("/api/laws/kaytanot-1990/preview", json=bad_req).json()
    checks.append(
        (
            "ביטוי לא קיים -> שגיאת apply() המדויקת חוזרת, לא ניחוש",
            bad_preview["error"] is not None and "לא נמצא" in bad_preview["error"],
        )
    )
    checks.append(("preview שגוי לא מחזיר שורות", bad_preview["lines"] == []))

    # מקרה שבור: ניסיון preview על חוק לא-amendable (מבנה פרקים)
    blocked_req = {"transformations": [], "bill": _GOOD_BILL}
    blocked_resp = client.post("/api/laws/maavak-2003/preview", json=blocked_req)
    # apply() על טרנספורמציות ריקות לא זורק, אבל law_footnote_key ל-maavak שונה -
    # מוודאים רק שהקריאה לא קורסת (500) בלי טיפול.
    checks.append(("preview על חוק לא-amendable לא קורס (500)", blocked_resp.status_code == 200))

    # POST /docx - מקרה תקין מפיק קובץ docx אמיתי
    docx_resp = client.post("/api/laws/kaytanot-1990/docx", json=good_req)
    checks.append(("docx: סטטוס 200", docx_resp.status_code == 200))
    checks.append(("docx: תוכן לא ריק", len(docx_resp.content) > 1000))
    checks.append(
        (
            "docx: content-type תקין",
            "wordprocessingml" in docx_resp.headers.get("content-type", ""),
        )
    )

    # POST /docx - מקרה שבור: apply() נכשל -> 400, לא 500 ולא קובץ שגוי
    bad_docx_resp = client.post("/api/laws/kaytanot-1990/docx", json=bad_req)
    checks.append(("docx עם ביטוי לא קיים -> 400, לא 500", bad_docx_resp.status_code == 400))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
