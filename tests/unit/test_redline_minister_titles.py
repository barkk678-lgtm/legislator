"""סבב התיקונים על אישורי הבנק, ב1 (הכרעת ברק 26.9.2026): חסימות שווא בקווים האדומים.

**תואר שר מרשימת השרים הרשמית של מאגר הכנסת לא עובר את בדיקת המילים של מפלגות
ויישובים** - "שר העבודה", "שר ירושלים ומסורת ישראל", ומה שיבוא אחרי הבחירות. כלל,
לא אישור נקודתי. **שומר 86(ד)(2) ממשיך לרוץ עליהם** (פסק השומר - על התבנית עם {שר}).
- "שר העבודה" עובר כתואר מהרשימה; "העבודה" כמפלגה בטקסט חופשי - עדיין נחסם.
- הפטור הוא **רק** למילים של מפלגות ויישובים, ורק לתואר עצמו: עלבון, אדם אמיתי או
  קבוצה - נחסמים גם בתוך תואר; ומפלגה מחוץ לתואר, באותה רשומה - נחסמת.
נכשל על הקוד הקודם ("שר העבודה" ו"שר ירושלים ומסורת ישראל" נחסמו בהרחבת הרשימה).
"""

import os
import sys
from pathlib import Path

os.environ["LEGISLATOR_MINISTERS_SOURCE"] = "fallback"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402
import families  # noqa: E402
import ministers  # noqa: E402


def test_official_title_passes_party_and_place_words():
    for title in ("שר העבודה", "שר ירושלים ומסורת ישראל"):
        text = f"באישור {title}"
        assert bank.redline_violation(text), f"בלי פטור - {title} נחסם (כמו היום)"
        assert bank.redline_violation(text, official_titles=[title]) == "", title


def test_party_in_free_text_still_blocked():
    assert "מפלגה" in bank.redline_violation("יתקן בשעות העבודה בלבד")
    assert "מפלגה" in bank.redline_violation("יתקן בשעות העבודה בלבד", official_titles=["שר העבודה"])
    # מפלגה מחוץ לתואר, באותה רשומה - נחסמת
    assert bank.redline_violation("באישור שר העבודה ומפלגת העבודה", official_titles=["שר העבודה"])
    assert bank.redline_violation("באישור שר הפנים בירושלים", official_titles=["שר הפנים"])


def test_exemption_only_for_parties_and_places():
    """עלבון / אדם אמיתי / קבוצה - נחסמים גם בתוך "תואר"."""
    for title in ("שר הטיפשים", "שר נתניהו", "השר לענייני ערבים"):
        assert bank.redline_violation(f"באישור {title}", official_titles=[title]), title


def test_expansion_keeps_official_titles():
    """בהרחבת רשימת השרים (families._expand_ministers) - "שר העבודה" ו"שר ירושלים ומסורת
    ישראל" מגיעים לפלט. **פסק השומר לא נעקף** - הוא נבדק על התבנית, לפני ההרחבה (הטסט
    הבא)."""
    orig = ministers.titles
    ministers.titles = lambda: ["שר העבודה", "שר ירושלים ומסורת ישראל", "שר האוצר"]
    try:
        tmpl = [r for r in bank.load_all() if r.value_list == "ministers"]
        assert tmpl
        out = families._expand_ministers(tmpl)
    finally:
        ministers.titles = orig
    values = {r.value for r in out}
    assert {"שר העבודה", "שר ירושלים ומסורת ישראל", "שר האוצר"} <= values, values


def test_guard_still_runs_on_expanded_records():
    """שומר שחסם את התבנית - חוסם גם כל תואר שנפרש ממנה (הפטור הוא מהקווים האדומים בלבד)."""
    tmpl = [r for r in bank.load_all() if r.value_list == "ministers"][0]
    verdicts = {tmpl.id: {"key": tmpl.screen_key, "allowed": False, "reason": "86(ד)(2): בדיקה"}}
    orig_v, orig_all, orig_t = bank._screen_verdicts, bank.load_all, ministers.titles
    bank._screen_verdicts, bank.load_all = (lambda: verdicts), (lambda: [tmpl])
    ministers.titles = lambda: ["שר העבודה"]
    try:
        allowed, blocked = bank.load(tmpl.level)
        items = families._expand_ministers(allowed)
    finally:
        bank._screen_verdicts, bank.load_all, ministers.titles = orig_v, orig_all, orig_t
    assert not items and blocked, (items, blocked)


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_redline_minister_titles: כל הבדיקות עברו")
