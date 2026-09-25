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
    """ש4: טווח ge/le, **בלי סוגריים עוטפים**. הצורה הקודמת -
    `(...) and (KnessetNum eq 25 or KnessetNum eq 24)` - הוסיפה שני
    סוגריים, וכל צירוף של 2 מילים ומעלה נחסם ב-473."""
    kq._unit_cache.clear()
    seen = {}
    def spy(entity, *, filter=None, **k):
        seen["filter"] = filter
        return []
    original = with_fetch(spy)
    try:
        kq.run_unit(["מצוקת", "דיור"], knesset_nums=[25, 24])
        assert "KnessetNum ge 24 and KnessetNum le 25" in seen["filter"], seen["filter"]
        assert seen["filter"].count("(") == 2, seen["filter"]
    finally:
        kq.fetch = original
        kq._unit_cache.clear()


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
        if len(attempts) < 3:
            raise kq.OdataError("Client error '473 '")
        return [{"Id": 7, "Name": "מצוקת דיור"}]
    original, sleep = with_fetch(flaky), kq.time.sleep
    kq.time.sleep = lambda s: None
    try:
        out = kq.run_unit(["מצוקת", "דיור"])
        assert out["count"] == 1 and len(attempts) == 3
    finally:
        kq.fetch, kq.time.sleep = original, sleep
        kq._unit_cache.clear()


# ── ש4 (25.9.2026): ה-WAF סופר סוגריים; 474 היא חסימת כתובת ──────
def test_no_filter_ever_has_four_parentheses():
    """נמדד: 4 '(' ומעלה -> 473 תמיד. בודק כל צירוף של 1-5 מילים עם
    כל צורת בחירת כנסות שהממשק מאפשר."""
    words = ["זיהום", "אוויר", "מפרץ", "חיפה", "קריות"]
    for n in range(1, 6):
        for kn in (None, [25], [25, 24], [25, 24, 23], [25, 23], [25, 22, 20]):
            clause, _, _ = kq.feed_filter(words[:n], kn)
            assert clause.count("(") <= 3, (n, kn, clause)


def test_non_contiguous_knessets_are_filtered_locally():
    kq._unit_cache.clear()
    seen = {}
    def spy(entity, *, filter=None, **k):
        seen["filter"] = filter
        return [{"Id": 1, "Name": "מצוקת דיור", "KnessetNum": 25},
                {"Id": 2, "Name": "מצוקת דיור", "KnessetNum": 24},
                {"Id": 3, "Name": "מצוקת דיור", "KnessetNum": 23}]
    original = with_fetch(spy)
    try:
        out = kq.run_unit(["מצוקת", "דיור"], knesset_nums=[25, 23])
        assert "KnessetNum ge 23 and KnessetNum le 25" in seen["filter"], seen["filter"]
        assert [r["query_id"] for r in out["rows"]] == [1, 3], out["rows"]
    finally:
        kq.fetch = original
        kq._unit_cache.clear()


def test_single_knesset_is_eq_not_range():
    clause, _, keep = kq.feed_filter(["דיור"], [25])
    assert clause.endswith("KnessetNum eq 25") and keep is None, clause


def test_ip_block_474_is_not_retried():
    """חסימת כתובת: ניסיון חוזר רק מחמיר אותה."""
    kq._unit_cache.clear()
    attempts = []
    def blocked(entity, **k):
        attempts.append(1)
        raise kq.FeedBlockedError("474")
    original = with_fetch(blocked)
    try:
        try:
            kq.run_unit(["מצוקת", "דיור"])
            raise AssertionError("היה אמור לזרוק")
        except kq.FeedBlockedError:
            pass
        assert len(attempts) == 1, attempts
    finally:
        kq.fetch = original
        kq._unit_cache.clear()


# כותרות אמיתיות שהוצגו לברק על "מחסור בכוח אדם במשטרת ישראל" (תמונה 2),
# ועוד כותרות אמיתיות מהפיד מאותו לילה.
HEALTH = ["פערים בהתחסנות ילדים לשפעת בין המרכז לפריפריה כתוצאה ממחסור בכוח סיעודי",
          "מחסור בכוח אדם בתוכנית תיאום טיפול",
          "מחסור בכוח אדם רפואי במרכז הרפואי לגליל"]
POLICE = ["ירידה עקבית באיכות השוטרים וחשש מהורדת תנאי הקבלה",
          "המפכ\"ל הורה לגנוז את ממצאי הסקר הפנימי שנערך בקרב כ-30 אלף שוטרים"]
POLICE_DOMAIN = [["משטר", "שוטר", "שיטור", 'מג"ב', "משמר הגבול"]]


def test_domain_drops_the_health_rows_from_image_2():
    assert not any(kq.domain_match(t, POLICE_DOMAIN) for t in HEALTH)
    assert all(kq.domain_match(t, POLICE_DOMAIN) for t in POLICE)


def test_domain_match_normalizes_quotes_and_hyphens():
    assert kq.domain_match("פעילות מג״ב בירושלים", [['מג"ב']])
    assert kq.domain_match("זיהום אוויר בתל-אביב", [["תל אביב"]])
    assert kq.domain_match("כל כותרת", []), "תחום ריק = אין סינון"


def test_search_queries_applies_the_domain_to_every_row():
    plan = {"expanded": True, "domain": POLICE_DOMAIN,
            "units": [{"words": ["מחסור", "כוח", "אדם"], "kind": "phrase"},
                      {"words": ["מחסור", "שוטר"], "kind": "phrase"}]}
    rows = {("מחסור", "כוח", "אדם"): HEALTH + ["מחסור בכוח אדם במשטרה"],
            ("מחסור", "שוטר"): ["מחסור בשוטרים בדרום"]}
    def run(words):
        titles = rows[tuple(words)]
        return {"words": words, "count": len(titles), "too_broad": False,
                "rows": [{"query_id": hash(t) % 10**6, "title": t, "person_id": None}
                         for t in titles]}
    original = kq.enrich
    kq.enrich = lambda ids, persons: {"docs": {}, "names": {}}
    try:
        out = kq.search_queries("מחסור בכוח אדם במשטרת ישראל",
                                expand_fn=lambda q: plan, run_fn=run)
    finally:
        kq.enrich = original
    titles = [r["title"] for r in out["results"]]
    assert titles == ["מחסור בכוח אדם במשטרה", "מחסור בשוטרים בדרום"], titles


def test_plan_is_cached_per_topic_but_failures_are_not():
    import json as _json
    calls = []
    def fake(**k):
        calls.append(1)
        return _json.dumps({"domain": [["תחבור"]], "phrases": [["תחבורה", "ציבורית"]],
                            "alternatives": []}, ensure_ascii=False)
    original = kq.draft
    kq.draft, kq._plan_cache = fake, {}
    try:
        a = kq.expand_query("תחבורה ציבורית בנגב")
        b = kq.expand_query("תחבורה  ציבורית בנגב ")
        assert a is b and len(calls) == 1, calls
        def boom(**k):
            raise kq.LLMRequestError("down")
        kq.draft = boom
        assert kq.expand_query("נושא אחר")["expanded"] is False
        kq.draft = fake
        assert kq.expand_query("נושא אחר")["expanded"] is True, "כשל לא נשמר במטמון"
    finally:
        kq.draft, kq._plan_cache = original, {}


def test_expand_query_returns_the_domain():
    import json as _json
    reply = _json.dumps({"domain": ["משטר", "שוטר", "ש"], "phrases": [["מחסור", "שוטר"]],
                         "alternatives": []}, ensure_ascii=False)
    original = kq.draft
    kq.draft, kq._plan_cache = (lambda **k: reply), {}
    try:
        plan = kq.expand_query("מחסור בשוטרים")
    finally:
        kq.draft = original
    # רשימה שטוחה = היבט אחד; אות אחת אינה תחום
    assert plan["domain"] == [["משטר", "שוטר"]], plan["domain"]


def test_every_facet_must_match():
    """"זמני המתנה לניתוחים בפריפריה": רופאים בפריפריה אינם ניתוחים."""
    dom = [["ניתוח", "בית חולים"], ["פריפרי", "גליל", "נגב"]]
    assert kq.domain_match("זמני המתנה לניתוחים בבית החולים בגליל", dom)
    assert not kq.domain_match(
        "התארכות זמני המתנה לרופאים, במיוחד בפריפריה, על רקע מלחמת \"שאגת הארי\"", dom)
    assert not kq.domain_match("זמני המתנה לניתוחים במרכז", dom)


def test_expansion_failure_has_empty_domain():
    def boom(**k):
        raise kq.LLMRequestError("down")
    original = kq.draft
    kq.draft, kq._plan_cache = boom, {}
    try:
        plan = kq.expand_query("מחסור בשוטרים")
    finally:
        kq.draft = original
    assert plan["domain"] == [] and plan["expanded"] is False


# ── ש4, סבב 2: מה שנמדד באתר החי אחרי התיקון הראשון ─────────────
def test_short_term_is_a_whole_word():
    """"מור" ב"חמור" (מוסכניקים לנושא על מורים), ו"תקנ" ב"התקנת מצלמות"
    (לנושא על תקני שוטרים) - שניהם נמדדו באתר החי."""
    assert not kq.term_in("מור", "מחסור חמור במוסכניקים")
    assert not kq.term_in("מור", "מחסור בשופטים והפגיעה החמורה בהליכים משפטיים")
    assert not kq.term_in("תקנ", 'שימוש המשטרה במצלמות ע"פ חוק התקנת מצלמות')
    assert not kq.term_in("תקן", 'שימוש המשטרה במצלמות ע"פ חוק התקנת מצלמות')
    assert kq.term_in("תקן", "חריגה מהתקן במשטרה") and kq.term_in("תקן", "בתקן")
    assert kq.term_in("תקנים", "דוח מבקר המדינה מצביע על חוסר תקנים משטרתיים באגף התנועה")
    assert kq.term_in("מורים", "מחסור במורים במערכת החינוך")


def test_term_must_open_a_word_at_any_length():
    """סבב 4 באתר החי: "מורה" ב"החמורה", "מורים" ב"החמורים"."""
    assert not kq.term_in("מורה", "מחסור בשופטים והפגיעה החמורה בהליכים משפטיים")
    assert not kq.term_in("מורים", "פערי המיגון החמורים בחברה הערבית וחוסר מוכנות")
    for term, title in (("פריפרי", "זמני המתנה בפריפריה"), ("שוטר", "ירידה באיכות השוטרים"),
                        ("ניתוח", "תורים לניתוחים"), ("אלימ", "ביטול סקר האקלים והאלימות"),
                        ("משטר", "חוסר תקנים משטרתיים"), ('מג"ב', "פעילות מג״ב"),
                        ("תחבור ציבור", "העדר תחבורה ציבורית בישוב כסיפה")):
        assert kq.term_in(term, title), (term, title)


def test_multi_word_term_matches_word_by_word():
    """"בתי ספר" לא נמצא ב"בבתי הספר" - ושורה נכונה נזרקה."""
    title = "ביטול סקר האקלים והאלימות בבתי הספר"
    assert kq.term_in("בתי ספר", title)
    assert kq.domain_match(title, [["חינוך", "בתי ספר", "תלמיד"]])


def test_unit_local_filter_drops_short_stem_false_hits():
    kq._unit_cache.clear()
    rows = [{"Id": 1, "Name": "מחסור חמור במוסכניקים", "KnessetNum": 25},
            {"Id": 2, "Name": "מחסור משמעותי במורה", "KnessetNum": 25}]
    original = with_fetch(lambda *a, **k: rows)
    try:
        out = kq.run_unit(["מחסור", "מורה"])
        assert [r["query_id"] for r in out["rows"]] == [2], out["rows"]
    finally:
        kq.fetch = original
        kq._unit_cache.clear()


def test_broad_unit_supplies_rows_once_the_domain_narrows_it():
    """"תחבורה ציבורית" רחב (מעל 120) - אבל אחרי סינון ליישובי הנגב הוא
    צר, ורק ממנו נמצאות כסיפה ותל שבע (כותרותיהן אינן אומרות "נגב")."""
    titles = ["העדר תחבורה ציבורית בישוב כסיפה", "שירות תחבורה ציבורית הופסק בישוב תל שבע",
              "תחבורה ציבורית בשבת בעיתות חירום למשרתי מילואים"] + \
             [f"תחבורה ציבורית בעיר {i}" for i in range(130)]
    plan = {"expanded": True, "domain": [["תחבורה ציבור", "אוטובוס"], ["נגב", "כסיפה", "תל שבע"]],
            "units": [{"words": ["תחבורה", "ציבורית"], "kind": "phrase"}]}
    def run(words):
        return {"words": words, "count": len(titles), "too_broad": True,
                "rows": [{"query_id": i, "title": t, "person_id": None} for i, t in enumerate(titles)]}
    original = kq.enrich
    kq.enrich = lambda ids, persons: {"docs": {}, "names": {}}
    try:
        out = kq.search_queries("תחבורה ציבורית בנגב", expand_fn=lambda q: plan, run_fn=run)
    finally:
        kq.enrich = original
    assert [r["title"] for r in out["results"]] == titles[:2], out["results"]


# ── ש4, סבב 3: התופעה כהיבט; שליפה לפי הגוף ────────────────────────
def test_single_word_supplies_rows_when_two_facets_check_every_row():
    """"שוטר" לבדה: כל כותרות המשטרה - ומהן רק מה שיש בו גם מחסור."""
    titles = ["דוח מבקר המדינה מצביע על חוסר תקנים משטרתיים באגף התנועה",
              "ירידה עקבית באיכות השוטרים וחשש מהורדת תנאי הקבלה",
              "מחסור בכוח אדם רפואי במרכז הרפואי לגליל"]
    plan = {"expanded": True,
            "domain": [["מחסור", "חוסר", "תקנ", "כוח אדם"], ["משטר", "שוטר"]],
            "units": [{"words": ["שוטר"], "kind": "domain"}]}
    def run(words):
        return {"words": words, "count": 3, "too_broad": False,
                "rows": [{"query_id": i, "title": t, "person_id": None} for i, t in enumerate(titles)]}
    original = kq.enrich
    kq.enrich = lambda ids, persons: {"docs": {}, "names": {}}
    try:
        out = kq.search_queries("מחסור בשוטרים", expand_fn=lambda q: plan, run_fn=run)
    finally:
        kq.enrich = original
    assert [r["title"] for r in out["results"]] == titles[:1], out["results"]


def test_single_word_still_ranks_only_with_one_facet():
    plan = {"expanded": True, "domain": [["משטר", "שוטר"]],
            "units": [{"words": ["שוטר"], "kind": "phrase"}]}
    run = lambda words: {"words": words, "count": 1, "too_broad": False,
                         "rows": [{"query_id": 1, "title": "ירידה באיכות השוטרים", "person_id": None}]}
    original = kq.enrich
    kq.enrich = lambda ids, persons: {"docs": {}, "names": {}}
    try:
        out = kq.search_queries("שוטרים", expand_fn=lambda q: plan, run_fn=run)
    finally:
        kq.enrich = original
    assert out["results"] == [], out["results"]


def test_expand_adds_units_from_the_body_facet():
    import json as _json
    reply = _json.dumps({"domain": [["מחסור", "חוסר"], ["משטר", "שוטר", "מג\"ב"]],
                         "phrases": [["מחסור", "שוטר"]], "alternatives": []}, ensure_ascii=False)
    original = kq.draft
    kq.draft, kq._plan_cache = (lambda **k: reply), {}
    try:
        plan = kq.expand_query("מחסור בשוטרים")
    finally:
        kq.draft = original
    words = [u["words"] for u in plan["units"]]
    assert ["משטר"] in words and ["שוטר"] in words, words


# ── ש1: המגדר של חבר הכנסת - מהמאגר, לא מהשם ────────────────────
def test_mk_gender_exact_name_match_only():
    people = [{"FirstName": "עדי", "LastName": "עזוז", "GenderDesc": "נקבה"},
              {"FirstName": "יוראי", "LastName": "להב הרצנו", "GenderDesc": "זכר"},
              {"FirstName": "נועם", "LastName": "כהן", "GenderDesc": "זכר"},
              {"FirstName": "נועם", "LastName": "כהן", "GenderDesc": "נקבה"}]
    original = with_fetch(lambda *a, **k: people)
    kq._gender_cache = None
    try:
        assert kq.mk_gender("עדי עזוז") == "נקבה"
        assert kq.mk_gender("  יוראי   להב הרצנו ") == "זכר"
        assert kq.mk_gender("עזוז") is None, "שם חלקי אינו התאמה"
        assert kq.mk_gender("נועם כהן") is None, "שני מגדרים לאותו שם -> לא מנחשים"
        assert kq.mk_gender("") is None
    finally:
        kq.fetch = original
        kq._gender_cache = None


def test_mk_gender_feed_failure_is_none():
    def boom(*a, **k):
        raise OdataError("474")
    original = with_fetch(boom)
    kq._gender_cache = None
    try:
        assert kq.mk_gender("עדי עזוז") is None
    finally:
        kq.fetch = original
        kq._gender_cache = None


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_query_knesset: כל הבדיקות עברו")
