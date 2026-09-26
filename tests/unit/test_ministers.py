"""בנק §0.1 (אישורי ברק, 26.9.2026): רשימת השרים - ממאגר הכנסת, לא רשימה קבועה.

- גזירת התואר משם המשרד ובחזרה - דטרמיניסטית, עם טסטים חיוביים ושליליים.
- **ממשלה חדשה (אחרי הבחירות ב-27.10) - בלי שינוי קוד**: מאגר אחר במוק -> רשימה אחרת.
- מטמון 12 שעות; כישלון -> קובץ הגיבוי (מהמאגר) ורישום ביומן.
נכשל על הקוד הקודם (אין מודול ministers).
"""

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import ministers  # noqa: E402

os.environ.pop("LEGISLATOR_MINISTERS_SOURCE", None)   # כאן בודקים את המאגר עצמו (במוק), לא את מתג הבדיקות


def test_title_from_ministry():
    cases = {"משרד הפנים": "שר הפנים", "משרד האוצר": "שר האוצר",
             "המשרד לביטחון לאומי": "השר לביטחון לאומי", "המשרד לשירותי דת": "השר לשירותי דת",
             "משרד ראש הממשלה": "ראש הממשלה", "משרד החדשנות, המדע והטכנולוגיה": "שר החדשנות, המדע והטכנולוגיה",
             "  משרד   התיירות ": "שר התיירות"}
    for m, t in cases.items():
        assert ministers.minister_title(m) == t, (m, ministers.minister_title(m))


def test_title_negative():
    for m in ("משרד", "המשרד ל", "משרדי הממשלה", "רשות המסים", "הכנסת", "", "משרדים אחרים", "המשרד"):
        assert ministers.minister_title(m) is None, (m, ministers.minister_title(m))


def test_ministry_from_title():
    cases = {"שר הפנים": "משרד הפנים", "השר לביטחון לאומי": "המשרד לביטחון לאומי",
             "ראש הממשלה": "משרד ראש הממשלה", "השר להגנת הסביבה": "המשרד להגנת הסביבה"}
    for t, m in cases.items():
        assert ministers.ministry_of(t) == m, (t, ministers.ministry_of(t))
        assert ministers.minister_title(m) == t          # הלוך ושוב


def test_ministry_negative():
    for t in ("השר", "שר", "סגן שר הפנים", "שרת הפנים", "המנהל הכללי", "השרה לביטחון לאומי",
              "ראש הממשלה החליפי", "סגן ראש הממשלה", ""):
        assert ministers.ministry_of(t) is None, (t, ministers.ministry_of(t))


def _with_feed(ministries_by_id, current_ids):
    def fake_fetch(entity, **kw):
        if entity == "KNS_PersonToPosition":
            return [{"GovMinistryID": i} for i in current_ids]
        if entity == "KNS_GovMinistry":
            return [{"Id": i, "Name": n} for i, n in ministries_by_id.items()]
        raise AssertionError(entity)
    return fake_fetch


def _run(fake):
    orig, ministers.fetch = ministers.fetch, fake
    ministers._cache, ministers._failed_at = None, 0.0
    try:
        return ministers.current_ministers()
    finally:
        ministers.fetch = orig
        ministers._cache, ministers._failed_at = None, 0.0


def test_new_government_no_code_change():
    now = _run(_with_feed({1: "משרד הפנים", 2: "משרד ראש הממשלה", 3: "המשרד לביטחון לאומי", 4: "משרד התיירות"},
                          [1, 2, 3]))
    later = _run(_with_feed({1: "משרד הפנים והמשילות", 2: "משרד ראש הממשלה", 5: "המשרד לחלל"}, [1, 2, 5]))
    assert now["source"] == later["source"] == "feed"
    assert now["titles"] == ["השר לביטחון לאומי", "שר הפנים"], now      # בלי ראש הממשלה, בלי משרד בלי שר
    assert later["titles"] == ["השר לחלל", "שר הפנים והמשילות"], later
    assert now["titles"] != later["titles"]


def test_fallback_is_logged_and_from_the_feed_file():
    def broken(entity, **kw):
        raise ministers.OdataError("WAF 474")
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    ministers.log.addHandler(handler)
    try:
        got = _run(broken)
    finally:
        ministers.log.removeHandler(handler)
    assert got["source"] == "fallback" and got["titles"], got
    assert any("גיבוי" in r.getMessage() for r in records), [r.getMessage() for r in records]
    assert "ראש הממשלה" not in got["titles"]


def test_cache_12_hours():
    calls = []

    def fake(entity, **kw):
        calls.append(entity)
        return _with_feed({1: "משרד הפנים"}, [1])(entity, **kw)
    orig, ministers.fetch = ministers.fetch, fake
    ministers._cache, ministers._failed_at = None, 0.0
    try:
        ministers.current_ministers()
        ministers.current_ministers()
        assert len(calls) == 2, calls                      # שתי בקשות בפעם הראשונה, אפס בשנייה
        assert ministers._OK_TTL == 12 * 3600
    finally:
        ministers.fetch = orig
        ministers._cache, ministers._failed_at = None, 0.0


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_ministers: כל הבדיקות עברו")
