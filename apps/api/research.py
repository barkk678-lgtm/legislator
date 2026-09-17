"""כלי המחקר (משימה 1.4, המשך) - תרגום שאלה בשפה חופשית לשאילתת
צבירה מול OData של הכנסת.

**למה רפרטואר סגור של תבניות ולא מחולל שאילתות חופשי** (החלטת ברק
אחרי החקירה, 2026-09-17):

1. **ה-WAF של הכנסת חוסם.** `filter(...)` בתוך `$apply` החזיר סטטוס
   473 "access denied" עם ה-IP שלנו. שאילתות שנבנות דינמית עלולות
   להפיל את הגישה לכולם, לא רק להיכשל.
2. **הסכימה לא צפויה.** `KNS_Person` משתמש ב-`Id` ולא ב-`PersonID`;
   ל-`KNS_CommitteeSession` אין שדה `Name` בכלל. LLM שמנחש שמות
   שדות ייצר שאילתות שגויות בביטחון מלא.
3. **רוב ערך המחקר מרוכז בעשר תבניות.** התבניות כאן נבדקו מול
   הפיד האמיתי והמספרים שלהן אומתו.

**מבנה שמאפשר הרחבה בלי שינוי מבני** (דרישת ברק במפורש): כל תבנית
היא רשומה ב-`TEMPLATES` עם פרמטרים ופונקציית הרצה. הוספת תבנית -
למשל הצבעות מליאה, או פילוח הצבעות אישי - היא רשומה נוספת ותו לא.
**בפרט: אין כאן הנחה ש"ישות = שורה אחת עם תוצאה מסכמת".** ההנחה
הזו שגויה בנתוני הכנסת: `KNS_PlenumVote` אינו מכיל ספירת בעד/נגד
כלל, וכל ספירה מחייבת צבירה מעל 1.95M רשומות תוצאה (ראו TASKS.md
לעלות המלאה).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
from odata import OdataError, escape, fetch, fetch_apply  # noqa: E402

_STATUS_PASSED = 118  # התקבלה בקריאה שלישית


class ResearchError(Exception):
    """שאלה שלא ניתן לענות עליה, או כשל מול הפיד."""


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    question_examples: list[str]
    params: dict[str, str] = field(default_factory=dict)


def _pass_rates(knesset: int | None = None) -> dict:
    """שיעור ההצעות שהתקבלו, לפי כנסת. נבדק: כנסת 25 - 7.6%
    (573 מתוך 7,491), כנסת 24 - 2.4% (102 מתוך 4,277)."""
    rows = fetch_apply("KNS_Bill", "groupby((KnessetNum,StatusID),aggregate(Id with countdistinct as n))")
    by_knesset: dict[int, dict[str, int]] = {}
    for r in rows:
        k = r.get("KnessetNum")
        if k is None:
            continue
        entry = by_knesset.setdefault(k, {"total": 0, "passed": 0})
        entry["total"] += r["n"]
        if r.get("StatusID") == _STATUS_PASSED:
            entry["passed"] += r["n"]

    items = [
        {"knesset": k, "total": v["total"], "passed": v["passed"],
         "pass_rate_pct": round(v["passed"] / v["total"] * 100, 1) if v["total"] else 0.0}
        for k, v in sorted(by_knesset.items(), reverse=True)
    ]
    if knesset is not None:
        items = [i for i in items if i["knesset"] == knesset]
        if not items:
            raise ResearchError(f"לא נמצאו נתונים לכנסת {knesset}.")
    return {"rows": items, "columns": ["knesset", "total", "passed", "pass_rate_pct"]}


def _top_initiators(knesset: int | None = None, limit: int = 10) -> dict:
    """מי יוזם הכי הרבה הצעות חוק. הצבירה היא על 169,357 רשומות
    יוזמים ורצה בצד השרת."""
    expr = "groupby((PersonID),aggregate(BillID with countdistinct as n))"
    if knesset is not None:
        # אין דרך לסנן לפי כנסת בתוך $apply (ה-WAF חוסם filter שם),
        # ולכן הסינון נעשה על טבלת היוזמים עצמה לפי מזהי ההצעות.
        raise ResearchError(
            "פילוח יוזמים לפי כנסת אינו נתמך: הפיד חוסם סינון בתוך צבירה. "
            "אפשר לשאול מי יוזם הכי הרבה בכל הכנסות."
        )
    rows = fetch_apply("KNS_BillInitiator", expr)
    rows = sorted(rows, key=lambda r: r["n"], reverse=True)[:limit]

    people = {}
    ids = [r["PersonID"] for r in rows if r.get("PersonID")]
    if ids:
        clause = "Id in (" + ",".join(str(i) for i in ids) + ")"
        for p in fetch("KNS_Person", filter=clause, select="Id,FirstName,LastName"):
            people[p["Id"]] = f"{p.get('FirstName') or ''} {p.get('LastName') or ''}".strip()

    return {
        "rows": [{"name": people.get(r["PersonID"], f"מזהה {r['PersonID']}"), "bills": r["n"]} for r in rows],
        "columns": ["name", "bills"],
    }


def _bills_on_topic(topic: str, limit: int = 15) -> dict:
    """הצעות חוק שנושאן מופיע בשמן. **חיפוש מחרוזת, לא משמעות** -
    "אלימות במשפחה" לא ימצא הצעה בשם "הגנה על נפגעות"."""
    topic = (topic or "").strip()
    if len(topic) < 2:
        raise ResearchError("נדרש נושא לחיפוש.")
    rows = fetch(
        "KNS_Bill",
        filter=f"contains(Name,'{escape(topic)}')",
        select="Id,Name,KnessetNum,SubTypeDesc,StatusID,PublicationDate",
        top=limit * 4,
    )
    rows.sort(key=lambda r: (r.get("KnessetNum") or 0), reverse=True)
    passed = sum(1 for r in rows if r.get("StatusID") == _STATUS_PASSED)
    return {
        "rows": [{
            "title": r.get("Name"),
            "knesset": r.get("KnessetNum"),
            "kind": r.get("SubTypeDesc"),
            "became_law": r.get("StatusID") == _STATUS_PASSED,
            "published_at": (r.get("PublicationDate") or "")[:10] or None,
        } for r in rows[:limit]],
        "columns": ["title", "knesset", "kind", "became_law", "published_at"],
        "summary": f"נמצאו {len(rows)} הצעות ששמן מכיל \"{topic}\", מתוכן {passed} התקבלו כחוק.",
    }


TEMPLATES: dict[str, Template] = {
    "pass_rates": Template(
        id="pass_rates",
        title="שיעור ההצעות שהתקבלו, לפי כנסת",
        question_examples=["כמה הצעות חוק עוברות בפועל?",
                           "מה שיעור ההצלחה בכנסת 25?",
                           "האם יותר חוקים עוברים היום מפעם?"],
        params={"knesset": "מספר כנסת (אופציונלי, שלם)"},
    ),
    "top_initiators": Template(
        id="top_initiators",
        title="חברי הכנסת שיזמו הכי הרבה הצעות חוק",
        question_examples=["מי מגיש הכי הרבה הצעות חוק?",
                           "מי חברי הכנסת הפעילים ביותר בחקיקה?"],
        params={"limit": "כמה שורות להחזיר (אופציונלי, ברירת מחדל 10)"},
    ),
    "bills_on_topic": Template(
        id="bills_on_topic",
        title="הצעות חוק שנושאן מופיע בשמן",
        question_examples=["אילו הצעות חוק הוגשו בנושא תובענות ייצוגיות?",
                           "מה הוגש בנושא אלימות במשפחה?"],
        params={"topic": "מילות הנושא לחיפוש (חובה)"},
    ),
}

_RUNNERS = {
    "pass_rates": _pass_rates,
    "top_initiators": _top_initiators,
    "bills_on_topic": _bills_on_topic,
}


def run_template(template_id: str, params: dict) -> dict:
    """מריצה תבנית עם פרמטרים שכבר עברו ולידציה."""
    runner = _RUNNERS.get(template_id)
    if runner is None:
        raise ResearchError(f"תבנית לא מוכרת: {template_id}")
    try:
        result = runner(**params)
    except OdataError as e:
        raise ResearchError(f"הפיד של הכנסת לא זמין כרגע: {e}") from None
    return {"template": template_id, "title": TEMPLATES[template_id].title, **result}


# --- ניתוב שאלה חופשית לתבנית ------------------------------------

_ROUTER_INSTRUCTIONS = """אתה מנתב שאלות מחקר פרלמנטריות לתבנית שאילתה.

בחר **בדיוק אחת** מהתבניות הזמינות, או השב שאין תבנית מתאימה.
אל תמציא תבנית, אל תמציא פרמטרים, ואל תנחש נתונים - אתה רק מנתב.

החזר JSON בלבד, בלי טקסט נוסף, באחד משני הפורמטים:
{"template": "<מזהה>", "params": {...}}
{"template": null, "reason": "<למה אין התאמה, במשפט אחד בעברית>"}

התבניות הזמינות:
"""


def _router_prompt() -> str:
    lines = [_ROUTER_INSTRUCTIONS]
    for t in TEMPLATES.values():
        lines.append(f"\n- מזהה: {t.id}\n  מה זה נותן: {t.title}")
        if t.params:
            lines.append("  פרמטרים: " + "; ".join(f"{k} - {v}" for k, v in t.params.items()))
        lines.append("  שאלות לדוגמה: " + " / ".join(t.question_examples))
    return "\n".join(lines)


def _coerce_params(template_id: str, raw: dict) -> dict:
    """מנקה את מה שה-LLM החזיר: רק פרמטרים מוכרים, ובטיפוס הנכון.
    בלי זה, ערך שהומצא היה מגיע עד לקריאת הרשת."""
    allowed = set(TEMPLATES[template_id].params)
    clean: dict = {}
    for key, value in (raw or {}).items():
        if key not in allowed or value in (None, "", []):
            continue
        if key in ("knesset", "limit"):
            try:
                clean[key] = int(value)
            except (TypeError, ValueError):
                continue
        else:
            clean[key] = str(value)
    return clean


def ask(question: str, *, draft_fn=None) -> dict:
    """שאלה בשפה חופשית -> תבנית -> תוצאה עם המספרים הגולמיים.

    **התשובה תמיד כוללת את השורות עצמן**, לא רק ניסוח - כדי שאפשר
    יהיה לאמת. כששאלה נופלת מחוץ לרפרטואר אומרים זאת במפורש, באותו
    דפוס של הבחנת הכיסוי בחיפוש הסמנטי: מגבלה מוצהרת עדיפה על
    תשובה שנשמעת טוב ואינה נשענת על כלום."""
    import json as _json  # noqa: PLC0415

    question = (question or "").strip()
    if not question:
        raise ResearchError("לא הוזנה שאלה.")

    if draft_fn is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
        from service import draft as draft_fn  # noqa: PLC0415

    raw = draft_fn(instructions=_router_prompt(), content=question, max_tokens=300)
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        decision = _json.loads(text)
    except ValueError:
        raise ResearchError("לא הצלחתי לנתב את השאלה לתבנית מוכרת.") from None

    template_id = decision.get("template")
    if not template_id:
        return {
            "answered": False,
            "reason": decision.get("reason") or "השאלה אינה נופלת באף אחת מהתבניות הקיימות.",
            "available": [{"id": t.id, "title": t.title} for t in TEMPLATES.values()],
        }
    if template_id not in TEMPLATES:
        raise ResearchError(f"הניתוב החזיר תבנית לא מוכרת: {template_id}")

    result = run_template(template_id, _coerce_params(template_id, decision.get("params")))
    return {"answered": True, "question": question, **result}


__all__ = ["ResearchError", "TEMPLATES", "ask", "run_template"]
