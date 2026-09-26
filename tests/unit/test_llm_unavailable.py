"""סבב הסגירה של ההסתייגויות, א2 (ברק 26.9.2026): המודל לא זמין - הודעה בעברית.

נמצא באתר החי (26.9): כשחשבון Anthropic התרוקן, המשתמש קיבל את שגיאת ה-API הגולמית -
"שכבת ה-LLM לא זמינה: HTTP 400 מ-Anthropic: {"type":"error",...credit balance...}".
עכשיו - בכל כלי שנוגע במודל (מומחה התקנון, השאילתות, ההצעה לסדר, תקציר ההצעה, בודק
הניסוח) המשתמש רואה **"השירות אינו זמין כרגע, נסו שוב בעוד כמה דקות"**, והסיבה הטכנית
נרשמת ב-chat_log כ-error. שלושה מצבים: קרדיט, מגבלת קצב, שירות שנפל - ומפתח חסר.
נכשל על הקוד הקודם (ההודעה הגולמית עברה למשתמש).
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
sys.path.insert(0, str(ROOT / "packages" / "documents"))

from fastapi.testclient import TestClient  # noqa: E402
import agenda_tool  # noqa: E402
import chat_log  # noqa: E402
import main  # noqa: E402
import query_tool  # noqa: E402
import rules_expert  # noqa: E402
from chat_layer import Preflight  # noqa: E402
from service import UNAVAILABLE_MESSAGE, LLMConfigError, LLMRequestError  # noqa: E402

MSG = "השירות אינו זמין כרגע, נסו שוב בעוד כמה דקות"
FAILURES = {
    "credit": LLMRequestError('HTTP 400 מ-Anthropic (לא-חולף): {"type":"error","error":{"message":'
                              '"Your credit balance is too low to access the Anthropic API."}}'),
    "rate": LLMRequestError('HTTP 429 מ-Anthropic (לא-חולף): {"type":"error","error":{"type":"rate_limit_error"}}'),
    "down": LLMRequestError("קריאה ל-Anthropic נכשלה: HTTP 529 מ-Anthropic: overloaded_error"),
    "config": LLMConfigError("ANTHROPIC_API_KEY חסר"),
}
RAW_MARKERS = ("HTTP", "Anthropic", "credit", "rate_limit", "overloaded", "ANTHROPIC_API_KEY", "LLM")

rows: list[dict] = []
chat_log._post = rows.append
main.chat_preflight = lambda text: Preflight("substantive", None)
client = TestClient(main.app, raise_server_exceptions=False)
H = {"X-Chat-User": "u-anon-1", "X-Chat-Conv": "c123"}


def _raiser(exc):
    def f(*a, **kw):
        raise exc
    return f


def _clean(text: str) -> bool:
    return MSG in text and not any(m in text for m in RAW_MARKERS)


def test_message_is_the_agreed_one():
    assert UNAVAILABLE_MESSAGE == MSG


def test_query_agenda_rules_show_hebrew_and_log_reason():
    for name, exc in FAILURES.items():
        rows.clear()
        query_tool.draft_conversation = _raiser(exc)
        main.draft_query = query_tool.draft_query
        r = client.post("/api/query/draft", headers=H, json={
            "turns": [{"role": "user", "content": "מחסור בשוטרים"}], "kind": "רגילה",
            "minister": "השר", "mk_name": "x"})
        assert r.status_code == 503 and _clean(r.json()["detail"]), (name, r.status_code, r.text[:200])
        assert rows and rows[-1]["kind"] == "error" and str(exc)[:20] in rows[-1]["reply"], (name, rows[-1:])

        rows.clear()
        agenda_tool.draft = _raiser(exc)
        main.draft_agenda = agenda_tool.draft_agenda
        r = client.post("/api/agenda/draft", headers=H, json={
            "topic_description": "מחסור בשוטרים", "mk_name": "x", "kind": "רגילה"})
        assert r.status_code == 503 and _clean(r.json()["detail"]), (name, r.status_code, r.text[:200])
        assert rows and rows[-1]["kind"] == "error" and str(exc)[:20] in rows[-1]["reply"], (name, rows[-1:])

        rows.clear()
        rules_expert.answer_with_sources_stream = _raiser(exc)
        rules_expert.sources = lambda: []
        main.rules_expert_stream = rules_expert.ask_stream
        r = client.post("/api/rules/ask/stream", headers=H, json={"question": "מה המניין בוועדה?"})
        events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
        errors = [e["error"] for e in events if "error" in e]
        assert errors and _clean(errors[0]), (name, r.text[:300])
        assert rows and rows[-1]["kind"] == "error" and str(exc)[:20] in rows[-1]["reply"], (name, rows[-1:])

        rules_expert.answer_with_sources = _raiser(exc)
        main.rules_expert_ask = rules_expert.ask
        r = client.post("/api/rules/ask", json={"question": "מה המניין בוועדה?"})
        assert r.status_code == 503 and _clean(r.json()["detail"]), (name, r.text[:200])


def test_summary_and_critique_hebrew():
    import critique  # noqa: PLC0415
    import summarize  # noqa: PLC0415
    from extract_docx import extract_bill  # noqa: PLC0415

    docx = ROOT / "tests" / "fixtures" / "real-bills" / "13948414.docx"
    for name, exc in FAILURES.items():
        orig = summarize.summarize_bill
        summarize.summarize_bill = _raiser(exc)
        try:
            r = client.post("/api/documents/summarize", files={"file": ("b.docx", docx.read_bytes())})
        finally:
            summarize.summarize_bill = orig
        assert r.status_code == 503 and _clean(r.json()["detail"]), (name, r.text[:200])

        result = critique.critique_bill(extract_bill(docx), draft_fn=_raiser(exc))
        assert result.items and _clean(result.explain_error), (name, result.explain_error)


def test_missing_key_handler_hebrew():
    """מפתח חסר שמגיע עד ה-handler המרכזי - גם הוא לא מראה שם משתנה למשתמש."""
    @main.app.get("/__test_llm_config")
    def _boom():
        raise LLMConfigError("ANTHROPIC_API_KEY חסר")
    r = client.get("/__test_llm_config")
    assert r.status_code == 503 and _clean(r.json()["detail"]), r.text


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_llm_unavailable: כל הבדיקות עברו")
