"""בדיקות ל-apps/api/admin_ingest.py (ברק, 2026-09-17) - בלי רשת/DB.
בודקות רק את שכבת האבטחה (_require_secret) - שאר הלוגיקה (rate
limit/עיבוד chunks בפועל) דורשת DB+OpenAI אמיתיים, נבדקה בנפרד חי
(ראו night-report.md).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import admin_ingest  # noqa: E402
from admin_ingest import IngestAuthError, _require_secret  # noqa: E402


def main():
    ok = True

    # --- INGEST_SECRET לא מוגדר בסביבה (המצב האמיתי כאן) -> נכשלת תמיד, גם עם טוקן ---
    assert os.environ.get("INGEST_SECRET") is None, "הבדיקה מניחה שאין INGEST_SECRET בסביבה"
    threw = False
    try:
        _require_secret("כל טוקן")
    except IngestAuthError:
        threw = True
    ok = ok and threw
    print(("OK " if threw else "FAIL"), "בלי INGEST_SECRET בסביבה -> תמיד IngestAuthError, לא endpoint פתוח בטעות")

    # --- INGEST_SECRET מוגדר, טוקן נכון -> עובר ---
    admin_ingest.os.environ["INGEST_SECRET"] = "סוד-לבדיקה"
    try:
        threw = False
        try:
            _require_secret("סוד-לבדיקה")
        except IngestAuthError:
            threw = True
        passed = not threw
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "טוקן נכון -> עובר בלי שגיאה")

        # --- טוקן שגוי -> נכשל ---
        threw = False
        try:
            _require_secret("טוקן-שגוי")
        except IngestAuthError:
            threw = True
        ok = ok and threw
        print(("OK " if threw else "FAIL"), "טוקן שגוי -> IngestAuthError")

        # --- בלי טוקן בכלל (None) -> נכשל ---
        threw = False
        try:
            _require_secret(None)
        except IngestAuthError:
            threw = True
        ok = ok and threw
        print(("OK " if threw else "FAIL"), "בלי טוקן בכלל -> IngestAuthError")
    finally:
        del admin_ingest.os.environ["INGEST_SECRET"]

    # --- ה-endpoint עצמו: בלי header, בלי INGEST_SECRET -> 401 ברור, לא קורס ---
    from fastapi.testclient import TestClient  # noqa: E402
    from main import app  # noqa: E402

    client = TestClient(app)
    resp = client.post("/api/admin/ingest-chunks")
    passed = resp.status_code == 401
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "POST /api/admin/ingest-chunks בלי טוקן -> 401 ->", resp.status_code if not passed else "")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
