"""ת4 + ת5 (25.9.2026): השכבה המשותפת לצ'אטבוטים - סיווג לפני תשובה.
בלי רשת: המסווג והמנסח מוזרקים."""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "config"))

import chat_layer as cl  # noqa: E402
from client import LLMRequestError, RawCompletion  # noqa: E402


def fake(label):
    def _c(**kw):
        return RawCompletion(text=label, input_tokens=1, output_tokens=1, stop_reason="end_turn")
    return _c


def boom(**kw):
    raise LLMRequestError("רשת")


def main() -> int:
    checks = [
        ("חולין -> chitchat", cl.classify("אתה נהדר כל הכבוד!", complete_fn=fake("חולין")) == "chitchat"),
        ("עלבון -> insult", cl.classify("אתה מטומטם", complete_fn=fake("עלבון")) == "insult"),
        ("עניינית -> substantive", cl.classify("כמה חתימות?", complete_fn=fake("עניינית")) == "substantive"),
        ("פלט לא צפוי -> substantive (המסלול המוגן)", cl.classify("x", complete_fn=fake("אולי")) == "substantive"),
        ("כשל רשת -> substantive", cl.classify("x", complete_fn=boom) == "substantive"),
        ("הודעה ריקה -> substantive בלי קריאה", cl.classify("  ", complete_fn=boom) == "substantive"),
        ("מילה עם נקודה -> מזוהה", cl.classify("x", complete_fn=fake("חולין.")) == "chitchat"),
    ]
    pf = cl.preflight("אתה מטומטם", complete_fn=fake("עלבון"))
    checks.append(("עלבון: תשובה מוכנה, בלי קריאה נוספת",
                   pf.kind == "insult" and pf.reply in cl._INSULT_REPLIES))
    checks.append(("התשובה המקורית של ברק ברשימה",
                   "אני מזכיר, כאן זו לא מליאת הכנסת – נא להתבטא בכבוד 😉" in cl._INSULT_REPLIES))
    checks.append(("וריאציות: יותר מתשובה אחת",
                   len({cl.insult_reply(random.Random(i)) for i in range(40)}) > 1))
    checks.append(("חולין: preflight לא מנסח בעצמו",
                   cl.preflight("תודה", complete_fn=fake("חולין")).reply is None))
    reply = cl.chitchat_reply("תודה", tool="מומחה התקנון", can_do="שאלות על התקנון",
                              complete_fn=fake("בשמחה! 😊"))
    checks.append(("תשובת חולין מוחזרת", reply == "בשמחה! 😊"))
    checks.append(("תשובת חולין בכשל רשת - לא נופלת",
                   cl.chitchat_reply("תודה", tool="t", can_do="c", complete_fn=boom) == "תודה! 😊"))
    sys_prompt = cl._chitchat_system("מומחה התקנון", "שאלות על התקנון")
    checks.append(("הנחיית החולין אוסרת עובדות", "אסור לציין שום עובדה" in sys_prompt))

    failed = 0
    for name, ok in checks:
        print(("✓" if ok else "✗"), name)
        failed += not ok
    print(f"\n{len(checks) - failed}/{len(checks)} עברו")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
