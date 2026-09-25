"""ח17 + צ5 (26.9.2026) - הורדת Word בלי שום שירות חיצוני ברגע הלחיצה.

נמדד באתר החי לפני התיקון, על חמש העריכות של ברק בחוק-יסוד: הכנסת:
הורדת הצעת החוק 11.2-11.5 שניות, מתוכן render 0.5 - **השאר הוא המודל
שכותב את דברי ההסבר** (11-14 שניות, ועם ניסוח מחדש אחרי "נימוק מומצא" -
כפול). בשאילתה: mk_gender פנה למאגר הכנסת בכל הורדה, עד 20 שניות לעמוד,
וכישלון לא נשמר - כל הורדה אחרי כישלון שילמה שוב.

הבדיקות כאן: (1) /docx עם דברי הסבר שהלקוח שלח (נכתבו ברקע) - לא קורא
למודל; (2) /explanatory - הנתיב שבו המודל כן רץ, ברקע; (3) /api/query/export
לא פונה למאגר הכנסת כלל, והמגדר מגיע מהבקשה; (4) mk_gender שומר כישלון
במטמון. בלי רשת: המודל והפיד מוחלפים בפונקציות שנכשלות אם נקראו.
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "support"))
from isolate_env import isolate  # noqa: E402

isolate()

import io  # noqa: E402
import sys  # noqa: E402
import zipfile  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "knesset"))
from fastapi.testclient import TestClient  # noqa: E402
import knesset_queries as kq  # noqa: E402
import main  # noqa: E402
from odata import OdataError  # noqa: E402

client = TestClient(main.app)
LAW = "kaytanot-1990"
ORIG = "לא ינהל אדם קייטנה אלא אם כן יש בידו רשיון לפי חוק רישוי עסקים."
REQ = {"edits": [{"node_id": f"{LAW}/s2/p0", "field": "text", "text": ORIG.replace("רשיון", "היתר")}],
       "insertions": [], "bill": {"title": "", "initiator": "", "explanatory": []}}
calls = {"llm": 0, "feed": 0}


def _llm(*a, **k):
    calls["llm"] += 1
    return ["מוצע לקבוע כי לניהול קייטנה יידרש היתר, במקום רשיון."]


def _feed(*a, **k):
    calls["feed"] += 1
    raise OdataError("הפיד של הכנסת חוסם את השרת (474).")


main.draft_explanatory_llm = _llm
kq.fetch = _feed


def _doc_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        return z.read("word/document.xml").decode("utf-8")


def test_docx_with_ready_explanatory_does_not_call_the_model():
    calls["llm"] = 0
    req = {**REQ, "bill": {**REQ["bill"], "explanatory": ["נכתב ברקע: מוצע להחליף רשיון בהיתר."]}}
    r = client.post(f"/api/laws/{LAW}/docx", json=req)
    assert r.status_code == 200, r.text[:200]
    assert calls["llm"] == 0, calls
    assert "נכתב ברקע" in _doc_text(r.content)


def test_explanatory_endpoint_is_where_the_model_runs():
    calls["llm"] = 0
    r = client.post(f"/api/laws/{LAW}/explanatory", json=REQ)
    assert r.status_code == 200, r.text[:200]
    assert r.json()["explanatory"] == ["מוצע לקבוע כי לניהול קייטנה יידרש היתר, במקום רשיון."]
    assert calls["llm"] == 1, calls


def test_explanatory_without_changes_skips_the_model():
    calls["llm"] = 0
    r = client.post(f"/api/laws/{LAW}/explanatory", json={**REQ, "edits": []})
    assert r.json()["explanatory"] == [] and calls["llm"] == 0


def test_query_export_never_touches_the_knesset_feed():
    calls["feed"] = 0
    kq._gender_cache = None
    kq._gender_failed_at = 0.0
    q = {"kind": "רגילה", "minister": "השר לביטחון לאומי", "mk_name": "עדי עזוז",
         "subject": "מצבת כוח האדם", "body": "רקע.\nרצוני לשאול:\nמה?", "gender": "נקבה"}
    r = client.post("/api/query/export", json=q)
    assert r.status_code == 200, r.text[:200]
    assert calls["feed"] == 0, calls
    assert "חברת הכנסת" in _doc_text(r.content) and "שאלה" in _doc_text(r.content)


def test_mk_gender_failure_is_cached():
    calls["feed"] = 0
    kq._gender_cache = None
    kq._gender_failed_at = 0.0
    assert kq.mk_gender("עדי עזוז") is None
    assert kq.mk_gender("עדי עזוז") is None
    assert kq.mk_gender("אחר") is None
    assert calls["feed"] == 1, calls


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_download_no_external: כל הבדיקות עברו")
