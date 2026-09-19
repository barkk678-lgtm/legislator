"""סעיף שאינו נושא מספר במסמך אינו נזרק בשקט.

**הדפוס שזה מתקן, ולמה הוא המסוכן ביותר** (2026-09-19): בהצעות
אמיתיות מהכנסת, **סעיף 1 הוא לעתים היחיד שממוספר אוטומטית
ב-Word** (`w:numPr`) - Word מצייר "1." בתצוגה, ובקובץ אין לזה
טקסט. הגרסה הקודמת של `_reservation_sections` פתחה סעיף רק
כשהיה `line.number`, ולכן כל מה שקדם לסעיף הממוספר הראשון נעלם.

והסעיף שנעלם הוא בדיוק זה שמגדיר "(להלן - החוק העיקרי)", שכל
שאר הסעיפים מפנים אליו. ב-`13948363` נתפס סעיף אחד מתוך שניים -
**חצי מההצעה** - ו-`warnings` היה ריק.

שני מסלולים, ושניהם רועשים:
1. אפשר להסיק את המספר (הראשון שזוהה הוא N>1) -> משחזרים כ-N-1
   **עם אזהרה**.
2. אי אפשר -> אזהרה מפורטת שאומרת כמה שורות אינן משויכות ומה הן.
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

FIX = ROOT / "tests" / "fixtures" / "real-bills"
_TYPE = ("application/vnd.openxmlformats-officedocument."
         "wordprocessingml.document")


def _analyze(api, stem):
    return api.post("/api/reservations/analyze",
                    files={"file": ("b.docx", (FIX / f"{stem}.docx").read_bytes(),
                                    _TYPE)}).json()


def main() -> int:
    api = TestClient(app)
    checks: list[tuple[str, bool]] = []

    # 13948363: 2 סעיפים בהצעה. לפני התיקון נתפס 1.
    d = _analyze(api, "13948363")
    recovered = [w for w in d["warnings"] if w.startswith("סעיף 1")]
    checks.append(("13948363: שני הסעיפים נתפסים (היה 1)", d["sections_found"] == 2))
    checks.append(("13948363: השחזור מדווח באזהרה ולא בשקט", len(recovered) == 1))
    checks.append(("13948363: האזהרה אומרת לוודא", "ודאו" in recovered[0]))

    # 13948394: 5 סעיפים. לפני התיקון נתפסו 4.
    d = _analyze(api, "13948394")
    checks.append(("13948394: חמישה סעיפים (היו 4)", d["sections_found"] == 5))
    checks.append(("13948394: אזהרת שחזור קיימת",
                   any(w.startswith("סעיף 1") for w in d["warnings"])))

    # הצעה תקינה שמתחילה בסעיף 1 מוקלד - אין שחזור ואין המצאה
    d = _analyze(api, "13948365")
    checks.append(("הצעה עם מספור מוקלד: בלי אזהרת שחזור",
                   not any(w.startswith("סעיף ") and "שוחזר" in w
                           for w in d["warnings"])))

    # טקסט לפני סעיף 1 שאי אפשר להסיק ממנו מספר -> אזהרה, לא השמטה
    d = _analyze(api, "13569200")
    loud = [w for w in d["warnings"] if w.startswith("נמצא טקסט")]
    checks.append(("טקסט שלא ניתן לשייך -> אזהרה רועשת", len(loud) == 1))
    checks.append(("האזהרה מצטטת את הטקסט עצמו", "פרק א" in loud[0]))
    checks.append(("41 הסעיפים לא נפגעו", d["sections_found"] == 41))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
