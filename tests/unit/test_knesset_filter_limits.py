"""הצעות דומות ופרסומי החוק ותיקוניו מול שתי המגבלות של הפיד של הכנסת
(132, 26.9.2026).

1. **חומת האש (473):** סינון עם 4 סוגריים פותחים ומעלה נחסם, תמיד (ש2/ש4).
2. **מורכבות הביטוי (400):** שרשרת `or` ארוכה נדחית - 25 נמדדו ב-knesset_citations,
   ובאתר החי נדחו גם עד 24 שמות. הפיד המזויף כאן דוחה 20 ומעלה.

ברק ביקש לבדוק שהמלכודת של ש2 לא קיימת בשני הכלים. **הסוגריים - לא:** כל
סינון בהם עם סוגר אחד לכל היותר. **אבל מגבלת ה-or - כן, בהצעות הדומות:**
שמות היוזמים נשלפו במנות של 40 `Id eq X or ...`, ועשר הצעות פרטיות עם הרבה
חותמים עוברות 25 בקלות. הפיד דחה, והמשתמש ראה "לא הצלחתי לבדוק את
היוזמים" בכל עשר התוצאות. שוחזר באתר החי - "הצעת חוק הגנת הצרכן (תיקון –
עסקה ברוכלות)": 10/10 בלי יוזמים, שלוש פעמים ברצף.

הפיד כאן מזויף, אבל אוכף את שתי המגבלות בדיוק כמו האמיתי - בלי רשת.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "knesset"))

import knesset_bills as kb  # noqa: E402
import knesset_citations as kc  # noqa: E402
from odata import OdataError  # noqa: E402

BILLS = [{"Id": 1000 + i, "Name": f"הצעת חוק הגנת הצרכן (תיקון - עסקה ברוכלות {i})",
          "KnessetNum": 25, "SubTypeDesc": "פרטית", "StatusID": 1, "PrivateNumber": i,
          "PublicationDate": None} for i in range(10)]
SIGNERS = 5   # לכל הצעה - 50 אנשים שונים סה"כ


class FakeFeed:
    def __init__(self):
        self.filters = []

    def __call__(self, entity, *, filter=None, select=None, top=None, **_):
        f = filter or ""
        self.filters.append((entity, f))
        if f.count("(") >= 4:
            raise OdataError(f"כשל בקריאה ל-{entity}: 473 (WAF)")
        if f.count(" or ") >= 19:
            raise OdataError(f"כשל בקריאה ל-{entity}: 400 (מורכבות)")
        if entity == "KNS_Bill":
            return BILLS
        if entity == "KNS_BillInitiator":
            return [{"BillID": b["Id"], "PersonID": b["Id"] * 10 + k, "Ordinal": k}
                    for b in BILLS for k in range(SIGNERS)]
        if entity == "KNS_Person":
            ids = [int(x) for x in __import__("re").findall(r"\d+", f)]
            return [{"Id": i, "FirstName": "חבר", "LastName": f"כנסת {i}"} for i in ids]
        if entity == "KNS_LawBinding":
            return [{"Id": i, "LawID": 5000 + i, "BindingTypeDesc": "תיקון"} for i in range(169)]
        return []


def test_similar_bills_initiators_survive_many_signers():
    feed = FakeFeed()
    kb.fetch = feed
    out = kb.similar_bills("הצעת חוק הגנת הצרכן (תיקון – עסקה ברוכלות) (הוראת שעה), התשפ\"ו–2026")
    res = out["results"]
    assert len(res) == 10, len(res)
    missing = [r["bill_id"] for r in res if r["initiators_unavailable"]]
    assert not missing, f"יוזמים לא נשלפו ל-{len(missing)} הצעות; סינונים: {feed.filters}"
    assert all(len(r["initiators"]) == SIGNERS for r in res), [len(r["initiators"]) for r in res]


def test_similar_bills_filters_stay_under_both_limits():
    feed = FakeFeed()
    kb.fetch = feed
    kb.similar_bills("הצעת חוק העונשין (תיקון מס' 150) (עבירות מין (הגנה על קטינים))", knesset_num=25)
    for entity, f in feed.filters:
        assert f.count("(") < 4, (entity, f)
        assert f.count(" or ") < 19, (entity, f.count(" or "))


def test_citations_filters_stay_under_both_limits():
    """חוק עם 169 קישורים (כמו העונשין) - `Id in (...)` במנות, סוגר אחד."""
    feed = FakeFeed()
    kc.fetch = feed
    kc._israel_law_id = lambda law_id: 2000006
    kc.citations_for_law("law-2000006")
    assert feed.filters, "לא נשלחה אף בקשה"
    for entity, f in feed.filters:
        assert f.count("(") < 4, (entity, f)
        assert f.count(" or ") < 19, (entity, f.count(" or "))


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_knesset_filter_limits: כל הבדיקות עברו")
