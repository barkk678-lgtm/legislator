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

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "validate"))
from engine import amend  # noqa: E402
from render_bill import Bill, write_docx  # noqa: E402
from validator import validate  # noqa: E402

from apply_changes import apply_pending_changes  # noqa: E402
from insert_preview import preview_insertion_label  # noqa: E402
from law_registry import LAWS, load_law, law_summaries  # noqa: E402
from tree_view import as_of_display, node_view, touched_section_numbers  # noqa: E402
from schemas import BillMetaIn, InsertPreviewRequestIn, RenderRequest  # noqa: E402

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


@app.get("/api/laws/{law_id}")
def api_law(law_id: str) -> dict:
    if law_id not in LAWS:
        raise HTTPException(404, f"חוק לא מוכר: {law_id}")
    cfg = LAWS[law_id]
    root = load_law(law_id)
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


def _bill_from_meta(bill_meta: BillMetaIn, lines: list) -> Bill:
    return Bill(
        knesset="הכנסת העשרים וחמש",
        title=bill_meta.title,
        initiator=bill_meta.initiator,
        submitted_date=bill_meta.submitted_date,
        lines=lines,
        explanatory=bill_meta.explanatory,
    )


def _render(law_id: str, req: RenderRequest):
    """הליבה המשותפת ל-preview ול-docx: apply_pending_changes() ->
    amend() -> validate(). מחזירה dict מוכן ל-JSON (preview) - docx
    בונה Bill בעצמו מתוך אותו lines."""
    if law_id not in LAWS:
        raise HTTPException(404, f"חוק לא מוכר: {law_id}")
    cfg = LAWS[law_id]
    before = load_law(law_id)
    result = apply_pending_changes(before, req.edits, req.insertions)
    lines = amend(before, result.after, result.annotations, law_footnote_key=cfg.footnote_key)
    bill = _bill_from_meta(req.bill, lines)
    refs = {cfg.footnote_key: req.bill.source_ref}
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
    }


@app.post("/api/laws/{law_id}/insert-preview")
def api_insert_preview(law_id: str, req: InsertPreviewRequestIn) -> dict:
    if law_id not in LAWS:
        raise HTTPException(404, f"חוק לא מוכר: {law_id}")
    before = load_law(law_id)
    result = apply_pending_changes(before, req.edits, req.insertions)
    preview = preview_insertion_label(result.after, req.anchor_node_id, req.level)
    return dataclasses.asdict(preview)


@app.post("/api/laws/{law_id}/docx")
def api_docx(law_id: str, req: RenderRequest):
    before, result, lines, bill, findings = _render(law_id, req)
    cfg = LAWS[law_id]
    refs = {cfg.footnote_key: req.bill.source_ref}

    out_path = Path(tempfile.mkstemp(suffix=".docx")[1])
    write_docx(bill, refs, SKELETON, out_path)
    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{law_id}-הצעת-חוק.docx",
    )
