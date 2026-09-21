"""FastAPI - שכבה דקה בלבד מעל packages/amend, packages/render,
packages/validate הקיימים, ומעל diff_translate.py/insert_preview.py/
apply_changes.py (משימה 10ב - עריכה חופשית). ראו TASKS.md משימה 10ב.

חוק ברזל: אין כאן שום לוגיקה משפטית ואין לוגיקת תצוגה - כל endpoint
הוא "פרסר בקשה -> קריאה לפונקציה טהורה קיימת -> סריאליזציה של התוצאה".
אין state בשרת: הלקוח שולח בכל בקשה את מלוא מצבו (edits+insertions),
ולכן גם "ייצוא זמין תמיד" הוא פשוט אותה בקשה בדיוק, ל-endpoint אחר.

הרצה: pip install -r requirements.txt, ואז מהתיקייה הזו -
uvicorn main:app --reload - ואז http://127.0.0.1:8000/
"""

import dataclasses
import io
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "validate"))
from bill_title import default_bill_title  # noqa: E402
from embeddings import EmbeddingConfigError, EmbeddingRequestError, embed_one  # noqa: E402
from engine import amend  # noqa: E402
from node import LegislativeNode, find_sections  # noqa: E402
from render_bill import Bill, write_docx  # noqa: E402
from validator import validate  # noqa: E402

from apply_changes import apply_pending_changes  # noqa: E402
from explanatory_draft import draft_explanatory_notes  # noqa: E402
from insert_preview import preview_insertion_label  # noqa: E402
from agenda_tool import AgendaDraftError, draft_agenda  # noqa: E402
from llm_draft import draft_bill_title_llm, draft_explanatory_llm  # noqa: E402
from law_registry import LawNotFoundError, get_law_config, load_law, law_summaries, search_law_titles  # noqa: E402
from query_tool import QueryDraftError, draft_query, write_query_docx  # noqa: E402
from admin_ingest import (  # noqa: E402
    IngestAuthError,
    _require_secret as _require_ingest_secret,
    IngestRateLimitError,
    IngestStorageLimitError,
    run_ingest_batch,
)
from knesset_bills import similar_bills  # noqa: E402
from knesset_citations import OdataError, citations_for_law  # noqa: E402
from knesset_queries import search_queries  # noqa: E402
from research import TEMPLATES as RESEARCH_TEMPLATES, ResearchError, ask as research_ask  # noqa: E402
from rules_expert import RulesExpertError, ask as rules_expert_ask  # noqa: E402
from service import LLMConfigError, LLMRequestError  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "config"))
from env_file import MissingSecret  # noqa: E402
from semantic_search import (  # noqa: E402
    SemanticSearchConfigError,
    SemanticSearchRequestError,
    indexed_law_ids,
    search as semantic_search,
)
from tree_view import as_of_display, node_view, touched_section_numbers  # noqa: E402
from schemas import (  # noqa: E402
    AgendaDraftRequestIn,
    BillMetaIn,
    DraftRequestIn,
    InsertPreviewRequestIn,
    QueryDraftRequestIn,
    QueryExportRequestIn,
    RenderRequest,
    ResearchAskRequestIn,
    RulesAskRequestIn,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SKELETON = REPO_ROOT / "reference" / "skeleton-pshia.docx"

app = FastAPI(title="מנסח החקיקה - עריכה חופשית")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

_jinja_env = Environment(loader=FileSystemLoader(HERE / "templates"))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    template = _jinja_env.get_template("index.html")
    return template.render()


# ── שגיאות תצורה -> 503 עם הסבר, לא 500 ───────────────────────────
# נמצא ב-tests/unit/test_endpoint_smoke.py (2026-09-19): שלוש נקודות
# קצה החזירו "Internal Server Error" כשמפתח חסר. זו אינה קריסה, וזה
# בדיוק מה שיקרה ביום שמפתח יפוג או יסובב - המשתמש היה מקבל שגיאה
# שנראית כמו באג במקום הסבר מה חסר.
#
# מרכזי ולא בכל endpoint: כל נתיב שנוגע ב-DB או במודל מגיע לכאן,
# כולל כאלה שייכתבו אחר כך. **ההודעה מכילה שם משתנה בלבד ולעולם
# לא ערך** - ראו packages/config/env_file.py.
@app.exception_handler(MissingSecret)
@app.exception_handler(LLMConfigError)
@app.exception_handler(EmbeddingConfigError)
async def _config_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/api/laws")
def api_laws() -> list[dict]:
    return law_summaries()


@app.get("/api/laws/search")
def api_search_laws(q: str = "") -> list[dict]:
    """חיפוש שם-חוק בטקסט חופשי (משימה A) - ראו law_registry.
    search_law_titles לפירוט מקור הנתונים הנוכחי (fixtures, לא
    הקורפוס המלא) ומה חסר לחיבור המלא."""
    return search_law_titles(q)


def _dedupe_by_section(results: list[dict]) -> list[dict]:
    """תוצאה אחת לכל (חוק, סעיף) - הגבוהה ביותר. התוצאות מגיעות
    כבר ממוינות מה-RPC, ולכן הראשונה שנראית לכל סעיף היא הטובה
    ביותר ואין צורך למיין שוב."""
    best: dict[tuple[str, str], dict] = {}
    for row in results:
        key = (row["law_id"], row["section_number"])
        if key not in best:
            best[key] = row
    return list(best.values())


@app.get("/api/semantic-search")
def api_semantic_search(q: str = "", limit: int = 10) -> dict:
    """חיפוש סמנטי היברידי (משימה א, 1.3, 2026-09-16/17) - **שונה
    לגמרי** מ-/api/laws/search: זה חיפוש *שמות חוקים* (טקסט מדויק),
    זה חיפוש *תוכן סעיפים* (משמעות, לא רק מחרוזת) - ראו semantic_
    search.py.

    מחזיר `coverage` בנוסף ל-`results`, תמיד (גם כשיש תוצאות), כי
    רק 67 מתוך 1,094 החוקים מאונדקסים (ראו docs/indexing-priority-
    250.md). `unindexed_name_matches` הוא הלב של דרישת ברק להבדיל
    בין "לא נמצא" ל"לא מאונדקס": חוק ששמו תואם את השאילתה אבל אין
    לו chunks - זו מגבלת כיסוי, לא היעדר תוצאה. ההרכבה כאן ולא
    ב-semantic_search.py כי זו השכבה שכבר מכירה גם את חיפוש-השמות
    (search_law_titles) וגם את החיפוש הסמנטי - אין צורך במימוש שני
    של התאמת-שמות."""
    try:
        # שולפים יותר מהמבוקש ואז מאחדים לפי סעיף: סעיף ארוך מפוצל
        # לכמה chunks, ובלי האיחוד אותו סעיף מופיע פעמיים-שלוש ברשימה
        # ונראה כמו תקלה. שומרים את ה-chunk עם הציון הגבוה ביותר.
        results = _dedupe_by_section(semantic_search(q, limit=limit * 3))[:limit]
        indexed = indexed_law_ids()
    except SemanticSearchConfigError as e:
        raise HTTPException(503, str(e))
    except SemanticSearchRequestError as e:
        raise HTTPException(502, str(e))

    name_matches = search_law_titles(q, limit=5) if q.strip() else []
    return {
        "results": results,
        "coverage": {
            "indexed_laws": len(indexed),
            "total_laws": len(law_summaries()),
            "unindexed_name_matches": [
                {"id": m["id"], "title": m["title"]} for m in name_matches if m["id"] not in indexed
            ],
        },
    }


@app.get("/api/admin/openai-check")
def api_openai_check() -> dict:
    """אבחון בלבד (ברק, 2026-09-17): "האם ה-embeddings יכולים להיווצר
    מהקוד שרץ ב-Vercel במקום מהסביבה שלך - שם הרשת פתוחה". embedding
    אחד למחרוזת קבועה וקצרה (עלות זניחה - שברי-שבר סנט) - לא כותב
    כלום, רק מדווח אם הקריאה ל-api.openai.com הצליחה מכאן (מ-Vercel),
    בניגוד לסביבת ה-agent (חסום שם ברמת proxy, ראו night-report.md)."""
    import time as _time

    start = _time.monotonic()
    try:
        vector = embed_one("בדיקת חיבור")
    except (EmbeddingConfigError, EmbeddingRequestError) as e:
        return {"ok": False, "error": str(e), "error_type": type(e).__name__}
    return {"ok": True, "dimensions": len(vector), "latency_ms": round((_time.monotonic() - start) * 1000)}


@app.get("/api/admin/knesset-files-check")
def api_knesset_files_check() -> dict:
    """אבחון בלבד: האם `fs.knesset.gov.il` (שרת הקבצים של הכנסת)
    נגיש מ-Vercel. הוא חסום מסביבת ה-agent, בדיוק כמו api.openai.com
    היה - ולכן נבדק מכאן, מאותה סיבה ובאותו דפוס (ראו CLAUDE.md
    "גבולות רשת").

    שם יושבים הטקסטים המלאים של שאילתות והצעות חוק. **זה שיפור,
    לא תנאי** - כלי השאילתא עובד על שם/מגיש/תאריך גם בלי זה."""
    import time as _time

    import httpx as _httpx

    # קובץ אמיתי שהתקבל מ-KNS_DocumentQuery, לא כתובת מומצאת.
    url = "https://fs.knesset.gov.il//19/parliamentquestion/19_pq_221299.doc"
    start = _time.monotonic()
    try:
        with _httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url)
        return {
            "reachable": resp.status_code == 200,
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type"),
            "bytes": len(resp.content),
            "latency_ms": round((_time.monotonic() - start) * 1000),
        }
    except _httpx.HTTPError as e:
        return {"reachable": False, "error": str(e)[:200], "error_type": type(e).__name__}


# סוגי המסמכים שהם הצעת החוק עצמה. שאר הערכים ב-GroupTypeDesc הם
# מסמכים מלווים (קטע מדברי הכנסת, חומר רקע, פרוטוקול ועדה, החלטת
# ממשלה) או החוק לאחר פרסום - לא הצעה. ברק: "אך ורק הצעות חוק".
_BILL_DOC_TYPES = (
    "הצעת חוק לדיון מוקדם",
    "הצעת חוק לקריאה הראשונה",
    "הצעת חוק לקריאה השנייה והשלישית",
)
# חתימות הבייטים של פורמטי Word. סיומת אינה הוכחה - קובץ שנכשל
# באימות הזה נזרק ולא מנוסה (דרישה מפורשת של ברק).
_DOCX_MAGIC = b"PK\x03\x04"                       # docx = ZIP
_DOC_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"   # doc = OLE2


@app.get("/api/admin/knesset-bill-docs")
def api_knesset_bill_docs(x_ingest_secret: str | None = Header(None),
                          limit: int = 40, doc_ids: str | None = None,
                          allow_doc: bool = False) -> dict:
    """מאתר קובצי Word של **הצעות חוק בלבד** ומוריד אותם מ-Vercel,
    שם `fs.knesset.gov.il` נגיש (חסום מסביבת ה-agent).

    שלושה מסננים, לפי דרישת ברק:
    1. `GroupTypeDesc` חייב להיות סוג של הצעת חוק - לא נספח, לא
       פרוטוקול, לא חומר רקע ולא החוק לאחר פרסום.
    2. הסיומת חייבת להיות `.docx`. `ApplicationDesc='DOC'` מכסה גם
       את הפורמט הבינארי הישן, ש-python-docx אינו יודע לקרוא.
    3. **אימות בייטים אחרי ההורדה** - קובץ שאינו ZIP (כלומר אינו
       docx באמת) נזרק ומדווח, לא מנוסה.

    מוגן באותו טוקן. ההורדה היא של כתובת שמגיעה מה-API של הכנסת
    לפי מזהה, לא של כתובת חופשית מהקורא."""
    import base64  # noqa: PLC0415

    import httpx as _httpx  # noqa: PLC0415

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
    from odata import fetch  # noqa: PLC0415

    try:
        _require_ingest_secret(x_ingest_secret)
    except IngestAuthError as e:
        raise HTTPException(401, str(e))

    # doc_ids: מזהי מסמך מפורשים, מופרדים בפסיקים. נוסף 2026-09-18
    # לצורך משיכת נוסחים לקריאה שנייה ושלישית, שאינם נשלפים בברירת
    # המחדל (הם ישנים - רק 4 מסמכי Word מהסוג הזה קיימים בכלל ב-OData,
    # מול 2,676 PDF). **המזהה משמש לשליפת שורה מ-KNS_DocumentBill,
    # לא ככתובת הורדה** - כתובת ההורדה ממשיכה להגיע מה-API של הכנסת
    # בלבד, בדיוק כמו במסלול הרגיל, ושלושת המסננים חלים כרגיל.
    # הפרמטר knesset הקודם הוסר: הוא היה מוצהר ולא בשימוש בשום שאילתה.
    if doc_ids:
        wanted = [int(x) for x in doc_ids.split(",") if x.strip().isdigit()]
        if not wanted:
            raise HTTPException(422, "doc_ids חייב להכיל מזהים מספריים מופרדים בפסיקים")
        rows = fetch("KNS_DocumentBill",
                     filter="Id in (" + ",".join(str(i) for i in wanted) + ")",
                     select="Id,BillID,GroupTypeDesc,FilePath,LastUpdatedDate")
    else:
        clause = " or ".join(f"GroupTypeDesc eq '{t}'" for t in _BILL_DOC_TYPES)
        rows = fetch("KNS_DocumentBill",
                     filter=f"({clause}) and ApplicationDesc eq 'DOC'",
                     select="Id,BillID,GroupTypeDesc,FilePath,LastUpdatedDate",
                     orderby="LastUpdatedDate desc", top=limit * 6)

    docs, rejected = [], []
    with _httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for r in rows:
            if len(docs) >= limit:
                break
            path = (r.get("FilePath") or "").replace("\\", "/")
            # allow_doc: מותר רק במסלול doc_ids המפורש, ולצורך חקירה.
            # `.doc` בינארי אינו נקרא על ידי python-docx, ולכן הוא לעולם
            # אינו חלק מהמסלול הרגיל - אבל כשמבקשים מסמך מסוים בשמו,
            # חסימה בגלל סיומת רק מסתירה אותו. אימות הבייטים למטה עדיין
            # חל: קובץ שאינו Word כלל נזרק גם כאן.
            allowed_ext = (".docx", ".doc") if (allow_doc and doc_ids) else (".docx",)
            if not path.lower().endswith(allowed_ext):
                rejected.append({"id": r["Id"], "why": "סיומת אינה docx"})
                continue
            try:
                resp = client.get(path)
                resp.raise_for_status()
            except _httpx.HTTPError as e:
                rejected.append({"id": r["Id"], "why": f"הורדה נכשלה: {type(e).__name__}"})
                continue
            body = resp.content
            is_docx = body.startswith(_DOCX_MAGIC)
            is_legacy_doc = body.startswith(_DOC_MAGIC)
            if not (is_docx or (allow_doc and doc_ids and is_legacy_doc)):
                kind = "doc בינארי ישן" if is_legacy_doc else "אינו Word"
                rejected.append({"id": r["Id"], "why": f"אימות בייטים נכשל ({kind})"})
                continue
            docs.append({
                "id": r["Id"], "bill_id": r.get("BillID"),
                "doc_type": r.get("GroupTypeDesc"),
                "updated_at": (r.get("LastUpdatedDate") or "")[:10],
                "bytes": len(body),
                "content_b64": base64.b64encode(body).decode(),
            })

    return {"documents": docs, "rejected": rejected,
            "examined": len(rows), "accepted": len(docs)}


@app.post("/api/admin/ingest-chunks")
def api_admin_ingest_chunks(
    x_ingest_secret: str | None = Header(None),
    max_laws: int | None = None,
    bypass_rate_limit: bool = False,
    phase: int = 1,
) -> dict:
    """מריץ מנה אחת (מוגבלת-תקציב) של ingest ל-search_chunks - ראו
    admin_ingest.py לפירוט מלא (טוקן/מגבלת-קצב/לוג/המשך-הרצה).
    מיועד להיקרא חוזר-ונשנה (לא בקשה אחת שממצה את כל הקורפוס) -
    כל קריאה ממשיכה מהחוק הבא שלא הושלם.

    max_laws (אופציונלי): תקרת-חוקים לריצות-בדיקה מבוקרות, ראו
    admin_ingest.run_ingest_batch.

    bypass_rate_limit: מסלול ההרצה היזומה (ברק, 2026-09-17) - עוקף
    את מגבלת הקצב בלבד, **מוגן באותו טוקן בדיוק**. ברירת המחדל
    (false) משאירה את המגבלה בתוקף לכל קריאה אחרת.

    507 = שומר המרווח עצר: נותר פחות מ-50MB עד תקרת ה-Free tier."""
    try:
        return run_ingest_batch(
            secret=x_ingest_secret,
            max_laws=max_laws,
            bypass_rate_limit=bypass_rate_limit,
            phase=phase,
        )
    except IngestAuthError as e:
        raise HTTPException(401, str(e))
    except IngestRateLimitError as e:
        raise HTTPException(429, str(e))
    except IngestStorageLimitError as e:
        raise HTTPException(507, str(e))


# --- OData של הכנסת (משימה 1.4) ---------------------------------
# שלושת הנתיבים קוראים חי מהפיד של הכנסת, בלי להעתיק אותו ל-DB:
# שאילתה ממוקדת נמדדה ב-~0.6 שניות, ושלוש הטבלאות היו תופסות ~30MB
# מתוך 52MB שנותרו ב-Free tier. 502 = הפיד לא זמין, לא באג אצלנו.


@app.post("/api/documents/summarize")
async def api_summarize_document(file: UploadFile = File(...)) -> dict:
    """תקציר של הצעת חוק מקובץ שהמשתמש מעלה (משימה 2.1).

    PDF מסומן במפורש כפחות מדויק: החילוץ ממנו נמדד ב-~91% מהמילים
    העבריות מול הכלי הטוב ביותר, סדר הבלוקים משתנה, וכותרות רצות
    מתערבבות. לנוסח משולב נדרש Word - ראו docs/night-report.md."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "documents"))
    from extract_docx import DocumentExtractError, extract_bill  # noqa: PLC0415
    from summarize import summarize_bill  # noqa: PLC0415

    name = (file.filename or "").lower()
    if not name.endswith(".docx"):
        raise HTTPException(
            415,
            "נתמכים קובצי Word מסוג .docx בלבד. **פתחו את הקובץ ב-Word "
            "ושמרו אותו מחדש: קובץ ← שמירה בשם ← מסמך Word (.docx).** "
            "ב-.doc הישן הטקסט נקרא, אבל עומק ההזחה של הסעיפים אינו "
            "ניתן לשחזור ממנו, ובלעדיו אי אפשר להבחין בין מספור ההצעה "
            "לנוסח המצוטט שבתוכה. שמירה מחדש ב-Word משחזרת את המבנה "
            "ואת הסגנונות. PDF - אותו הדבר.",
        )
    try:
        bill = extract_bill(io.BytesIO(await file.read()))
    except DocumentExtractError as e:
        raise HTTPException(422, str(e))

    try:
        summary = summarize_bill(bill)
    except (LLMConfigError, LLMRequestError) as e:
        raise HTTPException(503, f"שירות ה-LLM אינו זמין: {e}")

    return {
        "summary": summary.text,
        "title": summary.title,
        "initiators": summary.initiators,
        "lines_used": summary.lines_used,
        "explanatory_used": summary.explanatory_used,
        "warnings": summary.warnings,
    }


@app.post("/api/documents/critique")
async def api_critique_document(file: UploadFile = File(...)) -> dict:
    """ביקורת ניסוח על הצעת חוק שהועלתה (משימה 2.2).

    **הממצאים נקבעים בקוד דטרמיניסטי (packages/validate), לא על ידי
    מודל.** ה-LLM רק מנסח את ההסבר לכל ממצא. אם אין ממצאים - אין
    קריאת מודל בכלל, ואם ההסבר נכשל - הממצאים עדיין מוחזרים במלואם
    (explained=false). ראו packages/documents/critique.py."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "documents"))
    from critique import critique_bill  # noqa: PLC0415
    from extract_docx import DocumentExtractError, extract_bill  # noqa: PLC0415

    name = (file.filename or "").lower()
    if not name.endswith(".docx"):
        raise HTTPException(
            415,
            "נתמכים קובצי Word מסוג .docx בלבד. **פתחו את הקובץ ב-Word "
            "ושמרו אותו מחדש: קובץ ← שמירה בשם ← מסמך Word (.docx).** "
            "ב-.doc הישן הטקסט נקרא, אבל עומק ההזחה של הסעיפים אינו "
            "ניתן לשחזור ממנו, ובלעדיו אי אפשר להבחין בין מספור ההצעה "
            "לנוסח המצוטט שבתוכה. שמירה מחדש ב-Word משחזרת את המבנה "
            "ואת הסגנונות. PDF - אותו הדבר.",
        )
    try:
        bill = extract_bill(io.BytesIO(await file.read()))
    except DocumentExtractError as e:
        raise HTTPException(422, str(e))

    result = critique_bill(bill)
    return {
        "title": result.title,
        "checks_run": list(result.checks_run),
        "passed": result.passed,
        "not_checked": result.not_checked,
        "explained": result.explained,
        "explain_error": result.explain_error,
        "dropped_explanations": result.dropped_explanations,
        "warnings": result.extraction_warnings,
        "findings": [
            {
                "check": it.check_number,
                "description": it.description,
                "severity": it.severity,
                "status": it.status,
                "message": it.message,
                "what": it.what,
                "why": it.why,
                "fix": it.fix,
            }
            for it in result.items
        ],
    }


@app.post("/api/reservations/analyze")
async def api_reservations_analyze(file: UploadFile = File(...)) -> dict:
    """מדידת הצעה שהועלתה: כמה הסתייגויות אפשר לייצר וכמה עוגנים
    מובחנים יש. **מדידה בלבד, בלי LLM ובלי רשת.**"""
    sections, bill = await _reservation_sections(file)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "reservations"))
    from generate import measure  # noqa: PLC0415

    from quality import anchor_points  # noqa: PLC0415

    result = measure(sections)
    # **עלות מצב האיכות, דטרמיניסטית ולפני כל קריאה למודל:** קריאה
    # אחת לכל סעיף, וגודל ההנחיה ידוע מראש. מוצג כדי שההחלטה להריץ
    # תילקח מתוך מספר ולא מתוך תחושה.
    quality_calls = sum(1 for _, text in sections if anchor_points(text))
    return {
        "title": bill.title,
        "sections_found": len(sections),
        # **אין "total".** measure() הפסיקה להחזיר אותו במכוון (ברק,
        # 2026-09-18): מספר ההסתייגויות האפשריות אינו מדידה של ההצעה
        # אלא תוצר של תקרה שאנחנו קובעים. ה-endpoint המשיך לקרוא לו
        # עד 2026-09-19 והחזיר 500 על כל מדידה.
        "distinct": result["distinct"],
        "per_section": result["per_section"],
        "quality_calls": quality_calls,
        "quality_points": sum(len(anchor_points(text)) for _, text in sections),
        "quality_prompt_chars": sum(len(text) for _, text in sections if anchor_points(text)),
        "warnings": bill.warnings,
    }


@app.post("/api/reservations/quality")
async def api_reservations_quality(
    file: UploadFile = File(...),
    proposers: str = Form(""),
    sections_limit: int = Form(0),
    download: bool = Form(False),
):
    """מצב האיכות: הסתייגות מהותית אחת לכל נקודת עיגון.

    **כאן המודל כן כותב טקסט, ולכן כאן - ורק כאן - שומר 86(ד)(2)
    חל.** מה שנחסם נזרק ואינו מוחזר למשתמש (חוק ברזל 7); מוחזרת
    רק הספירה, לדיווח.

    `sections_limit` קיים בשביל העלות: קריאה אחת למודל לכל סעיף.
    הטוקנים בפועל מוחזרים ב-`usage`, ולא בהערכה - `draft_fn` כאן
    עוטף את `complete` ישירות וסופר את מה שה-API דיווח."""
    sections, bill = await _reservation_sections(file)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "reservations"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
    from client import DEFAULT_MODEL, LLMConfigError, LLMRequestError, complete  # noqa: PLC0415
    from quality import quality_reservations  # noqa: PLC0415
    from render_docx import build_document  # noqa: PLC0415

    usage = {"drafting_calls": 0, "screening_calls": 0,
             "input_tokens": 0, "output_tokens": 0, "model": DEFAULT_MODEL}

    def _counted(kind):
        def call(*, instructions: str, content: str, max_tokens: int = 1600) -> str:
            completion = complete(system=instructions, user_message=content,
                                  max_tokens=max_tokens)
            usage[kind] += 1
            usage["input_tokens"] += completion.input_tokens
            usage["output_tokens"] += completion.output_tokens
            return completion.text
        return call

    # **שתי קריאות, לא אחת.** הניסוח וסינון 86(ד)(2) הן שתי קריאות
    # נפרדות בתשלום, ודיווח שסופר רק את הראשונה מציג כמחצית מהעלות.
    drafted = _counted("drafting_calls")
    screened = _counted("screening_calls")

    chosen = sections[:sections_limit] if sections_limit > 0 else sections
    items, blocked = [], []
    try:
        for number, text in chosen:
            passed, reasons = quality_reservations(
                text, section_number=number, draft_fn=drafted,
                screen_draft_fn=screened)
            items.extend(passed)
            blocked.extend(reasons)
    except LLMConfigError as e:
        raise HTTPException(503, str(e))
    except LLMRequestError as e:
        raise HTTPException(502, f"שכבת ה-LLM נכשלה: {e}")

    if download:
        names = [n.strip() for n in proposers.split(",") if n.strip()]
        doc = build_document(bill_title=bill.title or "הצעת חוק",
                             reservations=items, proposers=names, budget_flags={})
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type=("application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"),
            headers={"Content-Disposition": 'attachment; filename="reservations-quality.docx"',
                     "X-Reservations-Count": str(len(items))},
        )

    return {
        "title": bill.title,
        "sections_used": len(chosen),
        "sections_found": len(sections),
        "passed": [{"section_number": it.section_number, "text": it.text,
                    "rationale": it.rationale} for it in items],
        "blocked_count": len(blocked),
        "usage": usage,
        # אזהרות החילוץ חוזרות גם כאן, לא רק ב-/analyze: המשתמש
        # יכול להגיע ישירות לניסוח בלי למדוד קודם.
        "warnings": bill.warnings,
    }


@app.post("/api/reservations/generate")
async def api_reservations_generate(
    file: UploadFile = File(...),
    proposers: str = Form(""),
    limit_per_section: int = Form(50),
) -> StreamingResponse:
    """מצב הכמות -> קובץ Word בפורמט שבו הסתייגויות מוגשות לוועדה.

    **בלי LLM בכלל בנתיב הזה** - מצב הכמות דטרמיניסטי לחלוטין, וזו
    בדיוק ההגנה המבנית (CLAUDE.md חוק ברזל 8)."""
    sections, bill = await _reservation_sections(file)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "reservations"))
    from generate import budgetary_flags, quantity_reservations  # noqa: PLC0415
    from render_docx import build_document  # noqa: PLC0415

    items, flags = [], {}
    for number, text in sections:
        produced = quantity_reservations(text, section_number=number)[:limit_per_section]
        for index, reason in budgetary_flags(produced, section_text=text).items():
            flags[len(items) + index] = reason
        items.extend(produced)

    names = [n.strip() for n in proposers.split(",") if n.strip()]
    doc = build_document(bill_title=bill.title or "הצעת חוק",
                         reservations=items, proposers=names, budget_flags=flags)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="reservations.docx"',
                 "X-Reservations-Count": str(len(items)),
                 # בהורדת קובץ אין גוף JSON להציג בו אזהרות.
                 "X-Extraction-Warnings": str(len(bill.warnings))},
    )


async def _reservation_sections(file: UploadFile):
    """חילוץ (מספר סעיף, נוסח) מהצעה שהועלתה. Word בלבד - ראו
    drafting-rules.md §9.3: מתוך 2,680 נוסחי קריאה 2-3 ב-OData רק
    4 הם Word, ולכן אין משיכה אוטומטית והמשתמש מעלה בעצמו."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "documents"))
    from extract_docx import DocumentExtractError, extract_bill  # noqa: PLC0415

    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(
            415,
            "נתמכים קובצי Word מסוג .docx בלבד. **פתחו את הקובץ ב-Word "
            "ושמרו אותו מחדש: קובץ ← שמירה בשם ← מסמך Word (.docx).** "
            "ב-.doc הישן מספרי הסעיפים אינם ניתנים להפרדה מהנוסח "
            "המצוטט שבתוכם, והסתייגות שתעוגן למספר שגוי גרועה "
            "מהודעת שגיאה.",
        )
    try:
        bill = extract_bill(io.BytesIO(await file.read()))
    except DocumentExtractError as e:
        raise HTTPException(422, str(e))

    # **טקסט שלפני הסעיף הממוספר הראשון אינו נזרק** (ברק,
    # 2026-09-19). הגרסה הקודמת פתחה סעיף רק כשהיה `line.number`,
    # וכל מה שקדם לו נעלם בשקט. זה לא מקרה קצה: בשתי הצעות אמיתיות
    # (`13948363`, `13948394`) **סעיף 1 הוא היחיד שממוספר אוטומטית
    # ב-Word**, ולכן `number` שלו ריק - וזה בדיוק הסעיף שמגדיר
    # "(להלן - החוק העיקרי)" שכל שאר הסעיפים מפנים אליו.
    # ב-13948363 נתפס סעיף אחד מתוך שניים: חצי מההצעה, בלי אזהרה.
    lead: list[str] = []
    sections, current, buffer = [], "", []
    for line in bill.lines:
        if line.number:
            if current:
                sections.append((current.rstrip("."), " ".join(buffer).strip()))
            current, buffer = line.number, [line.text]
        elif current:
            buffer.append(line.text)
        elif line.text.strip():
            lead.append(line.text)
    if current:
        sections.append((current.rstrip("."), " ".join(buffer).strip()))

    if lead:
        text = " ".join(lead).strip()
        first = sections[0][0] if sections else ""
        # מספר שלפני הראשון שכן זוהה. אם הראשון הוא "2" - זה "1".
        inferred = ""
        if first.isdigit() and int(first) > 1:
            inferred = str(int(first) - 1)
        if inferred:
            sections.insert(0, (inferred, text))
            bill.warnings.append(
                f"סעיף {inferred} לא נשא מספר במסמך (כנראה מספור אוטומטי "
                f"של Word, שאינו טקסט) - שוחזר מהמיקום ומהסעיף שאחריו. "
                f"ודאו שהמספור נכון.")
        else:
            # לא ניתן להסיק - **אזהרה רועשת**, לא השמטה שקטה.
            bill.warnings.append(
                f"נמצא טקסט לפני הסעיף הממוספר הראשון ולא ניתן להסיק "
                f"את מספרו (הסעיף הראשון שזוהה: {first or 'אין'}). "
                f"{len(lead)} שורות אינן משויכות לאף סעיף: "
                f"{text[:120]!r}")
    if not sections:
        raise HTTPException(422, "לא זוהו סעיפים ממוספרים במסמך.")
    return sections, bill


@app.post("/api/research/ask")
def api_research_ask(req: ResearchAskRequestIn) -> dict:
    """שאלת מחקר בשפה חופשית -> תבנית שאילתה -> מספרים גולמיים.
    רפרטואר סגור בכוונה (ראו research.py): ה-WAF של הכנסת חוסם
    שאילתות דינמיות, והסכימה לא צפויה מספיק כדי ש-LLM ינחש שדות."""
    try:
        return research_ask(req.question)
    except ResearchError as e:
        raise HTTPException(422, str(e))


@app.get("/api/research/templates")
def api_research_templates() -> list[dict]:
    """מה הכלי יודע לענות - מוצג בממשק כדי שהמשתמש לא ינחש."""
    return [{"id": t.id, "title": t.title, "examples": t.question_examples}
            for t in RESEARCH_TEMPLATES.values()]


@app.get("/api/laws/{law_id}/citations")
def api_law_citations(law_id: str) -> dict:
    """מראי מקום לחוק: הפרסום המקורי וכל תיקון, בפורמט המוכן
    להערת שוליים. נבדק: 1,077 מתוך 1,094 חוקי הקורפוס (98.4%)
    מקבלים מראי מקום."""
    try:
        return citations_for_law(law_id)
    except OdataError as e:
        raise HTTPException(502, str(e))


@app.get("/api/bills/similar")
def api_similar_bills(title: str = "", knesset: int | None = None, limit: int = 10) -> dict:
    """הצעות חוק קיימות שדומות בשמן - הבדיקה שהחוברת הסגולה מחייבת
    ושעוזר פרלמנטרי עושה היום ידנית."""
    try:
        return similar_bills(title, knesset_num=knesset, limit=limit)
    except OdataError as e:
        raise HTTPException(502, str(e))


@app.get("/api/queries/search")
def api_queries_search(q: str = "", limit: int = 12) -> dict:
    """שאילתות קודמות באותו נושא, לחיבור לכלי ניסוח השאילתא."""
    try:
        return search_queries(q, limit=limit)
    except OdataError as e:
        raise HTTPException(502, str(e))


@app.get("/api/laws/{law_id}")
def api_law(law_id: str) -> dict:
    try:
        root = load_law(law_id)
    except LawNotFoundError:
        raise HTTPException(404, f"חוק לא מוכר: {law_id}")
    cfg = get_law_config(law_id, root)
    # **find_sections ולא root.children** - זו הייתה השארית האחרונה
    # של הבאג מ-2026-09-16: חוק עם מבנה חלק/פרק/סימן (פקודת הנזיקין,
    # העונשין, התכנון והבניה) הוחזר כאן "לא ניתן לעריכה" בעוד
    # ש-amend() וה-view ב-DB כבר מצאו את סעיפיו ועבדו עליהם. התוצאה
    # הייתה סתירה בתוך ה-API עצמו: /api/laws/search אמר amendable=true
    # ו-/api/laws/{id} אמר false על אותו חוק בדיוק.
    amendable = bool(find_sections(root))
    return {
        "id": law_id,
        "title": root.full_title or law_id,
        "as_of_display": as_of_display(root),
        "amendable": amendable,
        "known_source_ref": cfg.known_source_ref,
        "footnote_key": cfg.footnote_key,
        # מזהה הגרסה שממנה נטען העץ. נדרש להיסטוריית ההצעות: טיוטה
        # שמורה מחזיקה אותו, וכשפותחים אותה מחדש והמזהה השתנה -
        # המשתמש מקבל אזהרה במקום לגלות בשקט שהנוסח מתחתיו זז.
        "version_id": root.version_id,
        "tree": node_view(root),
    }


def _bill_from_meta(bill_meta: BillMetaIn, lines: list, before: LegislativeNode) -> Bill:
    """submitted_date לא מגיע מהמשתמש - Bill מספק placeholder משלו
    (ראו render_bill.Bill.submitted_date): תאריך ההגשה נקבע בפועל על
    ידי מזכירות הכנסת, לא ידוע ולא נקבע כאן.

    title: אם המשתמש לא הזין שם, נבנה ברירת מחדל דטרמיניסטית (שם החוק
    + שנה נוכחית, ראו bill_title.default_bill_title) במקום להשאיר
    כותרת ריקה - ראו משוב המשתמש: "אתה ממש העלמת את כל הכותרת".
    תיאור התיקון עצמו (לא ניתן לגזירה אמינה) מסומן PLACEHOLDER, מודגש
    צהוב ב-docx (ראו render_bill.run_with_placeholder_highlight)."""
    title = bill_meta.title.strip() or default_bill_title(before.full_title or "")
    explanatory = bill_meta.explanatory or draft_explanatory_notes(lines)
    return Bill(
        knesset="הכנסת העשרים וחמש",
        title=title,
        initiator=bill_meta.initiator,
        lines=lines,
        explanatory=explanatory,
    )


def _render(law_id: str, req: RenderRequest):
    """הליבה המשותפת ל-preview ול-docx: apply_pending_changes() ->
    amend() -> validate(). מחזירה dict מוכן ל-JSON (preview) - docx
    בונה Bill בעצמו מתוך אותו lines."""
    try:
        before = load_law(law_id)
    except LawNotFoundError:
        raise HTTPException(404, f"חוק לא מוכר: {law_id}")
    cfg = get_law_config(law_id, before)
    result = apply_pending_changes(before, req.edits, req.insertions)
    # כיבוי הערות השוליים מתבצע כאן, בשכבת ההרכבה, ולא בתוך amend():
    # המנוע ממשיך לייצר את המפתחות, והבחירה אם להציג אותם היא של
    # המשתמש (ברק, 2026-09-17 - ראו drafting-rules.md §4).
    lines = amend(before, result.after, result.annotations,
                  law_footnote_key=cfg.footnote_key if req.include_footnotes else None)
    bill = _bill_from_meta(req.bill, lines, before)
    # מראה המקום (ס"ח) ידוע מראש לכל חוק ב-law_registry - לא שדה קלט
    # מהמשתמש (10ב). אם לא ידוע (known_source_ref=None), נשאר ריק -
    # הוולידטור (בדיקה 2) יתריע במפורש, לא ננחש ערך.
    refs = {cfg.footnote_key: cfg.known_source_ref or ""} if req.include_footnotes else {}
    findings = validate(bill, before, refs)
    return before, result, lines, bill, findings


@app.post("/api/laws/{law_id}/render")
def api_render(law_id: str, req: RenderRequest) -> dict:
    before, result, lines, bill, findings = _render(law_id, req)
    return {
        "lines": [dataclasses.asdict(ln) for ln in lines],
        "findings": [dataclasses.asdict(f) for f in findings],
        "edit_statuses": [dataclasses.asdict(s) for s in result.edit_statuses],
        "insertion_errors": [dataclasses.asdict(e) for e in result.insertion_errors],
        "touched_sections": sorted(touched_section_numbers(before, result.after)),
        # עץ ה"אחרי" הנוכחי (אחרי כל העריכות/ההוספות עד כה) - הלקוח
        # מרנדר ממנו מחדש את צד העריכה בכל פעם, כדי שסעיפים/סעיפים
        # קטנים/פסקאות שהוספו כרגע יופיעו כצמתים אמיתיים לעריכה, לא
        # רק כתקציר סטטי (ראו TASKS.md משימה 10ב, משוב המשתמש).
        "tree": node_view(result.after),
    }


@app.post("/api/laws/{law_id}/draft")
def api_draft(law_id: str, req: DraftRequestIn) -> dict:
    """טיוטת LLM לשם ההצעה ולדברי ההסבר (משימה ה, 2026-09-16) -
    **לא** נקרא מ-/render (ראו llm_draft.py) - endpoint נפרד שהלקוח
    מפעיל במפורש (כפתור "הצע טיוטה"), כדי לא להוסיף latency/LLM לכל
    preview חי. המשתמש עדיין עורך את התוצאה בטופס לפני שליחה - זו
    התנהגות בכוונה (CLAUDE.md חוק ברזל 4), לא קיצור-דרך זמני."""
    try:
        before = load_law(law_id)
    except LawNotFoundError:
        raise HTTPException(404, f"חוק לא מוכר: {law_id}")
    cfg = get_law_config(law_id, before)
    result = apply_pending_changes(before, req.edits, req.insertions)
    lines = amend(before, result.after, result.annotations, law_footnote_key=cfg.footnote_key)
    touched = touched_section_numbers(before, result.after)
    return {
        "title": draft_bill_title_llm(before.full_title or "", lines),
        "explanatory": draft_explanatory_llm(lines, before, result.after, touched),
    }


@app.post("/api/laws/{law_id}/insert-preview")
def api_insert_preview(law_id: str, req: InsertPreviewRequestIn) -> dict:
    try:
        before = load_law(law_id)
    except LawNotFoundError:
        raise HTTPException(404, f"חוק לא מוכר: {law_id}")
    result = apply_pending_changes(before, req.edits, req.insertions)
    preview = preview_insertion_label(result.after, req.anchor_node_id, req.level)
    return dataclasses.asdict(preview)


@app.post("/api/laws/{law_id}/docx")
def api_docx(law_id: str, req: RenderRequest):
    before, result, lines, bill, findings = _render(law_id, req)
    cfg = get_law_config(law_id, before)
    refs = {cfg.footnote_key: cfg.known_source_ref or ""} if req.include_footnotes else {}

    out_path = Path(tempfile.mkstemp(suffix=".docx")[1])
    write_docx(bill, refs, SKELETON, out_path)
    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{law_id}-הצעת-חוק.docx",
    )


# ── כלי שאילתא (משימה ו, 2026-09-16) ────────────────────────────────────
# לא נוגע בנוסח חוק בכלל - לא כפוף לחוקי ברזל 1-2 (CLAUDE.md). "בלי
# state בשרת" (10ב) חל גם כאן: /export מקבל את הטיוטה המלאה מהלקוח
# (אחרי עריכת המשתמש), לא רק מזהה - כמו /docx לעיל.


@app.post("/api/query/draft")
def api_query_draft(req: QueryDraftRequestIn) -> dict:
    try:
        return draft_query(
            topic_description=req.topic_description, kind=req.kind, minister=req.minister, mk_name=req.mk_name
        )
    except QueryDraftError as e:
        raise HTTPException(422, str(e))


@app.post("/api/query/export")
def api_query_export(req: QueryExportRequestIn):
    query = {
        "kind": req.kind,
        "minister": req.minister,
        "mk_name": req.mk_name,
        "subject": req.subject,
        "body": req.body,
    }
    out_path = Path(tempfile.mkstemp(suffix=".docx")[1])
    write_query_docx(query, skeleton=SKELETON, out=out_path)
    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="שאילתה.docx",
    )


# ── כלי הצעה לסדר היום (משימה ז, 2026-09-16) ────────────────────────────
# זהה ל-/api/query/draft במבנה, בלי /export (ברק, במפורש) - ראו
# agenda_tool.py.


@app.post("/api/agenda/draft")
def api_agenda_draft(req: AgendaDraftRequestIn) -> dict:
    try:
        return draft_agenda(topic_description=req.topic_description, mk_name=req.mk_name)
    except AgendaDraftError as e:
        raise HTTPException(422, str(e))


# ── מומחה התקנון (ברק, 2026-09-17) ──────────────────────────────────────
# ראו rules_expert.py - חיבור packages/llm.answer_with_sources() +
# retrieval מילות-מפתח (עד שחיפוש סמנטי, משימה א, יהיה זמין).


@app.post("/api/rules/ask")
def api_rules_ask(req: RulesAskRequestIn) -> dict:
    try:
        result = rules_expert_ask(req.question)
    except RulesExpertError as e:
        raise HTTPException(503, str(e))
    return {
        "text": result.text,
        "refused": result.refused,
        "refusal_reason": result.refusal_reason,
        "cited_source_ids": result.cited_source_ids,
    }
