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
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
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
from node import LegislativeNode  # noqa: E402
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
    IngestRateLimitError,
    IngestStorageLimitError,
    run_ingest_batch,
)
from knesset_bills import similar_bills  # noqa: E402
from knesset_citations import OdataError, citations_for_law  # noqa: E402
from knesset_queries import search_queries  # noqa: E402
from rules_expert import RulesExpertError, ask as rules_expert_ask  # noqa: E402
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
    amendable = any(c.node_type == "section" for c in root.children)
    return {
        "id": law_id,
        "title": root.full_title or law_id,
        "as_of_display": as_of_display(root),
        "amendable": amendable,
        "known_source_ref": cfg.known_source_ref,
        "footnote_key": cfg.footnote_key,
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
    lines = amend(before, result.after, result.annotations, law_footnote_key=cfg.footnote_key)
    bill = _bill_from_meta(req.bill, lines, before)
    # מראה המקום (ס"ח) ידוע מראש לכל חוק ב-law_registry - לא שדה קלט
    # מהמשתמש (10ב). אם לא ידוע (known_source_ref=None), נשאר ריק -
    # הוולידטור (בדיקה 2) יתריע במפורש, לא ננחש ערך.
    refs = {cfg.footnote_key: cfg.known_source_ref or ""}
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
    refs = {cfg.footnote_key: cfg.known_source_ref or ""}

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
