"""פרסור הוראות תיקון - הכיוון ההפוך (נוסח משולב).

**המחרוזות כאן הן מהצעות חוק אמיתיות** שנמשכו מה-OData של הכנסת,
לא מומצאות.

**מה שהבדיקה שומרת עליו:** מה שלא זוהה נרשם ב-`unparsed` ואינו
מנוחש. נוסח משולב חלקי שמוצג כמלא הוא נוסח חוק שגוי שנראה אמין -
בדיוק הכשל שחוק ברזל 2 קיים כדי למנוע.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "amend"))

from parse_instructions import parse_instructions  # noqa: E402

# הצעה 13948412 - שוויון ההזדמנויות בעבודה. מקרה הזהב הראשון.
GOLDEN = [
    ("1.", 'בחוק שוויון ההזדמנויות בעבודה, התשמ"ח–1988, בסעיף 4(א), '
           'אחרי פסקה (2) יבוא:'),
    ("", '"(3)\tהילד נמצא בטיפולו הבלעדי של העובד מחמת נכות או מחלה של '
         'בת הזוג ורופא אישר בכתב כי בשל הנכות או המחלה כאמור בת הזוג '
         'אינה מסוגלת לטפל בילד."'),
]


def main():
    ok = True

    def check(name, passed, extra=""):
        nonlocal ok
        ok &= bool(passed)
        print(("OK   " if passed else "כשל  ") + name + (f" — {extra}" if extra else ""))

    plan = parse_instructions(GOLDEN)
    check("זוהה החוק המתוקן", plan.law is not None,
          plan.law.full if plan.law else "")
    check("שם החוק נכון",
          plan.law and plan.law.name == "שוויון ההזדמנויות בעבודה")
    check("השנה העברית נתפסה ולא נבלעה בשם",
          plan.law and "1988" in plan.law.year, plan.law.year if plan.law else "")
    check("זוהתה הוראה אחת", len(plan.operations) == 1, str(len(plan.operations)))
    check("שום שורה לא נותרה בלי פירוש", plan.unparsed == [], str(plan.unparsed))
    check("התוכנית תקינה", plan.ok)

    if plan.operations:
        op = plan.operations[0]
        check("הסעיף: 4", op.section == "4", op.section)
        check("הסעיף הקטן: א", op.subsection == "א", str(op.subsection))
        check("סוג היחידה: פסקה", op.after_kind == "paragraph", op.after_kind)
        check("אחרי פסקה (2)", op.after_label == "2", op.after_label)
        check("התווית החדשה: (3)", op.new_label == "3", op.new_label)
        check("הנוסח החדש נתפס במלואו",
              op.new_text.startswith("הילד נמצא בטיפולו הבלעדי")
              and op.new_text.endswith("לטפל בילד."))
        check("המרכאות העוטפות הוסרו",
              not op.new_text.startswith('"') and not op.new_text.endswith('"'))

    # --- הצעה שמתקנת כמה חוקים: מזוהה ונדחית, לא מפורשת חלקית ---
    multi = [
        ("1.", 'בחוק שוויון ההזדמנויות בעבודה, התשמ"ח–1988, בסעיף 4(א), '
               'אחרי פסקה (2) יבוא:'),
        ("", '"(3)\tנוסח חדש."'),
        ("2.", 'בחוק דמי מחלה, התשל"ו–1976, בסעיף 2(א), אחרי פסקה (1) יבוא:'),
        ("", '"(2)\tנוסח אחר."'),
    ]
    plan2 = parse_instructions(multi)
    check("הצעה שמתקנת כמה חוקים - הזיהוי תופס", bool(plan2.extra_laws),
          str(plan2.extra_laws))
    check("הצעה כזו אינה מסומנת תקינה", not plan2.ok)
    check("ויש סיבה מפורשת למשתמש", "יותר מחוק אחד" in plan2.blocking_reason,
          plan2.blocking_reason[:60])

    # --- הוראה שאינה מוכרת: נרשמת, לא מנוחשת ---
    # **עודכן במשימה 63:** הדוגמה הקודמת כאן הייתה החלפת מילים
    # ('במקום "אלף" יבוא "אלפיים"'), שנתמכת מאז - אז הבדיקה הפסיקה
    # לבדוק את מה שנכתבה בשבילו. הוחלפה במחיקה, שבאמת אינה נתמכת
    # (ha-hoveret-ha-sgula.pdf §7.10.3). כשגם היא תיתמך - להחליף
    # שוב, לא למחוק את הבדיקה.
    unknown = [
        ("1.", 'בחוק פלוני, התש"ף–2020, בסעיף 5, המילים "בהקדם האפשרי" – יימחקו.'),
    ]
    plan3 = parse_instructions(unknown)
    check("דפוס שאינו נתמך נרשם ב-unparsed", len(plan3.unparsed) == 1,
          str(plan3.unparsed))
    check("ואינו מייצר פעולה מנוחשת", plan3.operations == [])
    check("והתוכנית אינה תקינה", not plan3.ok)

    # --- הוראה בלי הנוסח החדש: לא ממציאים תוכן ---
    truncated = [("1.", 'בחוק פלוני, התש"ף–2020, בסעיף 4(א), אחרי פסקה (2) יבוא:')]
    plan4 = parse_instructions(truncated)
    check("הוראה בלי הנוסח החדש אינה מייצרת הוספה ריקה",
          plan4.operations == [] and len(plan4.unparsed) == 1)

    # --- מספור מחדש: הנקודה אחרי המרכאות אינה חלק מהנוסח (26.9) ---
    # המנוע כותב `"(ב) ...".`, כמו ההצעות האמיתיות. עד כאן `".` נשאר בסוף
    # היחידה החדשה בנוסח המשולב.
    relabel = [
        ("1.", 'בחוק פלוני, התש"ף–2020, בסעיף 1, האמור בו יסומן "(א)" ואחריו יבוא:'),
        ("", '"(ב) עובד רשאי לזקוף.".'),
    ]
    op = parse_instructions(relabel).operations
    check("מספור מחדש: הנוסח בלי '\".' בסופו", op and op[0].new_text == "עובד רשאי לזקוף.",
          repr(op[0].new_text if op else op))
    sub = parse_instructions([
        ("1.", 'בחוק פלוני, התש"ף–2020, בסעיף 34(א), האמור בו יסומן "(1)" ואחריו יבוא:'),
        ("", '"(2) על אף האמור בפסקה (1), כך.".'),
    ]).operations
    check("ח11-ב: 'בסעיף 34(א), האמור בו יסומן \"(1)\"' - הסעיף הקטן נקרא כמכולה",
          sub and sub[0].container == "א" and sub[0].relabeled_label == "1" and sub[0].new_label == "2",
          repr(sub))

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
