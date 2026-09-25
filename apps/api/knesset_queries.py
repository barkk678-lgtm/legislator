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

**הקישור מוביל לדף השאילתה באתר הכנסת, לא לקובץ** (ברק, ב6,
22.9.2026): `m.knesset.gov.il/apps/query/details/<Id>`. קודם הוא
הוריד את קובץ ה-Word, וזו התנהגות שקופצת על המשתמש במקום לתת לו
לקרוא. **הדף עצמו לא אומת מסביבת ה-agent** - `m.knesset.gov.il`
חסום כאן (403 מהפרוקסי), כמו `fs.knesset.gov.il`. הדפוס והדוגמה
(480993) הגיעו מברק.

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
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
from odata import FeedBlockedError, OdataError, escape, fetch, fetch_raw_array  # noqa: E402
from service import LLMConfigError, LLMRequestError, draft  # noqa: E402
from dates import display_date  # noqa: E402

# יחידה שמחזירה יותר מזה - רחבה מדי לשליפה, משמשת לדירוג בלבד.
# הערך נגזר מהמדידה: "מצוקת דיור" 46, "מחירי דירות" 43, "זיהום אוויר"
# 116 - כולן שימושיות; "דיור"/"חינוך"/"חיפה"/"נגב" חצו 200 (התקרה
# שנשלפה) והחזירו רעש. 120 מפריד בין השתיים.
GENERIC_CAP = 120
# **צירוף רחב מוחזק עד סוף החיפוש** (החלטת ברק, 2026-09-22). יחידה
# שמתאימה ליותר מזה אינה מציגה שורות בזמן אמת - רק בסוף, ורק את
# מה שהצטלב עם צירוף אחר. נמדד שזה מה שמפריד 89% מ-96%: הרעש כולו
# היה שורות של צירוף רחב שנכנסו ב-2.8 שניות, לפני שידענו מה מצטלב.
# המחיר: בנושא שבו הצירוף הפותח רחב, השורה הראשונה ב-5.5 שניות
# במקום 2.8. "שלוש שניות עדיפות על ארבע שורות רעש בראש הרשימה,
# כי הראש הוא מה שנקרא."
HOLD_ABOVE = 60
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
    if count <= HOLD_ABOVE:
        return 6
    return 0   # רחב - מוחזק לסוף, ורק ההצלבה שלו מוצגת

_EXPAND_SYSTEM = (
    "אתה מפרק נושא של שאילתה פרלמנטרית לצירופי חיפוש. החזר JSON בלבד:\n"
    '{"domain": [["...", ...], ...], "phrases": [["מילה", ...], ...], '
    '"alternatives": [["מילה", ...], ...]}\n\n'
    "כלל לכל המילים: **החלק המשותף לכל הנטיות**, כי החיפוש הוא תת-מחרוזת. "
    "משטרה/משטרת/שוטרים -> 'משטר' ו'שוטר'; ניתוחים/ניתוח -> 'ניתוח'. "
    "**אבל מונח של פחות מ-4 אותיות נבדק כמילה שלמה** - אז כתוב את הצורות "
    "המלאות, לא גזע: 'מורה','מורים','מורות' (לא 'מור'); 'תקן','תקנים','תקינה' "
    "(לא 'תקנ'). בלי ה' הידיעה ובלי ב/ל/מ/ו/ש/כ בתחילת מילה. "
    "**כתיב מלא, כמו בכותרות הכנסת**: אוויר (לא אויר), תוכנית, כסיפה. "
    "**בצירוף סמיכות** המילה שמשתנה (בית/בתי) וה' הידיעה נשמטות: בית ספר / "
    "בתי הספר -> 'ספר'; מערכת החינוך -> 'חינוך' (אחרת 'בית ספר' לא ימצא "
    "'בבתי הספר').\n\n"
    "domain: **מה שכל תוצאה חייבת לחלוק עם הנושא** - רשימה של עד שלושה היבטים. "
    "כל היבט הוא רשימת כל הדרכים שבהן הוא נכתב בכותרת (נרדפים, יחידות, "
    "תפקידים, צורות), ותוצאה חייבת להכיל מונח אחד לפחות **מכל** היבט.\n"
    "- היבט 1, תמיד: **התופעה עצמה** - מה קורה (מחסור, זמני המתנה, אלימות, "
    "זיהום אוויר), על כל נרדפיה. 'מחסור בכוח אדם' -> "
    '["מחסור","חוסר","חסרים","תקן","תקנים","תקינה","מצבת","כוח אדם","גיוס"].\n'
    "- היבט 2, כשיש: **הגוף או התחום** - שם העצם שהנושא עוסק בו (משטרה, "
    "מורים, ניתוחים). **לא רחב ממנו** - 'ניתוחים' -> [\"ניתוח\"], לא רופאים "
    "או בריאות; **ולא צר ממנו** - 'מחסור במורים בבתי ספר תיכוניים' -> "
    "[\"מורה\",\"מורים\",\"מורות\",\"הוראה\"], והתיכון אינו היבט נפרד. "
    "'במשטרת ישראל' -> "
    '["משטר","שוטר","שיטור","מג\"ב","משמר הגבול"]. '
    "כשהתופעה היא התחום עצמו ('תחבורה ציבורית') - היבט אחד לשניהם.\n"
    "- היבט 3, **רק מקום גאוגרפי** שהנושא נוקב בו: היישובים והאזורים שבו. "
    "'במפרץ חיפה' -> "
    '["מפרץ חיפה","חיפה","קרית חיים","קרית ביאליק","קרית מוצקין","קרית ים",'
    '"קרית אתא","קריות","נשר","טירת כרמל","בזן","בז\"ן"]. '
    "'בנגב' -> נגב, באר שבע, ויישובי הנגב. **ליישובים - עד 25, כולל קטנים**: "
    "כותרת שאילתה נוקבת לרוב ביישוב ('העדר תחבורה ציבורית בישוב ...') ולא באזור.\n"
    "- **נרדפים מדויקים בלבד, לא מושגים קרובים**: ל'אלימות' - תקיפה, "
    "בריונות; לא 'פגיעה' (פגיעה בזכויות אינה אלימות).\n"
    "- אם הנושא עמום מכדי לזהות אפילו את התופעה - [].\n\n"
    "phrases: פירוק הנושא ליחידות המשמעות שלו. כל יחידה היא רשימת המילים "
    "שחייבות להופיע *יחד* בכותרת. יחידות נפרדות נבדקות בנפרד.\n"
    "- יחידה של מילה אחת מותרת רק אם המילה נושאית בפני עצמה (דיור, אלימות, "
    "פריפריה, נגב). מילה ריקה (מצוקה, בעיה, נושא, מצב, טיפול) לעולם לא לבדה - "
    "רק יחד עם המילה שהיא נסמכת אליה.\n"
    "- 2 עד 4 יחידות, עד 3 מילים ביחידה.\n\n"
    "alternatives: עד 4 ניסוחים חלופיים לאותו נושא, כפי שהוא עשוי להיות מנוסח "
    "בכותרת שאילתה. כל ניסוח הוא רשימת מילים שחייבות להופיע יחד, עד 3.\n"
    "- ניסוח חלופי חייב לתאר את **אותו נושא בדיוק**, לא נושא סמוך. "
    "ל'אלימות במערכת החינוך' - 'אלימות בבתי ספר' הוא ניסוח חלופי; "
    "'בטיחות במוסדות חינוך' הוא נושא אחר ואסור להחזיר אותו.\n"
    "- מוטב להחזיר שניים מדויקים מארבעה שאחד מהם גולש.\n\n"
    'דוגמה - הקלט "מצוקת הדיור בפריפריה":\n'
    '{"domain": [["מצוקת","משבר","יוקר","מחסור","מחירי"], '
    '["דיור","דירה","דירות","שיכון","משכנת","מחיר למשתכן"], '
    '["פריפרי","נגב","גליל","עיירות פיתוח","עיירת פיתוח"]], '
    '"phrases": [["מצוקת","דיור"], ["דיור"], ["פריפרי"]], '
    '"alternatives": [["יוקר","דיור"], ["משבר","דיור"], ["שיכון","ציבורי"], '
    '["מחירי","דירות"]]}'
)

_DOMAIN_MAX = 30
_QUOTES = str.maketrans({"״": '"', "׳": "'", "”": '"', "“": '"', "’": "'", "-": " ", "־": " "})


def _norm_title(text: str) -> str:
    """השוואת תחום: גרשיים עבריים ואנגליים זהים, מקף = רווח
    ("תל-אביב" = "תל אביב"), רווחים מכווצים."""
    return " ".join((text or "").translate(_QUOTES).split())


_SHORT_STEM = 3
_PREFIXES = "והבלמשכ"


_HEB_WORD = re.compile(r"[א-ת]+|[^\sא-ת]+")


def _word_matches(word: str, token: str) -> bool:
    """מילה מהמונח מול מילה מהכותרת: אחרי הסרת 0-3 אותיות שימוש מתחילת
    מילת הכותרת, היא **מתחילה** במילת המונח; ומונח של עד 3 אותיות - שווה
    לה בדיוק."""
    for cut in range(0, min(3, len(token) - 1) + 1):
        if cut and token[cut - 1] not in _PREFIXES:
            break
        rest = token[cut:]
        if (rest == word) if len(word) <= _SHORT_STEM else rest.startswith(word):
            return True
    return False


def term_in(term: str, title: str) -> bool:
    """מונח מופיע בכותרת - **בתחילת מילה, ומילה-מילה** (ש4).

    ארבעה כשלים שנמדדו באתר החי, כל אחד עם התאמה פשוטה יותר:
    - תת-מחרוזת: "מור" (מורים) ב"ח**מור**" - "מחסור **חמור** במוסכניקים"
      לנושא על מורים. ו**גם באורך 4**: "מורה" ב"הח**מורה**" - "מחסור
      בשופטים והפגיעה החמורה" חזר. בעברית אין מילים מורכבות, ולכן מונח
      אמיתי תמיד פותח מילה, אחרי אותיות שימוש (ו/ה/ב/ל/מ/ש/כ):
      "בפריפריה", "השוטרים", "והאלימות" - כן; "החמורה" - לא (ח אינה
      אות שימוש).
    - מונח של עד 3 אותיות: "תקנ" (תקנים) ב"ה**תקנ**ת מצלמות". כאן גם
      תחילת מילה אינה מספיקה - המילה חייבת להיות המונח עצמו ("בתקן").
    - כמה מילים: "בתי ספר" לא נמצא ב"בבתי **ה**ספר". כל מילה לחוד."""
    tokens = _HEB_WORD.findall(_norm_title(title))
    return all(any(_word_matches(w, tok) for tok in tokens)
               for w in _HEB_WORD.findall(_norm_title(term)))


def domain_match(title: str, domain: list[list[str]]) -> bool:
    """**כל תוצאה חייבת להכיל מונח מכל היבט של התחום** (ש4, 25.9.2026):
    הגוף או התחום, ומקום אם נקבו בו. תחום ריק = אין סינון (המודל לא
    זיהה גוף, או שההרחבה נכשלה).

    נמדד לפני התיקון: "מחסור בכוח אדם במשטרת ישראל" -> שלוש תוצאות,
    שלושתן על בריאות ("מחסור בכוח אדם רפואי במרכז הרפואי לגליל").
    הצירוף "מחסור בכוח" נכון מילולית - מה שחסר הוא הגוף. חייב להיות
    זהה ל-pqDomainMatch ב-static/app.js."""
    if not domain:
        return True
    return all(any(term_in(term, title) for term in facet) for facet in domain)


def _clean_facet(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for term in raw:
        if isinstance(term, str):
            term = _norm_title(term)
            # מונח של אות אחת תופס כל כותרת - אינו תחום.
            if len(term) >= 2 and term not in out:
                out.append(term)
    return out[:_DOMAIN_MAX]


def _clean_domain(raw) -> list[list[str]]:
    """עד שלושה היבטים (תופעה, גוף, מקום). המודל מחזיר לפעמים רשימה שטוחה
    של מחרוזות - זה היבט אחד, לא עשרים."""
    if not isinstance(raw, list) or not raw:
        return []
    if all(isinstance(x, str) for x in raw):
        raw = [raw]
    facets = [f for f in (_clean_facet(x) for x in raw) if f]
    return facets[:3]


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


_PLAN_CACHE_TTL = 6 * 3600
_plan_cache: dict[str, tuple[float, dict]] = {}


def expand_query(q: str) -> dict:
    """ראו _expand_query. **מטמון לפי נושא** (ש4): הפירוק הוא קריאת מודל,
    והוא משתנה מקריאה לקריאה - נמדד ש"תחבורה ציבורית בנגב" החזיר פעם
    תוצאה אחת ופעם ארבע, לפי אילו יישובים המודל מנה. בלי מטמון, "נסה שוב"
    ושני ביקורים באותו נושא נותנים תוצאות שונות. כשל אינו נשמר."""
    key = " ".join(q.split())
    hit = _plan_cache.get(key)
    if hit and time.time() - hit[0] < _PLAN_CACHE_TTL:
        return hit[1]
    plan = _expand_query(q)
    if plan.get("expanded"):
        _plan_cache[key] = (time.time(), plan)
        if len(_plan_cache) > _UNIT_CACHE_MAX:
            _plan_cache.pop(next(iter(_plan_cache)))
    return plan


def _expand_query(q: str) -> dict:
    """קריאת LLM אחת -> יחידות חיפוש, ממוינות לפי סגוליות (מספר מילים
    יורד, ואז סדר המודל: צירופים לפני נרדפות).

    **כשל בהרחבה אינו "לא נמצא".** אם הקריאה נכשלת חוזרים לחיפוש
    המילולי בדיוק כפי שהיה, ומסמנים `expanded=False` כדי שהממשק
    יאמר שההרחבה לא רצה - ולא יציג צמצום תוצאות כאילו זו המציאות."""
    q = q.strip()
    literal = {"units": [{"words": [q], "kind": "literal"}], "expanded": False, "domain": []}
    try:
        raw = draft(instructions=_EXPAND_SYSTEM, content=q, max_tokens=700).strip()
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
    domain = _clean_domain(parsed.get("domain"))
    # **שליפה לפי הגוף, סינון לפי התופעה** (ש4). עם שני היבטים ומעלה
    # מוסיפים את שני המונחים הראשונים של ההיבט השני כיחידות: כל כותרות
    # המשטרה ("שוטר", "משטר"), ומהן נשאר רק מה שיש בו גם מחסור. שתי
    # קריאות נוספות לפיד, והכיסוי כבר לא תלוי בניחוש הצירוף.
    if len(domain) >= 2:
        for term in domain[1][:2]:
            key = (term,)
            if " " not in term and len(term) >= 3 and key not in seen:
                seen.add(key)
                units.append({"words": [term], "kind": "domain"})
    units.sort(key=lambda u: -len(u["words"]))
    return {"units": units, "expanded": True, "domain": domain}


_current_knesset_cache: int | None = None


def current_knesset() -> int | None:
    """מספר הכנסת המכהנת, מתוך `KNS_KnessetDates.IsCurrent` (ב5).

    **ולא `max(KnessetNum)`, שהוא המלכודת כאן.** נמדד (22.9.2026):
    בפיד כבר יושבת שורה לכנסת ה-26 - אבל `PlenumStart` שלה הוא
    10.11.2026, כלומר היא טרם התכנסה, ו-`IsCurrent` שלה False.
    המקסימום היה מחזיר 26 ומסנן את כל התוצאות האמיתיות החוצה.
    השורה היחידה עם `IsCurrent=True` היא כנסת 25, מושב 4.

    **כשל אינו 25.** ערך קבוע היה נכון היום ושגוי בעוד חודשיים,
    בלי שאיש ישים לב. None אומר "לא ידוע", והקורא מחפש בלי סינון
    כנסת ואומר זאת."""
    global _current_knesset_cache
    if _current_knesset_cache:
        return _current_knesset_cache
    try:
        rows = fetch("KNS_KnessetDates", filter="IsCurrent eq true",
                     select="KnessetNum", top=5)
    except OdataError:
        return None
    nums = [r.get("KnessetNum") for r in rows if r.get("KnessetNum")]
    if not nums:
        return None
    _current_knesset_cache = max(nums)
    return _current_knesset_cache


def default_knesset_nums() -> list[int]:
    """ברירת המחדל לחיפוש: הכנסת הנוכחית והקודמת (ברק). נגזרת ולא
    קבועה - היום 25 ו-24, ובעוד חודשיים 26 ו-25."""
    current = current_knesset()
    return [current, current - 1] if current else []


# **מטמון לפי צירוף** (ש2, 25.9.2026). מאגר השאילתות משתנה לאט - אין
# סיבה לשאול את הפיד את אותו צירוף פעמיים באותו יום, וכל בקשה שנחסכת
# היא בקשה שלא נחסמת. בזיכרון התהליך: ב-Vercel מופע חם משרת בקשות
# רבות. מטמון משותף בדאטהבייס - אחרי ניקוי המקום (task 130).
_WAF_MAX_PARENS = 3   # ראו feed_filter: 4 סוגריים ומעלה -> 473 תמיד
_UNIT_CACHE_TTL = 6 * 3600
_UNIT_CACHE_MAX = 500
_unit_cache: dict[tuple, tuple[float, dict]] = {}


def feed_filter(words: list[str], knesset_nums: list[int] | None = None
                ) -> tuple[str, list[str], set[int] | None]:
    """המסנן שנשלח לפיד: (המסנן, המילים שנשלחו, כנסות לסינון מקומי או None).

    **ה-WAF של הכנסת סופר סוגריים** (ש4, 25.9.2026). נמדד על מטריצה
    של מספר מילים x צורת סינון הכנסת, כל תא בבקשה נפרדת בהפסקה:
    מסנן עם **4 סוגריים פותחים ומעלה -> HTTP 473 תמיד**; 3 ומטה ->
    עובר. זה מסביר את כל התצפיות: 4 contains() בלי כנסת נחסם (ש2);
    contains() אחד עם `(KnessetNum in (25,24))` נחסם; ו**כל צירוף של
    2-3 מילים עם סינון הכנסת של ברירת המחדל נחסם** - הסוגריים העוטפים
    `(... ) and (KnessetNum eq 25 or KnessetNum eq 24)` הוסיפו שניים.
    עד כאן זה מה שהמשתמש קיבל בכל חיפוש: רק צירופים של מילה אחת עברו
    (הרחבים, הרועשים), ו"מחסור בשוטרים" החזיר אפס. מדידת ש2 רצה בלי
    סינון כנסת ולכן לא ראתה את זה.

    ולכן: **בלי סוגריים עוטפים**, וכנסות כטווח `ge`/`le` (בלי סוגריים
    בכלל). כל contains() הוא סוגר אחד -> עד 3 מילים לפיד. בחירת כנסות
    לא רציפה (למשל 25 ו-23) נשלפת כטווח ומסוננת מקומית."""
    feed_words = sorted(words, key=len, reverse=True)[:_WAF_MAX_PARENS]
    parts = [f"contains(Name,'{escape(w)}')" for w in feed_words]
    keep: set[int] | None = None
    nums = sorted({int(n) for n in knesset_nums or []})
    if nums:
        lo, hi = nums[0], nums[-1]
        parts.append(f"KnessetNum eq {lo}" if lo == hi
                     else f"KnessetNum ge {lo} and KnessetNum le {hi}")
        if len(nums) != hi - lo + 1:
            keep = set(nums)
    return " and ".join(parts), feed_words, keep


def run_unit(words: list[str], *, top: int = 200, knesset_nums: list[int] | None = None) -> dict:
    """יחידת חיפוש אחת = קריאה אחת לפיד. **כל** מילות היחידה חייבות
    להופיע בכותרת (and, לא or) - זה מה שמונע את "מצוקת" לבדה.

    `contains` הוא תת-מחרוזת, ולכן מילה בצורת בסיס תופסת גם את הצורה
    המוטה: 'פריפריה' תופסת 'בפריפריה'. זו הסיבה שההנחיה מבקשת צורת
    בסיס - במקום רשימת תחיליות לקילוף, שהייתה שוברת מילים כמו "מורים"."""
    words = [w.strip() for w in words if w and w.strip()]
    if not words:
        return {"words": [], "rows": [], "count": 0}
    clause, feed_words, keep_knessets = feed_filter(words, knesset_nums)
    cache_key = (tuple(words), tuple(sorted(knesset_nums or [])), top)
    cached = _unit_cache.get(cache_key)
    if cached and time.time() - cached[0] < _UNIT_CACHE_TTL:
        return cached[1]
    # ניסיון חוזר רק על 473, ועד שלוש פעמים. **473 נגרם מהתוכן** (ראו
    # feed_filter) ואחרי התיקון לא אמור להופיע; הניסיון נשאר כרשת ביטחון.
    # **474 אינו מנוסה שוב** - זו חסימת כתובת, וכל ניסיון חוזר רק מחמיר
    # אותה (odata.FeedBlockedError, המפסק שם).
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
        except FeedBlockedError:
            raise
        except OdataError as e:
            if attempt == 2 or "473" not in str(e):
                raise
            time.sleep(0.5 * 2 ** attempt + random.uniform(0, 0.4))
    if keep_knessets is not None:
        rows = [r for r in rows if r.get("KnessetNum") in keep_knessets]
    # contains בפיד הוא על-קבוצה: המילים שלא נשלחו (מעל 3), וגזע קצר
    # שנמצא באמצע מילה ("מור" ב"חמור") - נבדקים כאן, מקומית.
    rows = [r for r in rows if all(term_in(w, r.get("Name") or "") for w in words)]
    result = {
        "words": words,
        "count": len(rows),
        "too_broad": len(rows) > GENERIC_CAP,
        "rows": [{
            "query_id": r["Id"],
            "page_url": page_url(r["Id"]),
            "title": r.get("Name"),
            "kind": r.get("TypeDesc"),
            "knesset": r.get("KnessetNum"),
            "submitted_at": display_date(r.get("SubmitDate")),
            "person_id": r.get("PersonID"),
        } for r in rows],
    }
    _unit_cache[cache_key] = (time.time(), result)
    if len(_unit_cache) > _UNIT_CACHE_MAX:
        _unit_cache.pop(next(iter(_unit_cache)))   # הישן ביותר
    return result


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


_gender_cache: tuple[float, dict[str, set[str]]] | None = None
_GENDER_TTL = 24 * 3600


def mk_gender(full_name: str) -> str | None:
    """"זכר"/"נקבה" מ-`KNS_Person.GenderDesc` לפי **התאמה מדויקת של השם
    המלא** בין המכהנים (ש1, 25.9.2026) - לשורת "חבר/חברת הכנסת X
    שאל/שאלה" בקובץ השאילתה.

    **לא מסיקים מגדר מהשם.** אין התאמה, יש שתי התאמות במגדר שונה, או
    שהפיד לא זמין -> None, והקובץ כותב את הצורה הכפולה. קריאה אחת
    לפיד ליום (כל המכהנים, בעימוד), לא קריאה לכל ייצוא."""
    global _gender_cache
    name = " ".join((full_name or "").split())
    if not name:
        return None
    if not _gender_cache or time.time() - _gender_cache[0] > _GENDER_TTL:
        try:
            rows = fetch("KNS_Person", filter="IsCurrent eq true",
                         select="FirstName,LastName,GenderDesc")
        except OdataError:
            return None
        by_name: dict[str, set[str]] = {}
        for r in rows:
            full = " ".join(f"{r.get('FirstName') or ''} {r.get('LastName') or ''}".split())
            if full and r.get("GenderDesc") in ("זכר", "נקבה"):
                by_name.setdefault(full, set()).add(r["GenderDesc"])
        _gender_cache = (time.time(), by_name)
    found = _gender_cache[1].get(name, set())
    return next(iter(found)) if len(found) == 1 else None


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


def page_url(query_id: int | None) -> str | None:
    """דף השאילתה באתר הכנסת. ללא מזהה - אין קישור, ולא קישור שבור."""
    return f"https://m.knesset.gov.il/apps/query/details/{query_id}" if query_id else None


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
    # התחום (ש4): שורה שאינה מכילה אף מונח מהתחום לא נספרת ולא מוצגת.
    # המכסה נקבעת לפי מה שנשאר - "זיהום אוויר" (116) אחרי סינון לחיפה
    # הוא צירוף צר ומדויק, לא רחב.
    domain = plan.get("domain") or []
    if domain:
        units = [{**u, "rows": [r for r in u["rows"] if domain_match(r.get("title"), domain)]}
                 for u in units]
        units = [{**u, "count": len(u["rows"])} for u in units]

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
        # צירוף רחב (מעל GENERIC_CAP) מדרג בלבד - **אלא אם יש תחום**: אחרי
        # הסינון לתחום הוא כבר צר ("תחבורה ציבורית" + יישובי הנגב), ורק כך
        # נמצאו כסיפה ותל שבע, שכותרותיהן אינן אומרות "נגב".
        # **שני היבטים ומעלה = כל שורה נבדקת על שני צירים בלתי תלויים**
        # (תופעה + גוף), ולכן גם מילה בודדת ("שוטר") רשאית לספק שורות:
        # כל כותרות המשטרה, ומהן רק מה שיש בו מחסור. כך ההתאמה לא תלויה
        # בכך שהמודל ניחש את הצירוף המדויק - נמדד שבאותו נושא הוא מצא את
        # "חוסר תקנים משטרתיים" בהרצה אחת ולא בשנייה.
        strict = len(domain) >= 2
        if not strict and (u["too_broad"] and not domain or _is_single_word(u["words"])):
            continue
        budget = unit_budget(u["count"])
        broad = u["count"] > HOLD_ABOVE
        used = 0
        for row in u["rows"]:
            if row["query_id"] in taken:
                continue
            row = {**row, "matched": rank[row["query_id"]], "matched_by": " ".join(u["words"]),
                   "unit_count": u["count"], "broad": broad}
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
    # ואז הזנב - עד ארבע שורות שהתאימו לצירוף אחד בלבד, מהצירוף הצר
    # ביותר. **שורה של צירוף רחב אינה נכנסת לזנב**: מצירוף רחב מוצג
    # רק מה שהצטלב, ולא התאמה בודדת שאינה מלמדת דבר.
    tail = 0
    for row in sorted(held, key=lambda r: r["unit_count"]):
        if row["broad"] or row["matched"] >= 2 or row["query_id"] in taken \
                or tail >= MAX_RANK1_ROWS:
            continue
        if len(chosen) >= MAX_ROWS:
            break
        taken.add(row["query_id"])
        chosen.append(row)
        tail += 1

    chosen = chosen[:limit] if limit else chosen
    extra = enrich([r["query_id"] for r in chosen], [r["person_id"] for r in chosen])
    for r in chosen:
        r["page_url"] = page_url(r["query_id"])
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
            "expanded": plan["expanded"], "domain": domain}


__all__ = ["FeedBlockedError", "OdataError", "current_knesset", "default_knesset_nums",
           "domain_match", "enrich", "mk_gender", "expand_query", "feed_filter", "page_url", "run_unit",
           "search_queries", "unit_budget"]
