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

    def _set(reply):
        agenda_tool.draft = lambda **kw: reply

    # --- פרסור תקין: נושא:/נימוק:/בקשה: ---
    _set(
        "נושא: מצוקת דיור לזוגות צעירים\n"
        "נימוק: מחירי הדיור עלו משמעותית בשנים האחרונות, ורבים מהזוגות הצעירים מתקשים לרכוש דירה ראשונה.\n"
        "בקשה: מוצע כי הכנסת תדון בצעדים להנגשת דיור לזוגות צעירים."
    )
    try:
        a = draft_agenda(topic_description="מחירי הדיור גבוהים מדי לזוגות צעירים", mk_name="דנה לוי")
        passed = (
            a["subject"] == "מצוקת דיור לזוגות צעירים"
            and a["reasoning"].startswith("מחירי הדיור עלו")
            and a["request_text"].startswith("מוצע כי הכנסת תדון")
            and a["mk_name"] == "דנה לוי"
        )
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "פרסור תקין: נושא/נימוק/בקשה ->", a if not passed else "")
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
