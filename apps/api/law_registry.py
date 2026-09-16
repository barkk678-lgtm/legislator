"""רישום החוקים הזמינים - שכבת שליפה (ברק, 2026-09-16: "כתוב את קוד
ה-httpx"). ראו TASKS.md משימה 10.

**שכבת שליפה נפרדת מהפרסור, במכוון (ברק, 2026-09-16, דרישה 1):**
שני חוקי ה-fixture (kaytanot-1990, maavak-2003) ממשיכים להיטען מקובץ
+ `parse_wikitext` בדיוק כמו קודם - בלי שום תלות ברשת/ב-Supabase.
כל חוקי ה-DB (1,093 בקורפוס - כולל 94 הפקודות/דברי המלך מהערב)
נטענים כ-עץ מוכן-בנוי מטבלת `nodes` דרך REST (PostgREST) - **לא
עובר פרסור מחדש** (הוויקיטקסט כבר פורסר פעם אחת ב-ingest; הקריאה
כאן היא שחזור עץ ממודל שורות שטוחות, לוגיקה שונה לגמרי מ-
wikitext_parser.py). שני הנתיבים לא חולקים קוד, ולכן טסטים שרצים
על fixtures לא נוגעים ב-DB בכלל, אפילו בעקיפין.

**משתני סביבה (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) - נקראים
רק כשקוד DB-מכוון נקרא בפועל, לא בייבוא המודול** (כדי שהמודול ייבא
נקי גם כש-Supabase לא מוגדר בכלל - מצב תקין ב-dev/test, לא שגיאה).
**אבל אם קוד DB-מכוון כן נקרא וחסר משתנה - שגיאה ברורה ומיידית
(RuntimeError עם שם המשתנה החסר), לפני כל קריאת רשת** - לא נכשל
באמצע בניית תשובה עם שגיאת httpx מבלבלת (ברק: "לא כישלון שקט
באמצע בקשה"). service_role משמש אך ורק כאן בצד השרת - אף פעם לא
חוזר ללקוח (לא מופיע בשום JSON שה-API מחזיר).

**עימוד (pagination) - קריטי, לא אופציונלי:** PostgREST מגביל
תוצאת ברירת מחדל ל-1,000 שורות. נבדק בפועל (2026-09-16): חוק
העונשין (2,682 nodes) חוזר **חתוך ל-1,000 בלי שגיאה** בלי עימוד -
כשל שקט שהיה מייצר עץ תקין-למראה אבל חסר 60% מהתוכן. `_fetch_all_pages`
למטה מטפל בזה תמיד, לא רק ל"חוקים גדולים".

**amendable מחושב בזול, לא בבניית-עץ-מלא לכל חוק:** law_summaries()
צריך amendable ל-1,093 חוקים בלי לשלוף nodes.text של כולם (יקר
מיותר - השדה הזה משמש רק לדגל בוליאני). שאילתה אחת נגד ה-view
`amendable_law_ids` ב-DB (לא בונה עץ) - **תוקן (2026-09-16, ברק:
"42.3% מהקורפוס לא ניתן לעריכה... זה חור בלב המוצר"):** עד אז ה-view
בדק רק `parent_id = שורש החוק` (ילד ישיר), אותה מגבלה צרה בדיוק כמו
`_is_amendable`/`amend()` - חוק עם מבנה חלק/פרק/סימן (20 החוקים
הגדולים בקורפוס, בלי יוצא מן הכלל - תכנון ובניה, ביטוח לאומי,
העונשין...) יצא "לא amendable" בטעות. ה-view עודכן (migration
`20260916140000_amendable_law_ids_recursive.sql`) לבדוק "יש לחוק
לפחות צומת section אחד עם numbering_space='law', בכל עומק" - תואם
בדיוק את `node.find_sections`/`_is_amendable` החדשים.

amendable מחושב, לא מוצהר: `_is_amendable` למטה משתמשת ב-
`node.find_sections` (רקורסיבי, בכל עומק, מסונן ל-numbering_
space="law" - כדי לא לספור סעיפי תוספת/לוח-השוואה) - אותה שאלה
בדיוק ש-`amend()`/`transform.py`/`insert_preview.py` עונות עליה
עכשיו. חוק בלי אף סעיף בכלל (למשל חוק התקשורת (שידורים) - קפוא
בצו ארעי של בג"ץ, ראו TASKS.md משימה 7) עדיין לא-amendable, בצדק -
זה מצב אמיתי, לא פער בקוד.
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))
from law_search import search_laws  # noqa: E402
from node import LegislativeNode, find_sections  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "wikitext"


class LawNotFoundError(Exception):
    """נזרקת מ-load_law כשה-law_id לא קיים לא ב-fixtures ולא ב-DB.
    main.py תופס אותה והופך ל-HTTPException(404) - מקור אמת יחיד
    ל"קיים?" (במקום בדיקת חברות נפרדת ב-dict לפני הטעינה)."""


@dataclass
class LawConfig:
    id: str  # law_id שמועבר ל-parse_wikitext, ומשמש כמזהה ה-URL
    footnote_key: str  # מפתח הערת השוליים לחוק עצמו (בטבלת refs)
    known_source_ref: str | None  # מראה מקום ידוע (ס"ח); None = לא ידוע


# שני חוקי ה-fixture - ראו הדוקסטרינג העליון: נתיב טעינה נפרד מה-DB,
# לא נוגע ברשת בכלל. slug = שם קובץ תחת tests/fixtures/wikitext/.
_FIXTURE_SLUGS: dict[str, str] = {
    "kaytanot-1990": "kaytanot",
    "maavak-2003": "maavak-birgunei-plisha",
}
FIXTURE_LAWS: dict[str, LawConfig] = {
    "kaytanot-1990": LawConfig(
        id="kaytanot-1990",
        footnote_key="kaytanot",
        known_source_ref='ס"ח התש"ן, עמ\' 155.',
    ),
    "maavak-2003": LawConfig(
        id="maavak-2003",
        footnote_key="maavak",
        known_source_ref=None,
    ),
}


def _is_amendable(root: LegislativeNode) -> bool:
    return bool(find_sections(root))


def _load_fixture_law(law_id: str) -> LegislativeNode:
    slug = _FIXTURE_SLUGS[law_id]
    text = (FIXTURES / f"{slug}.wikitext").read_text(encoding="utf-8")
    meta = json.loads((FIXTURES / f"{slug}.meta.json").read_text(encoding="utf-8"))
    return parse_wikitext(text, law_id=law_id, as_of=meta["revision_timestamp"])


# ---------------------------------------------------------------------------
# שכבת DB (REST/PostgREST) - כל הגישה ל-Supabase מרוכזת כאן.
# ---------------------------------------------------------------------------


def _supabase_config() -> tuple[str, str]:
    """קוראת את שני משתני הסביבה. נכשלת ברעש ומיידית אם חסר אחד -
    ראו הדוקסטרינג העליון להסבר למה זה קורה כאן ולא בייבוא המודול."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    missing = [name for name, val in [("SUPABASE_URL", url), ("SUPABASE_SERVICE_ROLE_KEY", key)] if not val]
    if missing:
        raise RuntimeError(
            "חסרים משתני סביבה נדרשים לחיבור לקורפוס המלא: "
            + ", ".join(missing)
            + ". בלי אלה אין גישה אלא לשני חוקי ה-fixture."
        )
    return url.rstrip("/"), key


def _supabase_client() -> httpx.Client:
    url, key = _supabase_config()
    return httpx.Client(
        base_url=f"{url}/rest/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
        timeout=30.0,
    )


def _fetch_all_pages(client: httpx.Client, path: str, params: dict, page_size: int = 1000) -> list[dict]:
    """שליפה עם עימוד מלא - ראו הדוקסטרינג העליון: PostgREST חותך
    ל-1,000 שורות בלי שגיאה בלי זה. ממשיכה עד שעמוד חוזר קטן מ-page_size
    (כולל 0 - סוף)."""
    rows: list[dict] = []
    offset = 0
    while True:
        page_params = dict(params, limit=str(page_size), offset=str(offset))
        resp = client.get(path, params=page_params)
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def _db_law_summaries() -> list[dict]:
    with _supabase_client() as client:
        laws_rows = _fetch_all_pages(
            client, "/laws",
            {"select": "id,full_title,law_versions!laws_current_version_fk(source_ref)",
             "current_version_id": "not.is.null"},
        )
        # amendable_law_ids: view ב-DB (לא שאילתה על nodes ישירות מכאן) -
        # DISTINCT על 45K+ צמתי section, מסונן ל-parent_id שהוא שורש חוק
        # בעצמו, מחושב פעם אחת ב-Postgres. בלי זה: שליפת parent_id גולמי
        # מ-nodes נמדדה בפועל ב-30 שניות ל-GET /api/laws (2026-09-16) -
        # לא סביר לרשימת חוקים. ראו migration
        # 20260916130000_fix_amendable_law_ids_view_scope_to_roots.
        amendable_rows = _fetch_all_pages(client, "/amendable_law_ids", {"select": "law_id"})
    section_parents = {row["law_id"] for row in amendable_rows}

    summaries = []
    for row in laws_rows:
        source_ref = (row.get("law_versions") or {}).get("source_ref") or None
        summaries.append(
            {
                "id": row["id"],
                "title": row["full_title"] or row["id"],
                "amendable": row["id"] in section_parents,
                "known_source_ref": source_ref,
            }
        )
    return summaries


def _fetch_db_law_id(law_id: str) -> int | None:
    """מחזירה current_version_id אם law_id קיים ב-DB עם גרסה נוכחית,
    אחרת None (לא קיים / עדיין לא הושלמה טעינתו - ראו replace_law_version)."""
    with _supabase_client() as client:
        resp = client.get(
            "/laws",
            params={
                "id": f"eq.{law_id}",
                "select": "full_title,law_versions!laws_current_version_fk(id,source_ref,as_of)",
            },
        )
        resp.raise_for_status()
        rows = resp.json()
    if not rows or rows[0].get("law_versions") is None:
        return None
    return rows[0]


def _build_tree_from_rows(rows: list[dict]) -> LegislativeNode:
    """משחזרת עץ LegislativeNode ממודל שורות שטוח (law_version_id
    קבוע לכל השורות - כבר סונן לפני הקריאה). **לא פרסור** - הוויקיטקסט
    כבר פורסר פעם אחת ב-ingest; זו רק הרכבת אותו עץ מחדש מ-parent_id."""
    nodes_by_id: dict[str, LegislativeNode] = {}
    children_ids: dict[str, list[tuple[int, str]]] = {}
    root_id = None

    for row in rows:
        node = LegislativeNode(
            id=row["id"],
            node_type=row["node_type"],
            number=row["number"] or "",
            margin_title=row["margin_title"],
            margin_title_raw=row["margin_title_raw"],
            text=row["text"] or "",
            text_raw=row["text_raw"] or "",
            is_normative=row["is_normative"],
            status=row["status"],
            numbering_space=row["numbering_space"],
            raw_amendment_note=row["raw_amendment_note"],
        )
        nodes_by_id[row["id"]] = node
        if row["parent_id"] is None:
            root_id = row["id"]
        else:
            children_ids.setdefault(row["parent_id"], []).append((row["raw_order"], row["id"]))

    if root_id is None:
        raise ValueError("לא נמצא צומת שורש (parent_id=NULL) בקבוצת השורות")

    for parent_id, ordered in children_ids.items():
        parent = nodes_by_id.get(parent_id)
        if parent is None:
            continue  # לא אמור לקרות (FK מאכוף) - מוגן מוגזם, לא נחשב לשגיאה
        parent.children = [nodes_by_id[child_id] for _, child_id in sorted(ordered)]

    return nodes_by_id[root_id]


def _load_db_law(law_id: str) -> LegislativeNode:
    law_row = _fetch_db_law_id(law_id)
    if law_row is None:
        raise LawNotFoundError(law_id)
    version = law_row["law_versions"]

    with _supabase_client() as client:
        node_rows = _fetch_all_pages(
            client, "/nodes",
            {"law_version_id": f"eq.{version['id']}",
             "select": "id,parent_id,raw_order,node_type,number,margin_title,margin_title_raw,"
                       "text,text_raw,is_normative,status,numbering_space,raw_amendment_note"},
        )

    root = _build_tree_from_rows(node_rows)
    root.full_title = law_row["full_title"]
    root.source_ref = version.get("source_ref") or ""
    root.as_of = version.get("as_of")
    return root


# ---------------------------------------------------------------------------
# ממשק ציבורי - נקרא מ-main.py
# ---------------------------------------------------------------------------


def load_law(law_id: str) -> LegislativeNode:
    """טוענת ומפרסרת/משחזרת מחדש בכל קריאה - אין מטמון בשרת (העיקרון
    "אין state בשרת" ב-main.py חל גם כאן). מזהה fixture או DB לפי
    id בלבד - law_id-ים אמיתיים תמיד מהצורה "law-<מספר>", אף fixture
    לא בצורה הזו, כך שאין דו-משמעות."""
    if law_id in FIXTURE_LAWS:
        return _load_fixture_law(law_id)
    return _load_db_law(law_id)


def get_law_config(law_id: str, root: LegislativeNode) -> LawConfig:
    """מראה מקום/footnote_key - ל-fixtures מגיע מ-FIXTURE_LAWS (לא
    השתנה); לחוקי DB, footnote_key=law_id (כבר ייחודי גלובלית) ו-
    known_source_ref מגיע מ-root.source_ref שכבר מולא ב-_load_db_law
    (ריק/None עבור רוב הקורפוס כרגע - משימה 8, מראי מקום, טרם מומשה;
    הוולידטור יתריע במפורש על כך, לא ננחש ערך)."""
    if law_id in FIXTURE_LAWS:
        return FIXTURE_LAWS[law_id]
    return LawConfig(id=law_id, footnote_key=law_id, known_source_ref=root.source_ref or None)


# מטמון 15 דקות ל-law_summaries() בלבד (ברק, 2026-09-16) - "רשימת
# 1,093 השמות היא נתון שמשתנה פעם ביום אחרי ingest, לא בכל בקשה...
# זה לא state של משתמש, זה נתון קבוע." load_law() לא נוגע בזה בכלל -
# נשאר תמיד טעינה טרייה. תא בזיכרון-תהליך בלבד: ב-Vercel כל cold
# start מתחיל מטמון ריק מחדש - לא בעיה, רק אומר שהמטמון "עוזר" בעיקר
# בתוך instance חם, לא ערובה גלובלית.
_SUMMARIES_CACHE: dict = {"data": None, "fetched_at": 0.0}
_SUMMARIES_CACHE_TTL_SECONDS = 15 * 60


def law_summaries() -> list[dict]:
    """שני ה-fixtures תמיד מופיעים (dev/test offline). חוקי ה-DB
    מתווספים **רק אם Supabase מוגדר** - זה מצב תקין (למשל dev מקומי
    בלי DB), לא שגיאה: הרשימה היא "מה זמין", לא ניסיון-חובה לגעת
    ב-DB. לעומת זאת load_law() על law_id ספציפי-ל-DB בלי env מוגדר
    כן נכשל ברעש (ראו _supabase_config) - שם יש כוונה מפורשת לגשת
    ל-DB, כאן זו רק שאלת-זמינות."""
    now = time.monotonic()
    cached = _SUMMARIES_CACHE["data"]
    if cached is not None and (now - _SUMMARIES_CACHE["fetched_at"]) < _SUMMARIES_CACHE_TTL_SECONDS:
        return cached

    summaries = [
        {
            "id": law_id,
            "title": (root := _load_fixture_law(law_id)).full_title or law_id,
            "amendable": _is_amendable(root),
            "known_source_ref": cfg.known_source_ref,
        }
        for law_id, cfg in FIXTURE_LAWS.items()
    ]
    try:
        summaries.extend(_db_law_summaries())
    except RuntimeError:
        pass  # Supabase לא מוגדר - מצב תקין, ראו דוקסטרינג

    _SUMMARIES_CACHE["data"] = summaries
    _SUMMARIES_CACHE["fetched_at"] = now
    return summaries


def search_law_titles(query: str, limit: int = 20) -> list[dict]:
    """חיפוש שם-חוק (משימה A) - שכבה דקה מעל law_search.search_laws
    (הלוגיקה הטהורה, נבדקת בנפרד ב-tests/unit/test_law_search.py).
    מריץ על law_summaries() המלא (fixtures + DB אם מוגדר) - 1,093
    כותרות קצרות זה חיפוש-טקסט-בזיכרון זניח, לא צוואר בקבוק.

    **amendable מועבר הלאה (2026-09-16)** - חייב, כי ה-autocomplete
    בצד הלקוח מציג/חוסם לפי השדה הזה על תוצאת החיפוש עצמה, בלי
    לשלוף שוב את הרשימה המלאה. search_laws מחזירה בדיוק את ה-dict
    שקיבלה (ראו law_search.py) - אם לא מעבירים amendable כאן, הוא
    פשוט נעלם מהתשובה."""
    laws = [{"id": s["id"], "title": s["title"], "amendable": s["amendable"]} for s in law_summaries()]
    return search_laws(query, laws, limit=limit)
