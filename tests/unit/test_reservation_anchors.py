"""איתור עוגנים - **עם טסטים שליליים**, לא רק חיוביים.

הכלל ב-CLAUDE.md נולד משני כשלים באותו שבוע: `[א-ת]-\\d{4}` שתפס את
`ו-2010` בצירוף "לשנים 2009 ו-2010", ו-`ה?ת[קרש]...` שתפס את המילה
"תקופה". שניהם עברו טסט חיובי בהצלחה. רשימת המחרוזות השליליות כאן
היא עיקר הקובץ.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

from anchors import find_anchors, law_citation_spans  # noqa: E402


def _texts(text: str, kind: str) -> set[str]:
    return {a.text for a in find_anchors(text) if a.kind == kind}


def main():
    ok = True

    def check(name, passed, detail=""):
        nonlocal ok
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name, detail if not passed else "")

    # ── שנה עברית: חיובי ──────────────────────────────────────────
    for text, want in [
        ('חוק הקייטנות, התש"ן–1990', 'התש"ן'),
        ('פקודת הנזיקין, התשכ"ח–1968', 'התשכ"ח'),
        ('חוק X, התרפ"ט–1929', 'התרפ"ט'),
    ]:
        check(f"שנה עברית נתפסת: {want}", want in _texts(text, "hebrew_year"))

    # ── שנה עברית: **שלילי** ──────────────────────────────────────
    # כל אלה מתחילות ב-ת ונראות כמו ראשי תיבות. אף אחת אינה שנה.
    negatives = ["תקופה", "תקנות", "תשלום", "תרופה", "תשתית", "תקרה",
                 "תשובה", "תקציב", "תרבות", "תקין", "תשואה", "תקנה"]
    for word in negatives:
        text = f"בסעיף זה, {word} תיקבע בידי השר בתוך 30 ימים."
        found = _texts(text, "hebrew_year")
        check(f'שנה עברית לא תופסת "{word}"', not found, f"נתפס: {found}")

    # ── שנה לועזית: שלילי ─────────────────────────────────────────
    check("שנה לועזית לא תופסת מספר סעיף",
          "2020" in _texts("עד יום 31 בדצמבר 2020", "gregorian_year"))
    check("שנה לועזית לא תופסת 4 ספרות שאינן שנה",
          not _texts("סכום של 3500 שקלים", "gregorian_year"),
          f"נתפס: {_texts('סכום של 3500 שקלים', 'gregorian_year')}")

    # ── מספר: שלילי - לא מתוך מילה עברית ולא מתוך מספר ארוך ───────
    check("מספר לא נתפס מתוך מספר ארוך יותר",
          "202" not in _texts("בשנת 2020", "number"))

    # ── ציטוט שם חוק ──────────────────────────────────────────────
    cited = 'בחוק חומרי נפץ (תיקון מס\' 4 – הוראת שעה), התשע"ח–2018, במקום הרישה'
    spans = law_citation_spans(cited)
    check("ציטוט שם חוק מזוהה", len(spans) == 1, f"נמצאו {len(spans)}")
    in_cit = {a.text for a in find_anchors(cited) if a.in_law_citation}
    check("מספר התיקון והשנים מסומנים כבתוך הציטוט",
          {"4", "2018", 'התשע"ח'} <= in_cit, f"סומנו: {in_cit}")

    plain = "עד יום 31 בדצמבר 2020 יחולו הוראות אלה"
    check("נוסח בלי ציטוט - אף ערך אינו מסומן",
          not any(a.in_law_citation for a in find_anchors(plain)))

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
