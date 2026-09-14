"""רישום החוקים הזמינים למשימה 10 - שני fixtures בלבד, בלי ingest
מרשת. ראו TASKS.md משימה 10.

amendable מחושב, לא מוצהר: amend() (packages/amend/engine.py) מחפש
סעיפים רק ב-before.children הישירים (node_type=="section") - לא יורד
רקורסיבית לתוך פרק/סימן. חוק מאבק בארגוני פשיעה בנוי בפרקים (כל
הסעיפים מקוננים תחת chapter) - amend() לא היה זורק שגיאה, רק מחזיר
lines=[] בשקט (אין אף סעיף ב-before.children). זה בדיוק סוג הכשל
השקט שהפרויקט נמנע ממנו בכל מקום אחר, אז זה נבדק כאן במפורש כדי
שה-UI יחסום את זרימת התיקון בהודעה ברורה - לא יתקן את amend() (זה
שינוי היקף אמיתי שדורש מקרה זהב משלו, לא חלק ממשימה 10).
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))
from law_search import search_laws  # noqa: E402
from node import LegislativeNode  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "wikitext"


@dataclass
class LawConfig:
    id: str  # law_id שמועבר ל-parse_wikitext, ומשמש כמזהה ה-URL
    slug: str  # שם קובץ ה-fixture תחת tests/fixtures/wikitext/
    footnote_key: str  # מפתח הערת השוליים לחוק עצמו (בטבלת refs)
    known_source_ref: str | None  # מראה מקום ידוע (ס"ח); None = המשתמש מזין


LAWS: dict[str, LawConfig] = {
    "kaytanot-1990": LawConfig(
        id="kaytanot-1990",
        slug="kaytanot",
        footnote_key="kaytanot",
        known_source_ref='ס"ח התש"ן, עמ\' 155.',
    ),
    "maavak-2003": LawConfig(
        id="maavak-2003",
        slug="maavak-birgunei-plisha",
        footnote_key="maavak",
        known_source_ref=None,
    ),
}


def _is_amendable(root: LegislativeNode) -> bool:
    return any(c.node_type == "section" for c in root.children)


def load_law(law_id: str) -> LegislativeNode:
    """טוענת ומפרסרת מחדש בכל קריאה - שני חוקים קטנים, בלי צורך
    במטמון עבור כלי מקומי יחיד-משתמש."""
    cfg = LAWS[law_id]
    text = (FIXTURES / f"{cfg.slug}.wikitext").read_text(encoding="utf-8")
    meta = json.loads((FIXTURES / f"{cfg.slug}.meta.json").read_text(encoding="utf-8"))
    return parse_wikitext(text, law_id=cfg.id, as_of=meta["revision_timestamp"])


def law_summaries() -> list[dict]:
    summaries = []
    for law_id, cfg in LAWS.items():
        root = load_law(law_id)
        summaries.append(
            {
                "id": law_id,
                "title": root.full_title or law_id,
                "amendable": _is_amendable(root),
                "known_source_ref": cfg.known_source_ref,
            }
        )
    return summaries


def search_law_titles(query: str, limit: int = 20) -> list[dict]:
    """חיפוש שם-חוק (משימה A, ברק 2026-09-14) - שכבה דקה מעל
    law_search.search_laws (הלוגיקה הטהורה, נבדקת בנפרד ב-
    tests/unit/test_law_search.py).

    **מקור הנתונים כרגע: `LAWS` (שני fixtures בלבד) - כמו כל שאר
    apps/api היום, לא הקורפוס המלא ב-Supabase.** חיפוש על הקורפוס
    המלא (998 חוקים) דורש חיבור Postgres אמיתי (`psycopg` +
    `DATABASE_URL`) - בדיוק כפי שתועד מראש ב-db_ingest.py ("בעתיד
    (ingest מתוזמן, משימה 7) דרך psycopg + DATABASE_URL אמיתי").
    זו תלות חדשה שלא הותקנה הלילה (הוראה מפורשת - ראו docs/night-
    report.md). **כדי לחבר בעתיד:** להחליף את `law_summaries()`
    כמקור הרשומות ב-שאילתת `select id, full_title as title from
    laws` אמיתית - `search_laws` עצמה לא משתנה (מקבלת כל רשימת
    dicts עם id/title)."""
    laws = [{"id": s["id"], "title": s["title"]} for s in law_summaries()]
    return search_laws(query, laws, limit=limit)
