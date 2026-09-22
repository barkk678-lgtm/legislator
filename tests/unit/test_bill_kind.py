"""א6 - זיהוי הצעה מתקנת מול הצעה לחוק חדש, ושער הבדיקות 4 ו-7.

**למה בכלל:** שתי הבדיקות האלה נכשלות תמיד על הצעה לחוק חדש - לא
בגלל פגם בהצעה אלא כי הן שואלות שאלה לא רלוונטית. מתוך 40 ההצעות
האמיתיות שנבדקו, 18 היו חוקים חדשים, וכל אחת מהן קיבלה שתי שגיאות
שווא.

הכותרות כאן **נלקחו מהפיד של הכנסת** (KNS_Bill, כנסת 25) ולא
הומצאו - ראו CLAUDE.md, "נתוני בדיקה נגזרים ממבנה שקיים בקורפוס".
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "validate"))
sys.path.insert(0, str(ROOT / "packages" / "render"))

from bill_kind import classify, kind_from_body, kind_from_title  # noqa: E402
from render_bill import Bill, Line  # noqa: E402
from validator import CHECKS, bill_kind, validate_draft  # noqa: E402

AMEND_TITLES = [
    'הצעת חוק חינוך ממלכתי (תיקון - העסקת עובדי הוראה בחוזה אישי), התשפ"ג-2022',
    'הצעת חוק לימוד חובה (תיקון - מנהל מוסד חינוך), התשפ"ג-2022',
    'הצעת חוק לתיקון פקודת בריאות העם (הזכות לשימור פוריות), התשפ"ג-2022',
    'הצעת חוק לתיקון פקודת מס הכנסה (ניכוי תשלומים לביטוח בריאות לעצמאים), התשפ"ג-2022',
]
NEW_TITLES = [
    'הצעת חוק חינוך פיננסי, התשפ"ג-2022',
    'הצעת חוק סייעות במוסדות חינוך, התשפ"ג-2022',
    'הצעת חוק שוברים להשלמת לימודי בסיס בחינוך הבלתי פורמלי, התשפ"ג–2022',
]


def test_title_catches_the_paren_form():
    for t in AMEND_TITLES[:2]:
        assert kind_from_title(t) == "amending", t


def test_title_catches_the_letikun_form():
    """**הצורה שהמבחין הראשון שלי פספס לגמרי.** "הצעת חוק לתיקון
    פקודת X (תיאור)" - התיקון לפני הסוגריים. 62 הצעות בכנסת ה-25
    סווגו בטעות כחוק חדש עד שהצורה הזו נוספה."""
    for t in AMEND_TITLES[2:]:
        assert kind_from_title(t) == "amending", t


def test_plain_title_is_new():
    for t in NEW_TITLES:
        assert kind_from_title(t) == "new", t


def test_body_decides_when_the_title_is_silent():
    """משפחת "הרשויות המקומיות (גמול השתתפות בישיבות)" - שם של חוק
    קיים עם סוגריים מתארים, בלי המילה תיקון. מהכותרת אי אפשר לדעת;
    מהגוף אפשר."""
    title = 'הצעת חוק הרשויות המקומיות (גמול השתתפות בישיבות), התשפ"ג-2022'
    assert kind_from_title(title) == "new"
    kind, why = classify(title, ["בחוק הרשויות המקומיות, בסעיף 12, במקום..."])
    assert kind == "amending", why
    assert "נפתחים בהפניה" in why


def test_disagreement_is_unknown_not_a_guess():
    """כותרת אומרת תיקון, הגוף לא - לא מנחשים."""
    kind, why = classify('הצעת חוק X (תיקון - תיאור), התשפ"ג-2022',
                         ["מטרתו של חוק זה לקבוע הסדר חדש."])
    assert kind == "unknown", why
    assert "לא ניתן לקבוע" in why


def test_body_without_sections_is_unknown():
    assert kind_from_body([]) == "unknown"


def _bill(title, openings):
    return Bill(knesset="הכנסת העשרים וחמש", title=title, initiator="פלוני",
                lines=[Line(text=t, depth=0, number=f"{i+1}.")
                       for i, t in enumerate(openings)])


def test_new_law_does_not_get_two_false_failures():
    """**הלב של א6.** בדיקות 4 ו-7 מדווחות "לא נבדק" עם סיבה, ולא
    "נכשל" - הצעה תקינה לחוק חדש לא תיראה פגומה."""
    findings = {f.check_number: f for f in validate_draft(
        _bill('הצעת חוק חינוך פיננסי, התשפ"ג-2022',
              ["מטרתו של חוק זה להנחיל אוריינות פיננסית.",
               "שר החינוך ממונה על ביצוע חוק זה."]))}
    for n in (4, 7):
        assert findings[n].status == "לא נבדק", (n, findings[n])
        assert "חוק חדש" in findings[n].message, findings[n].message


def test_amending_bill_is_not_skipped_for_being_a_new_law():
    """**מה א6 כן עושה ומה לא.** על הצעה מתקנת, 4 ו-7 אינן מדולגות
    בגלל סוג ההצעה. הן עדיין מדולגות מסיבה אחרת - שתיהן ידועות
    כשגויות גם על הצעות מתקנות (4 נכשלה על 25 מתוך 40 ו-7 על 22
    מתוך 40, בעוד שרק 18 מתוך 40 היו חוקים חדשים - כלומר לפחות
    7 ו-4 כשלים בהתאמה היו על הצעות מתקנות אמיתיות). תיקון
    הבדיקות עצמן הוא משימה נפרדת."""
    findings = validate_draft(
        _bill('הצעת חוק לימוד חובה (תיקון - מנהל מוסד חינוך), התשפ"ג-2022',
              ["בחוק לימוד חובה, התש\"ט–1949, בסעיף 1, אחרי ההגדרה..."]))
    assert len(findings) == len(CHECKS)
    by_n = {f.check_number: f for f in findings}
    for n in (4, 7):
        assert "לא רלוונטית להצעת חוק חדש" not in by_n[n].message
        assert "לא ניתן היה לקבוע" not in by_n[n].message


def test_every_check_still_appears_exactly_once():
    """אף בדיקה לא נעלמת - הכלל שהוולידטור נבנה עליו."""
    findings = validate_draft(_bill('הצעת חוק כלשהו, התשפ"ג-2022', ["טקסט."]))
    assert sorted(f.check_number for f in findings) == sorted(CHECKS)


def test_bill_kind_is_reported_with_a_human_reason():
    kind, why = bill_kind(_bill('הצעת חוק חינוך פיננסי, התשפ"ג-2022', ["מטרתו של חוק זה..."]))
    assert kind == "new"
    assert why and "חוק חדש" in why


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_bill_kind: כל הבדיקות עברו")
