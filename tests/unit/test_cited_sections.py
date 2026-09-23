"""בדיקה 1 על מסמך שהועלה: מספרי הסעיפים שההצעה מתיימרת לתקן
קיימים בפועל בחוק המתוקן (ברק, 23.9.2026).

**כל השורות כאן הן ציטוט מילולי מהצעות אמיתיות** שבקורפוס
tests/fixtures/real-bills - לא נוסח שהומצא לצורך הבדיקה (CLAUDE.md:
"נתוני בדיקה נגזרים ממבנים שקיימים בקורפוס"). מספר ההצעה מופיע
בהערה ליד כל מקרה, כדי שאפשר יהיה לחזור למקור.

הבדיקה אופליין לחלוטין: מספרי סעיפי החוק נמסרים כקבוצה, בדיוק
כפי ש-validate_draft מקבלת אותם מהשכבה שמעליה.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "validate"))
sys.path.insert(0, str(ROOT / "packages" / "render"))

from cited_sections import (  # noqa: E402
    amended_law_name, main_law_citations, missing_sections)
from render_bill import Bill, Line  # noqa: E402
from validator import DRAFT_CHECKS, validate_draft  # noqa: E402


def _bill(title, rows):
    """rows: (טקסט, עומק, מספר, כותרת שוליים)"""
    return Bill(
        knesset=25, title=title, initiator="", bill_number="פ/1/25",
        submitted_date="", explanatory=[],
        lines=[Line(text=t, depth=d, number=n, side_heading=h)
               for t, d, n, h in rows],
    )


# ── שם החוק המתוקן ──────────────────────────────────────────────────

def test_law_name_with_year():
    # 13695213
    assert amended_law_name(
        'בחוק התכנון והבנייה, התשכ"ה–1965, בסעיף 110 –'
    ) == 'חוק התכנון והבנייה, התשכ"ה–1965'


def test_law_name_stops_before_lehalan():
    # 13821853
    assert amended_law_name(
        'בחוק הצבת מכשירי החייאה במקומות ציבוריים, התשס"ח–2008 (להלן – '
        'החוק העיקרי), בסעיף 1, לפני ההגדרה "מכשיר החייאה" יבוא:'
    ) == 'חוק הצבת מכשירי החייאה במקומות ציבוריים, התשס"ח–2008'


def test_law_name_without_a_year():
    # 13569214
    assert amended_law_name("בפקודת התעבורה –") == "פקודת התעבורה"


def test_law_name_is_not_cut_at_a_word_that_is_part_of_it():
    """"במקום" היא מילת הוראה **וגם** מילה בשם החוק. בלי דרישת
    הפסיק לפניה, השם נחתך ל"חוק הגבלת שימוש" (13948408)."""
    assert amended_law_name(
        'בחוק הגבלת שימוש במקום לשם מניעת ביצוע עבירות, התשס"ה–2005, '
        'בסעיף 3א(ב), המילים "וכן את התקדמות החקירה" יימחקו'
    ) == 'חוק הגבלת שימוש במקום לשם מניעת ביצוע עבירות, התשס"ה–2005'


def test_a_line_that_is_not_an_amending_instruction_has_no_law_name():
    assert amended_law_name("תחילתו של חוק זה שלושה חודשים מיום פרסומו.") == ""


# ── אילו אזכורים נאספים ──────────────────────────────────────────────

def test_collects_the_target_of_the_instruction():
    # 13695213
    name, cited = main_law_citations(_bill(
        'הצעת חוק התכנון והבנייה (תיקון), התשפ"ו–2026',
        [('בחוק התכנון והבנייה, התשכ"ה–1965, בסעיף 110 –', 0, "1.", "תיקון סעיף 110")],
    ))
    assert name == 'חוק התכנון והבנייה, התשכ"ה–1965'
    assert cited == ["110"]


def test_added_section_is_not_treated_as_an_existing_one():
    """"הוספת סעיף 9א2" נוקבת בסעיף שההצעה **יוצרת**. לפני התיקון
    הזה 13695183 דווחה ככשל על סעיף שלא אמור להתקיים."""
    name, cited = main_law_citations(_bill(
        'הצעת חוק הבנקאות (שירות ללקוח) (תיקון), התשפ"ו–2026',
        [('בחוק הבנקאות (שירות ללקוח), התשמ"א–1981, אחרי סעיף 9א1 יבוא:',
          0, "1.", "הוספת סעיף 9א2")],
    ))
    assert name == 'חוק הבנקאות (שירות ללקוח), התשמ"א–1981'
    assert cited == ["9א1"]


def test_reference_to_another_law_is_not_collected():
    """13821853 מפנה בתוך ההגדרה המוצעת ל"סעיף 158טו1 לחוק התכנון
    והבנייה" - סעיף של חוק אחר, שישה כשלי שווא לפני התיקון."""
    _, cited = main_law_citations(_bill(
        "הצעת חוק הצבת מכשירי החייאה (תיקון), התשפ\"ו–2026",
        [('בחוק הצבת מכשירי החייאה במקומות ציבוריים, התשס"ח–2008, בסעיף 1, '
          'לפני ההגדרה "מכשיר החייאה" יבוא:', 0, "1.", "תיקון סעיף 1"),
         ("בניין רב־קומות כהגדרתו בסעיף 158טו1 לחוק התכנון והבנייה;", 1, "", "")],
    ))
    assert cited == ["1"]


def test_cross_reference_inside_the_proposed_text_is_not_collected():
    """"כאמור בסעיף 95ד" בתוך הפרק המוצע (13948370) מפנה לסעיף
    שההצעה עצמה יוצרת - הפניה-אגב, לא יעד של הוראה."""
    _, cited = main_law_citations(_bill(
        'הצעת חוק הבחירות לכנסת (תיקון), התשפ"ו–2026',
        [('בחוק הבחירות לכנסת [נוסח משולב], התשכ"ט–1969 (להלן – החוק '
          'העיקרי), בסעיף 7, אחרי "פרקים ט\'," יבוא "ט\'1,".', 0, "1.", "תיקון סעיף 7"),
         ("רשימה של עובדיו שהם בוחרים הזכאים להצביע כאמור בסעיף 95ד, ורשאי "
          "הוא לכלול בה גם", 0, "", "")],
    ))
    assert cited == ["7"]


def test_an_indirect_amendment_is_attributed_to_its_own_law():
    """13569214 מתקנת שלושה חוקים. סעיפי החוקים הנוספים אינם
    נאספים - אחרת הם היו מדווחים כחסרים מהחוק הראשי."""
    name, cited = main_law_citations(_bill(
        'הצעת חוק לתיקון פקודת התעבורה, התשפ"ו–2026',
        [("בפקודת התעבורה, בסעיף 70 –", 0, "1.", "תיקון פקודת התעבורה"),
         ('בחוק כביש אגרה (כביש ארצי לישראל), התשנ"ה–1995, בסעיף 12 –',
          0, "2.", "תיקון חוק כביש אגרה")],
    ))
    assert name == "פקודת התעבורה"
    assert cited == ["70"]


def test_a_tail_section_does_not_reference_the_amended_law():
    """"תחילתו של סעיף 1" בסעיף התחילה מפנה לסעיף 1 של **ההצעה**."""
    _, cited = main_law_citations(_bill(
        'הצעת חוק הגנת הצרכן (תיקון), התשפ"ו–2026',
        [('בחוק הגנת הצרכן, התשמ"א–1981, סעיף 39 – בטל.', 0, "1.", "ביטול סעיף 39"),
         ("תחילתו של סעיף 1 ביום פרסומו.", 0, "2.", "תחילה")],
    ))
    assert cited == ["39"]


def test_missing_sections_is_a_plain_set_difference():
    assert missing_sections(["110", "999"], {"110", "111"}) == ["999"]


# ── הבדיקה עצמה בתוך validate_draft ─────────────────────────────────

_AMENDING = _bill(
    'הצעת חוק התכנון והבנייה (תיקון – היתר בנייה), התשפ"ו–2026',
    [('בחוק התכנון והבנייה, התשכ"ה–1965, בסעיף 110 –', 0, "1.", "תיקון סעיף 110")],
)


def _check(bill, number, **kw):
    return next(f for f in validate_draft(bill, **kw) if f.check_number == number)


def test_check_1_passes_when_the_section_exists():
    f = _check(_AMENDING, 1, law_sections={"110", "111"})
    assert f.status == "עבר" and "110" in f.message


def test_check_1_fails_when_the_section_does_not_exist():
    """בקרה שלילית - בלי זה אי אפשר לדעת שהבדיקה בכלל רצה."""
    f = _check(_AMENDING, 1, law_sections={"111"})
    assert f.status == "נכשל" and "110" in f.message


def test_check_1_is_not_checked_when_the_law_was_not_found():
    """**לעולם לא "עבר" כשאין מול מה לבדוק.**"""
    f = _check(_AMENDING, 1, law_note="החוק אינו במאגר")
    assert f.status == "לא נבדק" and f.message == "החוק אינו במאגר"


def test_check_1_is_not_checked_for_a_new_law_bill():
    new = _bill('הצעת חוק חינוך פיננסי, התשפ"ו–2026',
                [("מטרתו של חוק זה לקדם חינוך פיננסי.", 0, "1.", "מטרה")])
    f = _check(new, 1, law_sections={"1"})
    assert f.status == "לא נבדק" and "חוק חדש" in f.message


def test_checks_1_and_12_are_part_of_the_draft_checks():
    assert 1 in DRAFT_CHECKS and 12 in DRAFT_CHECKS


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_cited_sections: כל הבדיקות עברו")
