"""בדיקות ל-apps/api/semantic_search.py (משימה א, 2026-09-16/17) -
בלי רשת/DB בכלל. לא ניתן לבדוק את הנתיב המלא (embedding אמיתי + RPC
אמיתי) בסביבה הזו - חסום כפול, ראו docs/night-report.md. מה שכן
נבדק אופליין: query ריק לא נוגע ברשת בכלל, ו-/api/semantic-search
מחזיר 503 ברור (לא קורס/תקוע) כש-SUPABASE_URL/SUPABASE_SERVICE_
ROLE_KEY חסרים - בדיוק המצב האמיתי כאן.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from semantic_search import search  # noqa: E402


def _fail_if_called(*args, **kwargs):
    raise AssertionError("אסור לקרוא ל-embed_one/embed_batch בכלל על query ריק")


def main():
    ok = True

    # --- query ריק -> [] מיידית, בלי embedding/רשת בכלל ---
    import semantic_search as mod  # noqa: PLC0415

    original_embed_one = mod.embed_one
    mod.embed_one = _fail_if_called
    try:
        result = search("")
        passed = result == []
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "query ריק -> [] בלי לגעת ב-embed_one בכלל")

        result = search("   ")
        passed = result == []
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "query רק-רווחים -> [] בלי לגעת ב-embed_one בכלל")
    finally:
        mod.embed_one = original_embed_one

    # --- בלי SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY (המצב האמיתי כאן) ---
    assert os.environ.get("SUPABASE_URL") is None, "הבדיקה מניחה שאין SUPABASE_URL בסביבה"
    from fastapi.testclient import TestClient  # noqa: E402
    from main import app  # noqa: E402

    client = TestClient(app)
    resp = client.get("/api/semantic-search", params={"q": "מה העונש על גניבה"})
    passed = resp.status_code == 503
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "/api/semantic-search בלי משתני סביבה -> 503 ברור, לא קורס ->",
          resp.status_code if not passed else "")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
