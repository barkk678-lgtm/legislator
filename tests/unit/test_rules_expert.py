"""בדיקות ל-apps/api/rules_expert.py (ברק, 2026-09-17) - בלי רשת/DB.
בודקות רק את _rank_sources (retrieval מילות-מפתח, פונקציה טהורה) -
_load_sources ו-ask() דורשים DB/LLM אמיתיים, נבדקו בנפרד חי (ראו
night-report.md)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from rules_expert import SourceChunk, _rank_sources  # noqa: E402


def main():
    ok = True

    sources = [
        SourceChunk(id="a", label="חוק הכנסת, סעיף 1", text="הכנסת בוחרת יושב ראש מבין חבריה."),
        SourceChunk(id="b", label="חוק הכנסת, סעיף 2", text="ליושב הראש סגנים הנבחרים בידי הכנסת."),
        SourceChunk(id="c", label="תקנון הכנסת, סעיף 5", text="ועדת הכנסת דנה בענייני סדרי העבודה."),
    ]

    # --- שאלה עם חפיפת מילים ברורה -> הסעיפים הרלוונטיים בראש, לא כל השלושה ---
    ranked = _rank_sources("מי בוחר את יושב ראש הכנסת?", sources, top_k=2)
    passed = len(ranked) == 2 and {c.id for c in ranked} == {"a", "b"}
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "חפיפת מילים מדרגת נכון -> ", [c.id for c in ranked] if not passed else "")

    # --- שאלה בלי שום חפיפת מילים -> [] (לא מחזירה תוצאות אקראיות) ---
    ranked = _rank_sources("קסקסקס לאלאלא", sources, top_k=5)
    passed = ranked == []
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "בלי חפיפת מילים בכלל -> [] ריקה")

    # --- top_k מוגבל בפועל, לא מחזירה יותר ---
    many_matching = [SourceChunk(id=str(i), label="הכנסת", text="הכנסת דנה") for i in range(10)]
    ranked = _rank_sources("הכנסת", many_matching, top_k=3)
    passed = len(ranked) == 3
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "top_k מוגבל בפועל (3 מתוך 10 תואמים)")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
