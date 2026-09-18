"""ביקורת ניסוח (משימה 2.2) - בלי רשת.

הדבר היחיד שחשוב לאבטח כאן: **המודל לא יכול לשנות את הממצאים.** הוא
לא יכול להוסיף ליקוי, לא להעלים ליקוי, ולא להפוך כשל ל"עבר". הטסטים
למטה תוקפים בדיוק את שלושת המסלולים האלה, וכן את המסלול שבו ההסבר
נכשל לגמרי - שבו הממצאים חייבים לשרוד במלואם.

מקרי הקלט הם הצעות חוק אמיתיות מ-tests/fixtures/real-bills, לא
מסמכים מומצאים.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "documents"))

from critique import (  # noqa: E402
    _explanation_is_anchored,
    _parse_explanations,
    _referenced_lines,
    critique_bill,
)
from extract_docx import extract_bill  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "real-bills"
# 13948414: "(להלן– החוק עיקרי)" - כינוי בניסוח לא תקני, ליקוי אמיתי
# בהצעה שהונחה בכנסת (בדיקה 3).
BILL_WITH_FINDING = FIX / "13948414.docx"
# 13821878: עוברת את כל חמש הבדיקות שרצות על מסמך חיצוני.
BILL_CLEAN = FIX / "13821878.docx"


def main():
    ok = True

    def check(name, passed):
        nonlocal ok
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name)

    dirty = extract_bill(BILL_WITH_FINDING)
    clean = extract_bill(BILL_CLEAN)

    # 1. הצעה נקייה: אין ממצאים - ו**אין קריאה למודל בכלל**.
    calls = []

    def counting_draft(**kw):
        calls.append(kw)
        return "[]"

    result = critique_bill(clean, draft_fn=counting_draft)
    check("הצעה בלי ליקויים -> אין ממצאים", not result.items)
    check("הצעה בלי ליקויים -> אפס קריאות ל-LLM", not calls)
    check("הבדיקות שעברו מדווחות", len(result.passed) == 5)

    # 2. הצעה עם ליקוי אמיתי: הממצא נמצא בקוד, לפני כל מודל.
    result = critique_bill(dirty, draft_fn=lambda **kw: "[]")
    check("ליקוי אמיתי נמצא (בדיקה 3)", [i.check_number for i in result.items] == [3])
    check("הניסוח הדטרמיניסטי נשמר", "החוק עיקרי" in result.items[0].message)
    check("בלי הסבר -> explained=False", result.explained is False)

    # 3. המודל לא יכול להוסיף ממצא שלא נמצא בקוד.
    def inventing_draft(**kw):
        return json.dumps(
            [
                {"check": 3, "what": "כינוי לא תקני", "why": "ב", "fix": "ג"},
                {"check": 5, "what": "ליקוי שהמודל המציא", "why": "ב", "fix": "ג"},
            ],
            ensure_ascii=False,
        )

    result = critique_bill(dirty, draft_fn=inventing_draft)
    check("המודל לא מוסיף ממצא", [i.check_number for i in result.items] == [3])
    check("ההסבר של הממצא האמיתי נקלט", result.items[0].what == "כינוי לא תקני")
    check("explained=True כשיש הסבר", result.explained is True)

    # 4. המודל לא יכול להעלים ממצא: אם לא החזיר עליו הסבר, הממצא
    #    עדיין ברשימה עם הניסוח הדטרמיניסטי.
    result = critique_bill(dirty, draft_fn=lambda **kw: '[{"check": 99, "what": "x"}]')
    check("המודל לא מעלים ממצא", len(result.items) == 1 and result.items[0].check_number == 3)
    check("ממצא בלי הסבר -> what ריק אבל message קיים",
          result.items[0].what == "" and result.items[0].message)

    # 5. ההסבר קורס לגמרי -> הממצאים שורדים.
    def broken_draft(**kw):
        raise RuntimeError("המודל לא זמין")

    result = critique_bill(dirty, draft_fn=broken_draft)
    check("קריסת ההסבר לא מעלימה ממצא", len(result.items) == 1)
    check("סיבת הכישלון מדווחת", "RuntimeError" in result.explain_error)

    # 6. **שומר העוגן**: הסבר שמצביע על שורה שאינה בממצא נזרק.
    #    נמצא בביקורת 2026-09-18: המודל ניסח הסבר משכנע לממצא שלא
    #    הצליח לאתר. ההנחיה אומרת לו עכשיו לכתוב "לא הצלחתי לאתר",
    #    אבל הנחיה אינה אכיפה - זה החלק שנאכף בקוד.
    check("מספרי שורות נחלצים מטקסט", _referenced_lines("בשורות 2 ו-3 ובשורה 42") == {2, 3, 42})

    class _F:
        message = "נמצא ״ בשורות: [2, 3]"

    check("הסבר שמצביע על שורה שבממצא - עובר",
          _explanation_is_anchored({"what": "בשורה 2 יש גרש"}, _F()))
    check("הסבר שמצביע על שורה שאינה בממצא - נדחה",
          not _explanation_is_anchored({"what": "בשורה 99 יש גרש"}, _F()))
    check("הסבר בלי הצבעה על שורה - עובר (אין מה לאמת)",
          _explanation_is_anchored({"what": "יש גרש עברי"}, _F()))

    result = critique_bill(dirty, draft_fn=lambda **kw: json.dumps(
        [{"check": 3, "what": "בשורה 77 יש בעיה", "why": "ב", "fix": "ג"}], ensure_ascii=False))
    check("הסבר לא-מעוגן נזרק, הממצא נשאר",
          result.items[0].what == "" and result.items[0].message
          and result.dropped_explanations == [3])

    # 7. JSON עטוף ב-```json``` (התנהגות נפוצה של מודלים) נקרא נכון.
    parsed = _parse_explanations('```json\n[{"check": 3, "what": "א"}]\n```', [3])
    check("JSON בתוך גדר קוד נקרא", parsed.get(3, {}).get("what") == "א")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
