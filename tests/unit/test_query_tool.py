"""בדיקות ל-apps/api/query_tool.py (משימה ו, 2026-09-16) - בלי רשת.

בודקות: פרסור הפורמט נושא:/גוף: מתשובת ה-LLM, ספירת מילים ובדיקת
המגבלה לפי סוג השאילתה (50/40/בלי הגבלה - §48/49/50 תקנון הכנסת),
טיפול בסירוב-מודל מפורש, ותקינות ה-docx שנוצר (python-docx לבדיקה
בלבד - לא תלות של האפליקציה, ראו requirements.txt).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import query_tool  # noqa: E402
from query_tool import QueryDraftError, draft_query, write_query_docx  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SKELETON = REPO_ROOT / "reference" / "skeleton-pshia.docx"


def main():
    ok = True
    original_draft = query_tool.draft

    def _set(reply):
        query_tool.draft = lambda **kw: reply

    # --- פרסור תקין: נושא: + גוף:, ספירת מילים נכונה, within_limit=True ---
    _set("נושא: זמני המתנה במוקד 100\nגוף: האם נבדקו זמני ההמתנה במוקד 100 בשנה האחרונה?")
    try:
        q = draft_query(topic_description="משהו על מוקד 100", kind="רגילה", minister="לביטחון הפנים", mk_name="ישראל ישראלי")
        passed = (
            q["subject"] == "זמני המתנה במוקד 100"
            and q["body"] == "האם נבדקו זמני ההמתנה במוקד 100 בשנה האחרונה?"
            and q["word_count"] == 8
            and q["within_limit"] is True
            and q["word_limit"] == 50
        )
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "פרסור תקין: נושא/גוף/ספירת מילים/within_limit ->", q if not passed else "")
    finally:
        query_tool.draft = original_draft

    # --- חריגה ממגבלת המילים (שאילתה דחופה, 40 מילים) -> within_limit=False, לא נחתך בשקט ---
    long_body = " ".join(["מילה"] * 45)
    _set(f"נושא: נושא כלשהו\nגוף: {long_body}")
    try:
        q = draft_query(topic_description="תיאור", kind="דחופה", minister="הבריאות", mk_name="פלונית")
        passed = q["word_count"] == 45 and q["within_limit"] is False and q["word_limit"] == 40 and len(q["body"].split()) == 45
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "חריגה ממגבלת מילים -> within_limit=False, הגוף לא נחתך בשקט")
    finally:
        query_tool.draft = original_draft

    # --- שאילתה ישירה -> אין מגבלת מילים בכלל ---
    _set(f"נושא: נושא\nגוף: {long_body} עוד כמה מילים נוספות בשביל הבדיקה הזו כדי לוודא שאין הגבלה")
    try:
        q = draft_query(topic_description="תיאור", kind="ישירה", minister="האוצר", mk_name="פלוני")
        passed = q["word_limit"] is None and q["within_limit"] is True
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "שאילתה ישירה -> בלי מגבלת מילים, within_limit=True תמיד")
    finally:
        query_tool.draft = original_draft

    # --- סירוב מפורש מהמודל -> QueryDraftError, לא תשובה מזויפת ---
    _set("לא ניתן לנסח שאילתה: הבקשה מבקשת חוות דעת כללית, לא עניין עובדתי.")
    try:
        threw = False
        try:
            draft_query(topic_description="מה דעתך על הממשלה?", kind="רגילה", minister="ראש הממשלה", mk_name="פלוני")
        except QueryDraftError as e:
            threw = "חוות דעת כללית" in str(e)
        ok = ok and threw
        print(("OK " if threw else "FAIL"), "סירוב-מודל מפורש -> QueryDraftError עם ההסבר, לא תשובה מזויפת")
    finally:
        query_tool.draft = original_draft

    # --- פורמט לא תקין מהמודל (בלי נושא:/גוף:) -> QueryDraftError, לא קורס/מנחש ---
    _set("תשובה חופשית בלי הפורמט הנדרש בכלל.")
    try:
        threw = False
        try:
            draft_query(topic_description="תיאור", kind="רגילה", minister="החינוך", mk_name="פלוני")
        except QueryDraftError:
            threw = True
        ok = ok and threw
        print(("OK " if threw else "FAIL"), "פורמט לא תקין מהמודל -> QueryDraftError, לא קורס/מנחש")
    finally:
        query_tool.draft = original_draft

    # --- write_query_docx: מייצר קובץ תקין (python-docx לבדיקה בלבד) ---
    try:
        import docx  # noqa: PLC0415

        query = {
            "kind": "רגילה",
            "minister": "לביטחון הפנים",
            "mk_name": "ישראל ישראלי",
            "subject": "זמני המתנה במוקד 100",
            "body": "האם נבדקו זמני ההמתנה הממוצעים במוקד 100 בשנה האחרונה?",
        }
        out = write_query_docx(query, skeleton=SKELETON, out=Path("/tmp") / "test_query_tool_output.docx")
        d = docx.Document(str(out))
        texts = [p.text for p in d.paragraphs]
        passed = any("שאילתה רגילה" in t for t in texts) and any(query["subject"] in t for t in texts) and any(
            query["body"] in t for t in texts
        )
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "write_query_docx מייצר docx תקין וקריא")
        out.unlink(missing_ok=True)
    except ImportError:
        print("SKIP write_query_docx (python-docx לא מותקן - כלי בדיקה בלבד, לא תלות אפליקציה)")

    # שומר הנמען (2026-09-18). הנמען הוא נתון שהמשתמש בוחר, לא משהו
    # שהמודל קובע - ראו CLAUDE.md "פלט מודל אינו עובדה". נמצא בבדיקה
    # מול 10 שאלות אמיתיות שהמודל פתח גוף ב"לשר הפנים - " כשהנמען
    # שנבחר היה השר להגנת הסביבה, ורק פעם אחת מתוך ארבע - ולכן
    # ההנחיה לבדה אינה מספיקה.
    from query_tool import _strip_addressee  # noqa: PLC0415

    addressee_cases = [
        ("לשר הפנים - מה היה התקציב?", "מה היה התקציב?", "לשר הפנים -"),
        ("לכבוד השר להגנת הסביבה: מה קורה?", "מה קורה?", "לכבוד השר להגנת הסביבה:"),
        ("אל השר, מה נעשה?", "מה נעשה?", "אל השר,"),
        # אזכור באמצע הגוף הוא תוכן השאלה - לא נוגעים בו
        ("מה עשה משרד הפנים בנושא?", "מה עשה משרד הפנים בנושא?", ""),
        ("האם ידוע לשר על עיכובים?", "האם ידוע לשר על עיכובים?", ""),
    ]
    for given, want_body, want_removed in addressee_cases:
        got_body, got_removed = _strip_addressee(given)
        passed = got_body == want_body and got_removed == want_removed
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), f"שומר נמען: {given[:38]}",
              "" if passed else f"-> {got_body!r} / {got_removed!r}")

    # שם השר אינו מגיע למודל בכלל - הוא לא בהנחיות ולא בתוכן
    from query_tool import _instructions  # noqa: PLC0415

    no_minister = "הפנים" not in _instructions("רגילה") and "השר להגנת" not in _instructions("רגילה")
    ok = ok and no_minister
    print(("OK  " if no_minister else "FAIL"), "שם השר אינו חלק מההנחיות למודל")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
