"""בנק §0.2 (אישורי ברק, 26.9.2026): "{השנה הבאה}" / "{השנה שאחרי הבאה}" - מחושבת
ממועד הייצור, לפי Asia/Jerusalem, ונכתבת כמספר: "ביום 1 בינואר 2027". לעולם לא
"של השנה הבאה". נכשל על הקוד הקודם (המשתנה נשאר בפלט כמו שהוא).
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402

REC = bank.Record(id="t", level="serious", family="after_last",
                  template="תחילה|תחילתו של חוק זה {value}.", value="ביום 1 בינואר {השנה הבאה}",
                  status="approved")
REC2 = bank.Record(id="t2", level="serious", family="after_last",
                   template="תחילה|תחילתו של חוק זה ביום 1 בינואר {השנה שאחרי הבאה}.", value="",
                   status="approved")


def _at(dt):
    original = bank._now
    bank._now = lambda: dt
    try:
        return REC.text("ועדת הפנים"), REC2.text("ועדת הפנים")
    finally:
        bank._now = original


def test_next_years_from_production_date():
    a, b = _at(datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc))
    assert a == "תחילה|תחילתו של חוק זה ביום 1 בינואר 2027.", a
    assert b == "תחילה|תחילתו של חוק זה ביום 1 בינואר 2028.", b


def test_jerusalem_new_year_boundary():
    # 31.12.2026 22:30 UTC = 1.1.2027 00:30 בירושלים - "השנה הבאה" היא כבר 2028
    a, b = _at(datetime(2026, 12, 31, 22, 30, tzinfo=timezone.utc))
    assert a.endswith("ביום 1 בינואר 2028."), a
    assert b.endswith("ביום 1 בינואר 2029."), b
    a, _ = _at(datetime(2026, 12, 31, 21, 30, tzinfo=timezone.utc))   # 23:30 בירושלים
    assert a.endswith("ביום 1 בינואר 2027."), a


def test_never_textual_next_year():
    a, b = _at(datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc))
    for t in (a, b):
        assert "השנה" not in t and "{" not in t, t


def test_screen_key_unchanged_by_year():
    """החישוב בזמן הייצור - הגיבוב (ופסק השומר) לא משתנה משנה לשנה."""
    k = REC.screen_key
    _at(datetime(2030, 1, 5, tzinfo=timezone.utc))
    assert REC.screen_key == k


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservation_year: כל הבדיקות עברו")
