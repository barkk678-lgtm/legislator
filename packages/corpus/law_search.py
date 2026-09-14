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


def _normalize_for_search(text: str) -> str:
    n = normalize_text(text)
    n = strip_matres_lectionis(n)
    return re.sub(r"\s+", " ", n).strip()


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
    query_norm = _normalize_for_search(query)
    if not query_norm:
        return []
    query_tokens = [t for t in query_norm.split(" ") if t]

    scored: list[tuple[int, int, str, dict]] = []
    for law in laws:
        title = law.get("title") or ""
        title_norm = _normalize_for_search(title)
        rank = _rank(query_norm, title_norm, query_tokens)
        if rank is not None:
            scored.append((rank, len(title_norm), title_norm, law))

    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    return [law for _, _, _, law in scored[:limit]]
