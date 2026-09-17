"""כלי המחקר (משימה 1.4) - ניתוב ותבניות, בלי רשת.

הבדיקות נועלות את שלוש ההחלטות שמגנות על הכלי:
1. **רפרטואר סגור** - תבנית שהומצאה נדחית, ולא מגיעה לקריאת רשת.
2. **פרמטרים מנוקים** - ערך שהומצא או בטיפוס שגוי לא עובר הלאה.
3. **הודאה בחוסר** - שאלה מחוץ לרפרטואר מחזירה answered=False עם
   רשימת מה כן אפשר, ולא תשובה שנשמעת טוב ואינה נשענת על כלום.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import research  # noqa: E402
from research import TEMPLATES, ResearchError, _coerce_params, ask  # noqa: E402


def main():
    ok = True
    checks = []

    def router(payload):
        return lambda instructions, content, max_tokens=300: payload

    # --- ניקוי פרמטרים ---
    checks.append((_coerce_params("pass_rates", {"knesset": "25"}) == {"knesset": 25},
                   "מחרוזת מספרית מומרת לשלם"))
    checks.append((_coerce_params("pass_rates", {"knesset": "עשרים וחמש"}) == {},
                   "ערך לא-מספרי בפרמטר מספרי מושמט, לא מתפוצץ"))
    checks.append((_coerce_params("pass_rates", {"מומצא": 7}) == {},
                   "פרמטר שאינו בתבנית מושמט"))
    checks.append((_coerce_params("bills_on_topic", {"topic": "דיור"}) == {"topic": "דיור"},
                   "פרמטר תקין עובר"))

    # --- תבנית מומצאת נדחית לפני כל קריאת רשת ---
    saved = research.fetch_apply
    research.fetch_apply = lambda *a, **k: (_ for _ in ()).throw(AssertionError("אסור לגעת ברשת"))
    try:
        threw = False
        try:
            ask("שאלה", draft_fn=router('{"template": "מומצא", "params": {}}'))
        except ResearchError:
            threw = True
        checks.append((threw, "תבנית שהומצאה -> ResearchError בלי לגעת ברשת"))

        # --- תשובה שאינה JSON ---
        threw = False
        try:
            ask("שאלה", draft_fn=router("בטח, הנה התשובה שלך!"))
        except ResearchError:
            threw = True
        checks.append((threw, "תשובת LLM שאינה JSON -> שגיאה ברורה, לא קריסה"))

        # --- הודאה בחוסר ---
        out = ask("מה אמרו בדיון?", draft_fn=router('{"template": null, "reason": "תוכן דיונים אינו זמין"}'))
        checks.append((out["answered"] is False, "שאלה מחוץ לרפרטואר -> answered=False"))
        checks.append((len(out["available"]) == len(TEMPLATES),
                       "מוצגות כל התבניות הזמינות, כדי שלא ינחשו"))
    finally:
        research.fetch_apply = saved

    # --- התבניות מתועדות כראוי לניתוב ---
    for t in TEMPLATES.values():
        checks.append((bool(t.question_examples), f"לתבנית {t.id} יש שאלות לדוגמה לניתוב"))

    # --- שאלה ריקה ---
    threw = False
    try:
        ask("   ", draft_fn=router("{}"))
    except ResearchError:
        threw = True
    checks.append((threw, "שאלה ריקה -> שגיאה בלי לקרוא ל-LLM"))

    for passed, label in checks:
        ok = ok and passed
        print(("OK " if passed else "FAIL"), label)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
