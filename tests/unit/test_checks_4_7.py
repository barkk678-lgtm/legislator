"""97 - בדיקות 4 ו-7 מול ההצעות שהוגשו בפועל.

**הכיוון שברק נתן, והוא התברר כנכון:** "בדיקה שנכשלת על 25 מתוך
40 הצעות שהוגשו בפועל ועברו את הלשכה המשפטית היא כנראה בדיקה
שגויה, לא 25 הצעות שגויות."

נמדד מול tests/fixtures/real-bills (40 הצעות מהכנסת ה-25):

| | לפני | אחרי |
|---|---|---|
| בדיקה 4 על הצעות מתקנות | 21/36 נכשלו | **0/23** |
| בדיקה 7 על הצעות מתקנות | 18/36 נכשלו | **0/23** |

ושלוש הצורות שהבדיקות לא הכירו - כולן חוקיות ונמדדו בקורפוס:
הוראה שמתקנת יחידה שאינה סעיף ("הוספת פרק ט'1"), הוראה שמתקנת
חוק שלם ("תיקון פקודת התעבורה"), וסעיפי סיום ("תחילה").
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("packages/validate", "packages/render", "packages/corpus"):
    sys.path.insert(0, str(ROOT / p))

from render_bill import Bill, Line  # noqa: E402
from validator import (  # noqa: E402
    DRAFT_CHECKS, _check_4, _check_7, _is_valid_side_heading, bill_kind, validate_draft,
)


def bill(title, headings, texts=None):
    texts = texts or ["בחוק כלשהו, בסעיף 1, במקום..."] * len(headings)
    return Bill(knesset="כ", title=title, initiator="פ",
                lines=[Line(text=t, number=f"{i+1}.", depth=0, side_heading=h)
                       for i, (h, t) in enumerate(zip(headings, texts))])


# --- כותרות שוליים שנמדדו בהצעות אמיתיות ועליהן הבדיקה נכשלה ---
def test_section_heading_still_accepted():
    assert _is_valid_side_heading("תיקון סעיף 110")


def test_whole_unit_heading_is_legitimate():
    """13948370: "הוספת פרק ט'1" - הוספת פרק שלם, לא סעיף."""
    assert _is_valid_side_heading("הוספת פרק ט'1")
    assert _is_valid_side_heading("תיקון התוספת השלישית")


def test_whole_law_heading_is_legitimate():
    """13569214, הצעת "תיקוני חקיקה": כל סעיף מתקן חוק אחר."""
    assert _is_valid_side_heading("תיקון פקודת התעבורה")
    assert _is_valid_side_heading("תיקון חוק כביש אגרה (כביש ארצי לישראל)")


def test_closing_section_heading_is_legitimate():
    """סעיף סיום אינו הוראת תיקון, ולכן הפורמט אינו חל עליו."""
    for h in ("תחילה", "הוראות מעבר", "תחולה על מקומות כליאה", "מטרה"):
        assert _is_valid_side_heading(h), h


def test_line_break_inside_a_heading_is_not_a_finding():
    """13948392: "הוספת סעיפים 2ג\\nו־2ד" - שבירת שורה משארית חילוץ.
    כשל על תו לבן ולא על תוכן הוא כשל שנראה כמו ממצא."""
    assert _is_valid_side_heading("הוספת סעיפים 2ג\nו־2ד")


# --- שם ההצעה ---
def test_all_four_measured_title_forms_pass():
    for t in ('הצעת חוק הבנקאות (תיקון – שמירה על הסדר), התשפ"ו–2026',
              'הצעת חוק X (תיקון מס\' 12), התשפ"ו–2026',
              'הצעת חוק הקמת תחנות נוחות (תיקוני חקיקה), התשפ"ו–2026',
              'הצעת חוק לתיקון פקודת בתי הסוהר (מניעת כניסה), התשפ"ו–2026'):
        assert _check_7(bill(t, ["תיקון סעיף 1"])).status == "עבר", t


def test_double_space_in_the_title_is_not_a_finding():
    """13821886: "(תיקון  – ..." עם רווח כפול, שריד הקלדה."""
    t = 'הצעת חוק הביטוח הלאומי (תיקון  – מניעת הטבות), התשפ"ו–2026'
    assert _check_7(bill(t, ["תיקון סעיף 1"])).status == "עבר"


# --- והבדיקות עדיין תופסות שגיאה אמיתית ---
def test_a_genuinely_wrong_heading_is_still_caught():
    b = bill('הצעת חוק X (תיקון – תיאור), התשפ"ו–2026', ["שינוי הסעיף החמישי"])
    assert _check_4(b).status == "נכשל"


def test_a_genuinely_wrong_title_is_still_caught():
    b = bill('הצעת חוק משהו, התשפ"ו–2026', ["תיקון סעיף 5"])
    assert _check_7(b).status == "נכשל"


def test_both_checks_now_run_on_an_amending_draft():
    b = bill('הצעת חוק X (תיקון – תיאור), התשפ"ו–2026', ["תיקון סעיף 5"])
    assert bill_kind(b)[0] == "amending"
    fs = {f.check_number: f for f in validate_draft(b)}
    assert fs[4].status == "עבר" and fs[7].status == "עבר"
    assert 4 in DRAFT_CHECKS and 7 in DRAFT_CHECKS


def test_non_numeric_section_number_reports_instead_of_crashing():
    """**קריסה אינה ממצא.** כותרת "שינוי הסעיף החמישי" הפילה את
    בדיקה 9 ב-ValueError, והמשתמש קיבל 500 במקום תשובה."""
    b = bill('הצעת חוק X (תיקון – תיאור), התשפ"ו–2026', ["שינוי הסעיף החמישי"])
    fs = {f.check_number: f for f in validate_draft(b)}
    assert fs[9].status == "לא נבדק"
    assert "אינו מספר סעיף תקני" in fs[9].message


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_checks_4_7: כל הבדיקות עברו")
