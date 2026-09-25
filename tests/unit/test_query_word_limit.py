"""ש11 + ש14 (26.9.2026) - מגבלת המילים של שאילתה, בלי רשת.

ש11: המגבלה חלה על הגוף בלבד - לא על הכותרת ("שאילתה רגילה") ולא על
הנושא. נבדק באתר החי: הספירה כבר הייתה של הגוף בלבד (40 מילים, והנושא -
5 מילים - לא נספר); מה שחסר הוא שההנחיה למודל תאמר זאת במפורש, ומספור
שהמודל מוסיף לשאלות ("1.") לא ייספר כמילה.

ש14: "התכנס למגבלת המילים" - אחרי הניסוח סופרים בקוד; אם עדיין חורג,
ניסיון נוסף אחד עם הספירה בפועל; ואם גם הוא חורג - within_limit=False
חוזר, והממשק אומר זאת. המודל מוחלף ב-draft_conversation מדומה.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import query_tool  # noqa: E402
from query_tool import _instructions, body_word_count, draft_query  # noqa: E402

TURNS = [{"role": "user", "content": "מחסור בשוטרים בנגב"}]
LONG = "נושא: מחסור בשוטרים\nגוף: " + " ".join(["מילה"] * 60) + "\nרצוני לשאול:\nכמה חסרים?"
SHORT = "נושא: מחסור בשוטרים\nגוף: יש מחסור בשוטרים.\nרצוני לשאול:\nכמה חסרים?"


def _script(*replies):
    calls = []

    def fake(**kw):
        calls.append(kw["turns"])
        return replies[min(len(calls) - 1, len(replies) - 1)]
    query_tool.draft_conversation = fake
    return calls


def test_subject_and_heading_not_counted():
    d = (_script(SHORT), draft_query(turns=TURNS, kind="רגילה", minister="השר", mk_name="x"))[1]
    assert d["word_count"] == 7, d          # "יש מחסור בשוטרים." (3) + "רצוני לשאול:" (2) + "כמה חסרים?" (2)
    assert "מחסור" in d["subject"]


def test_model_numbering_is_not_a_word():
    assert body_word_count("רקע קצר.\nרצוני לשאול:\n1. כמה חסרים?\n2) מתי?") == 7


def test_instruction_says_heading_and_subject_are_excluded():
    text = _instructions("רגילה")
    assert "הכותרת" in text and "שורת הנושא אינן" in text and "נספרות" in text, text


def test_fit_limit_retries_once_with_the_real_count():
    calls = _script(LONG, SHORT)
    d = draft_query(turns=TURNS, kind="דחופה", minister="השר", mk_name="x", fit_limit=True)
    assert len(calls) == 2 and d["within_limit"] and d.get("fit_attempts") == 2, (len(calls), d)
    assert "64 מילים" in calls[1][-1]["content"] and "40" in calls[1][-1]["content"], calls[1][-1]


def test_fit_limit_still_over_reports_it():
    calls = _script(LONG, LONG, LONG)
    d = draft_query(turns=TURNS, kind="דחופה", minister="השר", mk_name="x", fit_limit=True)
    assert len(calls) == 2 and d["within_limit"] is False, (len(calls), d)


def test_without_fit_limit_no_retry():
    calls = _script(LONG, SHORT)
    d = draft_query(turns=TURNS, kind="דחופה", minister="השר", mk_name="x")
    assert len(calls) == 1 and d["within_limit"] is False


original = query_tool.draft_conversation
try:
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
finally:
    query_tool.draft_conversation = original
print("test_query_word_limit: כל הבדיקות עברו")
