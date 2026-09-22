"""ב7 - פורמט תאריך אחיד: 01.12.2026, בנקודות.

**למה מודול ולא תיקון נקודתי:** הפיד מחזיר ISO בשישה מקומות שונים,
וכל אחד חתך `[:10]` בנפרד. תיקון של מקום אחד היה משאיר את החמישה.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from dates import display_date  # noqa: E402


def test_iso_with_time_becomes_dotted():
    assert display_date("2026-12-01T00:00:00") == "01.12.2026"


def test_bare_iso_date():
    assert display_date("2026-12-01") == "01.12.2026"


def test_single_digit_day_keeps_its_zero():
    """01 ולא 1 - הפורמט שברק נתן."""
    assert display_date("2026-07-05") == "05.07.2026"


def test_empty_is_none_not_an_empty_string():
    assert display_date("") is None
    assert display_date(None) is None


def test_non_date_is_returned_as_is_not_dropped():
    """שדה שאינו תאריך אינו סיבה להעלים מידע."""
    assert display_date("לא ידוע") == "לא ידוע"
    assert display_date("2026") == "2026"


def test_every_api_module_routes_through_it():
    """אם מודול חדש יחתוך [:10] בעצמו, הבדיקה הזו תיפול."""
    offenders = []
    for name in ("knesset_queries.py", "knesset_bills.py", "knesset_citations.py",
                 "research.py", "main.py", "tree_view.py"):
        text = (ROOT / "apps" / "api" / name).read_text(encoding="utf-8")
        for line in text.split("\n"):
            if "Date" in line and "[:10]" in line and "#" not in line.split("[:10]")[0]:
                offenders.append(f"{name}: {line.strip()[:80]}")
    assert not offenders, "תאריך שנחתך ידנית במקום display_date:\n" + "\n".join(offenders)


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_dates: כל הבדיקות עברו")
