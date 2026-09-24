"""חיפוש חוקים לפי שם - התאמת טקסט חופשי על `full_title`, פונקציה
טהורה (משימה A, ברק 2026-09-14 - "בכל סדר שנוח לך" מתוך סדר העבודה
הלילי). לא תלויה במקור הנתונים (DB/fixture) - מקבלת רשימת חוקים
מוכנה, כדי שתהיה ניתנת לבדיקה בלי חיבור רשת/DB.

**נורמליזציה משתמשת בתשתית הקיימת, לא כפילות:** `text_normalize.
normalize_text` (מרכאות/מקפים) + `knesset_odata.strip_matres_lectionis`
(ו/י כאימות קריאה) - אותה לוגיקה בדיוק ששימשה להתאמת שם מול KNS
(ראו TASKS.md משימה 7). כדי שכתיב "תקנות" מול "תקנת" (למשל) לא
ימנע התאמה, בלי לבנות מנגנון נורמליזציה שני נפרד."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knesset_odata import strip_matres_lectionis  # noqa: E402
from text_normalize import normalize_text  # noqa: E402

# דירוג תוצאה - מספר נמוך יותר = התאמה חזקה יותר, ראו _rank.
_RANK_EXACT = 0
_RANK_PREFIX = 1
_RANK_SUBSTRING = 2
_RANK_ALL_TOKENS = 3
_RANK_COMPACT = 4


# **ה"א הידיעה בשנה העברית.** ויקיטקסט כותב "חוק העונשין, תשל\"ז-1977"
# והכנסת (וכל הצעת חוק אמיתית) כותבת "התשל\"ז". נמדד 23.9.2026: עשרה
# מתוך 23 החוקים שהצעות אמיתיות מתקנות לא נמצאו בקורפוס **רק** בגלל
# ההפרש הזה - ובהם חוק העונשין, חוק התכנון והבניה וחוק הבחירות לכנסת.
# הנורמליזציה מורידה את ה"א מצורת השנה בשני הצדדים, ולכן רק מוסיפה
# התאמות ואינה מבטלת אף אחת.
_YEAR_HE = re.compile(r"(?<![א-ת])ה(ת[א-ת]{0,3}\")")


# **מקף בין מילים = רווח** (ח6, 25.9.2026). השם הרשמי הוא "חוק-יסוד:
# הכנסת" והמשתמש מקליד "חוק יסוד: הכנסת" - אפס תוצאות. נמדד: 16 חוקי
# יסוד, ו-59 שמות חוקים בסך הכול עם מילה מקופת (ארץ-ישראל, בין-לאומי,
# בן-גוריון, קופת-חולים, שעת-חירום). מקף עברי (־) כבר הופך ל-"-"
# ב-normalize_text. רק מקף **בין שתי אותיות** - ה-en-dash של השנה
# ("התשנ"ד–1994") ומספרים לא נוגעים.
_WORD_HYPHEN = re.compile(r"(?<=[א-ת])-(?=[א-ת])")
# נקודתיים, נקודה-פסיק ופסיק - מפרידים ולא חלק מהשם לצורך חיפוש.
_SEPARATORS = re.compile(r"[:;,]")
_FINALS = str.maketrans("ךםןףץ", "כמנפצ")


def normalize_for_search(text: str) -> str:
    n = normalize_text(text)
    # **המקף מומר לפני הסרת אמות הקריאה, לא אחרי.** strip_matres_
    # lectionis מסירה י/ו רק באמצע מילה - ו"יסוד" שאחרי מקף נחשבה
    # אמצע מילה: "חוק-יסוד" -> "חק-סד" (הי' הראשונה נמחקה), מול
    # "חוק יסוד" -> "חק יסד". זו הסיבה האמיתית לאפס התוצאות, ולא רק
    # ההבדל בין מקף לרווח.
    n = _WORD_HYPHEN.sub(" ", n)
    n = _SEPARATORS.sub(" ", n)
    n = strip_matres_lectionis(n)
    n = _YEAR_HE.sub(r"\1", n)
    return re.sub(r"\s+", " ", n).strip()


def _compact(norm: str) -> str:
    """בלי רווחים ובלי אותיות סופיות: "בינלאומית" מול "בין-לאומית"
    (שנבדלים גם ב-ן/נ). שכבת התאמה אחרונה, לא תחליף לשאר."""
    return norm.replace(" ", "").translate(_FINALS)


def _rank(query_norm: str, title_norm: str, query_tokens: list[str]) -> int | None:
    """None = אין התאמה כלל."""
    if title_norm == query_norm:
        return _RANK_EXACT
    if title_norm.startswith(query_norm):
        return _RANK_PREFIX
    if query_norm in title_norm:
        return _RANK_SUBSTRING
    if query_tokens and all(tok in title_norm for tok in query_tokens):
        return _RANK_ALL_TOKENS
    compact_q = _compact(query_norm)
    if len(compact_q) >= 4 and compact_q in _compact(title_norm):
        return _RANK_COMPACT
    return None


def search_laws(query: str, laws: list[dict], limit: int = 20) -> list[dict]:
    """מחפשת בין `laws` (כל אחד dict עם לפחות "id" ו-"title") לפי
    התאמת טקסט חופשי ל-"title" (בפועל: full_title). מחזירה תת-רשימה
    מדורגת (query ריק/כולו רווחים -> רשימה ריקה, לא "הכול תואם").

    דירוג (מהחזק לחלש): התאמה מדויקת (אחרי נורמליזציה) > הכותרת
    מתחילה ב-query > ה-query מופיע כתת-מחרוזת בכותרת > כל מילות
    ה-query (מופרדות ברווח) מופיעות בכותרת, בכל סדר. שוויון דירוג -
    לפי אורך כותרת (קצרה יותר = ספציפית יותר), ואז אלפביתי, לשמור
    על סדר דטרמיניסטי."""
    query_norm = normalize_for_search(query)
    if not query_norm:
        return []
    query_tokens = [t for t in query_norm.split(" ") if t]

    scored: list[tuple[int, int, str, dict]] = []
    for law in laws:
        title = law.get("title") or ""
        title_norm = normalize_for_search(title)
        rank = _rank(query_norm, title_norm, query_tokens)
        if rank is not None:
            # באותה דרגה: כותרת שבה כל מילות החיפוש הן **מילים שלמות**
            # קודמת. "חוק יסוד" - חוקי היסוד לפני "חוק יסודות המשפט",
            # שבו "יסוד" הוא רק תחילת מילה.
            words = set(title_norm.split(" "))
            partial = not all(tok in words for tok in query_tokens)
            scored.append((rank, partial, len(title_norm), title_norm, law))

    scored.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    return [law for *_, law in scored[:limit]]


# שם פומבי לשכבות שצריכות להשוות שם-חוק לכותרת בקורפוס באותה
# נורמליזציה בדיוק (apps/api/amended_law.py, בדיקה 1 על מסמך שהועלה).
_normalize_for_search = normalize_for_search
