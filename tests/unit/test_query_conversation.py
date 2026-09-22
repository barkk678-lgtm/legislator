"""ב1 - הסירוב הדביק. בדיקות אופליין, בלי רשת.

**הבאג שנתפס (ברק, צילום מסך 2026-09-22):** המשתמש שאל שאלה לא
תקינה, קיבל סירוב מוצדק, ואז שאל שאלה תקינה לגמרי - וקיבל שוב
סירוב שמתייחס ל"חלק הראשון". הסיבה לא הייתה המודל אלא שורה אחת
בלקוח: כל הודעות המשתמש הודבקו ב-"\n" ונשלחו כתיאור אחד, ולכן
הגוש שנשלח עדיין הכיל את השאלה שנדחתה.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "config"))
sys.path.insert(0, str(ROOT / "packages" / "render"))

import query_tool as qt  # noqa: E402
from client import RawCompletion  # noqa: E402
from service import draft_conversation  # noqa: E402

GOOD = "נושא: מצבת כוח אדם במשטרה\nגוף: מהם נתוני התקן והמצבה בפועל?"


def capture():
    """מחזיר (fn, box) - fn מתעד מה נשלח בפועל למודל."""
    box = {}
    def fake(*, system, user_message=None, messages=None, max_tokens=1500, model=""):
        box["system"] = system
        box["messages"] = messages
        box["user_message"] = user_message
        return RawCompletion(text=GOOD, input_tokens=1, output_tokens=1, stop_reason="end_turn")
    return fake, box


def test_turns_are_sent_as_separate_messages_not_one_blob():
    fn, box = capture()
    turns = [
        {"role": "user", "content": "למה יש מלחמות וכאב"},
        {"role": "assistant", "content": "לא ניתן לנסח שאילתה: שאלה פילוסופית."},
        {"role": "user", "content": "למה אין מספיק שוטרים?"},
    ]
    draft_conversation(instructions="הנחיות", turns=turns, complete_fn=fn)
    assert box["user_message"] is None, "נשלחה מחרוזת אחת במקום תורים"
    assert box["messages"] == turns
    # **הלב של הבאג:** השאלה שנדחתה אינה חלק מההודעה האחרונה.
    assert "מלחמות" not in box["messages"][-1]["content"]


def test_instructions_stay_in_system_not_in_the_conversation():
    fn, box = capture()
    draft_conversation(instructions="כללי התקנון", turns=[{"role": "user", "content": "ש"}],
                       complete_fn=fn)
    assert box["system"] == "כללי התקנון"
    assert all("כללי התקנון" not in m["content"] for m in box["messages"])


def test_last_turn_must_be_the_user():
    for bad in ([], [{"role": "assistant", "content": "x"}]):
        try:
            draft_conversation(instructions="i", turns=bad, complete_fn=capture()[0])
        except ValueError:
            continue
        raise AssertionError(f"תורים לא תקינים התקבלו: {bad}")


def test_draft_query_passes_the_whole_conversation_through():
    fn, box = capture()
    import service
    original = service.complete
    qt.draft_conversation = lambda **kw: draft_conversation(**{**kw, "complete_fn": fn})
    turns = [{"role": "user", "content": "שאלה ראשונה"},
             {"role": "assistant", "content": "לא ניתן לנסח שאילתה: כללית מדי."},
             {"role": "user", "content": "מהם נתוני התקן במשטרה?"}]
    out = qt.draft_query(turns=turns, kind="רגילה", minister="לביטחון לאומי", mk_name="ברק")
    qt.draft_conversation = draft_conversation
    service.complete = original
    assert box["messages"] == turns
    assert out["body"].startswith("מהם נתוני התקן")
    assert out["within_limit"] is True


for name, fn_ in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn_()
        print(f"  ✓ {name}")
print("test_query_conversation: כל הבדיקות עברו")
