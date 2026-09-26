"""תשלום (הסתייגויות 4, 26.9) ומספרים בעברית - בלי רשת.

1. **המחיר**: 50 כלולות; $10 לכל 100 נוספות או חלק מהן - הערכים מ-config.
2. **התשלום מדומה**: מעבר לכלול - רק payment="demo" במצב הדגמה; במצב "live" (אין
   עדיין סליקה) - 402. בכל מקרה: **אין בבקשה ובתשובה אף שדה של פרטי תשלום.**
3. **ביקשו יותר ממה שההצעה מאפשרת** - short, בלי השלמה בחזרות, והמחיר על מה שנוצר.
4. numbers_he: מילים <-> מספר, זכר/נקבה, זוגי ("יומיים").
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "support"))
from isolate_env import isolate  # noqa: E402

isolate()

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import families  # noqa: E402
import numbers_he  # noqa: E402
import pricing  # noqa: E402

PDF = ROOT / "reference" / "הצעת חוק טבריה.pdf"
CFG = {"included": 50, "price_per_block_usd": 10, "block_size": 100, "default_count": 50, "payment_mode": "demo"}
_PAYMENT_WORDS = ("card", "credit", "cvv", "cvc", "iban", "כרטיס", "אשראי", "חשבון בנק")


def test_price():
    for count, want in ((1, 0), (50, 0), (51, 10), (150, 10), (151, 20), (250, 20), (1050, 100)):
        assert pricing.price_usd(count, CFG) == want, (count, pricing.price_usd(count, CFG))
    cfg = pricing.config()
    assert {k: cfg[k] for k in ("included", "price_per_block_usd", "block_size")} == \
        {"included": 50, "price_per_block_usd": 10, "block_size": 100}, "הערכים בהגדרות"


def _post(api, count, payment="", level="serious"):
    return api.post("/api/reservations/generate", files={"file": (PDF.name, PDF.read_bytes(), "application/pdf")},
                    data={"level": level, "families": "", "count": str(count), "payment": payment})


def _fake_plan(n):
    real = families.plan

    def fake(bill, level, fams, count):
        p = real(bill, level, fams, 1000)
        base = p.items[0]
        items = [families.Item(heading=base.heading, lines=[f'במקום "7" יבוא "{i + 8}".'], family="value_change",
                               group=f"g{i}", order=(0, i)) for i in range(min(count, n))]
        return families.Plan(items=items, available=n, groups=n, at_least_separate=len(items), requested=count)
    return fake


def test_api_payment_flow():
    api = TestClient(main.app, raise_server_exceptions=False)
    r = _post(api, 20)
    assert r.status_code == 200 and r.json()["price_usd"] == 0, r.text
    original_plan, original_cfg = families.plan, pricing.config
    families.plan = _fake_plan(300)
    try:
        r = _post(api, 120)
        assert r.status_code == 402, (r.status_code, r.text[:200])
        r = _post(api, 120, payment="demo")
        body = r.json()
        assert r.status_code == 200 and body["produced"] == 120 and body["price_usd"] == 10, r.text[:200]
        pricing.config = lambda: {**CFG, "payment_mode": "live"}
        r = _post(api, 120, payment="demo")
        assert r.status_code == 402 and "הסליקה עדיין לא מחוברת" in r.json()["detail"], r.text[:200]
    finally:
        families.plan, pricing.config = original_plan, original_cfg
    lowered = (str(body.keys()) + str(pricing.config())).lower()
    assert not any(w in lowered for w in _PAYMENT_WORDS), "שדה של פרטי תשלום"


def test_short_when_bill_allows_less():
    api = TestClient(main.app, raise_server_exceptions=False)
    body = _post(api, 500, payment="demo").json()
    assert body["short"] is True and body["produced"] == body["available"] < 500, body.get("produced")
    texts = [" ".join(it["lines"]) for it in body["items"]]
    assert len(texts) == len(set(texts)), "בלי חזרות"
    assert body["price_usd"] == pricing.price_usd(body["produced"]), "המחיר - על מה שנוצר"


def test_numbers_he():
    assert numbers_he.parse_words("שלושים") == 30
    assert numbers_he.parse_words("מאה ועשרים") == 120
    assert numbers_he.parse_words("שלושה עשר") == 13
    assert numbers_he.quantity(1, "ימים") == "יום אחד" or numbers_he.quantity(1, "ימים").startswith("יום")
    assert numbers_he.quantity(2, "ימים") == "יומיים"
    assert numbers_he.quantity(3, "ימים") == "שלושה ימים"
    assert numbers_he.quantity(120, "ימים") == "מאה ועשרים ימים"
    assert numbers_he.quantity(3, "שנים") == "שלוש שנים"
    got = [(q.value, q.unit) for q in numbers_he.find_quantities("בתוך שלושים ימים, ולכל היותר שנתיים")]
    assert (30, "ימים") in got and (2, "שנים") in got, got
    assert not numbers_he.find_quantities("ושבעה"), "ו' החיבור אינה חלק מכמות בלי יחידה"


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_reservations_pricing: כל הבדיקות עברו")
