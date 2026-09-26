"""בנק ההסתייגויות (הסתייגויות 3, 26.9) - בלי רשת.

נבדק:
1. **רק רשומה מאושרת מגיעה לפלט** - ממתינה/נדחתה נחסמת, גם כשהיא תקינה.
2. **קו אדום נחסם בטעינה** - אדם אמיתי, מפלגה, תקשורת, קבוצה דתית/אתנית, עיר,
   עלבון - גם אם אושרה וסוננה. דמויות בדיוניות, בעלי חיים, מזג אוויר, ספורט ואוכל
   - מותרים.
3. **שומר 86(ד)(2) על הבנק חוסם**: בלי פסק, פסק ישן (התבנית שונתה אחרי הסינון),
   או פסק "חסום" - לא מגיע לפלט.
4. **הבנק האמיתי כולו ממתין** (data/reservations_bank.json) - היום שום רשומה לא
   מגיעה לפלט, ומשפחות הבנק מדווחות "ממתינות".
5. **"לוועדת", לא "לועדת"** - אות שימוש לפני ו' (נמצא בבדיקת הצורות, 26.9;
   נכשל על הקוד הקודם).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402
import families  # noqa: E402
from pdf_bill import BillSection, BillUnit, ParsedBill  # noqa: E402


def rec(**kw):
    base = dict(id="t-1", level="serious", family="approval", template="באישור {value}",
                value="{committee} של הכנסת", status="approved", source="בדיקה")
    base.update(kw)
    return bank.Record(**base)


def screened(r, allowed=True):
    return {r.id: {"key": r.screen_key, "allowed": allowed, "reason": "" if allowed else "הסינון החזיר 'כן'"}}


def test_only_approved_reaches_output():
    for status, want in (("pending", "ממתינה לאישור"), ("rejected", "סטטוס: rejected")):
        r = rec(status=status)
        assert bank.check(r, screened(r)) == want, status
    r = rec()
    assert bank.check(r, screened(r)) == ""


def test_redlines_block_at_load_even_when_approved():
    for value in ("בנימין נתניהו", "הליכוד", "ערוץ 14", "המוסלמים", "טבריה", "הטיפשים"):
        r = rec(template="{value}", value=value, family="actor_swap")
        reason = bank.check(r, screened(r))
        assert reason.startswith("קו אדום"), (value, reason)


def test_allowed_fantasy_animals_weather_sport_food():
    for value in ("דמבלדור", "ועד הדולפינים", "השמש", "נבחרת ישראל בשחמט", "ועדת הפלאפל", "חמור"):
        assert bank.redline_violation(value) == "", value


def test_screen_guard_blocks():
    r = rec()
    assert bank.check(r, {}).startswith("לא עבר את שומר 86(ד)(2)")
    stale = {r.id: {"key": "0" * 16, "allowed": True}}
    assert bank.check(r, stale).startswith("לא עבר את שומר 86(ד)(2)"), "פסק על נוסח ישן"
    assert bank.check(r, screened(r, allowed=False)).startswith("נחסם בשומר 86(ד)(2)")


def test_real_bank_is_all_pending_and_screened_record_blocked():
    records = bank.load_all()
    assert records and all(r.status == "pending" for r in records), "כל הרשומות מתחילות ממתינות"
    for level in bank.LEVELS:
        allowed, blocked = bank.load(level)
        assert allowed == [] and blocked, level
    # approval-047 נחסם בסינון (26.9) - חסום גם אם יאושר
    r = next(r for r in records if r.id == "approval-047")
    approved = bank.Record(**{**r.__dict__, "status": "approved"})
    assert bank.check(approved).startswith("נחסם בשומר 86(ד)(2)"), bank.check(approved)
    # וכל רשומה שאינה חסומה בקו אדום - יש לה פסק על הנוסח הנוכחי
    verdicts = bank._screen_verdicts()
    missing = [r.id for r in records if verdicts.get(r.id, {}).get("key") != r.screen_key]
    assert not missing, f"רשומות בלי סינון על הנוסח הנוכחי: {missing[:5]}"


BILL = ParsedBill(title="חוק הבדיקה (תיקון), התשפ\"ו–2026", committee="ועדת הפנים והגנת הסביבה", sections=[
    BillSection("1", "תיקון סעיף 3", BillUnit("lead", "", "בחוק הבדיקה, בסעיף 3 –"), [
        BillUnit("paragraph", "(1)", 'השר יקבע כללים בתוך שלושים ימים;'),
        BillUnit("paragraph", "(2)", "סעיף קטן (ב) – בטל."),
    ]),
], warnings=[])


def test_pending_bank_families_reported_waiting():
    items, waiting = families.candidates(BILL, "serious", list(families.FAMILIES))
    assert set(waiting) == set(bank.BANK_FAMILIES), waiting
    assert all(it.family in ("value_change", "deletion") for it in items), {it.family for it in items}
    assert not any(it.record_id for it in items)


def test_approved_record_is_used_and_unapproved_is_not():
    ok, pending = rec(id="t-ok"), rec(id="t-pending", status="pending", template="בהתייעצות עם {value}")
    verdicts = {**screened(ok), **screened(pending)}
    original_all, original_verdicts = bank.load_all, bank._screen_verdicts
    bank.load_all = lambda: [ok, pending]
    bank._screen_verdicts = lambda: verdicts
    try:
        items, waiting = families.candidates(BILL, "serious", ["approval"])
    finally:
        bank.load_all, bank._screen_verdicts = original_all, original_verdicts
    texts = [it.text for it in items]
    assert items and all(it.record_id == "t-ok" for it in items), texts
    assert not any("בהתייעצות" in t for t in texts), texts
    assert waiting == []
    assert any('אחרי "השר" יבוא "באישור ועדת הפנים והגנת הסביבה של הכנסת"' in t for t in texts), texts


def test_prefix_doubles_vav():
    r = rec(family="conditions", template="ובלבד ש{value}", value="השר ידווח ל{committee} של הכנסת")
    assert r.text("ועדת הפנים והגנת הסביבה") == "ובלבד שהשר ידווח לוועדת הפנים והגנת הסביבה של הכנסת"
    assert rec().text("ועדת הכספים") == "באישור ועדת הכספים של הכנסת"      # בלי אות שימוש - בלי שינוי
    assert rec(template="ל{value}", value="וועדה").text() == "לוועדה"     # כבר כפולה - לא משולשת


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservations_bank: כל הבדיקות עברו")
