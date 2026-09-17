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

    # --- ההבחנה בין "לא נמצא" ל"לא מאונדקס" (ברק, 2026-09-17) ---
    # מזריקים את שלוש התלויות של ה-endpoint (חיפוש סמנטי, רשימת
    # המאונדקסים, חיפוש-שמות) כדי לבדוק את לוגיקת ההרכבה עצמה בלי
    # DB/רשת - זה כל מה שמבדיל בין שתי ההודעות בממשק.
    import main as main_mod  # noqa: PLC0415

    saved = (main_mod.semantic_search, main_mod.indexed_law_ids, main_mod.search_law_titles, main_mod.law_summaries)
    try:
        main_mod.semantic_search = lambda q, limit=10: []          # אין תוצאות סמנטיות
        main_mod.indexed_law_ids = lambda: {"law-2000479": 120}    # רק העונשין מאונדקס
        main_mod.search_law_titles = lambda q, limit=20: [
            {"id": "law-2000613", "title": "חוק התכנון והבניה", "amendable": True},
            {"id": "law-2000479", "title": "חוק העונשין", "amendable": True},
        ]
        main_mod.law_summaries = lambda: [{"id": f"law-{i}"} for i in range(1094)]

        body = client.get("/api/semantic-search", params={"q": "היתר בנייה"}).json()
        cov = body["coverage"]

        cases = [
            (body["results"] == [], "אין תוצאות סמנטיות -> results ריק"),
            (cov["indexed_laws"] == 1 and cov["total_laws"] == 1094, "הכיסוי מדווח (1 מתוך 1094)"),
            ([m["id"] for m in cov["unindexed_name_matches"]] == ["law-2000613"],
             "חוק ששמו תואם אבל לא מאונדקס -> מסומן כמגבלת כיסוי"),
            (all(m["id"] != "law-2000479" for m in cov["unindexed_name_matches"]),
             "חוק שכן מאונדקס לא מסומן כלא-מאונדקס"),
        ]
        for passed, label in cases:
            ok = ok and passed
            print(("OK " if passed else "FAIL"), label)

        # "לא נמצא" אמיתי: שום שם לא תואם -> אין מה להאשים בכיסוי
        main_mod.search_law_titles = lambda q, limit=20: []
        cov2 = client.get("/api/semantic-search", params={"q": "משהו שלא קיים"}).json()["coverage"]
        passed = cov2["unindexed_name_matches"] == []
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "אין התאמת-שם בכלל -> 'לא נמצא' אמיתי, בלי אזהרת כיסוי")
    finally:
        (main_mod.semantic_search, main_mod.indexed_law_ids, main_mod.search_law_titles, main_mod.law_summaries) = saved

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
