"""ב5 + ב6 - סינון לפי כנסת, והקישור לדף השאילתה. אופליין.

**ב5, המלכודת שנתפסה במדידה:** הכנסת הנוכחית נגזרת מ-
`KNS_KnessetDates.IsCurrent` ולא מ-`max(KnessetNum)`. נמדד
(22.9.2026) שבפיד כבר יושבת שורה לכנסת ה-26 שה-`PlenumStart`
שלה הוא 10.11.2026 - היא טרם התכנסה, ו-`IsCurrent` שלה False.
המקסימום היה מחזיר 26 ומסנן החוצה את כל התוצאות האמיתיות.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "knesset"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "config"))

import knesset_queries as kq  # noqa: E402
from odata import OdataError  # noqa: E402

# שורות אמיתיות מהפיד (22.9.2026), לא מומצאות
FEED_ROWS = [
    {"KnessetNum": 25, "IsCurrent": True},
]
ALL_ROWS = [{"KnessetNum": 25}, {"KnessetNum": 26}]


def with_fetch(fn):
    original = kq.fetch
    kq.fetch = fn
    kq._current_knesset_cache = None
    return original


def test_current_knesset_comes_from_is_current_not_from_max():
    original = with_fetch(lambda *a, **k: FEED_ROWS)
    try:
        assert kq.current_knesset() == 25
        assert max(r["KnessetNum"] for r in ALL_ROWS) == 26, "הפיד אכן מכיל 26"
    finally:
        kq.fetch = original
        kq._current_knesset_cache = None


def test_default_is_current_and_previous():
    original = with_fetch(lambda *a, **k: FEED_ROWS)
    try:
        assert kq.default_knesset_nums() == [25, 24]
    finally:
        kq.fetch = original
        kq._current_knesset_cache = None


def test_feed_failure_is_none_not_a_hardcoded_year():
    """**ערך קבוע היה נכון היום ושגוי בעוד חודשיים בלי שאיש ישים
    לב.** None אומר "לא ידוע", והקורא מחפש בלי סינון ואומר זאת."""
    def boom(*a, **k):
        raise OdataError("הפיד נפל")
    original = with_fetch(boom)
    try:
        assert kq.current_knesset() is None
        assert kq.default_knesset_nums() == []
    finally:
        kq.fetch = original
        kq._current_knesset_cache = None


def test_knesset_filter_is_added_to_the_clause():
    seen = {}
    def spy(entity, *, filter=None, **k):
        seen["filter"] = filter
        return []
    original = with_fetch(spy)
    try:
        kq.run_unit(["מצוקת", "דיור"], knesset_nums=[25, 24])
        assert "KnessetNum eq 25 or KnessetNum eq 24" in seen["filter"], seen["filter"]
        assert seen["filter"].startswith("("), "הצירוף חייב להיות בסוגריים משלו"
    finally:
        kq.fetch = original


def test_no_knesset_filter_means_no_clause():
    seen = {}
    def spy(entity, *, filter=None, **k):
        seen["filter"] = filter
        return []
    original = with_fetch(spy)
    try:
        kq.run_unit(["מצוקת", "דיור"])
        assert "KnessetNum" not in seen["filter"], seen["filter"]
    finally:
        kq.fetch = original


def test_page_url_pattern():
    assert kq.page_url(480993) == "https://m.knesset.gov.il/apps/query/details/480993"


def test_no_id_means_no_link_not_a_broken_one():
    assert kq.page_url(None) is None
    assert kq.page_url(0) is None


# ── ש2 (25.9.2026): ה-WAF חוסם 4 תנאי contains() ומעלה ─────────────
def test_four_word_unit_sends_three_contains_and_filters_all_four():
    """נמדד מול הפיד: 4 contains -> 473 תמיד, 3 -> תמיד עובר. יחידה של
    4 מילים מהמודל נכשלה בכל חיפוש - "4 מתוך 11 מקורות נבדקו"."""
    kq._unit_cache.clear()
    seen = {}
    def spy(entity, *, filter=None, **k):
        seen["filter"] = filter
        return [{"Id": 1, "Name": "מחסור בכוח אדם במשטרה"},
                {"Id": 2, "Name": "מחסור בכוח אדם בבתי חולים"}]   # בלי "משטרה"
    original = with_fetch(spy)
    try:
        out = kq.run_unit(["מחסור", "כוח", "אדם", "משטרה"])
        assert seen["filter"].count("contains(") == 3, seen["filter"]
        assert [r["query_id"] for r in out["rows"]] == [1], out["rows"]
        assert out["count"] == 1
    finally:
        kq.fetch = original
        kq._unit_cache.clear()


def test_three_word_unit_is_sent_as_is():
    kq._unit_cache.clear()
    seen = {}
    def spy(entity, *, filter=None, **k):
        seen["filter"] = filter
        return []
    original = with_fetch(spy)
    try:
        kq.run_unit(["כוח", "אדם", "משטרה"])
        assert seen["filter"].count("contains(") == 3
    finally:
        kq.fetch = original
        kq._unit_cache.clear()


def test_same_unit_twice_hits_the_feed_once():
    kq._unit_cache.clear()
    calls = []
    def spy(entity, **k):
        calls.append(1)
        return []
    original = with_fetch(spy)
    try:
        kq.run_unit(["מצוקת", "דיור"])
        kq.run_unit(["מצוקת", "דיור"])
        assert len(calls) == 1, calls
    finally:
        kq.fetch = original
        kq._unit_cache.clear()


def test_rate_limit_473_is_retried_until_it_passes():
    kq._unit_cache.clear()
    attempts = []
    def flaky(entity, **k):
        attempts.append(1)
        if len(attempts) < 4:
            raise kq.OdataError("Client error '473 '")
        return [{"Id": 7, "Name": "מצוקת דיור"}]
    original, sleep = with_fetch(flaky), kq.time.sleep
    kq.time.sleep = lambda s: None
    try:
        out = kq.run_unit(["מצוקת", "דיור"])
        assert out["count"] == 1 and len(attempts) == 4
    finally:
        kq.fetch, kq.time.sleep = original, sleep
        kq._unit_cache.clear()


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_query_knesset: כל הבדיקות עברו")
