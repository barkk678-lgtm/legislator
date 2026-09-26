"""אישורי הבנק §5 (חובה ורשות) ו-§6 (תוספת לפועל), ברק 26.9.2026.

§5: 14 הפעלים החדשים וצמד "חייב"; **מין ומספר מאותה טבלה סגורה** (תתקן <-> רשאית
לתקן, יתקנו <-> רשאים לתקן); **שלילה** - "אינו רשאי לתקן" לעולם לא "אינו יתקן";
**"יביא בחשבון"** - לא מופעל. לכל אחד - טסט שלילי.
§6: `במקום "{פועל}" יבוא "{פועל} {תוספת}"` - התוספת מיד אחרי הפועל, באותם שומרים;
בממשק "תוספת לפועל", ונכללת במקסימום וב"לפחות X ייספרו בנפרד".
נכשל על הקוד הקודם (אין צורות נקבה/רבים, אין שומר שלילה, אין תוספת לפועל).
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("LEGISLATOR_MINISTERS_SOURCE", "fallback")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402
import families  # noqa: E402
from pdf_bill import BillSection, BillUnit, ParsedBill  # noqa: E402

RECORDS = bank.load_all()
VERDICTS = {r.id: {"key": r.screen_key, "allowed": True} for r in RECORDS}

SENTENCES = [
    "שר הכלכלה יבטל את הרישיון בתוך שלושים ימים.",          # 1  פועל חדש (יבטל)
    "הוועדה תתקן את הצו לפי הצורך.",                          # 2  נקבה
    "הממונים יקצו לכך תקציב שנתי.",                            # 3  רבים, פועל חדש (יקצו)
    "הוועדה חייבת להודיע לציבור על כך.",                      # 4  חייבת
    "המנהלות רשאיות למסור מידע לציבור.",                      # 5  רבות
    "השר אינו רשאי לתקן את הצו לפני הדיון.",                  # 6  שלילה - אינו
    "המפקח לא יתקין מצלמות בבית פרטי.",                       # 7  שלילה - לא
    "השר יביא בחשבון את השיקולים הנוגעים לעניין.",            # 8  יביא בחשבון
    "השר יביא את הדוח לידיעת הכנסת.",                          # 9  יביא - בלי "בחשבון"
    "שר הכלכלה ימציא לוועדה דוח שנתי.",                        # 10 פועל שאינו בטבלה
    "אין הוא רשאי להורות על כך, והוא רשאי להורות לאחר שימוע.",   # 11 שני מופעים - לא ייחודי
]
BILL = ParsedBill(title="חוק הבדיקה", committee="ועדת הכלכלה", warnings=[], sections=[
    BillSection(str(i + 1), f"סעיף {i + 1}", BillUnit("lead", "", t), []) for i, t in enumerate(SENTENCES)])


def _items(level, fams):
    orig = bank._screen_verdicts
    bank._screen_verdicts = lambda: VERDICTS
    try:
        return families.candidates(BILL, level, fams)[0]
    finally:
        bank._screen_verdicts = orig


def _by_section(items):
    out = {}
    for it in items:
        out.setdefault(it.heading.replace("לסעיף ", ""), []).append(it.text)
    return out


DUTY = _by_section(_items("serious", ["duty"]))
MODS = _by_section(_items("serious", ["verb_modifier"]))


def test_new_verbs_and_gender_number():
    assert 'במקום "יבטל" יבוא "רשאי לבטל".' in DUTY["1"], DUTY.get("1")
    assert 'במקום "תתקן" יבוא "רשאית לתקן".' in DUTY["2"], DUTY.get("2")
    assert 'במקום "יקצו" יבוא "רשאים להקצות".' in DUTY["3"], DUTY.get("3")
    assert 'במקום "חייבת להודיע" יבוא "רשאית להודיע".' in DUTY["4"], DUTY.get("4")
    five = DUTY["5"]
    assert 'במקום "רשאיות למסור" יבוא "ימסרו".' in five and 'במקום "רשאיות למסור" יבוא "חייבות למסור".' in five, five


def test_future_plural_never_guesses_feminine():
    """"יתקנו" -> "רשאיות" רק כשהנושא ידוע כנקבה ברבים - וזה לא ידוע: רק "רשאים"."""
    assert not [t for t in DUTY["3"] if "רשאיות" in t], DUTY["3"]


def test_negation_blocks_duty_and_modifier():
    assert "6" not in DUTY and "7" not in DUTY, (DUTY.get("6"), DUTY.get("7"))
    assert not [t for t in sum(DUTY.values(), []) if "אינו יתקן" in t or "לא רשאי" in t]
    assert "6" not in MODS and "7" not in MODS, (MODS.get("6"), MODS.get("7"))


def test_yavi_bacheshbon_not_applied():
    assert "8" not in DUTY and "8" not in MODS, (DUTY.get("8"), MODS.get("8"))
    assert 'במקום "יביא" יבוא "רשאי להביא".' in DUTY["9"], DUTY.get("9")
    assert any(t.startswith('במקום "יביא" יבוא "יביא ') for t in MODS["9"]), MODS.get("9")


def test_form_not_in_table_not_applied():
    assert "10" not in DUTY and "10" not in MODS
    assert "11" not in DUTY and "11" not in MODS           # "רשאי להורות" פעמיים - עוגן לא ייחודי


def test_modifier_right_after_the_verb():
    assert 'במקום "יבטל" יבוא "יבטל בכתב".' in MODS["1"], MODS.get("1")
    assert 'במקום "רשאיות למסור" יבוא "רשאיות למסור בתוך שבעה ימים".' in MODS["5"], MODS.get("5")
    assert len(MODS["1"]) == 20                            # כל 20 התוספות הרציניות, באותה נקודה
    groups = {it.group for it in _items("serious", ["verb_modifier"]) if it.heading == "לסעיף 1"}
    assert len(groups) == 1, groups


def test_modifier_family_in_ui_and_counts():
    assert families.FAMILIES["verb_modifier"] == "תוספת לפועל"
    orig = bank._screen_verdicts
    bank._screen_verdicts = lambda: VERDICTS
    try:
        with_mod = families.availability(BILL, list(families.FAMILIES))
        without = families.availability(BILL, [f for f in families.FAMILIES if f != "verb_modifier"])
        plan = families.plan(BILL, "absurd", ["verb_modifier"], 5)
    finally:
        bank._screen_verdicts = orig
    for level in ("serious", "clever", "absurd"):
        assert with_mod[level]["available"] > without[level]["available"], (level, with_mod[level], without[level])
    assert plan.available >= 100 and plan.items and plan.at_least_separate >= 1, plan


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservation_duty_modifier: כל הבדיקות עברו")
