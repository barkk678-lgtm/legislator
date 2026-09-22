"""רנדר תבניות בתוך בלוק HTML גולמי, בלי לגעת בשלד.

**הכלל** (ברק, 22.9.2026): "נקה את הטקסט בתוך התאים בלי לגעת
בשלד ה-HTML."

**המלכודת שהבדיקה הזו נועלת:** הגרסה הראשונה פיצלה את הבלוק על
כל `<...>` והריצה _flatten על הקטעים שביניהן. זה קרס על שבעה
חוקים אמיתיים, כי **תבנית יכולה להימתח מעבר לתגית** - למשל
`{{מוקטן|כינוי התחום</th>` בחוק התקשורת. הפיצול חתך תבניות
באמצע, ושני החצאים נכשלו בפרסור.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))

from wikitext_parser import _render_raw_block  # noqa: E402

CASES = [
    # (תיאור, קלט, מה חייב להופיע בפלט, מה אסור שיופיע)
    ("תבנית בתוך תא - התוכן נשאר, המעטפת יורדת",
     '<table><tr><td>{{מוקטן|טור א׳}}</td></tr></table>',
     ["<table>", "<tr>", "<td>", "טור א׳"], ["{{מוקטן", "}}"]),

    ("הפניה פנימית מוחלפת בטקסט הנראה",
     '<tr><th>{{ח:פנימי|תוספת 1|בתוספת הראשונה}}</th></tr>',
     ["<th>", "בתוספת הראשונה"], ["{{ח:פנימי", "תוספת 1|"]),

    ("מאפייני התגית אינם נוגעים",
     '<table width="100%"><td colspan="4">{{מוקטן|x}}</td></table>',
     ['width="100%"', 'colspan="4"'], ["{{"]),

    ("{{ש}} בתוך טבלה הופך ל-<br>, לא לשורה חדשה",
     '<th>(1) {{ש}} מקראי המדחום</th>',
     ["<br>", "מקראי המדחום"], ["{{ש}}"]),

    # **המקרה שהפיל שבעה חוקים.**
    ("תבנית שנמתחת מעבר לתגית אינה נחתכת ואינה מפילה",
     '<tr><th>{{מוקטן|כינוי התחום</th><th>פירוש}}</th></tr>',
     ["כינוי התחום", "פירוש"], ["{{מוקטן"]),

    ("תבנית דו-לשונית עם תגית בתוכה",
     '<td>{{דוכיווני|אלפא|ALPHA-BHC<br>alpha}}</td>',
     ["אלפא", "ALPHA-BHC"], ["{{דוכיווני"]),

    ("בלוק בלי שום תגית HTML עובר רנדר מלא",
     '{{עמודות|2|{{דוכיווני|אִחוּד|consolidation}}}}',
     ["אִחוּד", "consolidation"], ["{{עמודות", "{{דוכיווני"]),

    ("תבנית שאינה נסגרת - נשארת גולמית ואינה מפילה",
     '<td>{{מוקטן|נשבר באמצע</td>',
     ["<td>", "נשבר באמצע"], []),

    ("טקסט בלי תבניות אינו משתנה",
     '<table><tr><td>נוסח רגיל</td></tr></table>',
     ["<table><tr><td>נוסח רגיל</td></tr></table>"], ["{{"]),
]


def main():
    failures = 0
    for label, src, must, must_not in CASES:
        try:
            out = _render_raw_block(src)
        except Exception as e:  # noqa: BLE001
            print(f"כשל  {label}: הפיל - {type(e).__name__}: {e}")
            failures += 1
            continue
        missing = [m for m in must if m not in out]
        leaked = [m for m in must_not if m in out]
        if missing or leaked:
            print(f"כשל  {label}")
            if missing:
                print(f"       חסר בפלט: {missing}")
            if leaked:
                print(f"       דלף לפלט: {leaked}")
            print(f"       הפלט: {out!r}")
            failures += 1
        else:
            print(f"OK   {label}")

    print("\nתוצאה:", "עבר" if not failures else f"{failures} כשלים")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
