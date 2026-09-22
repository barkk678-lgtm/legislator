"""מאגר השאילתות של הכנסת (משימה 1.4, תוצר ג).

מחליף את "שאילתות קודמות בנושא - בקרוב (1.4)" שכבר קיים בלשונית
השאילתות: לפני ניסוח שאילתה חדשה, לראות מה כבר נשאל באותו נושא,
מי שאל ומתי.

**מה יש ומה אין:** `KNS_Query` (42,824 רשומות) מחזיק כותרת, סוג
(רגילה/דחופה/ישירה), תאריך הגשה, מגיש ומשרד. **אין שדה נושא, קטגוריה
או תגית** - נבדקה רשימת השדות המלאה של הישות (Id, Number, Name, TypeID,
TypeDesc, StatusID, PersonID, GovMinistryID, KnessetNum, SubmitDate,
ReplyDatePlanned, ReplyMinisterDate, LastUpdatedDate). ולכן כל חיפוש
נושאי חייב לעבור דרך הכותרת. הטקסט המלא יושב כקובץ Word ב-
`fs.knesset.gov.il` - **נבדק ואומת שהוא נגיש מ-Vercel** (200,
application/msword), אף שהוא חסום מסביבת ה-agent.

**מחזירים קישור ולא מושכים את הקובץ** (החלטת ברק): המשתמש פותח
בעצמו. משיכה ופרסור של קובצי doc לכל חיפוש הייתה מאטה את החיפוש
עצמו בלי שביקשו זאת.

## למה החיפוש אינו התאמת מחרוזת אחת

עד 2026-09-22 החיפוש היה `contains(Name, <כל מה שהמשתמש הקליד>)`.
נמדד על שישה ניסוחים סבירים: **חמישה החזירו אפס** בזמן שהמאגר מלא
באותו נושא בניסוח אחר ("מצוקת הדיור בפריפריה" -> 0, בעוד "מצוקת
הדיור" לבדה -> 46). זה לא פיצ'ר חלש אלא מטעה: המשתמש הסיק שהנושא
בתולי. ראו CLAUDE.md, "לא נמצא" מול "לא הצלחתי לבדוק".

**הפירוק נעשה בקריאת LLM אחת** (expand_query) שמחזירה גם את הצירופים
וגם ניסוחים חלופיים - **ולא רשימת מילות מילוי מקודדת בקוד**. הכלל על
"מילה ריקה" (מצוקה, בעיה, נושא) יושב בהנחיה כמשפט עם דוגמאות, כדי
שיעבוד על כל נושא ולא רק על מה שנחזה מראש. עלות נמדדה: ~407 טוקני
קלט ו-147 פלט, $0.00228 לחיפוש.

**הדבר הקשיח היחיד בקוד הוא מספר, לא רשימה:** GENERIC_CAP. יחידה
שמחזירה יותר ממנו היא רחבה מדי ומשמשת **לדירוג בלבד, לא לשליפה** -
נמדד שכך נחסמות אוטומטית "דיור" (200+), "חינוך" (200+), "חיפה"
(200+) ו"נגב" (200+), בלי שאף אחת מהן מופיעה ברשימה כלשהי.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
from odata import OdataError, escape, fetch, fetch_raw_array  # noqa: E402
from service import LLMConfigError, LLMRequestError, draft  # noqa: E402

# יחידה שמחזירה יותר מזה - רחבה מדי לשליפה, משמשת לדירוג בלבד.
# הערך נגזר מהמדידה: "מצוקת דיור" 46, "מחירי דירות" 43, "זיהום אוויר"
# 116 - כולן שימושיות; "דיור"/"חינוך"/"חיפה"/"נגב" חצו 200 (התקרה
# שנשלפה) והחזירו רעש. 120 מפריד בין השתיים.
GENERIC_CAP = 120
# **"דירוג 1" נחתך לארבעה מקומות** (החלטת ברק: דיוק לפני כיסוי).
MAX_RANK1_ROWS = 4
MAX_STRONG_ROWS = 12
MAX_ROWS = MAX_STRONG_ROWS + MAX_RANK1_ROWS


def _is_single_word(words: list[str]) -> bool:
    """מילה בודדת = איבר אחד **בלי רווח בתוכו**. יחידה כמו
    ["מצוקת הדיור"] היא צירוף שנשלח כרצף אחד, לא מילה בודדת -
    הבחנה שנשברה פעם אחת בפיתוח והחזירה אפס תוצאות לחיפוש המילולי."""
    return len(words) == 1 and " " not in words[0].strip()


def unit_budget(count: int) -> int:
    """כמה שורות מותר ליחידה אחת לתרום למסך, לפי רוחבה.

    **נדרש בגלל התצוגה ההדרגתית, ונמדד.** בגרסת האצווה היו כל
    היחידות חוזרות יחד ואפשר היה לדרג לפי מספר ההתאמות לפני ההצגה.
    בתצוגה הדרגתית היחידה הראשונה שחוזרת תופסת את המסך - ונמדד
    (2026-09-22) ש"זיהום אוויר" (116 תוצאות) מילאה את כל 12 השורות
    בזיהום אוויר בתל אביב, באשקלון ובמודיעין, לפני ש"מפרץ חיפה"
    (13 תוצאות) הספיקה לחזור בכלל. הדיוק ירד מ-89% ל-77%.

    ככל שצירוף מתאים ליותר כותרות כך הוא מלמד פחות על הנושא, ולכן
    מכסתו קטנה. הסף העליון (GENERIC_CAP) נשאר "לדירוג בלבד"."""
    if count <= 25:
        return MAX_STRONG_ROWS
    if count <= 60:
        return 6
    if count <= GENERIC_CAP:
        return 3
    return 0

_EXPAND_SYSTEM = (
    "אתה מפרק נושא של שאילתה פרלמנטרית לצירופי חיפוש. החזר JSON בלבד:\n"
    '{"phrases": [["מילה", ...], ...], "alternatives": [["מילה", ...], ...]}\n\n'
    "phrases: פירוק הנושא ליחידות המשמעות שלו. כל יחידה היא רשימת המילים "
    "שחייבות להופיע *יחד* בכותרת. יחידות נפרדות נבדקות בנפרד.\n"
    "- מילים בצורת בסיס: בלי ה' הידיעה ובלי אותיות ב/ל/מ/ו/ש/כ בתחילת מילה.\n"
    "- יחידה של מילה אחת מותרת רק אם המילה נושאית בפני עצמה (דיור, אלימות, "
    "פריפריה, נגב). מילה ריקה (מצוקה, בעיה, נושא, מצב, טיפול) לעולם לא לבדה - "
    "רק יחד עם המילה שהיא נסמכת אליה.\n"
    "- 2 עד 4 יחידות.\n\n"
    "alternatives: עד 4 ניסוחים חלופיים לאותו נושא, כפי שהוא עשוי להיות מנוסח "
    "בכותרת שאילתה. כל ניסוח הוא רשימת מילים בצורת בסיס שחייבות להופיע יחד.\n"
    "- ניסוח חלופי חייב לתאר את **אותו נושא בדיוק**, לא נושא סמוך. "
    "ל'אלימות במערכת החינוך' - 'אלימות בבתי ספר' הוא ניסוח חלופי; "
    "'בטיחות במוסדות חינוך' הוא נושא אחר ואסור להחזיר אותו.\n"
    "- מוטב להחזיר שניים מדויקים מארבעה שאחד מהם גולש.\n\n"
    'דוגמה - הקלט "מצוקת הדיור בפריפריה":\n'
    '{"phrases": [["מצוקת","דיור"], ["דיור"], ["פריפריה"]], '
    '"alternatives": [["יוקר","דיור"], ["משבר","דיור"], ["שיכון","ציבורי"], '
    '["מחירי","דירות"]]}'
)


def _clean_unit(raw) -> tuple[str, ...] | None:
    """יחידה תקינה: רשימת מילים לא ריקות, בלי כפילויות, עד 5 מילים.
    המודל חוזר לפעמים עם מחרוזת אחת במקום רשימה - מפצלים ברווח."""
    if isinstance(raw, str):
        raw = raw.split()
    if not isinstance(raw, list):
        return None
    words: list[str] = []
    for w in raw:
        if not isinstance(w, str):
            return None
        w = w.strip()
        if w and w not in words:
            words.append(w)
    return tuple(words[:5]) or None


def expand_query(q: str) -> dict:
    """קריאת LLM אחת -> יחידות חיפוש, ממוינות לפי סגוליות (מספר מילים
    יורד, ואז סדר המודל: צירופים לפני נרדפות).

    **כשל בהרחבה אינו "לא נמצא".** אם הקריאה נכשלת חוזרים לחיפוש
    המילולי בדיוק כפי שהיה, ומסמנים `expanded=False` כדי שהממשק
    יאמר שההרחבה לא רצה - ולא יציג צמצום תוצאות כאילו זו המציאות."""
    q = q.strip()
    literal = {"units": [{"words": [q], "kind": "literal"}], "expanded": False}
    try:
        raw = draft(instructions=_EXPAND_SYSTEM, content=q, max_tokens=400).strip()
    except (LLMConfigError, LLMRequestError) as e:
        return {**literal, "expansion_error": str(e)}
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        raw = raw.lstrip("json").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {**literal, "expansion_error": "המודל לא החזיר JSON תקין."}

    units: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    for key, kind in (("phrases", "phrase"), ("alternatives", "alt")):
        for item in parsed.get(key) or []:
            words = _clean_unit(item)
            if words and words not in seen:
                seen.add(words)
                units.append({"words": list(words), "kind": kind})
    if not units:
        return {**literal, "expansion_error": "המודל לא החזיר אף צירוף."}
    # סגוליות: יותר מילים = צירוף צר יותר. בשוויון - סדר המודל.
    units.sort(key=lambda u: -len(u["words"]))
    return {"units": units, "expanded": True}


def run_unit(words: list[str], *, top: int = 200) -> dict:
    """יחידת חיפוש אחת = קריאה אחת לפיד. **כל** מילות היחידה חייבות
    להופיע בכותרת (and, לא or) - זה מה שמונע את "מצוקת" לבדה.

    `contains` הוא תת-מחרוזת, ולכן מילה בצורת בסיס תופסת גם את הצורה
    המוטה: 'פריפריה' תופסת 'בפריפריה'. זו הסיבה שההנחיה מבקשת צורת
    בסיס - במקום רשימת תחיליות לקילוף, שהייתה שוברת מילים כמו "מורים"."""
    words = [w.strip() for w in words if w and w.strip()]
    if not words:
        return {"words": [], "rows": [], "count": 0}
    clause = " and ".join(f"contains(Name,'{escape(w)}')" for w in words)
    # **הפיד מגביל קצב.** נמדד: מעל ~4 בקשות בו-זמנית הוא מחזיר
    # HTTP 473, וכשל כזה מתבטא כ"מקור שלא נבדק" אצל המשתמש. שני
    # ניסיונות חוזרים עם השהיה גדלה מכסים את הרוב; מה שנשאר נספר
    # ונאמר במפורש, ולא נבלע כתוצאה ריקה.
    for attempt in range(3):
        try:
            rows = fetch(
                "KNS_Query",
                filter=clause,
                select="Id,Name,TypeDesc,StatusID,SubmitDate,KnessetNum,PersonID,GovMinistryID",
                orderby="SubmitDate desc",
                top=top,
            )
            break
        except OdataError as e:
            if attempt == 2 or "473" not in str(e):
                raise
            time.sleep(0.8 * (attempt + 1))
    return {
        "words": words,
        "count": len(rows),
        "too_broad": len(rows) > GENERIC_CAP,
        "rows": [{
            "query_id": r["Id"],
            "title": r.get("Name"),
            "kind": r.get("TypeDesc"),
            "knesset": r.get("KnessetNum"),
            "submitted_at": (r.get("SubmitDate") or "")[:10] or None,
            "person_id": r.get("PersonID"),
        } for r in rows],
    }


def _person_names(person_ids: list[int]) -> dict[int, str]:
    """שמות המגישים. בלי זה השאילתה מוצגת בלי מי שאל אותה, וזה
    בדיוק המידע שמעניין מי שמנסח שאילתה חדשה."""
    names: dict[int, str] = {}
    unique = sorted({pid for pid in person_ids if pid})
    for i in range(0, len(unique), 30):
        clause = " or ".join(f"Id eq {pid}" for pid in unique[i : i + 30])
        for p in fetch("KNS_Person", filter=clause, select="Id,FirstName,LastName"):
            full = f"{p.get('FirstName') or ''} {p.get('LastName') or ''}".strip()
            # **"אין נתונים" הוא אדם במאגר של הכנסת, לא באג אצלנו** -
            # KNS_Person Id=30299, FirstName="אין", LastName="נתונים",
            # מוצמד לשאילתות ישנות שמגישן לא נרשם. נבדק בפיד בפועל.
            # מוצג בניסוח שמסביר, כדי שלא ייראה כמו תקלת תצוגה.
            names[p["Id"]] = "המגיש לא נרשם במאגר הכנסת" if full == "אין נתונים" else full
    return names


def _document_links(query_ids: list[int]) -> dict[int, str]:
    """קישור לקובץ המקורי של כל שאילתה. `KNS_DocumentQuery` מחזיר
    מערך חשוף עם מפתחות camelCase (ראו odata.fetch_raw_array), ולכן
    לא עובר דרך fetch הרגילה."""
    links: dict[int, str] = {}
    ids = [qid for qid in query_ids if qid]
    if not ids:
        return links
    for i in range(0, len(ids), 50):
        clause = "QueryID in (" + ",".join(str(q) for q in ids[i : i + 50]) + ")"
        try:
            for row in fetch_raw_array("KNS_DocumentQuery", filter=clause):
                qid, path = row.get("queryID"), row.get("filePath")
                if qid and path:
                    links.setdefault(qid, path)
        except OdataError:
            return links  # הקישור הוא תוספת, לא תנאי - חיפוש שעובד חשוב יותר
    return links


def enrich(query_ids: list[int], person_ids: list[int]) -> dict:
    """השלמה של שמות המגישים והקישורים לשורות שכבר על המסך. רצה
    **אחרי** שהשורות הוצגו, ולכן אינה מעכבת את התוצאה הראשונה; היא
    ממלאת שדות במקום, ולא מזיזה שורות.

    `names_unavailable`/`docs_unavailable` מבדילים בין "אין מגיש"
    לבין "לא הצלחתי לשלוף את השם" - ראו CLAUDE.md."""
    out: dict = {"names": {}, "docs": {}, "names_unavailable": False,
                 "docs_unavailable": False}
    try:
        out["names"] = {str(k): v for k, v in _person_names(person_ids).items()}
    except OdataError:
        out["names_unavailable"] = True
    try:
        out["docs"] = {str(k): v for k, v in _document_links(query_ids).items()}
    except OdataError:
        out["docs_unavailable"] = True
    return out


def search_queries(q: str, *, limit: int = 12, expand_fn=None, run_fn=None) -> dict:
    """הצינור המלא בקריאה אחת - **לא** המסלול שהממשק משתמש בו.
    הממשק קורא ל-plan/unit/enrich בנפרד כדי להציג בהדרגה (ראו
    static/app.js). נשמר כאן ל-API חיצוני ולבדיקת הקצה החיה, ומממש
    בדיוק את אותם כללי בחירה - כדי ששני המסלולים לא ייפרדו."""
    q = q.strip()
    if len(q) < 2:
        return {"query": q, "results": [], "note": "מונח חיפוש קצר מדי."}

    # expand_fn/run_fn: הזרקה לבדיקות אופליין - אותו דפוס בדיוק כמו
    # complete_fn ב-service.draft ו-fetch= ב-db_ingest.build_ingest_plan.
    plan = (expand_fn or expand_query)(q)
    runner = run_fn or run_unit
    units, failed = [], 0
    for u in plan["units"]:
        try:
            units.append(runner(u["words"]))
        except OdataError:
            failed += 1
    if not units:
        raise OdataError(f"כל {failed} קריאות החיפוש נכשלו.")

    rank: dict[int, int] = {}
    for u in units:
        for row in u["rows"]:
            rank[row["query_id"]] = rank.get(row["query_id"], 0) + 1

    chosen: list[dict] = []
    taken: set[int] = set()
    held: list[dict] = []   # נדחו בגלל מכסה - מועמדים לשלב השני
    for u in units:
        # **יחידה של מילה בודדת מדרגת ואינה שולפת.** נמדד
        # (2026-09-22): "פריפריה" לבדה הכניסה למסך זמני המתנה
        # לרופאים, התחסנות ילדים לשפעת והנחה בתחבורה ציבורית -
        # ארבע שורות רעש מתוך שש-עשרה. מילה אחת אינה מזהה נושא,
        # גם כשהיא נושאית בפני עצמה, כי היא מופיעה בכל תחום.
        # זו סטייה מודעת ממה שברק ניסח ("דירוג 1 נחתך לארבעה"):
        # הזנב נשאר ארבעה מקומות, אבל הוא מתמלא משורות של צירופים
        # שנדחו במכסה - לא משורות של מילה בודדת.
        if u["too_broad"] or _is_single_word(u["words"]):
            continue
        budget = unit_budget(u["count"])
        used = 0
        for row in u["rows"]:
            if row["query_id"] in taken:
                continue
            row = {**row, "matched": rank[row["query_id"]], "matched_by": " ".join(u["words"]),
                   "unit_count": u["count"]}
            if used < budget and len(chosen) < MAX_STRONG_ROWS:
                used += 1
                taken.add(row["query_id"])
                chosen.append(row)
            else:
                held.append(row)
    # שלב שני - ההצלבה: שורה שהתאימה ליותר מצירוף אחד היא התוצאה
    # המדויקת ביותר שיש, וגם אם נדחתה במכסה היא נכנסת עכשיו.
    for row in sorted(held, key=lambda r: (-r["matched"], r["unit_count"])):
        if row["matched"] < 2 or row["query_id"] in taken or len(chosen) >= MAX_STRONG_ROWS:
            continue
        taken.add(row["query_id"])
        chosen.append(row)
    # ואז הזנב - עד ארבע שורות שהתאימו לצירוף אחד בלבד, מהצירוף הצר ביותר.
    tail = 0
    for row in sorted(held, key=lambda r: r["unit_count"]):
        if row["matched"] >= 2 or row["query_id"] in taken or tail >= MAX_RANK1_ROWS:
            continue
        if len(chosen) >= MAX_ROWS:
            break
        taken.add(row["query_id"])
        chosen.append(row)
        tail += 1

    chosen = chosen[:limit] if limit else chosen
    extra = enrich([r["query_id"] for r in chosen], [r["person_id"] for r in chosen])
    for r in chosen:
        r["document_url"] = extra["docs"].get(str(r["query_id"]))
        r["asked_by"] = extra["names"].get(str(r["person_id"])) or None
        r.pop("person_id", None)

    note = "חיפוש בכותרות השאילתות. הטקסט המלא יושב בשרת הקבצים של הכנסת."
    if not plan["expanded"]:
        note = "ההרחבה לניסוחים חלופיים לא רצתה - חיפוש מילולי בלבד. " + note
    if failed:
        note = f"{failed} מקורות לא נבדקו בגלל תקלה בפיד. " + note
    return {"query": q, "results": chosen, "note": note,
            "sources_total": len(plan["units"]), "sources_failed": failed,
            "expanded": plan["expanded"]}


__all__ = ["OdataError", "enrich", "expand_query", "run_unit", "search_queries",
           "unit_budget"]
