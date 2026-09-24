"""כלי המחקר: מגבלה שהשאלה מזכירה והתבנית אינה יודעת להחיל.

**הליקוי שזה נועל** (ברק, 21.9.2026): "מי היוזמים הפוריים ביותר
בכנסת הנוכחית" החזיר עשרה שמות שמסתכמים ב-19,420 הצעות, בעוד
שבכנסת ה-25 הוגשו בסך הכול 7,491. המילים "בכנסת הנוכחית" לא
השפיעו על דבר, והתשובה סומנה answered=True.

**הבדיקה שברק הגדיר:** אותה שאלה עם המגבלה ובלעדיה - אם התוצאה
זהה, המגבלה נזרקה. הבדיקה כאן מריצה בדיוק את זה, על כל צירוף של
תבנית ומגבלה שהיא אינה יודעת להחיל. בלי רשת: המפיקים מוחלפים
בנתונים קבועים, כך שתוצאה זהה פירושה בוודאות שהמגבלה לא הופעלה
ולא סתם שהנתונים דומים.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import research  # noqa: E402
from research import (_APPLICABLE_CONSTRAINTS, _CONSTRAINT_LABELS,  # noqa: E402
                      TEMPLATES, ask, unapplicable_constraints)

# שאלה בסיסית לכל תבנית, וניסוח של כל מגבלה שאפשר להדביק לה.
BASE = {
    "pass_rates": "כמה הצעות חוק עוברות בקריאה שלישית",
    "top_initiators": "מי היוזמים הפוריים ביותר",
    "bills_on_topic": "אילו הצעות חוק הוגשו בנושא חינוך",
}
CONSTRAINT_TEXT = {
    "knesset": "בכנסת הנוכחית",
    "time_window": "בשנה האחרונה",
    "bill_kind": "הצעות חוק פרטיות",
}

FAKE = {
    "pass_rates": {"rows": [{"knesset": 25, "total": 7491, "passed": 573,
                             "pass_rate_pct": 7.6}],
                   "columns": ["knesset", "total", "passed", "pass_rate_pct"]},
    "top_initiators": {"rows": [{"name": "דב חנין", "bills": 3501}],
                       "columns": ["name", "bills"]},
    "bills_on_topic": {"rows": [{"title": "הצעה", "knesset": 16, "kind": "פרטית",
                                 "became_law": False, "published_at": None}],
                       "columns": ["title", "knesset", "kind", "became_law",
                                   "published_at"],
                       "summary": "נמצאו 60 הצעות."},
}


def _router(template_id):
    import json
    payload = json.dumps({"template": template_id, "params": {}})
    return lambda instructions, content, max_tokens=300: payload


def main():
    ok = True

    # מנטרלים רשת: כל מפיק מחזיר נתונים קבועים.
    research._cached_data = lambda tid, producer: FAKE[tid]
    research._bills_on_topic = lambda topic="", limit=15: FAKE["bills_on_topic"]
    research._RUNNERS["bills_on_topic"] = research._bills_on_topic
    research.fetch = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("אסור לגעת ברשת"))
    research.fetch_apply = research.fetch

    for tid in TEMPLATES:
        applicable = _APPLICABLE_CONSTRAINTS[tid]
        for constraint, text in CONSTRAINT_TEXT.items():
            plain_q = BASE[tid] + "?"
            with_q = f"{BASE[tid]} {text}?"
            plain = ask(plain_q, draft_fn=_router(tid))
            constrained = ask(with_q, draft_fn=_router(tid))

            if constraint in applicable:
                # התבנית יודעת להחיל - מותר לה לענות.
                good = constrained.get("answered") is True
                label = f"{tid} + {constraint}: יודעת להחיל, עונה"
            else:
                # **הבדיקה של ברק:** אסור שהתוצאה תהיה זהה לשאלה
                # בלי המגבלה, כי אז המגבלה נזרקה בשקט.
                same = (constrained.get("answered") is True
                        and constrained.get("rows") == plain.get("rows"))
                declared = (constrained.get("answered") is False
                            and constraint in (constrained.get("unapplicable") or []))
                good = declared and not same
                label = f"{tid} + {constraint}: אינה יודעת - מצהירה ולא עונה"
            ok &= good
            print(("OK   " if good else "כשל  ") + label)

    # הזיהוי עצמו: המקרה המדויק מהדיווח
    q = "מי היוזמים הפוריים ביותר בכנסת הנוכחית?"
    detected = unapplicable_constraints("top_initiators", q) == ["knesset"]
    ok &= detected
    print(("OK   " if detected else "כשל  ") + "המקרה מהדיווח מזוהה: 'בכנסת הנוכחית'")

    # שלילי: שאלה בלי מגבלה אינה נחסמת
    clean = unapplicable_constraints("top_initiators", "מי מגיש הכי הרבה הצעות חוק?") == []
    ok &= clean
    print(("OK   " if clean else "כשל  ") + "שאלה בלי מגבלה אינה נחסמת")

    # התשובה מציעה מה כן אפשר לשאול
    res = ask(q, draft_fn=_router("top_initiators"))
    offer = res.get("answerable_instead", "")
    has_offer = bool(offer) and "הנוכחית" not in offer
    ok &= has_offer
    print(("OK   " if has_offer else "כשל  ") + f"מוצעת שאלה חלופית: {offer!r}")

    # מזהה תבנית פנימי לא דולף למשתמש בנימוק של המנתב
    from research import _humanize
    humanized = _humanize("התבנית top_initiators אינה יודעת להגביל")
    clean = "top_initiators" not in humanized and "חברי הכנסת" in humanized
    ok &= clean
    print(("OK   " if clean else "כשל  ") + "מזהה תבנית מוחלף בשם עברי בנימוק")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
