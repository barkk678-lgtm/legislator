"""ס5 (ברק, 26.9): שומר נגד פרט חדש בהצעה לסדר - המקרה מהאתר החי, בדיוק.

על "מחסור חמור בשוטרים בנגב, תחנות נסגרות בלילה" המודל כתב (האתר החי, 26.9):
  "בתקופה האחרונה מתרבים הדיווחים על מחסור חמור בשוטרים ..."
  "... לצד עלייה במקרי פשיעה ואירועים פליליים באזור."
שתי טענות שלא נמסרו. הכלל: פרט חדש נתפס, ניסוח מחדש מותר.
על הקוד הקודם - הטיוטה חזרה כמו שהיא (אין שומר).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import agenda_tool  # noqa: E402
from agenda_tool import AgendaDraftError, draft_agenda  # noqa: E402

TOPIC = "מחסור חמור בשוטרים בנגב, תחנות נסגרות בלילה"
LIVE = (  # התשובה האמיתית מהאתר החי, מילה במילה
    "נושא: מחסור חמור בכוח אדם במשטרה בנגב וסגירת תחנות משטרה בשעות הלילה\n"
    "דברי הסבר: בתקופה האחרונה מתרבים הדיווחים על מחסור חמור בשוטרים בתחנות המשטרה ברחבי הנגב, "
    "מצב הגורם לסגירתן של תחנות בשעות הלילה ולפגיעה ביכולת המענה המבצעי לתושבי האזור.\n"
    "תופעה זו מותירה יישובים שלמים בנגב ללא מענה משטרתי זמין בשעות הרגישות ביותר, ותורמת לתחושת "
    "חוסר הביטחון האישי בקרב התושבים, לצד עלייה במקרי פשיעה ואירועים פליליים באזור.\n"
    "לנוכח האתגרים הביטחוניים והחברתיים הייחודיים של הנגב, יש חשיבות דחופה לקיים דיון שיבחן את "
    "היקף המחסור בכוח האדם, השלכותיו על הביטחון האישי של התושבים, ואת הצעדים הנדרשים לחיזוק "
    "הנוכחות המשטרתית באזור."
)
CLEAN = (  # ניסוח מחדש של מה שנאמר - מותר
    "נושא: המחסור בשוטרים בנגב וסגירת תחנות משטרה בלילה\n"
    "דברי הסבר: תחנות משטרה בנגב נסגרות בשעות הלילה בשל מחסור חמור בשוטרים, ותושבי האזור "
    "נותרים בלי מענה משטרתי זמין בשעות אלה.\n"
    "יש לקיים דיון דחוף בהיקף המחסור ובצעדים הנדרשים כדי שהתחנות יפעלו גם בלילה."
)


def _script(first, second=None):
    calls = {"retry": None}
    agenda_tool.draft = lambda **kw: first

    def conv(**kw):
        calls["retry"] = kw["turns"][-1]["content"]
        return second if second is not None else first
    agenda_tool.draft_conversation = conv
    return calls


def test_live_case_is_caught_and_rewritten():
    calls = _script(LIVE, CLEAN)
    d = draft_agenda(topic_description=TOPIC, mk_name="עדי עזוז")
    assert calls["retry"] and "עלייה" in calls["retry"] and "מתרב" in calls["retry"], calls["retry"]
    assert "דיווח" in calls["retry"], calls["retry"]
    joined = " ".join(d["explanation"])
    assert "עלייה במקרי פשיעה" not in joined and "מתרבים הדיווחים" not in joined, joined


def test_still_invented_after_rewrite_stops_visibly():
    _script(LIVE, LIVE)
    try:
        draft_agenda(topic_description=TOPIC, mk_name="עדי עזוז")
    except AgendaDraftError as e:
        assert "פרט שלא הופיע בדבריכם" in str(e) and "עלייה" in str(e), str(e)
        return
    raise AssertionError("צפויה עצירה גלויה")


def test_rephrasing_is_allowed():
    calls = _script(CLEAN)
    d = draft_agenda(topic_description=TOPIC, mk_name="עדי עזוז")
    assert calls["retry"] is None and d["subject"].startswith("המחסור בשוטרים"), (calls, d)


def test_user_said_it_so_it_is_supported():
    """המשתמש עצמו אמר שיש עלייה בפשיעה ושמתרבות הכתבות - לא נתפס."""
    calls = _script(LIVE)
    draft_agenda(topic_description=TOPIC + ". לאחרונה יש עלייה בפשיעה, ויש הרבה כתבות על זה", mk_name="x")
    assert calls["retry"] is None, calls


def test_partial_support_still_catches_the_rest():
    """אמר שהיו כתבות - אבל לא שהן "מתרבות" ולא שיש עלייה בפשיעה."""
    calls = _script(LIVE, CLEAN)
    draft_agenda(topic_description=TOPIC + ". היו על זה כתבות", mk_name="x")
    assert calls["retry"] and "עלייה" in calls["retry"] and "מתרב" in calls["retry"], calls
    assert "דיווח" not in calls["retry"].split(":")[1].split(".")[0], calls["retry"]



def test_trend_and_timing_claims():
    """מהרצה מקומית (26.9): "בחודשים האחרונים מסתמנת מגמה של סגירת סניפי דואר"."""
    found = agenda_tool.unsupported_agenda_claims(
        "בחודשים האחרונים מסתמנת מגמה של סגירת סניפי דואר ביישובים קטנים ברחבי הגליל",
        "סגירת סניפי דואר ביישובים קטנים בגליל")
    assert {"מגמ", "האחרונ"} <= set(found), found
    assert not agenda_tool.unsupported_agenda_claims(
        "לאחרונה נסגרים סניפי דואר בגליל", "לאחרונה סוגרים סניפי דואר בגליל")

orig = (agenda_tool.draft, agenda_tool.draft_conversation)
try:
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
finally:
    agenda_tool.draft, agenda_tool.draft_conversation = orig
print("test_agenda_invented_facts: כל הבדיקות עברו")
