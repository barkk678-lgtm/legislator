"""כללי הבחירה של "שאילתות קודמות בנושא" - אופליין, בלי רשת ובלי מודל.

הכללים כאן נגזרו ממדידה על שישה נושאים אמיתיים (2026-09-22), והם
מה שמפריד בין 89% דיוק ל-96%: יחידה רחבה מדי מדרגת ולא שולפת, ותוצאה
שהתאימה ליחידה אחת בלבד נחתכת לארבעה מקומות. הבדיקה נועלת אותם כדי
שלא ייסחפו בעריכה עתידית.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "knesset"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "config"))
import knesset_queries as kq  # noqa: E402
from odata import OdataError  # noqa: E402


def row(qid, title):
    return {"query_id": qid, "title": title, "kind": "רגילה", "knesset": 25,
            "submitted_at": "2024-01-01", "person_id": 900 + qid}


def unit(words, rows, *, broad=False):
    return {"words": words, "count": len(rows), "too_broad": broad, "rows": rows}


def run(plan_units, table, *, limit=12, failing=()):
    def expand(_q):
        return {"units": [{"words": w, "kind": "phrase"} for w in plan_units], "expanded": True}

    def runner(words):
        key = " ".join(words)
        if key in failing:
            raise OdataError("HTTP 473")
        return table[key]

    kq.enrich = lambda ids, persons: {"names": {}, "docs": {}, "names_unavailable": False,
                                      "docs_unavailable": False}
    return kq.search_queries("נושא כלשהו", limit=limit, expand_fn=expand, run_fn=runner)


def test_broad_unit_ranks_but_does_not_supply_rows():
    """"דיור" מחזירה 200+ תוצאות. היא מעלה את הדירוג של שורה שכבר
    נמצאה בצירוף צר, אבל אסור לה להכניס שורות משלה - זה בדיוק הרעש
    ש"מצוקת" לבדה הייתה מייצרת."""
    out = run(
        [["מצוקת", "דיור"], ["דיור"]],
        {"מצוקת דיור": unit(["מצוקת", "דיור"], [row(1, "מצוקת הדיור בעכו")]),
         "דיור": unit(["דיור"], [row(1, "מצוקת הדיור בעכו")] +
                      [row(i, f"דיור {i}") for i in range(2, 60)], broad=True)},
    )
    titles = [r["title"] for r in out["results"]]
    assert titles == ["מצוקת הדיור בעכו"], titles
    assert out["results"][0]["matched"] == 2, out["results"][0]


def test_single_word_unit_ranks_but_does_not_supply_rows():
    """מילה בודדת מדרגת ואינה שולפת. נמדד: "פריפריה" לבדה הכניסה
    זמני המתנה לרופאים והתחסנות לשפעת - רעש טהור."""
    strong = [row(i, f"צירוף {i}") for i in range(1, 4)]
    weak = [row(i, f"מילה בודדת {i}") for i in range(10, 20)]
    out = run(
        [["מצוקת", "דיור"], ["פריפריה"]],
        {"מצוקת דיור": unit(["מצוקת", "דיור"], strong),
         "פריפריה": unit(["פריפריה"], weak)},
    )
    titles = [r["title"] for r in out["results"]]
    assert titles == ["צירוף 1", "צירוף 2", "צירוף 3"], titles


def test_phrase_sent_as_one_string_is_not_a_single_word():
    """["מצוקת הדיור"] הוא צירוף, לא מילה בודדת - אחרת החיפוש
    המילולי (וצירופי המשתמש עצמו) היו מוחזרים ריקים."""
    out = run(
        [["מצוקת הדיור"]],
        {"מצוקת הדיור": unit(["מצוקת הדיור"], [row(1, "מצוקת הדיור בעכו")])},
    )
    assert [r["title"] for r in out["results"]] == ["מצוקת הדיור בעכו"]


def test_rank1_tail_is_capped_at_four():
    """שורות שנדחו במכסה והתאימו לצירוף אחד בלבד - עד ארבע, בסוף."""
    wide = [row(i, f"רחב {i}") for i in range(1, 40)]   # 39 -> מכסה 6
    out = run(
        [["מחירי", "דירות"]],
        {"מחירי דירות": unit(["מחירי", "דירות"], wide)},
    )
    assert len(out["results"]) == 6 + kq.MAX_RANK1_ROWS, len(out["results"])


def test_broad_unit_budget_does_not_flood_the_screen():
    """**הבאג שנמדד בדפדפן:** "זיהום אוויר" (116 תוצאות) מילאה את כל
    המסך לפני ש"מפרץ חיפה" (13) חזרה. יחידה רחבה מקבלת שלוש שורות."""
    broad = [row(i, f"זיהום אוויר {i}") for i in range(1, 100)]     # 99 -> רחב, מוחזק
    narrow = [row(500 + i, f"מפרץ חיפה {i}") for i in range(1, 15)]  # 14 -> מכסה 12
    out = run(
        [["זיהום", "אוויר"], ["מפרץ", "חיפה"]],
        {"זיהום אוויר": unit(["זיהום", "אוויר"], broad),
         "מפרץ חיפה": unit(["מפרץ", "חיפה"], narrow)},
    )
    titles = [r["title"] for r in out["results"]]
    assert sum(1 for t in titles if t.startswith("זיהום")) == 0, titles
    assert sum(1 for t in titles if t.startswith("מפרץ")) == 12, titles


def test_broad_unit_shows_only_what_intersects():
    """מצירוף רחב מוצג רק מה שהצטלב עם צירוף אחר - לא התאמה בודדת."""
    shared = row(7, "זיהום אוויר במפרץ חיפה")
    broad = [shared] + [row(i, f"זיהום אוויר {i}") for i in range(10, 100)]
    out = run(
        [["זיהום", "אוויר"], ["מפרץ", "חיפה"]],
        {"זיהום אוויר": unit(["זיהום", "אוויר"], broad),
         "מפרץ חיפה": unit(["מפרץ", "חיפה"], [shared])},
    )
    titles = [r["title"] for r in out["results"]]
    assert titles == ["זיהום אוויר במפרץ חיפה"], titles


def test_single_word_row_that_matches_twice_is_not_held_back():
    """שורה שהתאימה גם לצירוף וגם למילה הבודדת אינה "דירוג 1" -
    היא לא נכנסת למכסת הארבעה."""
    shared = row(5, "אלימות בבתי הספר")
    out = run(
        [["אלימות", "ספר"], ["אלימות"]],
        {"אלימות ספר": unit(["אלימות", "ספר"], [shared]),
         "אלימות": unit(["אלימות"], [shared] + [row(i, f"אלימות {i}") for i in range(20, 30)])},
    )
    assert out["results"][0]["title"] == "אלימות בבתי הספר"
    assert out["results"][0]["matched"] == 2
    assert len(out["results"]) == 1, [r["title"] for r in out["results"]]


def test_failed_unit_is_counted_not_swallowed():
    """**מופע שביעי של הדפוס.** קריאה שנכשלה אינה "אין תוצאות":
    המשתמש חייב לדעת שמקור לא נבדק."""
    out = run(
        [["מצוקת", "דיור"], ["שיכון", "ציבורי"]],
        {"מצוקת דיור": unit(["מצוקת", "דיור"], [row(1, "מצוקת הדיור בעכו")])},
        failing={"שיכון ציבורי"},
    )
    assert out["sources_failed"] == 1, out
    assert out["sources_total"] == 2, out
    assert "לא נבדקו" in out["note"], out["note"]


def test_all_units_failing_raises_instead_of_returning_empty():
    """אם כל הקריאות נכשלו - שגיאה, לא רשימה ריקה. רשימה ריקה
    הייתה מוצגת כ"לא נמצאו שאילתות", וזה שקר."""
    try:
        run([["מצוקת", "דיור"]], {}, failing={"מצוקת דיור"})
    except OdataError:
        return
    raise AssertionError("כישלון מלא החזיר תוצאה במקום לזרוק שגיאה")


def test_expansion_failure_falls_back_to_literal_and_says_so():
    """כשל בהרחבה אינו עוצר את החיפוש - אבל גם לא מוסתר."""
    def expand(q):
        return {"units": [{"words": [q], "kind": "literal"}], "expanded": False,
                "expansion_error": "המודל אינו זמין"}

    kq.enrich = lambda ids, persons: {"names": {}, "docs": {}, "names_unavailable": False,
                                      "docs_unavailable": False}
    out = kq.search_queries(
        "מצוקת הדיור", expand_fn=expand,
        run_fn=lambda w: unit(w, [row(1, "מצוקת הדיור בעכו")]))
    assert out["expanded"] is False
    assert "ההרחבה" in out["note"], out["note"]
    assert len(out["results"]) == 1


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_query_selection: כל הבדיקות עברו")
