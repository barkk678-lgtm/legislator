"""צ7 (26.9.2026) - רישום כל הודעה בשלושת הצ'אטים, בלי רשת.

נבדק: כל נקודת קצה כותבת שורה אחת עם הכלי, מזהה השיחה והמשתמש (מהכותרות),
ההודעה, התשובה והסיווג - חולין, עלבון, ענייני, סירוב, "לא מצאתי", תשובה
ששומר הציטוט החליף, תקלה. וכישלון בכתיבה **לא נוגע בתשובה למשתמש**.
הכתיבה ל-Supabase, המודל והסיווג מוחלפים בפונקציות מקומיות.
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "support"))
from isolate_env import isolate  # noqa: E402

isolate()

import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))

from fastapi.testclient import TestClient  # noqa: E402
import chat_log  # noqa: E402
import main  # noqa: E402
from chat_layer import Preflight  # noqa: E402
from service import LLMResult  # noqa: E402

rows: list[dict] = []
chat_log._post = rows.append
# המרת התגים לשמות נטענת מהמאגר - כאן לא נבדקת (ראו test_rules_expert)
main.rules_humanize_citations = lambda t: t
main.rules_source_labels = lambda ids: []
client = TestClient(main.app)
H = {"X-Chat-User": "u-anon-1", "X-Chat-Conv": "c123"}
Q = {"turns": [{"role": "user", "content": "מחסור בשוטרים"}], "kind": "רגילה", "minister": "השר", "mk_name": "x"}


def _preflight(kind):
    main.chat_preflight = lambda text: Preflight(kind, "נא להתבטא בכבוד 😉" if kind == "insult" else None)
    main.chat_chitchat_reply = lambda text, **kw: "בשמחה!"
    main.chat_chitchat_reply_stream = lambda text, **kw: iter(["בשמחה!"])


def _last():
    assert rows, "לא נרשמה שורה"
    return rows[-1]


def test_query_substantive_and_headers():
    _preflight("substantive")
    main.draft_query = lambda **kw: {"subject": "נושא", "body": "גוף", "word_count": 1, "within_limit": True}
    rows.clear()
    r = client.post("/api/query/draft", json=Q, headers=H)
    assert r.status_code == 200
    row = _last()
    assert (row["tool"], row["kind"], row["user_id"], row["conversation_id"], row["user_message"]) == \
        ("query", "substantive", "u-anon-1", "c123", "מחסור בשוטרים"), row
    assert row["reply"] == "נושא: נושא\nגוף: גוף" and row["meta"]["kind"] == "רגילה", row


def test_query_chitchat_insult_refusal_guard():
    for kind in ("chitchat", "insult"):
        _preflight(kind)
        rows.clear()
        client.post("/api/query/draft", json=Q, headers=H)
        assert _last()["kind"] == kind, rows
    _preflight("substantive")
    for detail, kind in (("לא ניתן לנסח שאילתה: חוות דעת כללית", "refused"),
                         ("לא ניתן לנסח שאילתה: הניסוח כלל פרט שלא הופיע בדבריכם", "guard_replaced"),
                         ("שכבת ה-LLM לא זמינה", "error")):
        def boom(**kw):
            raise main.QueryDraftError(detail)
        main.draft_query = boom
        rows.clear()
        assert client.post("/api/query/draft", json=Q, headers=H).status_code == 422
        assert _last()["kind"] == kind and _last()["reply"] == detail, rows


def test_agenda():
    _preflight("substantive")
    main.draft_agenda = lambda **kw: {"kind": "דחופה", "mk_name": "x", "subject": "נושא", "explanation": ["א.", "ב."]}
    main.current_speaker = lambda: {"name": "י", "gender": "זכר", "source": "fallback"}
    rows.clear()
    r = client.post("/api/agenda/draft", json={"topic_description": "קודם\nמחסור", "mk_name": "x"}, headers=H)
    assert r.status_code == 200
    row = _last()
    assert (row["tool"], row["kind"], row["user_message"]) == ("agenda", "substantive", "מחסור"), row
    assert row["reply"] == "נושא: נושא\nדברי הסבר: א.\nב.", row


def test_rules_kinds_from_the_guard():
    _preflight("substantive")
    cases = [(False, None, "substantive"),
             (True, "[דעה] נשאלתי לדעתי", "refused"),
             (True, "התשובה לא כללה אף ציטוט מקור, למרות שסופקו מקורות - נדחתה כלא-מעוגנת.", "guard_replaced"),
             (True, "אין מספיק מידע במקורות.", "not_found")]
    for refused, reason, kind in cases:
        result = LLMResult(text="" if refused else "תשובה [מקור:law-tkanon-haknesset/52]", refused=refused,
                           refusal_reason=reason, cited_source_ids=[] if refused else ["law-tkanon-haknesset/52"],
                           input_tokens=1, output_tokens=1)
        main.rules_expert_stream = lambda q, _r=result: iter(["תשובה", _r])
        rows.clear()
        r = client.post("/api/rules/ask/stream", json={"question": "שאלה"}, headers=H)
        assert r.status_code == 200 and '"done"' in r.text
        row = _last()
        assert (row["tool"], row["kind"], row["conversation_id"]) == ("rules", kind, "c123"), (kind, row)


def test_rules_chitchat_is_logged():
    _preflight("chitchat")
    rows.clear()
    client.post("/api/rules/ask/stream", json={"question": "תודה!"}, headers=H)
    assert _last()["kind"] == "chitchat" and _last()["reply"] == "בשמחה!", rows


def test_log_failure_never_breaks_the_answer():
    def down(row):
        raise RuntimeError("Supabase down")
    chat_log._post = down
    try:
        _preflight("substantive")
        main.draft_query = lambda **kw: {"subject": "נושא", "body": "גוף", "word_count": 1, "within_limit": True}
        r = client.post("/api/query/draft", json=Q, headers=H)
        assert r.status_code == 200 and r.json()["subject"] == "נושא"
        assert chat_log.log_turn(tool="query", conversation_id=None, user_id=None, message="m",
                                 reply="r", kind="substantive") is False
    finally:
        chat_log._post = rows.append


def test_unknown_kind_and_long_text_are_normalized():
    rows.clear()
    chat_log.log_turn(tool="query", conversation_id="c" * 500, user_id=None, message="x" * 30000,
                      reply=None, kind="weird", post=rows.append)
    row = rows[-1]
    assert row["kind"] == "error" and len(row["user_message"]) == 20000 and len(row["conversation_id"]) == 100, row


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_chat_log: כל הבדיקות עברו")
