"""סבב התיקונים על אישורי הבנק, ב2 (ברק 26.9.2026): אישור אנושי מפורש, באותו מנגנון
כמו ועד הדולפינים (§0.4), לשתי רשומות שנחסמו בקו אדום:
    verb_modifier-059 - "בשעות העבודה בלבד"   (קו אדום: מפלגה, "העבודה")
    conditions-128    - "מי מוריד את הזבל"      (קו אדום: עלבון, "זבל")
האישור - בשדה human_approval ברשומה (מי, מתי, למה) ו**רק לביטוי שהוא מאשר**
(redline: ["העבודה"]). קו אדום אחר באותה רשומה - עדיין חוסם; אישור בלי מי/מתי/למה - לא
תקף; ורשומה אחרת עם אותה מילה - נחסמת. נכשל על הקוד הקודם (שתיהן נחסמו).
"""

import os
import sys
from dataclasses import replace
from pathlib import Path

os.environ["LEGISLATOR_MINISTERS_SOURCE"] = "fallback"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402

RECS = {r.id: r for r in bank.load_all()}
VERDICTS = bank._screen_verdicts()
APPROVED = {"verb_modifier-059": "העבודה", "conditions-128": "זבל"}


def test_two_records_approved_and_released():
    for rid, phrase in APPROVED.items():
        r = RECS[rid]
        assert bank.redline_violation(r.text("ועדה")), (rid, "הקו האדום עצמו לא השתנה")
        a = r.human_approval or {}
        assert a.get("by") == "ברק" and a.get("at") and a.get("why"), (rid, a)
        assert a.get("redline") == [phrase], (rid, a)
        assert bank.check(r, VERDICTS) == "", (rid, bank.check(r, VERDICTS))


def test_other_redline_in_same_record_still_blocks():
    r = RECS["verb_modifier-059"]
    other = replace(r, value=r.value + " ובאישור הליכוד")
    reason = bank.check(other, {other.id: {"key": other.screen_key, "allowed": True}})
    assert "הליכוד" in reason or "ליכוד" in reason, reason


def test_approval_without_who_when_why_is_void():
    r = RECS["conditions-128"]
    for missing in ("by", "at", "why"):
        a = dict(r.human_approval)
        a[missing] = ""
        assert bank.check(replace(r, human_approval=a), VERDICTS), missing


def test_same_word_elsewhere_still_blocked():
    """הכלל לא השתנה: "העבודה" / "זבל" ברשומה בלי אישור - נחסמים."""
    for rid in APPROVED:
        r = replace(RECS[rid], id=rid + "-copy", human_approval=None)
        assert bank.check(r, {r.id: {"key": r.screen_key, "allowed": True}}).startswith("קו אדום"), rid


def test_dolphins_unchanged():
    """§0.4: אישור הדולפינים גובר על פסק השומר; אין לו redline - וקו אדום לא היה בו."""
    r = RECS["approval-164/actor-001"]
    assert bank.check(r, VERDICTS) == ""
    assert not (r.human_approval or {}).get("redline")


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_human_approval_redline: כל הבדיקות עברו")
