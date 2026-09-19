"""בדיקות ל-/api/reservations/quality ולמדידת העלות ב-/analyze.

**בלי רשת ובלי מפתח.** התפר הוא `client.httpx` ו-`client._api_key` -
שניהם נבדקים בזמן הקריאה ולא בזמן ההגדרה, ולכן הם התפר היחיד
שתופס גם את קריאת הניסוח וגם את קריאת הסינון (86(ד)(2)), שהיא
קריאה נפרדת למודל. החלפה של `client.complete` עצמה **לא** הייתה
תופסת את הסינון, כי `service.draft` קושר אותו כברירת מחדל בזמן
ההגדרה - וזה בדיוק מה שגרם לניסוח תקין להיחסם ב-LLMConfigError
בגרסה הראשונה של הטסט הזה.

נבדק כאן: שהעלות המדווחת היא מה שה-API החזיר ולא הערכה, ושמה
שנחסם **אינו** חוזר ללקוח אלא רק נספר (CLAUDE.md חוק ברזל 7).
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "support"))
from isolate_env import clear_secret, isolate, set_secret  # noqa: E402

# **הרמטיות.** עד 2026-09-19 הטסט הזה הסתמך על כך שבמקרה אין מפתחות
# בסביבה. מרגע שהם נטענים מקובץ, ההסתמכות הזו נשברה - ראו
# tests/support/isolate_env.py.
isolate()


import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import client as llm_client  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

BILL = ROOT / "tests" / "fixtures" / "reservations" / "573919.docx"
_SCREEN_MARK = "תקין"


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeHttpx:
    """מחליף את httpx כולו. `TransportError` נדרש כי complete תופסת
    אותו במפורש."""

    TransportError = llm_client.httpx.TransportError

    def __init__(self, drafting_reply):
        self.drafting_reply = drafting_reply
        self.calls = []

    def Client(self, **kw):  # noqa: N802 - חיקוי ה-API של httpx
        outer = self

        class _C:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, url, json=None, headers=None):  # noqa: A002
                outer.calls.append(json)
                is_screen = json["max_tokens"] <= 8
                text = _SCREEN_MARK if is_screen else outer.drafting_reply
                return _Resp({
                    "content": [{"type": "text", "text": text}],
                    "usage": {"input_tokens": 3 if is_screen else 700,
                              "output_tokens": 1 if is_screen else 120},
                    "stop_reason": "end_turn",
                })

        return _C()


def _upload():
    return {"file": ("bill.docx", BILL.read_bytes(),
                     "application/vnd.openxmlformats-officedocument."
                     "wordprocessingml.document")}


def _run(api, reply, **data):
    real_httpx, real_key = llm_client.httpx, llm_client._api_key
    llm_client.httpx = _FakeHttpx(reply)
    llm_client._api_key = lambda: "test-key"
    try:
        return api.post("/api/reservations/quality", files=_upload(), data=data).json()
    finally:
        llm_client.httpx, llm_client._api_key = real_httpx, real_key


def main() -> int:
    checks: list[tuple[str, bool]] = []
    api = TestClient(app)

    analyze = api.post("/api/reservations/analyze", files=_upload()).json()
    checks.append(("analyze מחזיר את עלות מצב האיכות מראש",
                   {"quality_calls", "quality_points", "quality_prompt_chars"} <= set(analyze)))
    checks.append(("analyze כבר לא מחזיר total (הוסר ממכוון ב-measure)",
                   "total" not in analyze))
    checks.append(("קריאה אחת לכל סעיף, לא יותר",
                   0 < analyze["quality_calls"] <= analyze["sections_found"]))
    checks.append(("נקודות עיגון לפחות כמספר הקריאות",
                   analyze["quality_points"] >= analyze["quality_calls"]))

    sections = analyze["sections_found"]
    good = json.dumps([{"point": 1, "text": 'במקום "30 ימים" יבוא "45 ימים".',
                        "rationale": "הארכת המועד"}], ensure_ascii=False)
    d = _run(api, good, sections_limit="5")
    checks.append(("sections_limit גדול ממספר הסעיפים אינו ממציא סעיפים",
                   d["sections_used"] == sections))
    checks.append(("התקבלה הסתייגות", len(d["passed"]) == sections))
    checks.append(("לכל הסתייגות מספר סעיף", all(p["section_number"] for p in d["passed"])))
    checks.append(("נשמר הנימוק", all(p["rationale"] for p in d["passed"])))
    checks.append(("usage סופר קריאת ניסוח לכל סעיף",
                   d["usage"]["drafting_calls"] == sections))
    checks.append(("usage סופר גם את קריאות הסינון - הן בתשלום",
                   d["usage"]["screening_calls"] == len(d["passed"])))
    checks.append(("usage מדווח את הטוקנים שה-API החזיר, לא הערכה",
                   (d["usage"]["input_tokens"], d["usage"]["output_tokens"])
                   == (700 * sections + 3 * len(d["passed"]),
                       120 * sections + 1 * len(d["passed"]))))
    checks.append(("שם המודל מדווח", bool(d["usage"]["model"])))
    checks.append(("אפס חסימות על ניסוח תקין", d["blocked_count"] == 0))

    bad = json.dumps([{"point": 1, "text": "ההצעה כולה תימחק.", "rationale": ""}],
                     ensure_ascii=False)
    d2 = _run(api, bad, sections_limit="1")
    checks.append(("ניסוח שנחסם אינו מוחזר", d2["passed"] == []))
    checks.append(("ניסוח שנחסם כן נספר", d2["blocked_count"] >= 1))
    checks.append(("הסיבות עצמן אינן נשלחות ללקוח", "blocked" not in d2))

    d3 = _run(api, "לא JSON בכלל", sections_limit="1")
    checks.append(("JSON שבור -> אפס הסתייגויות, לא קריסה", d3["passed"] == []))
    checks.append(("JSON שבור נספר כחסימה", d3["blocked_count"] >= 1))

    # בלי מפתח כלל - שגיאת תצורה מפורשת, לא 500 ולא הסתייגות מומצאת
    resp = api.post("/api/reservations/quality", files=_upload(),
                    data={"sections_limit": "1"})
    checks.append(("בלי ANTHROPIC_API_KEY -> 503 מפורש", resp.status_code == 503))
    checks.append(("ההודעה מסבירה מה חסר",
                   "ANTHROPIC_API_KEY" in resp.json().get("detail", "")))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
