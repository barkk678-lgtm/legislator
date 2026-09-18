"""רינדור מסמך ההסתייגויות - פריסה ומקרה ריק.

הפריסה משוחזרת ממסמך שהונח בכנסת, והמקרה הריק נלמד משני נוסחים
נוספים (2012, 2014) ששניהם ללא הסתייגויות. ראו drafting-rules.md §9.2.
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

from model import Reservation  # noqa: E402
from render_docx import EMPTY_NOTICE, _bill_reference, _proposers_line, write_docx  # noqa: E402


def _render(**kwargs):
    import docx  # noqa: PLC0415

    out = Path(tempfile.mkstemp(suffix=".docx")[1])
    write_docx(out, **kwargs)
    return [(p.style.name, p.text.strip()) for p in docx.Document(str(out)).paragraphs
            if p.text.strip()]


def main():
    ok = True

    def check(name, passed, detail=""):
        nonlocal ok
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name, detail if not passed else "")

    # שורת המציעים - בדיוק כפי שנצפתה במסמך האמיתי
    real = ("חברי הכנסת נפתלי בנט, אילת שקד, בצלאל סמוטריץ', "
            "מתן כהנא ואופיר סופר מציעים:")
    got = _proposers_line(["נפתלי בנט", "אילת שקד", "בצלאל סמוטריץ'",
                           "מתן כהנא", "אופיר סופר"])
    check("שורת המציעים זהה לנוסח האמיתי", got == real, f"התקבל: {got}")
    check("מציע יחיד", _proposers_line(["פלוני"]) == "חבר/ת הכנסת פלוני מציעים:")

    check("אין 'להצעת הצעת'",
          _bill_reference("הצעת חוק X, התש\"ף–2020") == "להצעת חוק X, התש\"ף–2020")
    check("שם בלי התחילית מקבל אותה",
          _bill_reference("חוק X") == "להצעת חוק X")

    # מקרה מלא
    res = [Reservation(anchor="31", value=v, axis="replace", section_number="1")
           for v in ("2", "3")]
    paras = _render(bill_title="הצעת חוק בדיקה", reservations=res, proposers=["פלוני"])
    styles = [s for s, _ in paras]
    check("Heading 1 -> Heading 2 -> Heading 3 -> List Paragraph",
          styles[0] == "Heading 1" and "Heading 2" in styles
          and "Heading 3" in styles and "List Paragraph" in styles, str(styles))
    check("שתי ההסתייגויות מופיעות",
          sum(1 for s, _ in paras if s == "List Paragraph") == 2)

    # **המקרה הריק** - המקטע קיים ונושא נוסח מפורש
    empty = _render(bill_title="הצעת חוק בדיקה", reservations=[], proposers=[])
    texts = [t for _, t in empty]
    check("מקטע ההסתייגויות קיים גם כשריק", "הסתייגויות" in texts)
    check(f"ונושא את הנוסח {EMPTY_NOTICE!r}", EMPTY_NOTICE in texts)
    check("אין כותרת 'לסעיף' כשאין הסתייגויות",
          not any(t.startswith("לסעיף") for t in texts))

    # סימון תקציבי
    flagged = _render(bill_title="הצעת חוק בדיקה", reservations=res,
                      proposers=["פלוני"], budget_flags={0: "דורש 50 ח\"כ"})
    check("סימון תקציבי מופיע בשורה עצמה",
          any("עלות תקציבית" in t for _, t in flagged))

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
