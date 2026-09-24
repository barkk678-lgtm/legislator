"""עשן: כל endpoint נקרא בפועל ואסור לו להחזיר 500.

**למה זה קיים, ולמה davka כך** (2026-09-19): `/api/reservations/analyze`
החזיר 500 על כל קובץ במשך יום שלם. ה-endpoint קרא `result["total"]`
אחרי ש-`measure()` הפסיקה להחזיר את המפתח הזה. שום בדיקה לא תפסה.

ניסיתי קודם בודק **סטטי** שמשווה שדות שהלקוח קורא מול שדות
שה-endpoint מחזיר. הרצתי אותו על הקוד שלפני התיקון כדי לוודא שהוא
תופס את הבאג הידוע - **והוא לא תפס**. הסיבה: המחרוזת `"total":`
כן מופיעה בגוף ה-endpoint (זה בדיוק השורה השבורה), ולכן התאמת
מפתחות סטטית עיוורת לה. בודק שלא מצליח למצוא את הבאג שכבר ידוע לי
שקיים - ה"אפס ממצאים" שלו חסר ערך.

לכן: קוראים ל-endpoint באמת. 500 = חריגה לא מטופלת. 4xx זה בסדר
גמור (קלט חסר, אין תצורה) - זה מה שהבדיקה **לא** בודקת.

הבדיקה מבודדת ממפתחות (tests/support/isolate_env.py), ולכן כל
נתיב שנוגע ב-DB או במודל אמור להיכשל ב-4xx/503 ולא ב-500.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "support"))
from isolate_env import isolate  # noqa: E402

isolate()

sys.path.insert(0, str(ROOT / "apps" / "api"))
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

DOCX = ROOT / "tests" / "fixtures" / "reservations" / "573919.docx"
_DOCX_TYPE = ("application/vnd.openxmlformats-officedocument."
              "wordprocessingml.document")


def _file():
    return {"file": ("bill.docx", DOCX.read_bytes(), _DOCX_TYPE)}


# (שיטה, נתיב, kwargs). law_id = fixture אמיתי שקיים בלי DB.
CASES = [
    ("GET", "/", {}),
    ("GET", "/api/laws", {}),
    ("GET", "/api/laws/search", {"params": {"q": "קייטנות"}}),
    ("GET", "/api/laws/search", {"params": {"q": ""}}),
    ("GET", "/api/laws/kaytanot-1990", {}),
    ("GET", "/api/laws/kaytanot-1990/citations", {}),
    ("GET", "/api/laws/lo-kayam-bכלל", {}),
    ("GET", "/api/admin/knesset-files-check", {}),
    ("GET", "/api/bills/similar", {"params": {"q": "חינוך"}}),
    ("GET", "/api/queries/search", {"params": {"q": "חינוך"}}),
    ("POST", "/api/reservations/analyze", {"files": _file()}),
    ("POST", "/api/reservations/quality", {"files": _file(),
                                           "data": {"sections_limit": "1"}}),
    ("POST", "/api/reservations/generate", {"files": _file()}),
    ("POST", "/api/documents/summarize", {"files": _file()}),
    ("POST", "/api/documents/critique", {"files": _file()}),
    ("POST", "/api/rules/ask", {"json": {"question": "מהי הסתייגות?"}}),
    ("POST", "/api/query/draft", {"json": {"question": "מה מצב הכבישים?"}}),
    ("POST", "/api/agenda/draft", {"json": {"topic": "בטיחות בדרכים"}}),
]


def main() -> int:
    api = TestClient(app, raise_server_exceptions=False)
    checks: list[tuple[str, bool]] = []
    for method, path, kwargs in CASES:
        try:
            resp = api.request(method, path, **kwargs)
            code = resp.status_code
        except Exception as e:  # noqa: BLE001
            checks.append((f"{method} {path} -> חריגה {type(e).__name__}", False))
            continue
        ok = code != 500
        detail = ""
        if not ok:
            detail = f" :: {resp.text[:160]}"
        checks.append((f"{method} {path} -> {code}{detail}", ok))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
