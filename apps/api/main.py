"""FastAPI - שכבה דקה בלבד מעל packages/amend, packages/render,
packages/validate, packages/corpus הקיימים. ראו TASKS.md משימה 10.

חוק ברזל: אין כאן שום לוגיקה משפטית ואין לוגיקת תצוגה (מעבר לתיוג
עברי טכני ב-tree_view.py) - כל endpoint הוא "פרסר בקשה -> קריאה
לפונקציה טהורה קיימת -> סריאליזציה של התוצאה". אין state בשרת: רשימת
הטרנספורמציות הממתינות חיה אצל הלקוח (JS), ונשלחת מחדש בכל תצוגה
מקדימה - כל בקשה עצמאית לגמרי, כדי שאפשר יהיה להחליף את ה-frontend
(משימה 10 -> Next.js בעתיד) בלי לגעת ב-API.

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
from transform import apply  # noqa: E402
from engine import amend  # noqa: E402
from render_bill import Bill, write_docx  # noqa: E402
from validator import validate  # noqa: E402

from law_registry import LAWS, load_law, law_summaries  # noqa: E402
from tree_view import as_of_display, node_view, touched_section_numbers  # noqa: E402
from schemas import PreviewRequest, transformation_in_to_dataclass  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SKELETON = REPO_ROOT / "reference" / "skeleton-pshia.docx"

app = FastAPI(title="מנסח החקיקה - ממשק מינימלי")
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


def _apply_and_amend(law_id: str, req: PreviewRequest):
    """הליבה המשותפת ל-preview ול-docx: apply() -> amend(). מחזירה
    (before, after, lines) או זורקת ValueError עם הודעה קריאה -
    בדיוק מה ש-transform.apply() כבר זורק היום (למשל ביטוי לא ייחודי),
    בלי לוגיקה חדשה."""
    if law_id not in LAWS:
        raise HTTPException(404, f"חוק לא מוכר: {law_id}")
    cfg = LAWS[law_id]
    before = load_law(law_id)
    transformations = [transformation_in_to_dataclass(t) for t in req.transformations]
    after, annotations = apply(before, transformations)
    lines = amend(before, after, annotations, law_footnote_key=cfg.footnote_key)
    return before, after, lines


@app.post("/api/laws/{law_id}/preview")
def api_preview(law_id: str, req: PreviewRequest) -> dict:
    cfg = LAWS[law_id] if law_id in LAWS else None
    try:
        before, after, lines = _apply_and_amend(law_id, req)
    except ValueError as exc:
        return {"error": str(exc), "lines": [], "findings": [], "after_tree": None, "touched_sections": []}

    bill = Bill(
        knesset="הכנסת העשרים וחמש",
        title=req.bill.title,
        initiator=req.bill.initiator,
        submitted_date=req.bill.submitted_date,
        lines=lines,
    )
    refs = {cfg.footnote_key: req.bill.source_ref}
    findings = validate(bill, before, refs)

    return {
        "error": None,
        "lines": [dataclasses.asdict(ln) for ln in lines],
        "findings": [dataclasses.asdict(f) for f in findings],
        "after_tree": node_view(after),
        "touched_sections": sorted(touched_section_numbers(before, after)),
    }


@app.post("/api/laws/{law_id}/docx")
def api_docx(law_id: str, req: PreviewRequest):
    cfg = LAWS[law_id]
    try:
        before, after, lines = _apply_and_amend(law_id, req)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    bill = Bill(
        knesset="הכנסת העשרים וחמש",
        title=req.bill.title,
        initiator=req.bill.initiator,
        submitted_date=req.bill.submitted_date,
        lines=lines,
    )
    refs = {cfg.footnote_key: req.bill.source_ref}

    out_path = Path(tempfile.mkstemp(suffix=".docx")[1])
    write_docx(bill, refs, SKELETON, out_path)
    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{law_id}-הצעת-חוק.docx",
    )
