"""בדיקות ל-apps/api/agenda_tool.py (משימה ז, 2026-09-16) - בלי רשת.
אותו דפוס בדיוק כמו test_query_tool.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import agenda_tool  # noqa: E402
from agenda_tool import AgendaDraftError, draft_agenda  # noqa: E402


def main():
    ok = True
    original_draft = agenda_tool.draft
    # ס5: השומר נגד פרט חדש מנסה ניסוח מחדש דרך draft_conversation - כאן בלי רשת.
    agenda_tool.draft_conversation = lambda **kw: (_ for _ in ()).throw(AssertionError("קריאה לא צפויה למודל"))

    def _set(reply):
        agenda_tool.draft = lambda **kw: reply

    # --- פרסור תקין: נושא: / דברי הסבר: (ס3 - המבנה של הטופס של הכנסת) ---
    _set(
        "נושא: מצוקת דיור לזוגות צעירים\n"
        "דברי הסבר: מחירי הדיור גבוהים מדי עבור זוגות צעירים.\n"
        "רבים מהזוגות הצעירים מתקשים לרכוש דירה ראשונה."
    )
    try:
        a = draft_agenda(topic_description="מחירי הדיור גבוהים מדי לזוגות צעירים", mk_name="דנה לוי")
        passed = (
            a["subject"] == "מצוקת דיור לזוגות צעירים"
            and a["explanation"] == ["מחירי הדיור גבוהים מדי עבור זוגות צעירים.",
                                     "רבים מהזוגות הצעירים מתקשים לרכוש דירה ראשונה."]
            and a["mk_name"] == "דנה לוי" and a["kind"] == "דחופה"
        )
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "פרסור תקין: נושא/דברי הסבר, פסקה לכל שורה ->", a if not passed else "")
        passed = draft_agenda(topic_description="x", mk_name="y", kind="רגילה")["kind"] == "רגילה"
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "הסוג עובר לטיוטה (דחופה/רגילה)")
    finally:
        agenda_tool.draft = original_draft

    # --- סירוב מפורש מהמודל -> AgendaDraftError ---
    _set("לא ניתן לנסח הצעה לסדר: התיאור מכיל לשון פוגענית שלא ניתן לנסח מחדש.")
    try:
        threw = False
        try:
            draft_agenda(topic_description="תיאור בעייתי", mk_name="פלוני")
        except AgendaDraftError as e:
            threw = "לשון פוגענית" in str(e)
        ok = ok and threw
        print(("OK " if threw else "FAIL"), "סירוב-מודל מפורש -> AgendaDraftError עם ההסבר")
    finally:
        agenda_tool.draft = original_draft

    # --- פורמט לא תקין -> AgendaDraftError, לא קורס ---
    _set("תשובה בלי הפורמט הנדרש.")
    try:
        threw = False
        try:
            draft_agenda(topic_description="תיאור", mk_name="פלוני")
        except AgendaDraftError:
            threw = True
        ok = ok and threw
        print(("OK " if threw else "FAIL"), "פורמט לא תקין -> AgendaDraftError, לא קורס/מנחש")
    finally:
        agenda_tool.draft = original_draft

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
