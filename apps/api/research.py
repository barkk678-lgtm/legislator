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

# ── מקור יחיד למפתחות ──────────────────────────────────────────────
# ראו packages/config/env_file.py: סביבה גוברת, ואם המשתנה אינו שם -
# נטען מ-/root/.claude/legislator.env (600, מחוץ לריפו).
_CONFIG_DIR = str(Path(__file__).resolve().parents[2] / "packages" / "config")
if _CONFIG_DIR not in sys.path:
    sys.path.insert(0, _CONFIG_DIR)
from env_file import MissingSecret, get as env_get, require, require_supabase  # noqa: E402


_STATUS_PASSED = 118  # התקבלה בקריאה שלישית

# **למה יש כאן מטמון בכלל:** לא מהירות - סיכון חסימה. ה-WAF של
# הכנסת כבר החזיר 473 עם ה-IP שלנו, וכל שאלה של משתמש מייצרת בקשות
# מ-IP אחד של Vercel. נמדד: יוזמים מובילים = 11 בקשות ו-12 שניות,
# שיעורי הצלחה = 4 בקשות. עשרה משתמשים במקביל = פרץ של ~110 בקשות.
# שתי התבניות האלה הן צבירות על כל הקורפוס: התשובה זהה לכל משתמש
# ומשתנה בקצב של שבועות. חיפוש לפי נושא אינו מוטמן - הוא תלוי-
# שאילתה ועולה בקשה אחת בלבד.
_CACHE_TTL_HOURS = 24 * 7


class ResearchError(Exception):
    """שאלה שלא ניתן לענות עליה, או כשל מול הפיד."""


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    question_examples: list[str]
    params: dict[str, str] = field(default_factory=dict)


def _pass_rates_data() -> dict:
    """הצבירה המלאה על כל הכנסות. **מופרדת מהסינון בכוונה**: כך
    גם שאלה ממוקדת ("כנסת 25") נענית מהמטמון ולא מייצרת בקשות
    לשרת הכנסת - הסינון ממילא מקומי."""
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
    return {
        "rows": [
            {"knesset": k, "total": v["total"], "passed": v["passed"],
             "pass_rate_pct": round(v["passed"] / v["total"] * 100, 1) if v["total"] else 0.0}
            for k, v in sorted(by_knesset.items(), reverse=True)
        ],
        "columns": ["knesset", "total", "passed", "pass_rate_pct"],
    }


def _pass_rates(knesset: int | None = None) -> dict:
    """שיעור ההצעות שהתקבלו. נבדק: כנסת 25 - 7.6% (573 מתוך 7,491),
    כנסת 24 - 2.4% (102 מתוך 4,277)."""
    data = _cached_data("pass_rates", _pass_rates_data)
    if knesset is None:
        return data
    rows = [r for r in data["rows"] if r["knesset"] == knesset]
    if not rows:
        raise ResearchError(f"לא נמצאו נתונים לכנסת {knesset}.")
    return {**data, "rows": rows}


def _top_initiators_data() -> dict:
    """צבירה על 169,357 רשומות יוזמים, בצד השרת. 11 בקשות - התבנית
    היקרה ביותר, ולכן זו שהמטמון הכי חשוב עבורה."""
    rows = fetch_apply("KNS_BillInitiator", "groupby((PersonID),aggregate(BillID with countdistinct as n))")
    rows = sorted(rows, key=lambda r: r["n"], reverse=True)[:50]

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


def _top_initiators(limit: int = 10) -> dict:
    """מי יוזם הכי הרבה הצעות חוק. הסינון לפי כנסת אינו נתמך: הפיד
    חוסם `filter` בתוך צבירה (WAF, סטטוס 473)."""
    data = _cached_data("top_initiators", _top_initiators_data)
    return {**data, "rows": data["rows"][: max(1, min(limit, 50))]}


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

# כמה בקשות לשרת הכנסת עולה כל תבנית - נמדד, לא הונח.
_REQUEST_COST = {"pass_rates": 4, "top_initiators": 11, "bills_on_topic": 1}

_RUNNERS = {
    "pass_rates": _pass_rates,
    "top_initiators": _top_initiators,
    "bills_on_topic": _bills_on_topic,
}


def _cache_client():
    """None כשאין תצורת Supabase - מצב תקין (dev מקומי), לא שגיאה.
    המטמון הוא אופטימיזציה; הכלי חייב לעבוד גם בלעדיו."""
    import httpx  # noqa: PLC0415

    # כאן **לא** זורקים: מחקר בלי DB עדיין עובד על נתוני הכנסת.
    url = env_get("SUPABASE_URL")
    key = env_get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return httpx.Client(
        base_url=f"{url.rstrip('/')}/rest/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=10.0,
    )


def _cache_get(template_id: str) -> dict | None:
    import datetime  # noqa: PLC0415

    client = _cache_client()
    if client is None:
        return None
    with client:
        try:
            resp = client.get("/knesset_agg_cache",
                              params={"template_id": f"eq.{template_id}", "select": "payload,refreshed_at", "limit": "1"})
            resp.raise_for_status()
            rows = resp.json()
        except Exception:
            return None  # מטמון לא זמין -> פשוט שואלים את הפיד
    if not rows:
        return None
    age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(rows[0]["refreshed_at"])
    if age > datetime.timedelta(hours=_CACHE_TTL_HOURS):
        return None
    return rows[0]["payload"]


def _cache_put(template_id: str, payload: dict, requests_saved: int) -> None:
    client = _cache_client()
    if client is None:
        return
    with client:
        try:
            client.post("/knesset_agg_cache", params={"on_conflict": "template_id"},
                        json=[{"template_id": template_id, "payload": payload,
                               "knesset_requests": requests_saved, "refreshed_at": "now()"}],
                        headers={"Prefer": "resolution=merge-duplicates,return=minimal"})
        except Exception:
            pass  # כישלון כתיבה למטמון לא אמור להפיל תשובה תקינה


def _cached_data(template_id: str, producer):
    """מחזירה צבירה מוטמנת, ובונה אותה אם פגה. כישלון מטמון לעולם
    לא מפיל תשובה: אם ה-DB לא זמין פשוט שואלים את הפיד."""
    cached = _cache_get(template_id)
    if cached is not None:
        return {**cached, "from_cache": True}
    data = producer()
    _cache_put(template_id, data, _REQUEST_COST.get(template_id, 0))
    return {**data, "from_cache": False}


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

**כלל הכרעה חשוב:** התבניות עונות על שאלות *כמותיות על ההליך
הפרלמנטרי* - כמה הוגשו, מי יזם, מה עבר. הן **אינן** עונות על
שאלות לגבי *תוכן הדין*: מה החוק אומר, מה העונש, מה מותר ומה אסור,
מה קורה במצב מסוים. לשאלות כאלה קיים במערכת חיפוש סמנטי נפרד, ולכן
עליך להשיב `{"template": null}` עם נימוק שמפנה אליו.

שים לב להבחנה בין "חוק" ל"הצעת חוק": התבניות מכסות **הצעות חוק**
(מה הוגש לכנסת), לא את נוסח החוק התקף. "אילו חוקים עוסקים ב..."
היא שאלת תוכן - החזר null.

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
            # שאלת תוכן אינה מבוי סתום - החיפוש הסמנטי יושב באותה
            # לשונית ועונה בדיוק על זה. הממשק מציע מעבר ישיר.
            "try_semantic_search": True,
            "question": question,
        }
    if template_id not in TEMPLATES:
        raise ResearchError(f"הניתוב החזיר תבנית לא מוכרת: {template_id}")

    result = run_template(template_id, _coerce_params(template_id, decision.get("params")))
    return {"answered": True, "question": question, **result}


__all__ = ["ResearchError", "TEMPLATES", "ask", "run_template"]
